"""
SVJ Multi-Axle Consistency Checker (v0.99)
===========================================
Cross-reference rules for multi-axle vehicles that JSON Schema cannot express
(spec §23.7). Used automatically by tools/validate.py; can also run standalone.

svj-py ships an identical copy as svj/multiaxle.py — keep the two files in sync
(tests/test_vehicle.py::test_multiaxle_checker_in_sync enforces it).

Usage:
    python tools/multiaxle_check.py <file.svj.json> [file2 ...]
"""

import json
import re
import sys

LEGACY = {"FL": "A1L", "FR": "A1R", "RL": "A2L", "RR": "A2R"}
A_CORNER = re.compile(r"^A([1-9][0-9]?)(L|R|C)$")
NEEDS_AXLE_BODY = {"torsion_beam", "solid_axle", "de_dion", "parallelogram", "pendulum_axle"}
LINK_PATH = re.compile(r"^([A-Z0-9]+)\.links\.([A-Za-z0-9_]+)$")


def _corner_keys(obj):
    return [k for k in (obj or {}) if not k.startswith(("x_", "_"))]


def canonical(key):
    """FL -> A1L etc.; A-keys unchanged."""
    return LEGACY.get(key, key)


def check(doc):
    errors, warnings = [], []
    susp = doc.get("suspension")
    corners = _corner_keys(susp) if isinstance(susp, dict) else []

    # ── 1. naming form ──────────────────────────────────────────────────────
    legacy = [k for k in corners if k in LEGACY]
    a_form = [k for k in corners if A_CORNER.match(k)]
    if legacy and a_form:
        errors.append(f"suspension mixes legacy corner names {sorted(legacy)} with A-notation {sorted(a_form)} (§23.1)")
    if legacy and len(legacy) != 4:
        errors.append(f"legacy corner names require all of FL/FR/RL/RR; found {sorted(legacy)} (§23.1)")

    canon = {canonical(k): k for k in corners}          # canonical -> as written
    axle_sides = {}
    for c in canon:
        m = A_CORNER.match(c)
        if m:
            axle_sides.setdefault(int(m.group(1)), set()).add(m.group(2))

    # ── 2. axle numbering & sides ──────────────────────────────────────────
    if axle_sides:
        n_max = max(axle_sides)
        missing = [n for n in range(1, n_max + 1) if n not in axle_sides]
        if missing:
            errors.append(f"axle numbering must be contiguous from A1; missing {['A%d' % n for n in missing]} (§23.1)")
        for n, sides in sorted(axle_sides.items()):
            if "C" in sides and sides & {"L", "R"}:
                errors.append(f"A{n} has both a centreline wheel (C) and side wheels (L/R) (§23.1)")
            elif sides in ({"L"}, {"R"}):
                warnings.append(f"A{n} has only side {''.join(sides)}; asymmetric axle — intended? (§23.1)")

    # ── 3. axles[] metadata ────────────────────────────────────────────────
    axles = doc.get("axles") or []
    axle_ids = [a.get("id") for a in axles]
    if len(axle_ids) != len(set(axle_ids)):
        errors.append("axles[] contains duplicate ids")
    for aid in axle_ids:
        if aid and axle_sides and int(aid[1:]) not in axle_sides:
            errors.append(f"axles[] entry {aid} has no corners in suspension")
    if axle_sides and axles:
        for n in axle_sides:
            if f"A{n}" not in axle_ids:
                warnings.append(f"A{n} has corners but no axles[] entry")
    if axle_sides and len(axle_sides) > 2 and not axles:
        warnings.append("vehicle has more than 2 axles but no axles[] metadata (§23.2)")
    xs = [a["position_x"] for a in sorted(axles, key=lambda a: int(a["id"][1:])) if "position_x" in a]
    if any(b >= a for a, b in zip(xs, xs[1:])):
        warnings.append("axles[].position_x should decrease from A1 rearwards (SAE X forward) (§23.2)")
    for a in axles:
        if a.get("lift") and not a.get("liftable"):
            warnings.append(f"{a['id']} has a lift block but liftable is not true")

    def axle_exists(aid):
        return bool(axle_sides) and aid[1:].isdigit() and int(aid[1:]) in axle_sides

    def corner_exists(key):
        return canonical(key) in canon

    # ── 4. per-corner rules ───────────────────────────────────────────────
    beam_axles = {}
    for key in corners:
        c = susp[key]
        topo = c.get("topology", {})
        stype = topo.get("system_type")
        if stype in NEEDS_AXLE_BODY and "axle_body" not in topo:
            warnings.append(f"suspension.{key}: system_type '{stype}' expects topology.axle_body (§9.2.4)")
        if stype == "pendulum_axle" and "pendulum_pivot" not in topo.get("axle_body", {}):
            warnings.append(f"suspension.{key}: pendulum_axle should define axle_body.pendulum_pivot (§9.2.1)")
        if "axle_body" in topo:
            m = A_CORNER.match(canonical(key))
            if m:
                beam_axles.setdefault(topo["axle_body"].get("id"), set()).add(int(m.group(1)))

        wheel = c.get("wheel", {})
        mult = wheel.get("multiplicity", 1)
        pos = wheel.get("positions")
        if pos is not None and len(pos) != mult:
            errors.append(f"suspension.{key}.wheel: positions has {len(pos)} entries but multiplicity is {mult} (§23.4)")
        if mult > 1 and pos is None and "dual_spacing" not in wheel:
            warnings.append(f"suspension.{key}.wheel: multiplicity {mult} without positions or dual_spacing (§23.4)")

        spring = c.get("spring", {})
        cref = spring.get("coupling_ref")
        if spring.get("type") == "none" and not cref:
            warnings.append(f"suspension.{key}.spring: type 'none' without coupling_ref — station is unsprung (§9.3)")
        if cref and cref not in {s.get("id") for s in doc.get("suspension_couplings") or []}:
            errors.append(f"suspension.{key}.spring.coupling_ref '{cref}' does not match any suspension_couplings id")

    for bid, ax in beam_axles.items():
        if len(ax) > 1:
            errors.append(f"axle_body '{bid}' is shared by corners of different axles {sorted('A%d' % n for n in ax)}; use suspension_couplings for inter-axle links (§23.5)")

    # ── 5. couplings ──────────────────────────────────────────────────────
    ids = set()
    for i, cp in enumerate(doc.get("suspension_couplings") or []):
        where = f"suspension_couplings[{i}] ('{cp.get('id')}')"
        if cp.get("id") in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(cp.get("id"))
        for aid in cp.get("axle_refs", []):
            if not axle_exists(aid):
                errors.append(f"{where}: axle_ref {aid} not present in suspension")
        side = cp.get("side")
        for aid in cp.get("axle_refs", []):
            if side in ("L", "R", "C") and axle_exists(aid) and side not in axle_sides[int(aid[1:])]:
                errors.append(f"{where}: {aid} has no side {side}")
        for con in cp.get("connections", []):
            if not corner_exists(con.get("corner_ref", "")):
                errors.append(f"{where}: connection corner_ref {con.get('corner_ref')} not present in suspension")
        for mem in cp.get("members", []):
            if not corner_exists(mem):
                errors.append(f"{where}: member {mem} not present in suspension")
                continue
            stype = susp[canon[canonical(mem)]].get("spring", {}).get("type")
            if cp["type"] == "pneumatic_circuit" and stype != "air":
                warnings.append(f"{where}: member {mem} spring type is '{stype}', expected 'air'")
            if cp["type"] == "hydraulic_circuit" and stype not in ("hydraulic", "hydropneumatic"):
                warnings.append(f"{where}: member {mem} spring type is '{stype}', expected hydraulic/hydropneumatic")
        for path in cp.get("torque_rod_refs", []):
            m = LINK_PATH.match(path)
            if not m or not corner_exists(m.group(1)):
                errors.append(f"{where}: torque_rod_ref '{path}' does not resolve to a corner")
                continue
            links = susp[canon[canonical(m.group(1))]].get("topology", {}).get("links", [])
            if m.group(2) not in {l.get("name") for l in links}:
                errors.append(f"{where}: torque_rod_ref '{path}' — no link named '{m.group(2)}'")
        if cp.get("type") in ("walking_beam", "trunnion_spring") and len(cp.get("axle_refs", [])) != 2:
            warnings.append(f"{where}: {cp['type']} normally couples exactly 2 axles")

    # ── 6. steering ───────────────────────────────────────────────────────
    steering = doc.get("steering") or {}
    steered = {a["id"] for a in axles if a.get("steered")}
    prim = steering.get("axle_ref")
    if prim and not axle_exists(prim):
        errors.append(f"steering.axle_ref {prim} not present in suspension")
    for extra in steering.get("additional_axles", []):
        aid = extra.get("axle_ref", "")
        if not axle_exists(aid):
            errors.append(f"steering.additional_axles: {aid} not present in suspension")
        elif axles and aid not in steered:
            warnings.append(f"steering.additional_axles: {aid} is not marked steered in axles[]")
        if aid == (prim or "A1"):
            errors.append(f"steering.additional_axles: {aid} is the primary steered axle")

    # ── 7. corner-keyed objects elsewhere ─────────────────────────────────
    for label, obj in (("chassis.mass_unsprung_per_corner", (doc.get("chassis") or {}).get("mass_unsprung_per_corner")),
                       ("powertrain.half_shafts", (doc.get("powertrain") or {}).get("half_shafts"))):
        for k in _corner_keys(obj):
            if corners and not corner_exists(k):
                errors.append(f"{label}.{k} has no matching suspension corner")
            if corners and ((k in LEGACY) != bool(legacy)):
                errors.append(f"{label}.{k} uses a different naming form than suspension (§23.1)")
    for dfl in (doc.get("powertrain") or {}).get("differentials", []):
        if dfl.get("axle_ref") and not axle_exists(dfl["axle_ref"]):
            errors.append(f"powertrain.differentials '{dfl.get('id')}': axle_ref {dfl['axle_ref']} not present")

    # ── 8. composite fields ───────────────────────────────────────────────
    ch = doc.get("chassis") or {}
    if len(xs) >= 2 and "wheelbase" in ch and ch.get("wheelbase_reference", "last_axle") == "last_axle":
        wb = xs[0] - xs[-1]
        if abs(wb - ch["wheelbase"]) > 0.01:
            warnings.append(f"chassis.wheelbase {ch['wheelbase']} differs from A1→last axle distance {wb:.3f} (§23.6)")

    return errors, warnings


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    ok = True
    for path in argv:
        with open(path, encoding="utf-8") as f:
            errs, warns = check(json.load(f))
        print(f"\nMulti-axle check: {path}")
        for w in warns:
            print(f"  WARN   {w}")
        for e in errs:
            print(f"  ERROR  {e}")
        if not errs:
            print("  OK")
        ok = ok and not errs
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
