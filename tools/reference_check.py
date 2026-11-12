#!/usr/bin/env python3
"""
SVJ physical consistency checks of the reference pose, mass properties, brakes, bushings and aero (spec 7.4, 12.6, 13.3, 24.4, 24.5).

A simulator built on SVJ needs these to agree before it can start without guessing:

  * springs (24.5): the force law is F = preload + rate * (L_ref - L), `preload` the force at the reference pose;
    a compression spring must not pull there. With `reference_pose.condition` `static_equilibrium` (the default
    reading) the springs must carry the sprung weight of each axle, by virtual work through the loop solver;
  * mass (7.4): the chassis body's own properties are the composite minus every listed body, and must be physical
    (positive mass, centre inside the vehicle, positive-definite inertia that satisfies the triangle inequality);
    from v0.111 every body with mass needs an inertia (an error; older files are not asked);
    `mass_unsprung_per_corner` is derived and is checked against the corner bodies;
  * brakes (12.6): the hydraulic chain decides the front share; `bias` is informative and is compared (0.02);
  * bushings (24.4): a rate so low that the static corner load would move the joint by centimetres is flagged;
    the wheel hinge's +Z axis must point left so that a positive coordinate rolls the wheel forward;
  * aero (13.3): `Cpm` against the `Cl_front`/`Cl_rear` split when both are given.

Usage:  python tools/reference_check.py file.svj.json
Library: check(doc) -> (errors, warnings)
"""
from __future__ import annotations

import json
import math
import sys

try:                                           # inside svj-py
    from svj import constraints as cc
    from svj import loopsolver as ls
    from svj.frame import frame_of, ISO
except ImportError:                            # running from tools/
    import constraints_check as cc
    import loop_solver as ls
    from convert_frame import frame_of, ISO

G = 9.81
BALANCE_TOL = 0.20          # spring support against sprung weight, per axle
BIAS_TOL = 0.02
SAG_LIMIT = 0.005           # m of static movement a bushing may be asked for
DEFAULT_INERTIA_RADIUS = 0.02   # m: a body without inertia counts as m * r^2 about its own point
AERO_TOL = 0.01
UNSPRUNG_TOL = 0.15


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _version(doc):
    try:
        return tuple(int(p) for p in str((doc.get("_metadata") or {}).get("version", "0")).split(".")[:2])
    except ValueError:
        return (0, 0)


def _eigs(m):
    """Eigenvalues of a symmetric 3x3 matrix (closed form)."""
    a11, a22, a33 = m[0][0], m[1][1], m[2][2]
    a12, a13, a23 = m[0][1], m[0][2], m[1][2]
    p1 = a12 ** 2 + a13 ** 2 + a23 ** 2
    q = (a11 + a22 + a33) / 3.0
    if p1 < 1e-18:
        return sorted((a11, a22, a33))
    p2 = (a11 - q) ** 2 + (a22 - q) ** 2 + (a33 - q) ** 2 + 2 * p1
    p = math.sqrt(p2 / 6.0)
    b = [[(m[i][j] - (q if i == j else 0.0)) / p for j in range(3)] for i in range(3)]
    det = (b[0][0] * (b[1][1] * b[2][2] - b[1][2] * b[2][1]) - b[0][1] * (b[1][0] * b[2][2] - b[1][2] * b[2][0])
           + b[0][2] * (b[1][0] * b[2][1] - b[1][1] * b[2][0]))
    r = max(-1.0, min(1.0, det / 2.0))
    phi = math.acos(r) / 3.0
    e1 = q + 2 * p * math.cos(phi)
    e3 = q + 2 * p * math.cos(phi + 2 * math.pi / 3)
    return sorted((e3, 3 * q - e1 - e3, e1))


def _stations(doc):
    out = {}
    for sid, st in ls._station_map(doc).items():
        c = ls._wheel_centre(doc, st, {})
        if c is not None:
            out[sid] = (st, c)
    return out


# ── springs and the reference pose ────────────────────────────────────────────
def _springs(doc, errors, warnings):
    for c in cc._constraints(doc, "spring"):
        if c.get("kind") == "torsional" or not _num(c.get("rate")) or c["rate"] <= 0 or not _num(c.get("preload")):
            continue
        if c["preload"] < 0 and c.get("reference") != "wheel":
            warnings.append(f"spring '{c.get('id')}': a compression spring (rate > 0) has a negative preload {c['preload']:.0f} N, "
                            "it pulls at the reference pose (spec 24.5: F = preload + rate * (installed_length - length))")


def _unsprung_total(doc):
    u = (doc.get("chassis") or {}).get("mass_unsprung_per_corner")
    if isinstance(u, dict):
        vals = [v for k, v in u.items() if _num(v) and not k.startswith("_")]
        if vals:
            return sum(vals)
    return None


def _balance(doc, warnings):
    ref = doc.get("reference_pose") if isinstance(doc.get("reference_pose"), dict) else {}
    if ref.get("condition", "static_equilibrium") != "static_equilibrium":
        return
    ch = doc.get("chassis") or {}
    M, cg = ch.get("mass_total"), ch.get("center_of_gravity")
    if not _num(M) or not isinstance(cg, list) or len(cg) != 3:
        return
    sts = _stations(doc)
    springs = [c for c in cc._constraints(doc, "spring") if c.get("kind") != "torsional" and _num(c.get("preload"))]
    if len(sts) < 2 or not springs:
        return
    xs = sorted(c[0] for _, c in sts.values())
    if xs[-1] - xs[0] < 0.5:
        return
    mid = (xs[0] + xs[-1]) / 2
    front = [s for s, (_, c) in sts.items() if c[0] >= mid]
    rear = [s for s in sts if s not in front]
    xf = sum(sts[s][1][0] for s in front) / len(front)
    xr = sum(sts[s][1][0] for s in rear) / len(rear)
    share_f = max(0.0, min(1.0, (cg[0] - xr) / (xf - xr)))
    unspr = _unsprung_total(doc)
    sprung = M - (unspr if unspr is not None else 0.10 * M)
    comps = ls._components(doc)
    h = 0.002
    got = {}
    for sid, (st, _) in sts.items():
        comp = next((set(c) for c in comps if st.get("upright_body") in c), None)
        mine = [c for c in springs if comp and (c.get("body_a") in comp or c.get("body_b") in comp)]
        if not mine:
            continue
        try:
            lo = ls.sweep(doc, sid, [-h])[0]
            hi = ls.sweep(doc, sid, [h])[0]
        except Exception:
            return
        if not (lo["converged"] and hi["converged"]):
            return
        w = 0.0
        for c in mine:
            if c.get("reference") == "wheel":
                w += c["preload"]
                continue
            k = c["id"]
            if k in lo["element_lengths"] and k in hi["element_lengths"]:
                w += -c["preload"] * (hi["element_lengths"][k] - lo["element_lengths"][k]) / (2 * h)
        got[sid] = w
    for name, group, share in (("front", front, share_f), ("rear", rear, 1 - share_f)):
        have = [got[s] for s in group if s in got]
        if len(have) != len(group):
            continue
        want = sprung * G * share
        if want > 1 and abs(sum(have) - want) > BALANCE_TOL * want:
            warnings.append(f"reference_pose: the {name} springs hold {sum(have):.0f} N at the wheels in the reference pose, the sprung weight "
                            f"of the axle is {want:.0f} N; the springs do not balance the load (spec 7.4, 24.5: static_equilibrium)")


# ── mass properties ───────────────────────────────────────────────────────────
def _mass(doc, errors, warnings):
    ch = doc.get("chassis") or {}
    strict = _version(doc) >= (0, 111)
    msg = errors if strict else warnings
    bodies = [b for b in (ch.get("mass_bodies") or []) if isinstance(b, dict) and _num(b.get("mass")) and b["mass"] > 0]
    if strict:
        miss = [b.get("id", "?") for b in bodies if cc.body_inertia(b) is None]
        if miss:
            errors.append(f"chassis.mass_bodies: {len(miss)} bodies with mass have no inertia ({', '.join(map(str, miss[:6]))}"
                          f"{', ...' if len(miss) > 6 else ''}); every body with mass > 0 needs one (spec 7.4)")
    M, cg = ch.get("mass_total"), ch.get("center_of_gravity")
    if not _num(M) or not isinstance(cg, list) or len(cg) != 3:
        return
    placed = [b for b in bodies if isinstance(b.get("position"), list) and len(b["position"]) == 3]
    total = sum(b["mass"] for b in placed)
    m0 = M - total
    if m0 > 1.0:
        p0 = [(M * cg[i] - sum(b["mass"] * b["position"][i] for b in placed)) / m0 for i in range(3)]
        wheels = [c for _, c in _stations(doc).values()]
        if wheels:
            lo = [min(p[0] for p in wheels) - 4.0, min(p[1] for p in wheels) - 0.3, min(p[2] for p in wheels) - 0.3]
            hi = [max(p[0] for p in wheels) + 4.0, max(p[1] for p in wheels) + 0.3, max(p[2] for p in wheels) + 3.0]
            if any(p0[i] < lo[i] or p0[i] > hi[i] for i in range(3)):
                msg.append(f"chassis: the remaining {m0:.1f} kg (mass_total minus the listed bodies) would sit at "
                           f"[{p0[0]:.2f}, {p0[1]:.2f}, {p0[2]:.2f}] given the centre_of_gravity, outside the vehicle: "
                           "the declared CG and the listed bodies do not agree (spec 7.4)")
        i_comp = cc._inertia_mat(ch.get("inertia"))
        if i_comp is not None:
            acc = i_comp
            for b in placed:
                ib = cc.body_inertia(b) or tuple(tuple(b["mass"] * DEFAULT_INERTIA_RADIUS ** 2 if i == j else 0.0 for j in range(3)) for i in range(3))
                acc = cc._madd(acc, cc._madd(ib, cc._steiner(b["mass"], cc._sub(tuple(b["position"]), tuple(cg)))), -1.0)
            acc = cc._madd(acc, cc._steiner(m0, cc._sub(tuple(p0), tuple(cg))), -1.0)
            e = _eigs(acc)
            if max(abs(v) for v in e) < 1e-6:
                pass                                      # no inertia declared for the chassis: nothing to compare
            elif e[0] <= 0:
                msg.append(f"chassis: the composite inertia minus the listed bodies is not positive definite (principal values "
                           f"{e[0]:.1f}, {e[1]:.1f}, {e[2]:.1f} kg*m2): the declared inertia and the bodies do not agree (spec 7.4)")
            elif e[0] + e[1] < e[2] * 0.99:
                msg.append(f"chassis: the remaining inertia violates the triangle inequality (principal values "
                           f"{e[0]:.1f}, {e[1]:.1f}, {e[2]:.1f} kg*m2) (spec 7.4)")
    if ch.get("mass_bodies_complete") is True and abs(m0) > max(0.5, 0.005 * M):
        msg.append(f"chassis: mass_bodies_complete is true but the bodies sum to {total:.1f} kg of {M:.1f} kg")
    # derived: mass_unsprung_per_corner against the corner bodies
    u = ch.get("mass_unsprung_per_corner")
    if isinstance(u, dict):
        by_id = {b.get("id"): b for b in (ch.get("mass_bodies") or []) if isinstance(b, dict)}
        for sid, (st, _) in _stations(doc).items():
            if not _num(u.get(sid)):
                continue
            s = 0.0
            for k in ("wheel_body", "upright_body"):
                b = by_id.get(st.get(k))
                s += b["mass"] if b and _num(b.get("mass")) else 0.0
            for b in by_id.values():
                sf = (b.get("mass_distribution") or {}).get("sprung_fraction")
                if _num(sf) and _num(b.get("mass")) and str(b.get("id", "")).lower().endswith("_" + sid.lower()):
                    s += (1 - sf) * b["mass"]
            if s > 0 and (s > u[sid] * (1 + UNSPRUNG_TOL) or (ch.get("mass_bodies_complete") is True and s < u[sid] * (1 - UNSPRUNG_TOL))):
                warnings.append(f"chassis.mass_unsprung_per_corner.{sid}: {u[sid]:.1f} kg, the corner bodies add up to {s:.1f} kg "
                                "(the field is derived; the bodies win, spec 7.4)")


# ── brakes ────────────────────────────────────────────────────────────────────
def _brakes(doc, warnings):
    br = doc.get("brakes")
    if not isinstance(br, dict) or not _num(br.get("bias")):
        return
    mc = br.get("master_cylinder") or {}
    d1 = mc.get("bore_primary", mc.get("bore"))
    d2 = mc.get("bore_secondary", d1)
    if not _num(d1) or not _num(d2) or d1 <= 0 or d2 <= 0:
        return
    sts = _stations(doc)
    if len(sts) < 2:
        return
    xs = [c[0] for _, c in sts.values()]
    mid = (min(xs) + max(xs)) / 2
    prop = br.get("proportioning") if isinstance(br.get("proportioning"), dict) else {}
    P = prop["knee_pressure"] if prop.get("type") == "knee" and _num(prop.get("knee_pressure")) else 3.0e6
    torque = {"front": 0.0, "rear": 0.0}
    for sid, (st, c) in sts.items():
        b = st.get("brake") if isinstance(st.get("brake"), dict) else None
        if not b:
            return
        a = (b.get("caliper") or {}).get("piston_area_total")
        r = (b.get("disc") or {}).get("effective_radius")
        pad = b.get("pad") or {}
        mu = pad.get("mu", pad.get("mu_cold", 1.0))
        if not (_num(a) and _num(r) and _num(mu)):
            return
        axle = "front" if c[0] >= mid else "rear"
        left = (c[1] >= 0) == (frame_of(doc) == ISO)
        if br.get("circuit_type") == "front_rear_split":
            d = d1 if axle == "front" else d2
        elif br.get("circuit_type") == "dual_diagonal":
            d = d1 if (axle == "front") == left else d2
        else:
            d = d1
        p = P * (d1 / d) ** 2                       # same piston force, line pressure follows the bore
        if axle == "rear" and prop.get("type") in ("fixed_ratio", "knee") and _num(prop.get("ratio")):
            knee = prop.get("knee_pressure", 0.0) if prop["type"] == "knee" else 0.0
            p = p if p <= knee else knee + prop["ratio"] * (p - knee)
        torque[axle] += p * a * 2 * mu * r
    tot = torque["front"] + torque["rear"]
    if tot > 0 and abs(torque["front"] / tot - br["bias"]) > BIAS_TOL:
        warnings.append(f"brakes: the hardware gives a front brake share of {torque['front'] / tot:.3f}, bias is {br['bias']:.3f}; "
                        "the hydraulic chain decides, bias is informative (spec 12.6)")


# ── bushings, wheel hinge ─────────────────────────────────────────────────────
def _bushings(doc, warnings):
    ch = doc.get("chassis") or {}
    sts = ls._station_map(doc)
    M = ch.get("mass_total")
    if _num(M) and sts:
        corner = M * G / len(sts)
        for c in cc._constraints(doc, "joint"):
            b = c.get("bushing")
            if not isinstance(b, dict):
                continue
            rates = [b[k] for k in ("rate_x", "rate_y", "rate_z") if _num(b.get(k)) and b[k] > 0]
            if rates and corner / min(rates) > SAG_LIMIT:
                warnings.append(f"joint '{c.get('id')}': bushing rate {min(rates):.3g} N/m would move {corner / min(rates) * 1000:.0f} mm under the static "
                                f"corner load of {corner:.0f} N (an upper bound: the arm's other pivots share it); a bushing must carry the car (spec 24.4)")
                break                                        # one finding is enough to send the author to the table
    left = 1.0 if frame_of(doc) == ISO else -1.0
    if _version(doc) < (0, 111):                  # the wheel spin sense is asked from v0.111; older files carry the earlier frames
        return
    for sid, st in sts.items():
        h = ls._wheel_hinge(doc, st)
        if not h or h.get("joint_type") != "revolute":
            continue
        side = "a" if h.get("body_a") == st.get("upright_body") else "b"
        fr = cc._frame(doc, h, side)
        if fr is None:
            continue
        R = cc.quat_to_mat(fr[1])
        zy = R[1][2]
        if abs(zy) > 0.5 and zy * left < 0:
            warnings.append(f"joint '{h.get('id')}': the +Z axis of the wheel hinge points right, so a positive coordinate rolls the wheel backwards; "
                            "positive is forward rolling, the axis points left (spec 24.4)")


# ── aero ──────────────────────────────────────────────────────────────────────
def _aero(doc, warnings):
    co = (doc.get("aerodynamics") or {}).get("coefficients")
    wb = (doc.get("chassis") or {}).get("wheelbase")
    if not isinstance(co, dict) or not all(_num(co.get(k)) for k in ("Cl_front", "Cl_rear", "Cpm")) or not _num(wb):
        return
    ref = co.get("cpm_reference", "wheelbase_midpoint")
    if ref != "wheelbase_midpoint":
        return
    implied = (co["Cl_front"] - co["Cl_rear"]) / 2.0          # lift at the axles about the midpoint, divided by the wheelbase
    if abs(co["Cpm"] - implied) > AERO_TOL:
        warnings.append(f"aerodynamics.coefficients: Cpm {co['Cpm']:.4f} disagrees with Cl_front/Cl_rear, which imply {implied:.4f} about the "
                        "wheelbase midpoint; give one of them (Cl_front and Cl_rear win, spec 13.3)")


def check(doc):
    errors, warnings = [], []
    if not isinstance(doc, dict):
        return errors, warnings
    for fn in (_springs, _mass, _brakes, _bushings, _aero):
        try:
            fn(doc, errors, warnings) if fn in (_springs, _mass) else fn(doc, warnings)
        except Exception as e:                    # a malformed file is the schema's finding, not a crash here
            warnings.append(f"reference_check: {fn.__name__[1:]} could not be evaluated ({type(e).__name__}: {e})")
    try:
        _balance(doc, warnings)
    except Exception:
        pass
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
        print("  OK     reference pose, mass, brakes consistent")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
