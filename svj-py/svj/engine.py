"""
SVJ Engine Declaration Checker (v0.107)
=======================================
Cross-field rules for the engine declaration that JSON Schema cannot express (spec §10.3.2, §14.2): the firing pattern,
the aspiration, the limiter and the consistency of the descriptors with the torque curve. It also holds the sound-order
formulas of spec §10.3.3, so a sound simulator does not have to look them up, and `sound_sources()` (§10.3.5), the list of
sources a game has to simulate.

The declaration only describes the engine; the torque curve stays the only source of torque.

Used automatically by tools/validate.py; can also run standalone.

svj-py ships an identical copy as svj/engine.py — keep the two files in sync
(tests/test_engine.py::test_checker_in_sync enforces it).

Usage:
    python tools/engine_check.py <file.svj.json> [file2 ...]
"""

import json
import re
import sys

CYCLE_DEG = {"four_stroke": 720.0, "two_stroke": 360.0}
SUPERCHARGER_KINDS = {"roots", "twin_screw", "centrifugal"}


# ── sound orders (spec 10.3.3) ────────────────────────────────────────────────
def cycle_degrees(cycle):
    """Crank angle of one firing cycle: 720 (four-stroke, the default), 360 (two-stroke)."""
    return CYCLE_DEG.get(cycle, 720.0)


def firing_frequency_hz(rpm, cylinders, cycle="four_stroke"):
    """Ignitions per second of the whole engine: (rpm / 60) * cylinders * 360 / cycle_degrees."""
    return rpm / 60.0 * cylinders * 360.0 / cycle_degrees(cycle)


def engine_order(cylinders, cycle="four_stroke"):
    """Firing frequency divided by the crank rotation frequency (cylinders / 2 for a four-stroke)."""
    return cylinders * 360.0 / cycle_degrees(cycle)


def harmonic_hz(rpm, order):
    """Frequency of the harmonic `order` of the crank rotation: order * rpm / 60."""
    return order * rpm / 60.0


def turbo_blade_pass_hz(blades, shaft_rpm):
    """Blade-pass frequency of a turbo compressor: blades * shaft_rpm / 60 (the shaft speed is not in the file)."""
    return blades * shaft_rpm / 60.0


def supercharger_whine_hz(rpm, pulley_ratio, lobes=1):
    """Supercharger whine: lobes * pulley_ratio * rpm / 60."""
    return lobes * pulley_ratio * rpm / 60.0


def motor_frequency_hz(wheel_rpm, gear_ratio, pole_pairs):
    """Electrical frequency of a motor: pole_pairs * (wheel_rpm * gear_ratio) / 60."""
    return pole_pairs * wheel_rpm * gear_ratio / 60.0


def firing_angles(engine):
    """Crank angles (deg) of the ignitions in firing order within one cycle: the declared `layout.firing_angles_deg`,
    else derived for even-firing inline, flat and radial engines, V8 with a flat or cross-plane crank and V12, and the
    single-pin V-twin. None when the pattern cannot be derived (declare `firing_angles_deg` then)."""
    lay = engine.get("layout") if isinstance(engine, dict) else None
    if not isinstance(lay, dict):
        return None
    given = lay.get("firing_angles_deg")
    if isinstance(given, list) and given and all(isinstance(a, (int, float)) for a in given):
        return [float(a) for a in given]
    n, arr = lay.get("cylinders"), lay.get("arrangement")
    cyc = cycle_degrees(engine.get("cycle"))
    if not isinstance(n, int) or n < 1 or engine.get("cycle") == "wankel":
        return None
    if arr in ("I", "flat", "radial") or (arr == "V" and n in (8, 12) and lay.get("crank") in ("flat_plane", "cross_plane", None)):
        return [cyc / n * i for i in range(n)]
    if arr == "V" and n == 2 and isinstance(lay.get("bank_angle_deg"), (int, float)):
        return [0.0, cyc / 2 - lay["bank_angle_deg"]] if engine.get("cycle", "four_stroke") == "four_stroke" else None
    return None


def sound_sources(doc):
    """What a game has to simulate for this vehicle, derived from the declaration (spec 10.3.5). No audio is stored in SVJ:
    each entry names a source, the shaft that drives it and how its frequency follows that shaft.

    Entries: {"id", "kind", "shaft", "ratio" or "hz", ...}. For a periodic source the frequency is
    `ratio * rev/s of the shaft` (`crank`, `turbo`, `motor`); `hz` is a fixed frequency; event sources have a `trigger`."""
    out = []
    pt = doc.get("powertrain") if isinstance(doc, dict) else None
    eng = pt.get("engine") if isinstance(pt, dict) else None
    if isinstance(eng, dict) and eng.get("kind", "ice") in ("ice", "rotary"):
        lay = eng.get("layout") if isinstance(eng.get("layout"), dict) else {}
        n = lay.get("cylinders")
        if isinstance(n, int) and n > 0:
            out.append({"id": "engine_fire", "kind": "combustion", "shaft": "crank", "ratio": engine_order(n, eng.get("cycle")),
                        "cylinders": n, "firing_angles_deg": firing_angles(eng), "cycle_deg": cycle_degrees(eng.get("cycle")),
                        "fuel": eng.get("fuel")})
        for c in ((eng.get("aspiration") or {}).get("chargers") or []):
            if not isinstance(c, dict):
                continue
            cid = c.get("id") or c.get("kind", "charger")
            if c.get("kind") == "turbo":
                if isinstance(c.get("blades"), int):
                    out.append({"id": f"{cid}_whistle", "kind": "turbo_whistle", "shaft": "turbo", "ratio": float(c["blades"]),
                                "note": "turbo shaft speed follows boost and is not in the file"})
                if c.get("wastegate") not in (None, "none"):
                    out.append({"id": f"{cid}_wastegate", "kind": "wastegate", "trigger": "boost_limit", "wastegate": c["wastegate"]})
            elif c.get("kind") in SUPERCHARGER_KINDS and isinstance(c.get("pulley_ratio"), (int, float)):
                out.append({"id": f"{cid}_whine", "kind": "supercharger_whine", "shaft": "crank",
                            "ratio": float(c.get("lobes", 1)) * c["pulley_ratio"]})
            elif c.get("kind") == "electric":
                out.append({"id": f"{cid}_whine", "kind": "electric_compressor", "shaft": "compressor",
                            "note": "speed not in the file"})
            if c.get("blow_off"):
                out.append({"id": f"{cid}_blow_off", "kind": "blow_off", "trigger": "throttle_lift"})
        ex = eng.get("exhaust")
        if isinstance(ex, dict):
            out.append({"id": "exhaust", "kind": "exhaust", **{k: ex[k] for k in ("headers", "merge", "catalyst", "resonators", "muffler", "outlets") if k in ex}})
            if ex.get("overrun") in ("burble", "pops"):
                out.append({"id": "overrun", "kind": "overrun", "trigger": "throttle_lift", "style": ex["overrun"]})
        it = eng.get("intake")
        if isinstance(it, dict):
            out.append({"id": "intake", "kind": "intake", **{k: it[k] for k in ("type", "airbox") if k in it}})
        lim = eng.get("limiter")
        if isinstance(lim, dict) and lim.get("type") not in (None, "none"):
            out.append({"id": "limiter", "kind": "limiter", "trigger": "rpm_limit", "style": lim["type"], "rpm": lim.get("rpm", eng.get("max_rpm"))})
    el = doc.get("electric") if isinstance(doc, dict) else None
    for m in ((el or {}).get("motors") or []):
        if not isinstance(m, dict):
            continue
        mid = m.get("id", "motor")
        if isinstance(m.get("pole_pairs"), int):
            out.append({"id": f"{mid}_whine", "kind": "motor_whine", "shaft": "motor", "ratio": float(m["pole_pairs"]),
                        "gear_ratio": m.get("gear_ratio"), "driven_axle": m.get("driven_axle")})
        if isinstance(m.get("inverter_switching_hz"), (int, float)):
            out.append({"id": f"{mid}_inverter", "kind": "inverter_whine", "hz": float(m["inverter_switching_hz"])})
    return out


# ── checks ────────────────────────────────────────────────────────────────────
def _check_layout(eng, warnings):
    lay = eng.get("layout")
    if not isinstance(lay, dict):
        return
    n = lay.get("cylinders")
    fo = lay.get("firing_order")
    if isinstance(fo, list) and isinstance(n, int) and sorted(x for x in fo if isinstance(x, int)) != list(range(1, n + 1)):
        warnings.append(f"powertrain.engine.layout.firing_order {fo} is not a permutation of cylinders 1..{n}")
    fa = lay.get("firing_angles_deg")
    if isinstance(fa, list):
        cyc = cycle_degrees(eng.get("cycle"))
        nums = [a for a in fa if isinstance(a, (int, float))]
        if isinstance(n, int) and len(fa) != n:
            warnings.append(f"powertrain.engine.layout.firing_angles_deg has {len(fa)} entries for {n} cylinders")
        if any(a >= cyc for a in nums):
            warnings.append(f"powertrain.engine.layout.firing_angles_deg must lie inside one cycle (0 to {cyc:g} deg for {eng.get('cycle', 'four_stroke')})")
        if nums != sorted(nums):
            warnings.append("powertrain.engine.layout.firing_angles_deg must be in ascending order (angles in firing order)")
    elif isinstance(n, int) and n > 1 and firing_angles(eng) is None and eng.get("cycle") != "wankel" and eng.get("kind", "ice") == "ice":
        warnings.append("powertrain.engine.layout: the firing pattern cannot be derived for this layout; declare layout.firing_angles_deg "
                        "(a sound simulator needs it)")
    cfg = eng.get("configuration")
    if isinstance(cfg, str) and isinstance(n, int):
        m = re.search(r"(\d+)", cfg)
        if m and int(m.group(1)) != n:
            warnings.append(f"powertrain.engine.configuration '{cfg}' names {m.group(1)} cylinders but layout.cylinders is {n}")


def _check_aspiration(eng, warnings):
    asp = eng.get("aspiration")
    if not isinstance(asp, dict):
        return
    t = asp.get("type")
    chargers = [c for c in (asp.get("chargers") or []) if isinstance(c, dict)]
    kinds = [c.get("kind") for c in chargers]
    if t == "na" and chargers:
        warnings.append("powertrain.engine.aspiration: type 'na' (naturally aspirated) lists chargers")
    elif t in ("turbo", "supercharger", "twin_charged", "electric_compressor") and not chargers:
        warnings.append(f"powertrain.engine.aspiration: type '{t}' lists no chargers")
    elif t == "turbo" and any(k not in (None, "turbo") for k in kinds):
        warnings.append("powertrain.engine.aspiration: type 'turbo' has a charger that is not a turbo")
    elif t == "supercharger" and any(k not in (None, *SUPERCHARGER_KINDS) for k in kinds):
        warnings.append("powertrain.engine.aspiration: type 'supercharger' has a charger that is not a roots, twin_screw or centrifugal blower")
    elif t == "electric_compressor" and any(k not in (None, "electric") for k in kinds):
        warnings.append("powertrain.engine.aspiration: type 'electric_compressor' has a charger that is not electric")
    elif t == "twin_charged" and not ("turbo" in kinds and any(k in SUPERCHARGER_KINDS for k in kinds)):
        warnings.append("powertrain.engine.aspiration: type 'twin_charged' needs a turbo and a supercharger")
    for c in chargers:
        if c.get("kind") == "turbo" and "pulley_ratio" in c:
            warnings.append(f"powertrain.engine.aspiration charger '{c.get('id', '?')}': a turbo has no pulley_ratio (it is not driven by the crankshaft)")
        if c.get("kind") in SUPERCHARGER_KINDS and "blades" in c:
            warnings.append(f"powertrain.engine.aspiration charger '{c.get('id', '?')}': blades describe a turbo compressor, not a blower")


def check(doc):
    """(errors, warnings) of the engine declaration and the motor sound fields. Everything is advisory (warnings)."""
    warnings = []
    pt = doc.get("powertrain") if isinstance(doc, dict) else None
    eng = pt.get("engine") if isinstance(pt, dict) else None
    el = doc.get("electric") if isinstance(doc, dict) else None
    if isinstance(eng, dict):
        _check_layout(eng, warnings)
        _check_aspiration(eng, warnings)
        lim, mx = eng.get("limiter"), eng.get("max_rpm")
        if isinstance(lim, dict) and isinstance(lim.get("rpm"), (int, float)) and isinstance(mx, (int, float)) and lim["rpm"] > mx:
            warnings.append(f"powertrain.engine.limiter.rpm ({lim['rpm']:g}) is above max_rpm ({mx:g})")
        curve = eng.get("torque_curve")
        if isinstance(mx, (int, float)) and isinstance(curve, list):
            top = max((p[0] for p in curve if isinstance(p, list) and p and isinstance(p[0], (int, float))), default=None)
            if top is not None and top > mx:
                warnings.append(f"powertrain.engine.torque_curve reaches {top:g} rpm, above max_rpm ({mx:g})")
        if eng.get("kind") == "electric":
            extra = [k for k in ("layout", "aspiration", "exhaust", "intake", "cycle", "fuel") if k in eng]
            if extra:
                warnings.append(f"powertrain.engine: kind 'electric' declares combustion fields ({', '.join(extra)})")
        if eng.get("kind") in ("ice", "rotary", None) and isinstance(el, dict) and el.get("hybrid_type") == "bev":
            warnings.append("powertrain.engine: an engine is declared but electric.hybrid_type is 'bev'")
    return [], warnings


def main(argv):
    ok = True
    for path in argv:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        _, warnings = check(doc)
        for w in warnings:
            print(f"  WARN   {path}: {w}")
        if not warnings:
            print(f"  OK     {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
