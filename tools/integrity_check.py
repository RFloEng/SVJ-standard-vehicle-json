"""
SVJ glTF Visual Binding Integrity Checker
==========================================
Validates that all visual bindings in an SVJ file are internally consistent
(spec §22, v0.99.2):

  1. Every visual.node follows SVJ::<category>::<id> with a known category.
  2. The <id> suffix matches the id of the part carrying the binding —
     uprights, links, wheels, springs, dampers, ARBs, brakes, steering,
     powertrain units, aero components. 'helper' nodes are exempt.
  3. Every visual.mesh_ref references a declared entry in assets.meshes.
  4. No two parts share the same visual.node (uniqueness).
  5. placement 'link_between_points' is only used on carriers with two
     resolvable ends; mesh_axis / from_point / scale_to_length only appear
     with it; from_point is within range of inboard_points.
  6. The category suits the kind of part, and link names come from the canonical
     vocabulary (warnings).

Rules 1–5 are errors; rule 6 and an ambiguous mesh_ref are warnings. Using the
legacy 'body' category on a non-body part is valid and reported as a NOTE.

Usage:
    python tools/integrity_check.py <path-to-file.svj.json> [...] [--strict]

Options:
    --strict    Treat warnings as errors (non-zero exit on any issue).
"""

import json
import re
import sys

CATEGORIES = (
    "body", "suspension", "steering", "wheel", "brake", "powertrain", "aero",
    "helper", "lod",
)
NODE_PATTERN = re.compile(r"^SVJ::(" + "|".join(CATEGORIES) + r")::([a-z0-9_]+)$")
STATION_RE = re.compile(r"^(FL|FR|RL|RR|A([1-9][0-9]?)(L|R|C))$")
PLACEMENT_ONLY = ("mesh_axis", "from_point", "scale_to_length")


def load_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", str(text).lower())


def with_station(base: str, station: str) -> set:
    """Accepted ids for a corner part: with and without the station suffix."""
    st = slug(station)
    base = slug(base)
    out = {base if base.endswith("_" + st) else base + "_" + st}
    out.add(base)
    return out


def collect_mesh_ids(data: dict) -> set:
    meshes = data.get("assets", {}).get("meshes", [])
    return {m["id"] for m in meshes if isinstance(m, dict) and "id" in m}


LINK_NAMES = []   # (location, link name, station) for the vocabulary advisory


def collect_bindings(data: dict) -> list:
    """
    Walk the document and collect every visual binding.
    Each entry: {location, visual, ids (accepted id set or None), kind, ends}
      kind  — part family, used for the category advisory
      ends  — True when the carrier has two resolvable ends (links, driveshafts)
    """
    out = []
    LINK_NAMES.clear()

    def add(location, visual, ids=None, kind="body", ends=False, link=None, shared=False):
        if isinstance(visual, dict):
            out.append({"location": location, "visual": visual, "ids": ids,
                        "kind": kind, "ends": ends, "link": link, "shared": shared})

    chassis = data.get("chassis") or {}
    add("chassis", chassis.get("visual"), {"chassis"}, "body")
    for i, body in enumerate(chassis.get("mass_bodies") or []):
        bid = body.get("id", f"<mass_bodies[{i}]>")
        add(f"chassis.mass_bodies[{bid}]", body.get("visual"), {slug(bid)}, "body")
    # v0.97 name, kept so older files still get checked
    for i, body in enumerate(chassis.get("mass_decomposition") or []):
        bid = body.get("id", f"<mass_decomposition[{i}]>")
        add(f"chassis.mass_decomposition[{bid}]", body.get("visual"), {slug(bid)}, "body")

    suspension = data.get("suspension") or {}
    for st in [k for k in suspension if STATION_RE.match(k)]:
        corner = suspension.get(st) or {}
        if not isinstance(corner, dict):
            continue
        topo = corner.get("topology") or {}
        upright = topo.get("upright") or {}
        up_ids = with_station(upright.get("id") or f"upright_{st}", st) | {f"upright_{slug(st)}"}
        add(f"suspension.{st}", corner.get("visual"), up_ids, "suspension")
        add(f"suspension.{st}.topology.upright", upright.get("visual"), up_ids, "suspension")
        axle = topo.get("axle_body") or {}
        # One beam/housing is shared by both stations of the axle, so the same
        # node may legitimately be bound from each of them (spec 22.7, rule 4).
        add(f"suspension.{st}.topology.axle_body", axle.get("visual"),
            with_station(axle.get("id") or "axle_body", st), "suspension", shared=True)
        for li, link in enumerate(topo.get("links") or []):
            name = link.get("name") or link.get("id") or f"link{li}"
            add(f"suspension.{st}.topology.links[{name}]", link.get("visual"),
                with_station(name, st), "suspension", ends=True, link=link)
            if link.get("visual"):
                LINK_NAMES.append((f"suspension.{st}.topology.links[{name}]", slug(name), slug(st)))
        wheel = corner.get("wheel") or {}
        add(f"suspension.{st}.wheel", wheel.get("visual"),
            with_station("wheel", st), "wheel")
        for pi, pos in enumerate(wheel.get("positions") or []):
            label = slug(pos.get("label") or f"p{pi + 1}")
            add(f"suspension.{st}.wheel.positions[{label}]", pos.get("visual"),
                {f"wheel_{slug(st)}_{label}"}, "wheel")
        for part, kind in (("spring", "suspension"), ("damper", "suspension"), ("arb", "suspension")):
            obj = corner.get(part) or {}
            if isinstance(obj, dict):
                ids = with_station(obj.get("id") or obj.get("bar_id") or part, st)
                add(f"suspension.{st}.{part}", obj.get("visual"), ids, kind)
        brake = corner.get("brake") or {}
        for part in ("disc", "caliper"):
            obj = brake.get(part) or {}
            if isinstance(obj, dict):
                add(f"suspension.{st}.brake.{part}", obj.get("visual"),
                    with_station(obj.get("id") or part, st), "brake")

    steering = data.get("steering") or {}
    add("steering", steering.get("visual"), {"rack", "steering_rack", "gear"}, "steering")
    for key, ids in (("column", {"column", "steering_column"}),
                     ("steering_wheel", {"wheel", "steering_wheel"})):
        obj = steering.get(key) or {}
        if isinstance(obj, dict):
            add(f"steering.{key}", obj.get("visual"), ids, "steering")

    pt = data.get("powertrain") or {}
    for key in ("engine", "gearbox", "clutch", "transfer_case"):
        obj = pt.get(key) or {}
        if isinstance(obj, dict):
            add(f"powertrain.{key}", obj.get("visual"), {key}, "powertrain")
    for i, df in enumerate(pt.get("differentials") or []):
        did = df.get("id", f"differential{i}")
        add(f"powertrain.differentials[{did}]", df.get("visual"), {slug(did)}, "powertrain")
    for i, ds in enumerate(pt.get("driveshafts") or []):
        did = ds.get("id", f"driveshaft{i}")
        add(f"powertrain.driveshafts[{did}]", ds.get("visual"), {slug(did)}, "powertrain", ends=True)

    for i, comp in enumerate((data.get("aerodynamics") or {}).get("components") or []):
        cid = comp.get("id") or comp.get("name") or f"component{i}"
        add(f"aerodynamics.components[{cid}]", comp.get("visual"), {slug(cid)}, "aero")

    return out


# Canonical link / part names (docs/naming_convention.md). Advisory only.
CANONICAL_LINK_NAMES = {
    "upper_wishbone", "lower_wishbone", "upper_link_front", "upper_link_rear",
    "lower_link_front", "lower_link_rear", "trailing_arm", "semi_trailing_arm",
    "leading_arm", "tie_rod", "toe_link", "camber_link", "drag_link", "pushrod",
    "pullrod", "rocker", "strut", "torque_rod", "panhard_rod", "watts_link_rod",
    "watts_pivot", "drop_link", "half_shaft", "axle_body",
}

# category → part kinds it is meant for ('body' and 'lod' are accepted everywhere)
CATEGORY_FIT = {
    "suspension": {"suspension"},
    "steering": {"steering"},
    "wheel": {"wheel"},
    "brake": {"brake"},
    "powertrain": {"powertrain", "body"},
    "aero": {"aero"},
}


def check(path: str, strict: bool = False) -> bool:
    print(f"\nChecking: {path}")
    print("=" * 60)

    try:
        data = load_file(path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ERROR  Could not load file: {e}")
        return False

    mesh_ids = collect_mesh_ids(data)
    bindings = collect_bindings(data)

    if not bindings:
        print("  INFO   No visual bindings found — nothing to check.")
        return True

    errors, warnings, notes, seen = [], [], [], {}

    for b in bindings:
        loc, v = b["location"], b["visual"]
        node = v.get("node", "")
        mesh_ref = v.get("mesh_ref")
        placement = v.get("placement", "rigid")

        # Rule 1 — node pattern
        m = NODE_PATTERN.match(node)
        if not m:
            errors.append(
                f"[{loc}] node '{node}' does not match SVJ::<category>::<id> "
                f"with a category from {', '.join(CATEGORIES)}"
            )
            continue
        category, suffix = m.group(1), m.group(2)

        # Rule 2 — id match
        if category != "helper" and b["ids"] and suffix not in b["ids"]:
            errors.append(
                f"[{loc}] Binding mismatch — node suffix '{suffix}' is not the part id "
                f"(expected one of: {', '.join(sorted(b['ids']))}). "
                f"Fix: rename the part id OR the glTF node so they match."
            )

        # Rule 3 — mesh_ref
        if mesh_ref is not None and mesh_ids and mesh_ref not in mesh_ids:
            errors.append(
                f"[{loc}] mesh_ref '{mesh_ref}' not found in assets.meshes "
                f"(declared: {sorted(mesh_ids)})"
            )
        if mesh_ref is None and len(mesh_ids) > 1:
            warnings.append(
                f"[{loc}] mesh_ref is absent but {len(mesh_ids)} mesh files are declared. "
                f"Add mesh_ref to avoid ambiguity."
            )

        # Rule 4 — uniqueness (a part shared between stations, e.g. an axle beam,
        # may be bound from each station it belongs to)
        if node in seen:
            if not (b["shared"] and seen[node][1]):
                errors.append(f"[{loc}] Duplicate node '{node}' — already used by '{seen[node][0]}'")
        else:
            seen[node] = (loc, b["shared"])

        # Rule 5 — placement
        if placement == "link_between_points":
            if not b["ends"]:
                errors.append(
                    f"[{loc}] placement 'link_between_points' needs a carrier with two ends "
                    f"(a suspension link or a driveshaft); this part has a body frame — use 'rigid'."
                )
            link = b["link"] or {}
            pts = link.get("inboard_points") or []
            fp = v.get("from_point")
            if b["ends"] and link:
                if not pts:
                    errors.append(f"[{loc}] placement 'link_between_points' but the link has no inboard_points")
                if not link.get("outboard_ref"):
                    errors.append(f"[{loc}] placement 'link_between_points' but the link has no outboard_ref")
                if isinstance(fp, int) and fp >= len(pts):
                    errors.append(
                        f"[{loc}] from_point {fp} is out of range — the link has {len(pts)} inboard point(s)"
                    )
        else:
            extra = [k for k in PLACEMENT_ONLY if k in v]
            if extra:
                errors.append(
                    f"[{loc}] {', '.join(extra)} only apply with placement 'link_between_points' "
                    f"(this binding is '{placement}')"
                )

        # Rule 6 — category fit (advisory)
        fit = CATEGORY_FIT.get(category)
        if fit and b["kind"] not in fit:
            warnings.append(
                f"[{loc}] category '{category}' on a {b['kind']} part — expected "
                f"'{b['kind']}' (or 'body')"
            )
        if category == "body" and b["kind"] not in ("body",):
            # Valid by the spec (v0.97 files used 'body' everywhere) — informational
            # only, so --strict stays usable on existing files.
            notes.append(
                f"[{loc}] category 'body' is the legacy v0.97 form for a {b['kind']} part; "
                f"'{b['kind']}' is preferred in v0.99.2"
            )

    for loc, name, st in LINK_NAMES:
        base = name[:-(len(st) + 1)] if name.endswith("_" + st) else name
        if base not in CANONICAL_LINK_NAMES:
            warnings.append(
                f"[{loc}] link name '{base}' is not in the canonical vocabulary "
                f"(docs/naming_convention.md) — fine for a house name, but exporters "
                f"will not recognise it"
            )

    for n in notes:
        print(f"  NOTE   {n}")
    for w in warnings:
        print(f"  WARN   {w}")
    for e in errors:
        print(f"  ERROR  {e}")

    if not errors and not warnings:
        suffix = f" ({len(notes)} note(s))" if notes else ""
        print(f"  OK     All {len(bindings)} visual binding(s) passed.{suffix}")
    elif not errors:
        print(f"  OK     {len(bindings)} binding(s) checked — {len(warnings)} warning(s), 0 errors.")
    else:
        print(f"\n  FAILED {len(errors)} error(s), {len(warnings)} warning(s) in {len(bindings)} binding(s).")

    return len(errors) == 0 and (not strict or len(warnings) == 0)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    strict = "--strict" in args
    files = [a for a in args if not a.startswith("--")]

    if not files:
        print("Error: no input file specified.")
        sys.exit(1)

    all_passed = True
    for path in files:
        if not check(path, strict=strict):
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
