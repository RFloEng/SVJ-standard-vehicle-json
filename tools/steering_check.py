#!/usr/bin/env python3
"""
SVJ steering consistency checks (spec 8.7).

The steering section states ratios and limits (`overall_ratio`, `lock_to_lock`, `max_steer_angle`, `rack_travel`), the
steering wheel (`position`, `column_axis`, `column_rake`) and, in the multibody model, the steering wheel joint and the coupling
that gives the steering gear its coordinate (spec 25.4). These must tell the same story. Checks, all warnings except a
self-contradiction in the file:

  * `max_steer_angle`, `lock_to_lock_turns` against `lock_to_lock` and `overall_ratio`;
  * `steering_wheel.column_axis` is a direction, it points away from the driver (forward), and `column_rake` agrees with it;
  * the steering wheel joint sits at `steering_wheel.position` on that axis;
  * the coupling ratio brings the gear to its travel at the steering lock (`rack_travel` / 2 at `lock_to_lock` / 2);
  * the wheel angle the loop solver needs for one radian of road-wheel steer equals `overall_ratio` (±10 %), and a
    positive wheel angle steers the road wheels to the right.

Usage:  python tools/steering_check.py file.svj.json
Library: check(doc) -> (errors, warnings)
"""
from __future__ import annotations

import json
import math
import sys

try:                                           # inside svj-py
    from svj import loopsolver as ls
    from svj.frame import frame_of, ISO
except ImportError:                            # running from tools/
    import loop_solver as ls
    from convert_frame import frame_of, ISO

REL_TOL = 0.02          # derived convenience fields
GEOMETRY_TOL = 0.10     # solved geometry against the stated overall ratio
ANGLE_TOL_DEG = 0.5


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _vec(v):
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(_num(c) for c in v)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v) if n > 1e-12 else None


def _zaxis(q):
    """z axis of a frame with orientation quaternion [x, y, z, w]."""
    x, y, z, w = q
    return (2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y))


def rake_of_axis(axis, up):
    """Column rake (rad): the angle of the steering wheel axis below the horizontal (axis points away from the driver)."""
    u = _unit(axis)
    return math.asin(max(-1.0, min(1.0, -up * u[2])))


def axis_of_rake(rake, up):
    """Steering wheel axis in the vertical plane of the vehicle, pointing forward and down, for a column rake (rad)."""
    return (math.cos(rake), 0.0, -up * math.sin(rake))


def wheel_axis(sw, up):
    """The unit axis of a `steering_wheel` object from `column_axis`, else from `column_rake`; None when it has neither."""
    if _vec(sw.get("column_axis")):
        return _unit(sw["column_axis"])
    if _num(sw.get("column_rake")):
        return axis_of_rake(sw["column_rake"], up)
    return None


def _gear_coupling(doc):
    """(wheel joint, gear joint, ratio) of the coupling that gives a steering joint its coordinate from a revolute joint."""
    cons = (doc.get("constraints") or doc.get("chassis", {}).get("constraints") or [])
    joints = {c.get("id"): c for c in cons if c.get("type") == "joint"}
    gears = {st.get("steering_joint") for st in (doc.get("wheel_stations") or []) if st.get("steering_joint")}
    for c in cons:
        if c.get("type") != "coupling" or not _num(c.get("ratio")) or c["ratio"] == 0:
            continue
        ja, jb = c.get("joint_a"), c.get("joint_b")
        if jb in gears and (joints.get(ja) or {}).get("joint_type") == "revolute":
            return joints[ja], joints[jb], float(c["ratio"])
        if ja in gears and (joints.get(jb) or {}).get("joint_type") == "revolute":
            return joints[jb], joints[ja], 1.0 / float(c["ratio"])
    return None


def _right_steer(doc, sid, X):
    """Road-wheel steer angle (rad) of a station in pose X, positive when the wheel points to the right of straight ahead."""
    a = ls.wheel_axis(doc, sid, X)
    if a is None:
        return None
    iso = frame_of(doc) == ISO                                  # the steer angle is defined in ISO axes (y to the left)
    centre_y = ls._wheel_centre(doc, ls._station_map(doc)[sid], X)[1] * (1 if iso else -1)
    s = 1.0 if centre_y >= 0 else -1.0                          # +1 on the left: the spin axis points outboard, to +y
    return math.atan2(s * a[0], s * a[1] * (1 if iso else -1))


def check(doc):
    errors, warnings = [], []
    st = doc.get("steering")
    if not isinstance(st, dict):
        return errors, warnings
    up = ls._up(doc)

    # 1. derived convenience fields
    if _num(st.get("lock_to_lock")) and _num(st.get("overall_ratio")) and st["overall_ratio"] > 0:
        if _num(st.get("max_steer_angle")):
            want = (st["lock_to_lock"] / 2) / st["overall_ratio"]
            if abs(st["max_steer_angle"] - want) > REL_TOL * want:
                warnings.append(f"steering: max_steer_angle {st['max_steer_angle']:.4f} rad differs from (lock_to_lock/2)/overall_ratio = {want:.4f} rad")
        if _num(st.get("lock_to_lock_turns")):
            want = st["lock_to_lock"] / (2 * math.pi)
            if abs(st["lock_to_lock_turns"] - want) > REL_TOL * want:
                warnings.append(f"steering: lock_to_lock_turns {st['lock_to_lock_turns']:.3f} differs from lock_to_lock/(2*pi) = {want:.3f}")

    # 2. the steering wheel placement
    sw = st.get("steering_wheel") if isinstance(st.get("steering_wheel"), dict) else {}
    axis = None
    if "column_axis" in sw:
        if not _vec(sw["column_axis"]) or _unit(sw["column_axis"]) is None:
            errors.append("steering.steering_wheel.column_axis: must be a non-zero [x, y, z] direction")
        else:
            n = math.sqrt(sum(c * c for c in sw["column_axis"]))
            if abs(n - 1) > 0.01:
                warnings.append(f"steering.steering_wheel.column_axis: length {n:.3f}; give a unit vector")
            axis = _unit(sw["column_axis"])
            if axis[0] <= 0:
                warnings.append("steering.steering_wheel.column_axis: must point away from the driver (forward, +x); "
                                "a positive wheel angle then turns clockwise as the driver sees it, which steers right")
            elif _num(sw.get("column_rake")):
                d = math.degrees(abs(rake_of_axis(axis, up) - sw["column_rake"]))
                if d > ANGLE_TOL_DEG:
                    errors.append(f"steering.steering_wheel: column_rake {math.degrees(sw['column_rake']):.1f} deg contradicts the axis "
                                  f"(rake {math.degrees(rake_of_axis(axis, up)):.1f} deg)")
    elif _num(sw.get("column_rake")):
        axis = axis_of_rake(sw["column_rake"], up)
    if _num(sw.get("column_rake")) and not -0.05 <= sw["column_rake"] <= math.radians(80):
        warnings.append(f"steering.steering_wheel.column_rake: {math.degrees(sw['column_rake']):.1f} deg is outside 0..80 deg")
    if "position" in sw and not _vec(sw["position"]):
        errors.append("steering.steering_wheel.position: must be [x, y, z]")

    # 3. the multibody chain: steering wheel joint -> coupling -> gear joint
    gc = _gear_coupling(doc)
    if gc is None:
        return errors, warnings
    wj, gj, ratio = gc
    fa = wj.get("frame_a") or {}
    if _vec(sw.get("position")) and wj.get("body_a") == "chassis" and _vec(fa.get("position")):
        d = math.dist(sw["position"], fa["position"])
        if d > 0.005:
            warnings.append(f"steering: joint '{wj.get('id')}' is {d * 1000:.0f} mm from steering_wheel.position")
    if axis is not None and isinstance(fa.get("orientation"), (list, tuple)) and len(fa["orientation"]) == 4:
        z = _zaxis(fa["orientation"])
        dot = sum(a * b for a, b in zip(z, axis))
        if abs(dot) < 0.999:
            warnings.append(f"steering: joint '{wj.get('id')}' axis is {math.degrees(math.acos(min(1.0, abs(dot)))):.1f} deg off steering_wheel.column_axis")
        elif dot < 0:
            warnings.append(f"steering: joint '{wj.get('id')}' axis points toward the driver; steering_wheel.column_axis points away, "
                            "so the joint's positive angle is anticlockwise")

    # 4. the gear reaches its travel at the lock (rack and pinion: the coupling ratio is m per rad)
    if gj.get("joint_type") == "translational" and _num(st.get("rack_travel")) and _num(st.get("lock_to_lock")):
        full = abs(ratio) * st["lock_to_lock"]
        if abs(full - st["rack_travel"]) > 0.05 * st["rack_travel"]:
            warnings.append(f"steering: coupling ratio {ratio:.5f} m/rad moves the rack {full * 1000:.0f} mm over lock_to_lock, "
                            f"rack_travel is {st['rack_travel'] * 1000:.0f} mm")

    # 5. the solved geometry against overall_ratio and the steering direction
    if not _num(st.get("overall_ratio")):
        return errors, warnings
    steered = [sid for sid, s in ls._station_map(doc).items() if s.get("steering_joint") == gj.get("id")]
    if not steered:
        return errors, warnings
    h = 0.01
    try:
        lo = ls.solve(doc, joint_values={wj["id"]: [-h]})
        hi = ls.solve(doc, joint_values={wj["id"]: [h]})
    except Exception as e:                      # a solver failure is a finding, not a crash of the validator
        warnings.append(f"steering: the steering chain does not solve ({e})")
        return errors, warnings
    if not (lo["converged"] and hi["converged"]):
        warnings.append("steering: the steering chain does not converge for a small steering wheel angle")
        return errors, warnings
    gains = []
    for sid in steered:
        a, b = _right_steer(doc, sid, hi["transforms"]), _right_steer(doc, sid, lo["transforms"])
        if a is not None and b is not None:
            gains.append((a - b) / (2 * h))        # road-wheel steer to the right per rad of steering wheel
    if not gains:
        return errors, warnings
    g = sum(gains) / len(gains)
    if g <= 0:
        warnings.append("steering: a positive steering wheel angle steers the road wheels to the left; "
                        "positive must be clockwise as the driver sees it (axis away from the driver) and steer right")
    elif abs(1 / g - st["overall_ratio"]) > GEOMETRY_TOL * st["overall_ratio"]:
        warnings.append(f"steering: the hardpoints and the coupling give a ratio of {1 / g:.1f} (steering wheel rad per road-wheel rad "
                        f"at the centre), overall_ratio is {st['overall_ratio']:.1f}")
    return errors, warnings


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        doc = json.load(f)
    errors, warnings = check(doc)
    for w in warnings:
        print("  WARN  ", w)
    for e in errors:
        print("  ERROR ", e)
    if not errors and not warnings:
        print("  OK     steering consistent")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
