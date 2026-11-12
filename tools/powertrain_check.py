"""
SVJ Powertrain Part-Load Checker (v0.108)
=========================================
Evaluators and cross-field rules for the part-load engine torque and engine braking (spec §10.3.6), the gearbox shift
points (§10.5.2) and the torque converter (§10.4.1). JSON Schema checks the shapes; this file checks the numbers against
each other and holds the formulas, so a simulator does not have to look them up.

Used automatically by tools/validate.py; can also run standalone.

svj-py ships an identical copy as svj/powertrain.py — keep the two files in sync
(tests/test_powertrain.py::test_checker_in_sync enforces it).

Usage:
    python tools/powertrain_check.py <file.svj.json> [file2 ...]
"""

import json
import sys


# ── evaluators (spec 10.3.6, 10.4.1, 10.5.2) ──────────────────────────────────
def interp(curve, x):
    """Linear interpolation of [[x, y], ...] (ascending x), held flat outside the range."""
    if not curve:
        raise ValueError("empty curve")
    if x <= curve[0][0]:
        return float(curve[0][1])
    if x >= curve[-1][0]:
        return float(curve[-1][1])
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 <= x <= x1:
            return float(y0) if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(curve[-1][1])


def throttle_curves(engine):
    """[(throttle, curve), ...] ascending: closed (0), the measured part-throttle curves, full (1). Missing ones are absent."""
    out = []
    if isinstance(engine.get("torque_curve_closed"), list):
        out.append((0.0, engine["torque_curve_closed"]))
    for pt in engine.get("part_throttle") or []:
        if isinstance(pt, dict) and isinstance(pt.get("curve"), list) and isinstance(pt.get("throttle"), (int, float)):
            out.append((float(pt["throttle"]), pt["curve"]))
    if isinstance(engine.get("torque_curve"), list):
        out.append((1.0, engine["torque_curve"]))
    return sorted(out, key=lambda t: t[0])


def engine_torque(engine, rpm, throttle=1.0):
    """Net crankshaft torque (Nm) at `rpm` and `throttle` (0 to 1): the linear interpolation, in torque, between the two
    curves that bracket the throttle, each read by linear interpolation in rpm. None when the throttle lies below the
    lowest curve the engine declares (no `torque_curve_closed`, so no engine braking is declared)."""
    th = min(max(float(throttle), 0.0), 1.0)
    curves = throttle_curves(engine)
    if not curves or th < curves[0][0]:
        return None
    for (t0, c0), (t1, c1) in zip(curves, curves[1:]):
        if t0 <= th <= t1:
            a, b = interp(c0, rpm), interp(c1, rpm)
            return a if t1 == t0 else a + (b - a) * (th - t0) / (t1 - t0)
    return interp(curves[-1][1], rpm)


def converter(tc, n_in, n_out):
    """Torque converter at pump speed n_in and turbine speed n_out (rev/min). `tc` is the clutch.torque_converter object.
    Returns {speed_ratio, K, TR, T_in, T_out, efficiency}: K = n_in / sqrt(T_in) (capacity factor),
    T_in = (n_in / K)^2, T_out = TR * T_in, efficiency = TR * speed_ratio."""
    if n_in <= 0:
        return {"speed_ratio": 0.0, "K": 0.0, "TR": 0.0, "T_in": 0.0, "T_out": 0.0, "efficiency": 0.0}
    sr = max(n_out, 0.0) / n_in
    k = interp(tc["capacity_factor"], sr)
    tr = interp(tc["torque_ratio"], sr)
    t_in = (n_in / k) ** 2 if k > 0 else 0.0
    return {"speed_ratio": sr, "K": k, "TR": tr, "T_in": t_in, "T_out": tr * t_in, "efficiency": tr * sr}


def shift_points_at(gearbox, throttle=1.0):
    """[[up_rpm, down_rpm], ...] per forward gear at `throttle`: `shift_points_vs_throttle` interpolated linearly when
    given (it replaces `shift_points`), else `shift_points`; None when the gearbox declares neither."""
    table = [t for t in (gearbox.get("shift_points_vs_throttle") or []) if isinstance(t, dict) and isinstance(t.get("points"), list)]
    if table:
        table.sort(key=lambda t: t.get("throttle", 0.0))
        th = min(max(float(throttle), 0.0), 1.0)
        if th <= table[0]["throttle"]:
            return [list(p) for p in table[0]["points"]]
        for a, b in zip(table, table[1:]):
            if a["throttle"] <= th <= b["throttle"] and len(a["points"]) == len(b["points"]):
                f = 0.0 if b["throttle"] == a["throttle"] else (th - a["throttle"]) / (b["throttle"] - a["throttle"])
                return [[pa[i] + (pb[i] - pa[i]) * f for i in range(2)] for pa, pb in zip(a["points"], b["points"])]
        return [list(p) for p in table[-1]["points"]]
    sp = gearbox.get("shift_points")
    return [list(p) for p in sp] if isinstance(sp, list) else None


# ── checks ────────────────────────────────────────────────────────────────────
def _ascending(curve):
    xs = [p[0] for p in curve if isinstance(p, list) and p and isinstance(p[0], (int, float))]
    return xs == sorted(xs)


def _check_engine(eng, warnings):
    closed, parts = eng.get("torque_curve_closed"), eng.get("part_throttle")
    for name, c in (("torque_curve_closed", closed),):
        if isinstance(c, list) and not _ascending(c):
            warnings.append(f"powertrain.engine.{name} must be ascending in rpm")
    ths = []
    for i, pt in enumerate(parts or []):
        if not isinstance(pt, dict):
            continue
        if isinstance(pt.get("curve"), list) and not _ascending(pt["curve"]):
            warnings.append(f"powertrain.engine.part_throttle[{i}].curve must be ascending in rpm")
        if isinstance(pt.get("throttle"), (int, float)):
            ths.append(pt["throttle"])
    if ths != sorted(ths) or len(set(ths)) != len(ths):
        warnings.append("powertrain.engine.part_throttle: throttle values must be strictly ascending")
    wot = eng.get("torque_curve")
    if isinstance(closed, list) and isinstance(wot, list) and closed and wot:
        rpms = sorted({p[0] for p in closed + wot if isinstance(p, list) and p})
        worse = [r for r in rpms if interp(closed, r) > interp(wot, r)]
        if worse:
            warnings.append(f"powertrain.engine.torque_curve_closed is above the full-throttle torque_curve at {worse[0]:g} rpm")
        idle = eng.get("idle_rpm") if isinstance(eng.get("idle_rpm"), (int, float)) else 0.0
        pos = [r for r in rpms if r > idle * 1.2 and interp(closed, r) > 0]
        if pos:
            warnings.append(f"powertrain.engine.torque_curve_closed is positive at {pos[0]:g} rpm: closed-throttle torque is engine braking and should be negative above idle")
    if isinstance(wot, list) and isinstance(closed, list) and parts:
        curves = throttle_curves(eng)
        rpms = sorted({p[0] for _t, c in curves for p in c if isinstance(p, list) and p})
        for (t0, c0), (t1, c1) in zip(curves, curves[1:]):
            if any(interp(c0, r) > interp(c1, r) + 1e-9 for r in rpms):
                warnings.append(f"powertrain.engine: the torque curve at throttle {t0:g} is above the one at throttle {t1:g}")
                break


def _check_gearbox(gb, warnings):
    ratios = gb.get("ratios") if isinstance(gb.get("ratios"), list) else None
    tables = []
    if isinstance(gb.get("shift_points"), list):
        tables.append(("shift_points", gb["shift_points"]))
    for i, t in enumerate(gb.get("shift_points_vs_throttle") or []):
        if isinstance(t, dict) and isinstance(t.get("points"), list):
            tables.append((f"shift_points_vs_throttle[{i}]", t["points"]))
    ths = [t.get("throttle") for t in (gb.get("shift_points_vs_throttle") or []) if isinstance(t, dict) and isinstance(t.get("throttle"), (int, float))]
    if ths != sorted(ths) or len(set(ths)) != len(ths):
        warnings.append("powertrain.gearbox.shift_points_vs_throttle: throttle values must be strictly ascending")
    for name, pts in tables:
        if ratios is not None and len(pts) != len(ratios):
            warnings.append(f"powertrain.gearbox.{name} has {len(pts)} pairs for {len(ratios)} forward gears")
            continue
        for k, p in enumerate(pts):
            if isinstance(p, list) and len(p) == 2 and k < len(pts) - 1 and p[0] <= p[1]:
                warnings.append(f"powertrain.gearbox.{name}[{k}]: up_rpm ({p[0]:g}) is not above down_rpm ({p[1]:g})")
        if ratios is None:
            continue
        for k in range(len(pts) - 1):
            try:
                up, down_next = pts[k][0], pts[k + 1][1]
                after = up * ratios[k + 1] / ratios[k]
            except (TypeError, IndexError, ZeroDivisionError):
                continue
            if down_next >= after:
                warnings.append(f"powertrain.gearbox.{name}: shifting up from gear {k + 1} at {up:g} rpm drops the engine to {after:g} rpm, "
                                f"which is at or below the down-shift speed of gear {k + 2} ({down_next:g} rpm): the gearbox would hunt")


def _check_converter(cl, warnings):
    tc = cl.get("torque_converter")
    if isinstance(tc, dict) and cl.get("type") not in (None, "torque_converter"):
        warnings.append(f"powertrain.clutch.torque_converter is given but clutch.type is '{cl.get('type')}'")
    if not isinstance(tc, dict):
        return
    for name in ("capacity_factor", "torque_ratio"):
        c = tc.get(name)
        if not isinstance(c, list) or not c:
            warnings.append(f"powertrain.clutch.torque_converter.{name} is missing")
            continue
        if not _ascending(c):
            warnings.append(f"powertrain.clutch.torque_converter.{name} must be ascending in speed ratio")
        if c[0][0] != 0:
            warnings.append(f"powertrain.clutch.torque_converter.{name} must start at speed ratio 0 (the stall point)")
        if name == "capacity_factor" and any(p[1] <= 0 for p in c):
            warnings.append("powertrain.clutch.torque_converter.capacity_factor must be positive")
        if name == "torque_ratio" and c[-1][1] < 1.0 - 1e-9 and not tc.get("lockup"):
            warnings.append(f"powertrain.clutch.torque_converter.torque_ratio ends at {c[-1][1]:g}, below 1, and there is no lockup")
        if name == "torque_ratio" and c[0][1] < 1.0:
            warnings.append("powertrain.clutch.torque_converter.torque_ratio is below 1 at stall: a converter multiplies torque there")


def check(doc):
    """(errors, warnings) of the part-load engine data, shift points and torque converter. Everything is advisory (warnings)."""
    warnings = []
    pt = doc.get("powertrain") if isinstance(doc, dict) else None
    if not isinstance(pt, dict):
        return [], warnings
    if isinstance(pt.get("engine"), dict):
        _check_engine(pt["engine"], warnings)
    if isinstance(pt.get("gearbox"), dict):
        _check_gearbox(pt["gearbox"], warnings)
    if isinstance(pt.get("clutch"), dict):
        _check_converter(pt["clutch"], warnings)
    return [], warnings


def main(argv):
    for path in argv:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        _, warnings = check(doc)
        for w in warnings:
            print(f"  WARN   {path}: {w}")
        if not warnings:
            print(f"  OK     {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
