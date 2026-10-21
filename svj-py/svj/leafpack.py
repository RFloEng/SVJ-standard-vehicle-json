#!/usr/bin/env python3
"""SVJ leaf-pack generator: a flexible leaf spring as bodies, joints and torsional springs (spec section 25.9).

A semi-elliptic pack loaded at the axle seat acts as two cantilevers clamped at the seat, each of length L/2 and bending
stiffness EI = E * n * b * t^3 / 12 (n leaves of width b and thickness t). Each half is cut into `segments` rigid
segments joined by revolute joints about the lateral axis, every joint carrying a torsional spring of rate
    k = EI / l * (M + 1)(2M + 1) / (2 M^2)          (l = segment length, M = segments per half)
whose correction factor makes the tip deflection of the chain equal the exact cantilever value F (L/2)^3 / (3 EI), so the
rate at the seat is 48 EI / L^3 for any M. The seat joint carries the axle, the ends are an eye (revolute) or a slipper
(translational along x) on the chassis. Everything generated is marked `x_derived`.

  leaf_pack(params) -> {"bodies": [...], "constraints": [...], "rate": N/m at the seat}
  python leaf_pack.py params.json            writes the generated items as JSON on stdout
"""
import json
import math
import sys

E_STEEL = 206e9
_S2 = math.sqrt(0.5)
Q_Z_TO_Y = [-_S2, 0.0, 0.0, _S2]          # frame whose z axis is the lateral +y axis (bending axis of the pack)
Q_Z_TO_X = [0.0, _S2, 0.0, _S2]           # frame whose z axis is the longitudinal +x axis (slipper sliding direction)


def bending_stiffness(p):
    """EI of the pack (N m^2): n leaves of width b and thickness t, no inter-leaf friction."""
    return float(p.get("E", E_STEEL)) * p["leaves"] * p["width"] * p["thickness"] ** 3 / 12.0


def seat_rate(p):
    """Vertical rate at the axle seat (N/m): 48 EI / L^3 with L the span between the end attachments."""
    return 48.0 * bending_stiffness(p) / (p["x_rear"] - p["x_front"]) ** 3


def joint_rate(p):
    m = int(p.get("segments", 4))
    seg = (p["x_rear"] - p["x_front"]) / 2.0 / m
    return bending_stiffness(p) / seg * (m + 1) * (2 * m + 1) / (2.0 * m * m)


def leaf_pack(p):
    """p: id, axle (body id of the axle), x_front, x_rear (end attachments), seat_x, y (lateral position), z (height of
    the pack at the seat), leaves, width, thickness, mass, optional E, segments (per half, default 4), arch (rise of the
    pack at the seat over its ends, m), end_front / end_rear ('eye' or 'slipper'; default eye in front, slipper at the rear), chassis (body id, default 'chassis'),
    front_attachment / rear_attachment (z of the hanger, default the end of the pack)."""
    pid, axle, chassis = p["id"], p["axle"], p.get("chassis", "chassis")
    m = int(p.get("segments", 4))
    xf, xr = float(p["x_front"]), float(p["x_rear"])
    xs = float(p.get("seat_x", (xf + xr) / 2.0))
    y, z0, arch = float(p.get("y", 0.0)), float(p["z"]), float(p.get("arch", 0.0))
    half = {"front": (xs, xf), "rear": (xs, xr)}
    k = joint_rate(p)
    seg_mass = float(p["mass"]) / (2 * m)
    bodies, cons = [], []

    def z_at(x):                                         # parabolic arch, z is down: the ends hang lower than the seat
        half_span = max(abs(xf - xs), abs(xr - xs))
        return z0 + arch * (((x - xs) / half_span) ** 2 - 1.0) if arch else z0

    for side, (x0, x1) in half.items():
        length = (x1 - x0) / m
        for i in range(1, m + 1):
            xa, xb = x0 + (i - 1) * length, x0 + i * length
            sid = f"{pid}_{side}_{i}"
            ell = abs(length)
            inertia = seg_mass * ell * ell / 12.0
            bodies.append({"id": sid, "name": f"Leaf pack {pid}, {side} segment {i}", "category": "suspension", "mass": seg_mass,
                           "position": [round((xa + xb) / 2, 6), y, round(z_at((xa + xb) / 2), 6)],
                           "inertia": {"Ixx": round(inertia * 0.05, 9), "Iyy": round(inertia, 9), "Izz": round(inertia, 9)},
                           "parent": chassis, "x_derived": True})
            prev = axle if i == 1 else f"{pid}_{side}_{i - 1}"
            frame = {"position": [round(xa, 6), y, round(z_at(xa), 6)], "orientation": Q_Z_TO_Y}
            cons.append({"id": f"hinge_{sid}", "type": "joint", "joint_type": "revolute", "body_a": prev, "body_b": sid,
                         "frame_a": frame, "frame_b": frame, "x_derived": True})
            cons.append({"id": f"bend_{sid}", "type": "spring", "kind": "torsional", "spring_type": "leaf", "rate": round(k, 6),
                         "body_a": prev, "body_b": sid, "frame_a": frame, "frame_b": frame, "x_derived": True})
        end = p.get("end_" + side, "eye" if side == "front" else "slipper")
        pos = [round(x1, 6), y, round(float(p.get(side + "_attachment", z_at(x1))), 6)]
        last = f"{pid}_{side}_{m}"
        if end == "eye":
            frame = {"position": pos, "orientation": Q_Z_TO_Y}
            cons.append({"id": f"eye_{pid}_{side}", "type": "joint", "joint_type": "revolute", "body_a": chassis, "body_b": last,
                         "frame_a": frame, "frame_b": frame, "x_derived": True})
        elif end == "slipper":
            frame = {"position": pos, "orientation": Q_Z_TO_X}
            cons.append({"id": f"slipper_{pid}_{side}", "type": "joint", "joint_type": "translational", "body_a": chassis,
                         "body_b": last, "frame_a": frame, "frame_b": frame, "x_derived": True})
        else:
            raise ValueError(f"end_{side}: '{end}' is neither 'eye' nor 'slipper'")
    return {"bodies": bodies, "constraints": cons, "rate": seat_rate(p)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(leaf_pack(json.load(fh)), indent=2))
