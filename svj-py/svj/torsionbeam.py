#!/usr/bin/env python3
"""SVJ twist-beam generator: a torsion-beam (twist-beam) rear axle as bodies, joints and a bushing (spec section 25.11).

Two trailing arms, each carrying its half of the cross beam, pivot on the chassis. The two halves meet at the middle of
the beam in a `fixed` joint whose `bushing` is soft in torsion about the lateral axis, k = G J / L (J the torsion
constant of the open section, L the beam length between the arms) and stiff in everything else (bending of the beam):
the beam twists when one wheel moves, the other side stays put. The beam lies on the line of the two pivots (lateral
axis): an offset beam, or pivot axes inclined in plan, would add bending of the beam to the twist, which this model does
not represent. The loop-closure solver (spec section 26) leaves the soft
directions of a bushing free (`SOFT_RATE`), so the two arms move independently and the twist is read from the joint.

  twist_beam(params) -> {"bodies": [...], "constraints": [...], "twist_rate": N m/rad, "roll_rate": N m/rad}
  python torsion_beam.py params.json        writes the generated items as JSON on stdout
"""
import json
import math
import sys

E_STEEL = 206e9
G_STEEL = 79.3e9
_S2 = math.sqrt(0.5)
SIDES = (("l", -1.0), ("r", 1.0))


Q_Z_TO_Y = [-_S2, 0.0, 0.0, _S2]                   # frame whose z axis is the lateral +y axis


def torsion_constant(p):
    """J (m^4): given as `torsion_constant`, else of an open section made of plates (b, t): sum b t^3 / 3."""
    if p.get("torsion_constant"):
        return float(p["torsion_constant"])
    return sum(b * t ** 3 / 3.0 for b, t in p["plates"])


def twist_rate(p):
    """Torsional rate of the beam (N m/rad): G J / L."""
    return float(p.get("G", G_STEEL)) * torsion_constant(p) / (2.0 * p["half_track_arms"])


def arm_length(p):
    return abs(p["wheel_x"] - p["pivot_x"])


def roll_rate(p):
    """Roll stiffness the beam adds (N m/rad), springs excluded: k_twist (track / arm length)^2."""
    return twist_rate(p) * (2.0 * p["half_track"] / arm_length(p)) ** 2


def twist_beam(p):
    """p: id (suffix, default 'r' for rear), chassis, pivot_x, pivot_z, half_track_arms (lateral position of the pivots),
    half_track (of the wheels), wheel_x, wheel_z, torsion_constant or plates [(b, t), ...], optional G, E,
    bending_I (m^4, default 40 J), arm_mass, beam_mass. The beam centre is the point on the pivot line in the middle."""
    ch = p.get("chassis", "chassis")
    beam_x, beam_z = float(p["pivot_x"]), float(p["pivot_z"])
    arm_m, beam_m = float(p.get("arm_mass", 6.0)), float(p.get("beam_mass", 8.0))
    L = 2.0 * p["half_track_arms"]
    J = torsion_constant(p)
    I = float(p.get("bending_I", 40.0 * J))
    k_tw = twist_rate(p)
    k_b = float(p.get("E", E_STEEL)) * I / L
    k_sh = 12.0 * float(p.get("E", E_STEEL)) * I / L ** 3
    bodies, cons = [], []
    for tag, s in SIDES:
        y_p, y_w = s * p["half_track_arms"], s * p["half_track"]
        bid = f"trailing_arm_r{tag}"
        px, pz = float(p["pivot_x"]), float(p["pivot_z"])
        wx, wz = float(p["wheel_x"]), float(p["wheel_z"])
        cx, cy, cz = (px + wx) / 2.0, (y_p + y_w) / 2.0, (pz + wz) / 2.0
        m = arm_m + beam_m / 2.0
        bodies.append({"id": bid, "name": f"Trailing arm R{tag.upper()} with half the beam", "category": "suspension", "mass": m,
                       "position": [round(cx, 6), round(cy, 6), round(cz, 6)],
                       "inertia": {"Ixx": round(m * 0.02, 6), "Iyy": round(m * 0.04, 6), "Izz": round(m * 0.05, 6)},
                       "parent": ch, "x_derived": True,
                       "markers": {"wheel_center": {"position": [round(wx, 6), y_w, round(wz, 6)]},
                                   "pivot": {"position": [round(px, 6), round(y_p, 6), round(pz, 6)]},
                                   "beam_center": {"position": [round(beam_x, 6), 0.0, round(beam_z, 6)]}}})
        frame = {"position": [round(px, 6), round(y_p, 6), round(pz, 6)], "orientation": Q_Z_TO_Y}
        cons.append({"id": f"pivot_{bid}", "type": "joint", "joint_type": "revolute", "body_a": ch, "body_b": bid,
                     "frame_a": frame, "frame_b": frame, "x_derived": True})
    centre = {"position": [round(beam_x, 6), 0.0, round(beam_z, 6)]}
    cons.append({"id": "twist_beam", "type": "joint", "joint_type": "fixed", "body_a": "trailing_arm_rl", "body_b": "trailing_arm_rr",
                 "frame_a": centre, "frame_b": centre, "x_derived": True,
                 "bushing": {"rate_x": k_sh, "rate_y": k_sh, "rate_z": k_sh, "rate_rx": k_b, "rate_ry": k_tw, "rate_rz": k_b}})
    return {"bodies": bodies, "constraints": cons, "twist_rate": k_tw, "roll_rate": roll_rate(p)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(twist_beam(json.load(fh)), indent=2))
