#!/usr/bin/env python3
"""SVJ anti-roll bar generator: a U-shaped bar as bodies, joints and a torsional spring (spec section 25.5).

The bar is two halves. Each half turns in a bearing on the chassis about the lateral axis and ends in a lever; a torsional
`spring` between the two halves carries the bar's torsion, k = G J / L (J the polar moment of the section, L the length of
the torsion section between the levers). A drop link (a body with a spherical joint at each end) joins every lever end to a
point of the suspension arm. Moving the two wheels in opposite directions twists the bar by the difference of the half
angles; moving them together turns both halves alike and loads nothing.

  anti_roll_bar(params) -> {"bodies", "constraints", "bar_rate": N m/rad, "drop_link_rate": N/m, "anti_roll_bar": {...}}
  python anti_roll_bar.py params.json         writes the generated items as JSON on stdout
"""
import json
import math
import sys

G_STEEL = 79.3e9
_S2 = math.sqrt(0.5)
Q_Z_TO_Y = [-_S2, 0.0, 0.0, _S2]                   # frame whose z axis is the lateral +y axis (the bar axis)


def polar_moment(p):
    """J (m^4) of a solid (`diameter`) or tubular (`diameter`, `inner_diameter`) round bar."""
    d, di = float(p["diameter"]), float(p.get("inner_diameter", 0.0))
    return math.pi * (d ** 4 - di ** 4) / 32.0


def lever_length(p):
    return math.hypot(float(p["lever_x"]), float(p.get("lever_z", 0.0)))


def bar_rate(p):
    """Torsional rate of the bar between the two halves (N m/rad): G J / L, L the span between the levers."""
    return float(p.get("G", G_STEEL)) * polar_moment(p) / (2.0 * abs(float(p["y_lever"])))


def drop_link_rate(p):
    """Rate at one drop link for wheels moving in opposite directions (N/m, before the motion ratio): 2 k / a^2."""
    return 2.0 * bar_rate(p) / lever_length(p) ** 2


def anti_roll_bar(p):
    """p: id, chassis (default 'chassis'), x, z (the bar axis), y_mount (lateral position of the bearings), y_lever
    (lateral position of the lever ends), lever_x (the lever end's offset from the axis along x, negative = rearward),
    lever_z (default 0), diameter [, inner_diameter], arm_l, arm_r (suspension body ids), link_l, link_r ([x, y, z] of the
    drop link's lower end on the arm), mass (the bar, default 5 kg), link_mass (default 0.2 kg), optional G, stations."""
    pid, ch = p["id"], p.get("chassis", "chassis")
    x, z = float(p["x"]), float(p["z"])
    ym, yl = abs(float(p["y_mount"])), abs(float(p["y_lever"]))
    ex, ez = x + float(p["lever_x"]), z + float(p.get("lever_z", 0.0))
    half_m = float(p.get("mass", 5.0)) / 2.0
    link_m = float(p.get("link_mass", 0.2))
    k = bar_rate(p)
    bodies, cons = [], []
    for tag, s in (("l", -1.0), ("r", 1.0)):
        half, link = f"{pid}_{tag}", f"drop_link_{pid}_{tag}"
        mid = [round((x + ex) / 2, 6), round(s * (ym + yl) / 4, 6), round((z + ez) / 2, 6)]
        bodies.append({"id": half, "name": f"Anti-roll bar {pid}, {'left' if s < 0 else 'right'} half", "category": "suspension", "mass": half_m,
                       "position": mid, "inertia": {"Ixx": round(half_m * 0.01, 6), "Iyy": round(half_m * 0.01, 6), "Izz": round(half_m * 0.01, 6)},
                       "parent": ch, "x_derived": True})
        bearing = {"position": [round(x, 6), round(s * ym, 6), round(z, 6)], "orientation": Q_Z_TO_Y}
        cons.append({"id": f"hinge_{half}", "type": "joint", "joint_type": "revolute", "body_a": ch, "body_b": half,
                     "frame_a": bearing, "frame_b": bearing, "x_derived": True})
        lever_end = [round(ex, 6), round(s * yl, 6), round(ez, 6)]
        low = [float(v) for v in p["link_" + tag]]
        bodies.append({"id": link, "name": f"Drop link {pid} {'left' if s < 0 else 'right'}", "category": "suspension", "mass": link_m,
                       "position": [round((lever_end[i] + low[i]) / 2, 6) for i in range(3)],
                       "inertia": {"Ixx": 0.001, "Iyy": 0.001, "Izz": 0.0001}, "parent": ch, "x_derived": True})
        cons.append({"id": f"ball_{link}_bar", "type": "joint", "joint_type": "spherical", "body_a": half, "body_b": link,
                     "frame_a": {"position": lever_end}, "frame_b": {"position": lever_end}, "x_derived": True})
        cons.append({"id": f"ball_{link}_arm", "type": "joint", "joint_type": "spherical", "body_a": p["arm_" + tag], "body_b": link,
                     "frame_a": {"position": [round(v, 6) for v in low]}, "frame_b": {"position": [round(v, 6) for v in low]}, "x_derived": True})
    centre = {"position": [round(x, 6), 0.0, round(z, 6)], "orientation": Q_Z_TO_Y}
    cons.append({"id": f"torsion_{pid}", "type": "spring", "kind": "torsional", "spring_type": "torsion_bar", "rate": round(k, 6),
                 "body_a": f"{pid}_l", "body_b": f"{pid}_r", "frame_a": centre, "frame_b": centre, "x_derived": True})
    entry = {"id": pid, "bar_rate": round(k, 6), "wheel_rate_equiv": round(drop_link_rate(p), 3)}
    if p.get("stations"):
        entry["stations"] = list(p["stations"])
    return {"bodies": bodies, "constraints": cons, "bar_rate": k, "drop_link_rate": drop_link_rate(p), "anti_roll_bar": entry}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(anti_roll_bar(json.load(fh)), indent=2))
