#!/usr/bin/env python3
"""
SVJ <-> Project Chrono::Vehicle JSON converter (spec section 30).

    python tools/chrono_convert.py --to svj    vehicle.json  out.svj.json [--data-root DIR] [--report FILE]
    python tools/chrono_convert.py --to chrono vehicle.svj.json out_dir/   [--report FILE]

Chrono -> SVJ reads the top-level vehicle JSON (Template "WheeledVehicle") and the subsystem files it names
("Input File" entries are relative to the Chrono vehicle data directory, `--data-root`). Tyres and the powertrain are not
part of the vehicle JSON in Chrono; give them with `--tire`, `--engine` and `--transmission`. The result is one SVJ
file (ISO 8855) with the source, copyright holder and licence in `_metadata.data_origin`.

SVJ -> Chrono writes a folder of Chrono JSON files (vehicle, chassis, suspension per axle as the
GenericWheeledSuspension template, steering, wheel, brake, tyre, engine, transmission, driveline) for the subset of SVJ
that Chrono can express. Whatever cannot be expressed is listed in the report (printed, optionally written as JSON);
nothing is dropped silently.

Every item of the report has a status:  exact | converted | assumed | lost
  exact      same quantity, same units, same meaning
  converted  same physics in another form (frame shift, sign, units, a curve resampled, a template written as bodies)
  assumed    a value had to be chosen (always marked, and `_est` in the SVJ output)
  lost       the target format has no place for it (the item is named, with the reason)

Pure Python, no dependencies. Mirrored byte for byte as svj-py/svj/chronoconvert.py.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import hashlib
import os
import struct
import re
import sys

SVJ_VERSION = "0.111"
EPS = 1e-9

# ======================================================================================================================
# Small vector / matrix / quaternion helpers (Chrono quaternions are [w, x, y, z]; SVJ ones [x, y, z, w])
# ======================================================================================================================


def vadd(a, b): return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
def vsub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def vscale(a, s): return [a[0] * s, a[1] * s, a[2] * s]
def vdot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def vcross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def vnorm(a): return math.sqrt(vdot(a, a))


def vunit(a):
    n = vnorm(a)
    if n < EPS:
        raise ValueError("zero-length direction")
    return [a[0] / n, a[1] / n, a[2] / n]


def mmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mT(A): return [[A[j][i] for j in range(3)] for i in range(3)]
def mvec(A, v): return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]
def mcols(u, v, w): return [[u[0], v[0], w[0]], [u[1], v[1], w[1]], [u[2], v[2], w[2]]]
def mcol(A, j): return [A[0][j], A[1][j], A[2][j]]
def eye(): return [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]


def q_to_mat(q):
    """Rotation matrix of a Chrono quaternion [w, x, y, z] (normalised first)."""
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mat_to_q(R):
    """Chrono quaternion [w, x, y, z] of a rotation matrix, with w >= 0."""
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        w, x, y, z = (R[2][1] - R[1][2]) / s, 0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        w, x, y, z = (R[0][2] - R[2][0]) / s, (R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
        w, x, y, z = (R[1][0] - R[0][1]) / s, (R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    return [w, x, y, z]


def rot_x(a): c, s = math.cos(a), math.sin(a); return [[1.0, 0, 0], [0, c, -s], [0, s, c]]
def rot_y(a): c, s = math.cos(a), math.sin(a); return [[c, 0, s], [0, 1.0, 0], [-s, 0, c]]
def rot_z(a): c, s = math.cos(a), math.sin(a); return [[c, -s, 0], [s, c, 0], [0, 0, 1.0]]


def svj_quat(R):
    """SVJ orientation [x, y, z, w] of a rotation matrix."""
    w, x, y, z = mat_to_q(R)
    return [round(x, 9), round(y, 9), round(z, 9), round(w, 9)]


def mat_from_svj_quat(q):
    return q_to_mat([q[3], q[0], q[1], q[2]])


def mirror_rot(R):
    """Chrono's reflection of a body or joint frame to the right side (ChGenericWheeledSuspension::TransformRotation):
    the y components of the X and Z axes change sign and Y = Z x X (a proper rotation)."""
    u, w = mcol(R, 0), mcol(R, 2)
    u = [u[0], -u[1], u[2]]
    w = [w[0], -w[1], w[2]]
    return mcols(u, vcross(w, u), w)


def mirror_pt(p): return [p[0], -p[1], p[2]]


def inertia_matrix(moments, products):
    """Chrono inertia as a 3x3 matrix. `Products of Inertia` are the off-diagonal ENTRIES [I01, I02, I12]
    (ChBody::SetInertiaXY), that is minus the integrals of xy, xz, yz."""
    p = products or [0, 0, 0]
    return [[moments[0], p[0], p[1]], [p[0], moments[1], p[2]], [p[1], p[2], moments[2]]]


def inertia_to_svj(M):
    """SVJ inertia object (spec 7.1: tensor with -Ixy, -Ixz, -Iyz off the diagonal)."""
    r = lambda x: round(x, 9) + 0.0
    return {"Ixx": r(M[0][0]), "Iyy": r(M[1][1]), "Izz": r(M[2][2]),
            "Ixy": r(-M[0][1]), "Ixz": r(-M[0][2]), "Iyz": r(-M[1][2])}


def inertia_from_svj(d):
    if isinstance(d, list):
        return [list(map(float, row)) for row in d]
    return [[d["Ixx"], -d.get("Ixy", 0.0), -d.get("Ixz", 0.0)],
            [-d.get("Ixy", 0.0), d["Iyy"], -d.get("Iyz", 0.0)],
            [-d.get("Ixz", 0.0), -d.get("Iyz", 0.0), d["Izz"]]]


def rotate_inertia(M, R):
    return mmul(mmul(R, M), mT(R))


def parallel_axis(m, d):
    """m (|d|^2 1 - d d^T)"""
    s = vdot(d, d)
    return [[m * ((s if i == j else 0.0) - d[i] * d[j]) for j in range(3)] for i in range(3)]


def madd(A, B): return [[A[i][j] + B[i][j] for j in range(3)] for i in range(3)]


def r6(x): return round(float(x), 6) + 0.0
def rv(v): return [r6(c) for c in v]


# ======================================================================================================================
# Report
# ======================================================================================================================

STATUSES = ("exact", "converted", "assumed", "lost")


class Report:
    def __init__(self, direction):
        self.direction = direction
        self.items = []          # (status, area, text)
        self.checks = []         # verification notes
        self.sources = []        # files read

    def add(self, status, area, text):
        assert status in STATUSES, status
        item = (status, area, text)
        if item not in self.items:
            self.items.append(item)

    def lost(self): return [i for i in self.items if i[0] == "lost"]

    def to_json(self):
        return {"direction": self.direction, "sources": self.sources,
                "items": [{"status": s, "area": a, "text": t} for s, a, t in self.items], "checks": self.checks}

    def text(self, show=("lost", "assumed", "converted")):
        out = [f"Conversion report ({self.direction})"]
        counts = {s: sum(1 for i in self.items if i[0] == s) for s in STATUSES}
        out.append("  " + ", ".join(f"{n} {s}" for s, n in counts.items()))
        for s in show:
            rows = [i for i in self.items if i[0] == s]
            if rows:
                out.append(f"\n  {s.upper()} ({len(rows)})")
                out += [f"    [{a}] {t}" for _, a, t in rows]
        if self.checks:
            out.append("\n  CHECKS")
            out += [f"    {c}" for c in self.checks]
        return "\n".join(out)


class ConversionError(Exception):
    """The input cannot be converted at all (an unsupported template that carries the vehicle's physics)."""


# ======================================================================================================================
# Reading Chrono JSON
# ======================================================================================================================

def strip_json_comments(text):
    """Chrono reads its JSON with rapidjson kParseCommentsFlag: // and /* */ comments are allowed."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True; out.append(c)
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 1
        else:
            out.append(c)
        i += 1
    return "".join(out)


def load_chrono_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.loads(strip_json_comments(f.read()))


class ChronoData:
    """Resolves the `Input File` names of a Chrono vehicle file against the Chrono vehicle data directory."""

    def __init__(self, vehicle_file, root=None, report=None):
        self.vehicle_file = os.path.abspath(vehicle_file)
        self.report = report
        self.vehicle = load_chrono_json(self.vehicle_file)
        self.root = root
        self.cache = {}
        if root is None:
            self.root = self._guess_root()
        if report is not None:
            report.sources.append(self._rel(self.vehicle_file))

    def _first_ref(self):
        for key in ("Chassis",):
            if isinstance(self.vehicle.get(key), dict) and "Input File" in self.vehicle[key]:
                return self.vehicle[key]["Input File"]
        for ax in self.vehicle.get("Axles", []):
            if "Suspension Input File" in ax:
                return ax["Suspension Input File"]
        return None

    def _guess_root(self):
        ref = self._first_ref()
        d = os.path.dirname(self.vehicle_file)
        if ref:
            while True:
                if os.path.isfile(os.path.join(d, ref)):
                    return d
                parent = os.path.dirname(d)
                if parent == d:
                    break
                d = parent
        return os.path.dirname(self.vehicle_file)

    def _rel(self, p):
        try:
            return os.path.relpath(p, self.root).replace("\\", "/")
        except ValueError:
            return p

    def path(self, name):
        for base in (self.root, os.path.dirname(self.vehicle_file)):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
        raise ConversionError(f"Chrono input file not found: {name} (data root {self.root}); use --data-root")

    def read(self, name):
        if name not in self.cache:
            p = self.path(name)
            self.cache[name] = load_chrono_json(p)
            if self.report is not None:
                self.report.sources.append(name)
        return self.cache[name]


def vec(a): return [float(x) for x in a]


# ======================================================================================================================
# Chrono subsystem -> neutral model (everything in the Chrono vehicle frame, before the shift to the SVJ origin)
# ======================================================================================================================

class Body:
    def __init__(self, name, pos, R, mass, I, kind=""):
        self.name, self.pos, self.R, self.mass, self.I, self.kind = name, list(pos), R, mass, I, kind   # I in vehicle axes
        self.markers = {}
        self.x_derived = False


class Joint:
    def __init__(self, name, jtype, a, b, pos, R, bushing=None, x_derived=False):
        self.name, self.type, self.a, self.b, self.pos, self.R = name, jtype, a, b, list(pos), R
        self.bushing, self.x_derived = bushing, x_derived


class Element:
    def __init__(self, kind, name, a, b, p1, p2, data):
        self.kind, self.name, self.a, self.b, self.p1, self.p2, self.data = kind, name, a, b, list(p1), list(p2), data


class SuspSide:
    """One side of one axle: bodies, joints and elements in the Chrono vehicle frame."""

    def __init__(self, side):
        self.side = side
        self.bodies, self.joints, self.elements = [], [], []
        self.wheel = None              # dict: body name, pos, R (spindle frame), mass, I, upright name
        self.hub_attach = None


def _bushing_from_chrono(bd):
    if not bd:
        return None
    return {"K_lin": bd["Stiffness Linear"], "D_lin": bd["Damping Linear"], "K_rot": bd["Stiffness Rotational"],
            "D_rot": bd["Damping Rotational"], "dof": bd.get("DOF")}


# ---- spring / damper laws ---------------------------------------------------------------------------------------

def tsda_laws(d):
    """Decode a Chrono TSDA JSON object (ReadTSDAFunctorJSON) into a neutral law."""
    law = {"free_length": d.get("Free Length"), "preload": d.get("Preload", 0.0), "stops": None}
    if "Minimum Length" in d and "Maximum Length" in d:
        law["stops"] = [d["Minimum Length"], d["Maximum Length"]]
    if "Map Data" in d:
        law["map"] = {"deformation": d["Deformation"], "data": d["Map Data"]}
    if "Spring Coefficient" in d:
        law["k"] = d["Spring Coefficient"]
    if "Spring Curve Data" in d:
        law["k_curve"] = d["Spring Curve Data"]
    if "Damping Coefficient" in d:
        law["c"] = d["Damping Coefficient"]
        if "Degressivity Compression" in d and "Degressivity Expansion" in d:
            law["degr"] = [d["Degressivity Compression"], d["Degressivity Expansion"]]
    if "Damping Curve Data" in d:
        law["c_curve"] = d["Damping Curve Data"]
    return law


DEFAULT_STOP_CURVE = [[0.0, 0.0], [2e-3, 200.0], [4e-3, 400.0], [6e-3, 600.0], [8e-3, 800.0], [10e-3, 1000.0],
                      [20e-3, 2500.0], [30e-3, 4500.0], [40e-3, 7500.0], [50e-3, 12500.0], [60e-3, 125000.0]]


# ---- chassis ---------------------------------------------------------------------------------------------------

def read_chassis(d, rep):
    """Composite of the chassis `Components` (a Void component removes mass): mass, COM, inertia about COM, vehicle axes."""
    if d.get("Template") != "RigidChassis":
        raise ConversionError(f"chassis template {d.get('Template')!r} is not supported (RigidChassis only)")
    comps = d.get("Components", [])
    m_tot, mc = 0.0, [0.0, 0.0, 0.0]
    parts = []
    for c in comps:
        fr = c["Centroidal Frame"]
        R = q_to_mat(fr["Orientation"])
        m = c["Mass"] * (-1.0 if c.get("Void") else 1.0)
        I = rotate_inertia(inertia_matrix(c["Moments of Inertia"], c.get("Products of Inertia")), R)
        parts.append((m, vec(fr["Location"]), I))
        m_tot += m
        mc = vadd(mc, vscale(vec(fr["Location"]), m))
    com = vscale(mc, 1.0 / m_tot)
    I = [[0.0] * 3 for _ in range(3)]
    for m, p, Ii in parts:
        I = madd(I, madd([[m * 0 + Ii[i][j] * (1 if m > 0 else -1) for j in range(3)] for i in range(3)],
                         parallel_axis(m, vsub(p, com))))
    if len(comps) > 1:
        rep.add("converted", "chassis", f"{len(comps)} chassis components (incl. voids) merged into one composite body")
    if any(c.get("Void") for c in comps):
        rep.add("converted", "chassis", "void components subtracted from the chassis mass and inertia")
    out = {"mass": m_tot, "com": com, "I": I, "name": d.get("Name", "chassis")}
    for k in ("Driver Position", "Rear Connector Location"):
        if k in d:
            out[k] = d[k]
    return out


# ---- suspension templates --------------------------------------------------------------------------------------

def _frame_from_dirs(u, v, w): return mcols(u, v, w)


def _plane_frame(F, B, U):
    """Chrono ChDoubleWishbone arm body frame: x along F-B, z normal to the arm plane."""
    w = vunit(vcross(vsub(B, U), vsub(F, U)))
    u = vunit(vsub(F, B))
    v = vcross(w, u)
    return mcols(u, v, w)


def read_double_wishbone(d, rep, side_name, steering_ref):
    """ChDoubleWishbone / DoubleWishbone JSON -> SuspSide (suspension-local coordinates, left or right)."""
    left = side_name == "L"
    sg = -1.0 if left else 1.0
    P = lambda key: vec(key) if left else mirror_pt(vec(key))

    def pts(sub, key): return P(d[sub][key])

    camber = math.radians(d.get("Camber Angle (deg)", 0.0))
    toe = math.radians(d.get("Toe Angle (deg)", 0.0))
    vfi = d.get("Vehicle-Frame Inertia", False)
    S = SuspSide(side_name)
    sp_rot = mmul(rot_z(sg * toe), rot_x(sg * camber))

    def body_inertia(sub, R):
        M = inertia_matrix(d[sub]["Moments of Inertia"], d[sub].get("Products of Inertia"))
        return M if vfi else rotate_inertia(M, R)

    up_pos = pts("Upright", "COM")
    S.bodies.append(Body("upright", up_pos, eye(), d["Upright"]["Mass"], body_inertia("Upright", eye()), "upright"))
    F, B, U = (pts("Upper Control Arm", k) for k in ("Location Chassis Front", "Location Chassis Back", "Location Upright"))
    Ru = _plane_frame(F, B, U)
    S.bodies.append(Body("upper_wishbone", pts("Upper Control Arm", "COM"), Ru, d["Upper Control Arm"]["Mass"],
                         body_inertia("Upper Control Arm", Ru), "upper_wishbone"))
    S.joints += [Joint("ball_upper_wishbone_inboard_1", "spherical", "chassis", "upper_wishbone", F, eye()),
                 Joint("ball_upper_wishbone_inboard_2", "spherical", "chassis", "upper_wishbone", B, eye()),
                 Joint("ball_upper_wishbone_outboard", "spherical", "upper_wishbone", "upright", U, eye())]
    F, B, U = (pts("Lower Control Arm", k) for k in ("Location Chassis Front", "Location Chassis Back", "Location Upright"))
    Rl = _plane_frame(F, B, U)
    S.bodies.append(Body("lower_wishbone", pts("Lower Control Arm", "COM"), Rl, d["Lower Control Arm"]["Mass"],
                         body_inertia("Lower Control Arm", Rl), "lower_wishbone"))
    S.joints += [Joint("ball_lower_wishbone_inboard_1", "spherical", "chassis", "lower_wishbone", F, eye()),
                 Joint("ball_lower_wishbone_inboard_2", "spherical", "chassis", "lower_wishbone", B, eye()),
                 Joint("ball_lower_wishbone_outboard", "spherical", "lower_wishbone", "upright", U, eye())]
    for sub in ("Upper Control Arm", "Lower Control Arm"):
        if "Bushing Data" in d[sub]:
            rep.add("lost", "suspension", f"DoubleWishbone '{sub}' bushing data: the arm hinge is written as two spherical joints "
                                          "without compliance (Chrono's revolute bushing has no equivalent two-pickup form)")
    # tie rod
    Tc, Tu = pts("Tierod", "Location Chassis"), pts("Tierod", "Location Upright")
    ref = steering_ref or "chassis"
    if "Mass" in d["Tierod"]:
        com = vscale(vadd(Tc, Tu), 0.5)
        axis = vunit(vsub(Tu, Tc))
        Rt = _rod_frame(axis)
        S.bodies.append(Body("tie_rod", com, Rt, d["Tierod"]["Mass"],
                             rotate_inertia(inertia_matrix(d["Tierod"]["Inertia"], None), eye()), "tie_rod"))
    else:
        com = vscale(vadd(Tc, Tu), 0.5)
        t = Body("tie_rod", com, _rod_frame(vunit(vsub(Tu, Tc))), 0.0, [[0.0] * 3 for _ in range(3)], "tie_rod")
        t.x_derived = True
        S.bodies.append(t)
        rep.add("converted", "suspension", "DoubleWishbone tie rod without mass (a Chrono distance constraint) is written as a massless "
                                           "rod body with a spherical joint at each end (x_derived)")
    S.joints += [Joint("ball_tie_rod_inboard", "spherical", ref, "tie_rod", Tc, eye()),
                 Joint("ball_tie_rod_outboard", "spherical", "tie_rod", "upright", Tu, eye())]
    # spring and shock between chassis and lower arm
    for key, nm in (("Spring", "spring"), ("Shock", "damper")):
        e = d[key]
        S.elements.append(Element(nm, nm, "chassis", "lower_wishbone", P(e["Location Chassis"]), P(e["Location Arm"]),
                                  tsda_laws(e)))
    # spindle
    sp = d["Spindle"]
    S.wheel = {"pos": P(sp["COM"]), "R": sp_rot, "mass": sp["Mass"], "inertia": sp["Inertia"], "radius": sp["Radius"],
               "width": sp["Width"], "upright": "upright", "axle_inertia": d.get("Axle", {}).get("Inertia", 0.0)}
    S.joints.append(Joint("hinge_wheel", "revolute", "upright", "wheel", P(sp["COM"]),
                          mmul(sp_rot, rot_x(-math.pi / 2))))
    return S


def _rod_frame(axis):
    """A frame with z along a rod (inertia of a rod body is given about its own axes in Chrono: x,y transverse)."""
    z = vunit(axis)
    helper = [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0]
    x = vunit(vcross(helper, z))
    y = vcross(z, x)
    return mcols(x, y, z)


JOINT_TYPES = {"Lock": "fixed", "Revolute": "revolute", "Spherical": "spherical", "Prismatic": "translational",
               "Cylindrical": "cylindrical", "Universal": "universal", "Point Line": None, "Point Plane": None}


def read_generic_suspension(d, rep, side_name, steering_ref):
    """ChGenericWheeledSuspension JSON (bodies, joints, distance constraints, TSDAs, RSDAs) -> SuspSide."""
    left = side_name == "L"
    sidei = "Left" if left else "Right"
    S = SuspSide(side_name)
    camber = math.radians(d.get("Camber Angle (deg)", 0.0))
    toe = math.radians(d.get("Toe Angle (deg)", 0.0))
    sg = -1.0 if left else 1.0
    sp_rot = mmul(rot_z(sg * toe), rot_x(sg * camber))
    P = lambda p: vec(p) if left else mirror_pt(vec(p))

    def ident(x):
        if isinstance(x, list):
            name, side = x[0], x[1]
        else:
            name, side = x, None
        if name == "Chassis" or name == "Subchassis":
            return "chassis"
        if name == "Steering":
            return steering_ref or "chassis"
        suffix = "" if side is None else {"Left": "l", "Right": "r"}[side]
        return _gname(name) + (("_" + suffix) if suffix else "")

    mirrored_names = {}
    for b in d.get("Bodies", []):
        mirrored_names[b["Name"]] = b["Mirrored"]
        pos = P(b["Position"]) if b["Mirrored"] or left else vec(b["Position"])
        R = q_to_mat(b["Rotation"])
        if b["Mirrored"] and not left:
            R = mirror_rot(R)
        M = inertia_matrix(b["Moments of Inertia"], b.get("Products of Inertia"))
        M = M if d.get("Vehicle-Frame Inertia") else rotate_inertia(M, R)
        S.bodies.append(Body(_gname(b["Name"]), pos, R, b["Mass"], M, b["Name"]))
    for j in d.get("Joints", []):
        jt = JOINT_TYPES.get(j["Type"])
        if jt is None:
            rep.add("lost", "suspension", f"generic suspension joint type '{j['Type']}' ({j['Name']}) has no SVJ joint type")
            continue
        pos = P(j["Position"]) if j["Mirrored"] or left else vec(j["Position"])
        R = q_to_mat(j["Rotation"])
        if j["Mirrored"] and not left:
            R = mirror_rot(R)
        a, b = ident(j["Body1"]), ident(j["Body2"])
        S.joints.append(Joint(_gname(j["Name"]), jt, a, b, pos, R, _bushing_from_chrono(j.get("Bushing Data"))))
    for k in d.get("Distance Constraints", []):
        p1, p2 = P(k["Point1"]), P(k["Point2"])
        com = vscale(vadd(p1, p2), 0.5)
        nm = _gname(k["Name"])
        rod = Body(nm, com, _rod_frame(vunit(vsub(p2, p1))), 0.0, [[0.0] * 3 for _ in range(3)], "rod")
        rod.x_derived = True
        S.bodies.append(rod)
        S.joints += [Joint("ball_" + nm + "_1", "spherical", ident(k["Body1"]), nm, p1, eye()),
                     Joint("ball_" + nm + "_2", "spherical", nm, ident(k["Body2"]), p2, eye())]
        rep.add("converted", "suspension", "generic suspension distance constraint -> massless rod body with two spherical joints")
    for t in d.get("TSDAs", []):
        S.elements.append(Element("tsda", _gname(t["Name"]), ident(t["Body1"]), ident(t["Body2"]), P(t["Point1"]), P(t["Point2"]),
                                  tsda_laws(t)))
    for r in d.get("RSDAs", []):
        S.elements.append(Element("rsda", _gname(r["Name"]), ident(r["Body1"]), ident(r["Body2"]),
                                  P(r["Position"]), P(r["Axis"]), {"rsda": r}))
    sp = d["Spindle"]
    att = ident(sp["Attachment Body"])
    S.wheel = {"pos": P(sp["COM"]), "R": sp_rot, "mass": sp["Mass"], "inertia": sp["Inertia"], "radius": sp["Radius"],
               "width": sp["Width"], "upright": att, "axle_inertia": d.get("Axle", {}).get("Inertia", 0.0)}
    S.joints.append(Joint("hinge_wheel", "revolute", att, "wheel", P(sp["COM"]), mmul(sp_rot, rot_x(-math.pi / 2))))
    return S


def _gname(name):
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


SUSPENSION_READERS = {"DoubleWishbone": read_double_wishbone, "GenericWheeledSuspension": read_generic_suspension}


# ---- steering ------------------------------------------------------------------------------------------------------

class SteerSys:
    def __init__(self):
        self.bodies, self.joints = [], []
        self.ref = None                 # body that the tie rods attach to
        self.kind = None
        self.max_angle = 0.0            # rad: the Chrono steering input +-1 (pinion or sector angle)
        self.pinion_radius = None
        self.gear_joint = None          # name of the joint that carries the steering input
        self.pivot = None
        self.rack_len = None
        self.axis = None
        self.tip = None
        self.name = None


def _axis_frame(z, towards):
    """Frame with z = the given axis and x towards a point (made orthogonal to z)."""
    z = vunit(z)
    x = vsub(towards, vscale(z, vdot(towards, z)))
    if vnorm(x) < 1e-9:
        x = [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0]
        x = vsub(x, vscale(z, vdot(x, z)))
    x = vunit(x)
    return mcols(x, vcross(z, x), z)


def read_steering(d, loc, rotq, rep):
    R = q_to_mat(rotq)
    P = lambda p: vadd(loc, mvec(R, vec(p)))
    S = SteerSys()
    S.name = d.get("Name")
    t = d.get("Template")
    if t == "RackPinion":
        sl = d["Steering Link"]
        com = sl["COM"] if isinstance(sl["COM"], (int, float)) else sl["COM"][1]
        pos = P([0, com, 0])
        S.bodies.append(Body("rack", pos, R, sl["Mass"], rotate_inertia(inertia_matrix(sl["Inertia"], None), R), "rack"))
        S.joints.append(Joint("slide_rack", "translational", "chassis", "rack", pos, mmul(R, rot_x(-math.pi / 2))))
        S.ref, S.kind = "rack", "rack_and_pinion"
        S.pinion_radius = d["Pinion"]["Radius"]
        S.max_angle = math.radians(d["Pinion"]["Maximum Angle (deg)"])
        S.gear_joint = "slide_rack"
        S.pivot = pos
        S.rack_len = sl.get("Length")
        S.axis = mcol(R, 1)
        return S
    if t == "PitmanArm":
        link, arm = d["Steering Link"], d["Pitman Arm"]
        vfi = d.get("Vehicle-Frame Inertia", False)

        def mk(blk):
            M = inertia_matrix(blk["Moments of Inertia"], blk.get("Products of Inertia"))
            return M if vfi else rotate_inertia(M, R)
        S.bodies.append(Body("center_link", P(link["COM"]), R, link["Mass"], mk(link), "center_link"))
        S.bodies.append(Body("pitman_arm", P(arm["COM"]), R, arm["Mass"], mk(arm), "pitman_arm"))
        rev = d["Revolute Joint"]
        zdir = mvec(R, vunit(vec(rev["Direction"])))
        Rrev = _axis_frame(zdir, vsub(P(arm["COM"]), P(rev["Location"])))
        S.joints.append(Joint("hinge_sector", "revolute", "chassis", "pitman_arm", P(rev["Location"]), Rrev))
        uj = d["Universal Joint"]
        xa, ya = mvec(R, vunit(vec(uj["Direction Arm"]))), mvec(R, vunit(vec(uj["Direction Link"])))
        S.joints.append(Joint("universal_pitman_tip", "universal", "pitman_arm", "center_link", P(uj["Location"]),
                              mcols(xa, ya, vcross(xa, ya))))
        rs = d["Revolute-Spherical Joint"]
        rc, rl = P(rs["Location Chassis"]), P(rs["Location Link"])
        zr = mvec(R, vunit(vec(rs["Direction"])))
        Ri = _axis_frame(zr, vsub(rl, rc))
        idler = Body("idler_arm", vscale(vadd(rc, rl), 0.5), Ri, 0.0, [[0.0] * 3 for _ in range(3)], "idler_arm")
        idler.x_derived = True
        S.bodies.append(idler)
        S.joints.append(Joint("hinge_idler", "revolute", "chassis", "idler_arm", rc, Ri))
        S.joints.append(Joint("ball_idler_link", "spherical", "idler_arm", "center_link", rl, eye()))
        rep.add("converted", "steering", "Pitman arm revolute-spherical joint -> massless idler arm body (revolute on the chassis, spherical on the link)")
        S.ref, S.kind = "center_link", "recirculating_ball"
        S.max_angle = math.radians(rev["Maximum Angle (deg)"])
        S.gear_joint = "hinge_sector"
        S.pivot = P(rev["Location"])
        S.tip = P(uj["Location"])
        S.axis = zdir
        return S
    raise ConversionError(f"steering template {t!r} is not supported (RackPinion, PitmanArm)")


# ---- naming ----------------------------------------------------------------------------------------------------------

def station_ids(n_axles):
    """SVJ station names (spec 23.1): FL FR RL RR for two axles, A1L A1R A2L ... otherwise."""
    if n_axles == 2:
        return [("FL", "FR"), ("RL", "RR")]
    return [(f"A{i + 1}L", f"A{i + 1}R") for i in range(n_axles)]


# ---- the Chrono vehicle -> SVJ document ----------------------------------------------------------------------------

def _guess_tire(data, rep):
    """Pick a tyre file of the same model family as the vehicle (first folder under the data root): Pac02, then TMeasy, Fiala, Rigid."""
    rel = _relto(data.vehicle_file, data.root)
    top = rel.split("/")[0]
    found = {}
    for dp, _, fns in os.walk(os.path.join(data.root, top)):
        for fn in sorted(fns):
            if fn.lower().endswith(".json") and "tire" in fn.lower():
                try:
                    dj = load_chrono_json(os.path.join(dp, fn))
                    t = dj.get("Template")
                    if t == "Pac02Tire" and not (dj.get("TIR Specification File") and os.path.exists(os.path.join(data.root, dj["TIR Specification File"]))):
                        continue                                  # the .tir file is not in the distribution
                except Exception:
                    continue
                if t in ("Pac02Tire", "TMeasyTire", "FialaTire", "RigidTire"):
                    found.setdefault(t, _relto(os.path.join(dp, fn), data.root))
    for t in ("Pac02Tire", "TMeasyTire", "FialaTire", "RigidTire"):
        if t in found:
            rep.add("assumed", "tyre", f"no --tire given: {found[t]} ({t}) taken from the same model folder; the vehicle file does not name its tyre")
            return found[t]
    if top != "generic":                                   # fall back on the generic folder's tyres
        for dp, _, fns in os.walk(os.path.join(data.root, "generic", "tire")):
            for fn in sorted(fns):
                if fn.endswith("FialaTire.json"):
                    rep.add("assumed", "tyre", "no tyre in the model folder: the generic Fiala tyre is used")
                    return "generic/tire/" + fn
    return None


def _relto(path, root):
    """Path relative to root with forward slashes; the file name alone when it lies on another drive."""
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return os.path.basename(path)


def chrono_to_svj(vehicle_file, data_root=None, tire_file=None, engine_file=None, transmission_file=None, rep=None, camber="physical", origin="chrono", mesh_dir=None):
    rep = rep or Report("chrono->svj")
    rep.origin = origin
    rep.mesh_dir = mesh_dir
    data = ChronoData(vehicle_file, data_root, rep)
    V = data.vehicle
    top = _relto(data.vehicle_file, data.root).split("/")[0]
    rep.asset_name = "chrono_" + re.sub(r"[^a-z0-9]+", "_", top.lower()).strip("_")
    if V.get("Template") != "WheeledVehicle":
        raise ConversionError(f"vehicle template {V.get('Template')!r} not supported (WheeledVehicle only)")
    for key in ("Rear Chassis", "Subchassis"):
        if V.get(key):
            raise ConversionError(f"'{key}' is not supported (articulated / subchassis vehicles)")
    chassis = read_chassis(data.read(V["Chassis"]["Input File"]), rep)

    steers, steer_raw = [], []
    rep.steer_raw = steer_raw
    for s in V.get("Steering Subsystems", []):
        sd = data.read(s["Input File"])
        steers.append(read_steering(sd, vec(s["Location"]), s["Orientation"], rep))
        steer_raw.append({"file": s["Input File"], "template": sd.get("Template"), "raw": sd, "location": vec(s["Location"]),
                          "orientation": list(s["Orientation"])})
    axles = V["Axles"]
    n_ax = len(axles)
    ids = station_ids(n_ax)
    order = sorted(range(n_ax), key=lambda i: -vec(axles[i]["Suspension Location"])[0])
    if order != list(range(n_ax)):
        rep.add("converted", "axles", "axles renumbered front to back (SVJ A1 is the front axle)")
    ax_rank = {ai: r for r, ai in enumerate(order)}

    if not tire_file:
        tire_file = _guess_tire(data, rep)
    tire = read_tire(data, tire_file, rep, camber) if tire_file else None
    if tire is None:
        raise ConversionError("a tyre file is required (--tire): the ground plane of the SVJ frame is placed from the tyre radius")

    stations = []
    for ai, ax in enumerate(axles):
        if "Wheel Separation" in ax:
            raise ConversionError("axles with dual wheels ('Wheel Separation') are not supported yet")
        sd = data.read(ax["Suspension Input File"])
        tpl = sd.get("Template")
        if tpl not in SUSPENSION_READERS:
            raise ConversionError(f"suspension template {tpl!r} (axle {ai + 1}) is not supported; supported: "
                                  + ", ".join(sorted(SUSPENSION_READERS)))
        loc = vec(ax["Suspension Location"])
        st_idx = ax.get("Steering Index", -1)
        steer = steers[st_idx] if st_idx is not None and st_idx >= 0 else None
        if ax.get("Antirollbar Input File"):
            rep.add("lost", "suspension", f"axle {ai + 1}: anti-roll bar '{ax['Antirollbar Input File']}' is not converted")
        for sidec in ("L", "R"):
            S = SUSPENSION_READERS[tpl](sd, rep, sidec, steer.ref if steer else None)
            for b in S.bodies:
                b.pos = vadd(b.pos, loc)
            for j in S.joints:
                j.pos = vadd(j.pos, loc)
            for e in S.elements:
                e.p1 = vadd(e.p1, loc)
                if e.kind != "rsda":
                    e.p2 = vadd(e.p2, loc)
            S.wheel["pos"] = vadd(S.wheel["pos"], loc)
            stations.append({"axle": ai, "side": sidec, "susp": S, "tpl": tpl, "steer": steer, "ax": ax, "sd": sd,
                             "id": ids[ax_rank[ai]][0 if sidec == "L" else 1]})
        rep.add("exact", "suspension", f"axle {ai + 1}: {tpl} hardpoints, masses and inertias")
    return _assemble(data, V, chassis, steers, stations, tire, engine_file, transmission_file, rep)


# ---- tyres ---------------------------------------------------------------------------------------------------------

def parse_tir(text):
    """ADAMS/TYDEX .tir file -> {SECTION: {NAME: value}} (numbers become floats, quoted strings stay strings)."""
    out, sec = {}, None
    for raw in text.splitlines():
        line = raw.split("$")[0].strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("["):
            sec = line.strip("[]").strip().upper()
            out[sec] = {}
            continue
        if "=" in line and sec:
            k, v = [s.strip() for s in line.split("=", 1)]
            v = v.strip()
            if v.startswith("'"):
                out[sec][k.upper()] = v.strip("'")
            else:
                try:
                    out[sec][k.upper()] = float(v.split()[0])
                except ValueError:
                    out[sec][k.upper()] = v
    return out


_PJ_GROUPS = (("lateral", ("PCY", "PDY", "PEY", "PKY", "PHY", "PVY", "PPY")),
              ("longitudinal", ("PCX", "PDX", "PEX", "PKX", "PHX", "PVX", "PPX")),
              ("aligning", ("QBZ", "QCZ", "QDZ", "QEZ", "QHZ", "SSZ", "PPZ")),
              ("overturning", ("QSX", "QPX")),
              ("rolling_resistance", ("QSY",)),
              ("combined", ("RBX", "RCX", "REX", "RHX", "RBY", "RCY", "REY", "RHY", "RVY", "ROX")))


def tir_name_to_svj(name):
    """PCY1 -> pCy1, QBZ1 -> qBz1, SSZ1 -> ssz1, QSX1 -> qsx1 (the naming of spec 11.6.1)."""
    stem = name[:3]
    if stem in ("SSZ", "QSX", "QSY"):
        return name.lower()
    return name[0].lower() + name[1].upper() + name[2].lower() + name[3:]


def pac02_to_set(tir, rep, camber="physical"):
    """Chrono Pac02 .tir coefficients -> SVJ tyre set (ISO 8855 coefficients)."""
    sets = {}
    used = set()
    pj = {g: {} for g, _ in _PJ_GROUPS}
    scaling = {}
    for sec, vals in tir.items():
        for k, v in vals.items():
            if not isinstance(v, float):
                continue
            if sec == "SCALING_COEFFICIENTS":
                scaling[k] = v
                continue
            for g, stems in _PJ_GROUPS:
                if k[:3] in stems and k[3:].isdigit():
                    pj[g][tir_name_to_svj(k)] = v
                    used.add(k)
                    break
    pj = {g: c for g, c in pj.items() if c}
    lat = pj.get("lateral")
    if lat is not None:
        # Chrono Pac02 (ChPac02Tire.cpp): mu_y ~ (1 + PDY3 gamma^2) where MF 5.2 / 6.2 write (1 - pDy3 gamma^2), and the cornering stiffness
        # is Ky = PKY1 FNOMIN sin(2 atan(Fz / (PKY2 Fz0'))) with the factor 2 fixed in code (no PKY4, no PKY5).
        if "pDy3" in lat:
            lat["pDy3"] = -lat["pDy3"]
            rep.add("converted", "tyre", "Pac02 PDY3 enters as (1 + PDY3 gamma^2) in Chrono, (1 - pDy3 gamma^2) in the SVJ evaluator: pDy3 = -PDY3")
        lat.setdefault("pKy4", 2.0)
        lat.setdefault("pKy5", 0.0)
        rep.add("assumed", "tyre", "Pac02 has no PKY4 / PKY5: pKy4 = 2 and pKy5 = 0 reproduce Chrono's sin(2 atan(Fz / (PKY2 Fz0'))) cornering stiffness")
    out = {"model": "MF62" if str(tir.get("MODEL", {}).get("PROPERTY_FILE_FORMAT", "")).upper().startswith("MF_") else "MF52"}
    out.update(pj)
    if scaling:
        out["scaling"] = {k: v for k, v in scaling.items() if k in SCALING_NAMES}
    out["axis_system"] = "SAE_J670"            # Chrono evaluates SAE/Pacejka signs and converts its outputs to ISO
    unused = sorted(k for sec, vals in tir.items() for k, v in vals.items()
                    if isinstance(v, float) and sec != "SCALING_COEFFICIENTS" and k not in used
                    and sec in ("LONGITUDINAL_COEFFICIENTS", "LATERAL_COEFFICIENTS", "ALIGNING_COEFFICIENTS", "OVERTURNING_COEFFICIENTS", "ROLLING_COEFFICIENTS"))
    if unused:
        rep.add("lost", "tyre", f"Pac02 coefficients without an SVJ group, kept in x_chrono.tir: {', '.join(unused)}")
    return out, unused


SCALING_NAMES = ("LFZO", "LCX", "LMUX", "LEX", "LKX", "LHX", "LVX", "LXAL", "LCY", "LMUY", "LEY", "LKY", "LHY", "LVY", "LKYC",
                 "LYKA", "LVYKA", "LTR", "LRES", "LKZC", "LS", "LMY")


def _tire_pacejka_iso(pj, camber):
    """SAE-sign Pacejka block -> ISO 8855 (spec 11.6, tire_model.to_iso_set); `camber` is 'faithful' (keep Chrono's gamma
    sign) or 'physical' (also mirror_camber)."""
    try:
        from svj import tiremodel as tm
    except ImportError:
        import tire_model as tm
    out = tm.to_iso_set(pj)
    if camber == "physical":
        out = tm.mirror_camber(out)
    return out


def read_tire(data, name, rep, camber="physical"):
    d = data.read(name)
    data.tire_json = d
    t = d.get("Template")
    T = {"template": t, "name": d.get("Name"), "file": name, "raw": d}
    if t == "RigidTire":
        T.update(radius=d["Radius"], width=d["Width"], mass=d["Mass"], inertia=d["Inertia"], kz=None, rim_radius=None)
        T["set"] = {"description": f"{d.get('Name')} (Chrono {t})", "source": "estimated",
                    "dimensions": {"overall_diameter": 2 * d["Radius"], "section_width": d["Width"]},
                    "construction": {"mass": d["Mass"]}}
        cm = d.get("Contact Material", {})
        if "Coefficients" in cm and "Normal Stiffness" in cm["Coefficients"]:
            T["set"]["construction"]["vertical_stiffness"] = cm["Coefficients"]["Normal Stiffness"]
            T["set"]["construction"]["vertical_damping"] = cm["Coefficients"].get("Normal Damping", 0.0)
        rep.add("lost", "tyre", "RigidTire has no slip-force law in SVJ (friction, restitution, contact material stay in x_chrono.tires)")
        T["chrono_keep"] = {"friction": cm.get("Coefficient of Friction"), "restitution": cm.get("Coefficient of Restitution"),
                            "contact_material": cm}
    elif t == "TMeasyTire":
        de = d["Design"]
        T.update(radius=de["Unloaded Radius [m]"], width=de["Width [m]"], mass=de["Mass [kg]"], inertia=de["Inertia [kg.m2]"],
                 rim_radius=de["Rim Radius [m]"], kz=None)
        s = {"description": f"{d.get('Name')} (Chrono {t})", "source": "estimated",
             "dimensions": {"overall_diameter": 2 * T["radius"], "section_width": T["width"],
                            "aspect_ratio": round((T["radius"] - T["rim_radius"]) / T["width"], 6)},
             "construction": {"mass": T["mass"]}, "rim": {"diameter": 2 * T["rim_radius"]}}
        if "Parameters" in d:
            P = d["Parameters"]
            v = P["Vertical"]
            pn = v["Nominal Vertical Force [N]"]
            if "Vertical Tire Stiffness [N/m]" in v:
                T["kz"] = v["Vertical Tire Stiffness [N/m]"]
                s["construction"]["vertical_stiffness"] = T["kz"]
            s["construction"]["vertical_damping"] = v["Tire Vertical Damping [Ns/m]"]
            L, X, A = P["Lateral"], P["Longitudinal"], P["Aligning"]
            s["tmeasy"] = {"Fz0": pn,
                           "dFy0": L["Initial Slopes dFy/dsy [N]"][0], "Fy_max": L["Maximum Fy Load [N]"][0],
                           "alpha_max": L["Slip sy at Maximum Fy"][0], "Fy_slide": L["Sliding Fy Load [N]"][0],
                           "alpha_slide": L["Slip sy where sliding begins"][0],
                           "dFx0": X["Initial Slopes dFx/dsx [N]"][0], "Fx_max": X["Maximum Fx Load [N]"][0],
                           "kappa_max": X["Slip sx at Maximum Fx"][0], "Fx_slide": X["Sliding Fx Load [N]"][0],
                           "kappa_slide": X["Slip sx where sliding begins"][0],
                           "dFy0_dFz": (L["Initial Slopes dFy/dsy [N]"][1] - L["Initial Slopes dFy/dsy [N]"][0]) / pn,
                           "Fy_max_dFz": (L["Maximum Fy Load [N]"][1] - L["Maximum Fy Load [N]"][0]) / pn,
                           "Fz_dependency": "linear"}
            rep.add("converted", "tyre", "TMeasy parameters given at the nominal load and twice the nominal load: SVJ keeps the values at the nominal "
                                         "load and the slope to 2 Fz as dFy0_dFz, Fy_max_dFz; the other 2 Fz values and the aligning parameters stay in x_chrono.tires")
        else:
            rep.add("lost", "tyre", "TMeasy tyre specified by load index / bearing capacity: Chrono derives its force parameters from the load "
                                    "index at run time (GuessTruck80Par / GuessPassCar70Par); the SVJ tmeasy block is not generated, the "
                                    "specification is kept in x_chrono.tires")
        T["set"] = s
        T["chrono_keep"] = {"friction": d.get("Coefficient of Friction"), "rolling_resistance": d.get("Rolling Resistance Coefficient")}
    elif t == "FialaTire":
        fp = d["Fiala Parameters"]
        T.update(radius=fp["Unloaded Radius"], width=fp["Width"], mass=d["Mass"], inertia=d["Inertia"], rim_radius=None,
                 kz=fp.get("Vertical Stiffness"), kz_curve=fp.get("Vertical Curve Data"))
        s = {"description": f"{d.get('Name')} (Chrono {t})", "source": "estimated",
             "dimensions": {"overall_diameter": 2 * T["radius"], "section_width": T["width"]},
             "construction": {"mass": d["Mass"], "vertical_stiffness": T["kz"], "vertical_damping": fp.get("Vertical Damping")},
             "relaxation": {"lateral": fp.get("Y Relaxation Length"), "longitudinal": fp.get("X Relaxation Length")}}
        s["relaxation"] = {k: v for k, v in s["relaxation"].items() if v is not None}
        T["set"] = s
        T["chrono_keep"] = {"friction": d.get("Coefficient of Friction"), "fiala": {k: fp[k] for k in ("CSLIP", "CALPHA", "UMIN", "UMAX", "Rolling Resistance") if k in fp}}
        rep.add("lost", "tyre", "Fiala slip stiffness, saturation and friction (CSLIP, CALPHA, UMIN, UMAX): no SVJ force model equivalent "
                                "(brush parameters are not derived from them); kept in x_chrono.tires")
    elif t == "Pac02Tire":
        tir = parse_tir(open(data.path(d["TIR Specification File"]), encoding="utf-8", errors="replace").read())
        data.report.sources.append(d["TIR Specification File"])
        dim, vert = tir["DIMENSION"], tir["VERTICAL"]
        sc = tir.get("SCALING_COEFFICIENTS", {})
        T.update(radius=dim["UNLOADED_RADIUS"], width=dim["WIDTH"], mass=d["Mass"], inertia=d["Inertia"],
                 rim_radius=dim.get("RIM_RADIUS"), kz=vert["VERTICAL_STIFFNESS"] * sc.get("LCZ", 1.0))
        pj, unused = pac02_to_set(tir, rep, camber)
        pj = _tire_pacejka_iso(pj, camber)
        s = {"description": f"{d.get('Name')} (Chrono {t})", "source": "estimated",
             "dimensions": {"overall_diameter": 2 * T["radius"], "section_width": T["width"],
                            "aspect_ratio": dim.get("ASPECT_RATIO")},
             "rim": {"diameter": 2 * dim["RIM_RADIUS"]} if "RIM_RADIUS" in dim else {},
             "construction": {"mass": d["Mass"], "vertical_stiffness": T["kz"], "vertical_damping": vert.get("VERTICAL_DAMPING")},
             "reference": {"load": vert.get("FNOMIN"), "pressure": tir.get("TIRE_CONDITIONS", {}).get("IP_NOM"),
                           "speed": tir.get("MODEL", {}).get("LONGVL")},
             "pressure": tir.get("TIRE_CONDITIONS", {}).get("IP"),
             "pacejka": pj}
        s["rim"] = {k: v for k, v in s["rim"].items() if v is not None}
        s["reference"] = {k: v for k, v in s["reference"].items() if v is not None}
        s["construction"] = {k: v for k, v in s["construction"].items() if v is not None}
        s["dimensions"] = {k: v for k, v in s["dimensions"].items() if v is not None}
        T["set"] = {k: v for k, v in s.items() if v not in (None, {})}
        T["chrono_keep"] = {"friction": d.get("Coefficient of Friction"), "tir": d["TIR Specification File"],
                            "tyreside": tir.get("MODEL", {}).get("TYRESIDE"), "unused_coefficients": unused,
                            "use_mode": tir.get("MODEL", {}).get("USE_MODE")}
        rep.add("converted", "tyre", "Pac02 coefficients are SAE/Pacejka signs (Chrono converts its outputs to ISO): rewritten with "
                                     "tire_model.to_iso_set and declared ISO_8855")
        rep.add("assumed", "tyre", "camber: " + ("mirror_camber applied. Chrono feeds an ISO-signed inclination angle (a lean to the right is positive) into its SAE-sign "
                                              "Pac02 formulas; evaluated literally that pushes a tyre leaning right towards the LEFT, which fails the physical sign oracle "
                                              "(svj-py/tests/test_tyre_sign_oracle.py). The set is mirrored so that the SVJ evaluator obeys the oracle; Chrono's own "
                                              "behaviour at camber was read from ChPac02Tire.cpp / ChTire.cpp and not run (no PyChrono). Use --tyre-camber faithful to keep Chrono's literal sign"
                                              if camber == "physical" else
                                              "left as Chrono evaluates it (literal sign); this fails the physical sign oracle for camber thrust"))
        rep.add("lost", "tyre", f"Pac02 TYRESIDE={tir.get('MODEL', {}).get('TYRESIDE')}: Chrono flips the asymmetry terms (PHY1, PVY1, RHX1, ...) "
                                "on the other side; SVJ has one set per tyre set, the right-side mirroring is not represented")
    else:
        raise ConversionError(f"tyre template {t!r} is not supported (RigidTire, TMeasyTire, FialaTire, Pac02Tire)")
    return T


def tire_deflection(T, fz):
    if not fz or fz <= 0:
        return 0.0
    if T.get("kz_curve"):
        pts = sorted(T["kz_curve"])
        for (d0, f0), (d1, f1) in zip(pts, pts[1:]):
            if f0 <= fz <= f1:
                return d0 + (d1 - d0) * (fz - f0) / (f1 - f0)
        return pts[-1][0] + (fz - pts[-1][1]) / ((pts[-1][1] - pts[-2][1]) / (pts[-1][0] - pts[-2][0]))
    kz = T.get("kz")
    return fz / kz if kz else 0.0


# ---- assembling the SVJ document -------------------------------------------------------------------------------------

G = 9.81
LICENSE_TEXT = "BSD-3-Clause"
COPYRIGHT = "Copyright (c) 2016, Project Chrono Development Team. All rights reserved."
CHRONO_URL = "https://projectchrono.org"


def _min_norm_loads(xs, mass, x_cg):
    """Axle loads that sum to the weight and balance about x_cg, with the smallest sum of squares (exact for two axles)."""
    n = len(xs)
    W = mass * G
    if n == 1:
        return [W]
    xm = sum(xs) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    if sxx < 1e-12:
        return [W / n] * n
    # F_i = a + b (x_i - xm): sum F = W -> a = W / n;  sum F x_i = W x_cg -> b = (W x_cg - W xm) / sxx
    a, b = W / n, W * (x_cg - xm) / sxx
    return [a + b * (x - xm) for x in xs]


def _frame_dict(pos, R, shift):
    return {"position": rv(vsub(pos, shift)), "orientation": svj_quat(R)}


def _bushing_to_svj(bd, jtype, rep, name):
    if not bd:
        return None
    b = {}
    kl, kr = bd["K_lin"], bd["K_rot"]
    for ax in "xyz":
        b["rate_" + ax] = kl
        b["damping_" + ax] = bd["D_lin"]
    for ax in ("rx", "ry"):
        b["rate_" + ax] = kr
    b["rate_rz"] = kr
    dof = bd.get("dof")
    if dof:
        if jtype == "revolute":
            if dof["Stiffness Rotational"] > 0:
                b["rate_rz"] = dof["Stiffness Rotational"]
            else:
                b.pop("rate_rz")
        elif jtype in ("translational", "cylindrical") and dof["Stiffness Linear"] > 0:
            b["rate_z"] = dof["Stiffness Linear"]
        elif jtype in ("translational", "cylindrical"):
            b.pop("rate_z")
    elif jtype == "revolute":
        b.pop("rate_rz")
    b = {k: v for k, v in b.items() if v}
    if any(bd.get(k) for k in ("D_rot",)):
        rep.add("lost", "suspension", f"bushing rotational damping of {name} (SVJ bushing has translational damping only)")
    return b


def _spring_constraints(cid, e, shift, rep, a, b):
    """Chrono TSDA spring law -> SVJ spring constraint(s) (+ the stop spring)."""
    law = e.data
    out = []
    L_ref = vnorm(vsub(e.p1, e.p2))
    L0 = law.get("free_length")
    base = {"type": "spring", "body_a": a, "frame_a": {"position": rv(vsub(e.p1, shift)), "orientation": [0, 0, 0, 1]},
            "body_b": b, "frame_b": {"position": rv(vsub(e.p2, shift)), "orientation": [0, 0, 0, 1]}}
    has_k = "k" in law or "k_curve" in law
    if "map" in law:
        rep.add("lost", "suspension", f"{cid}: map spring-damper (force against deflection and speed) is not converted")
    if has_k:
        sp = dict(base, id=cid, spring_type="coil")
        P = law.get("preload", 0.0) or 0.0
        if "k" in law:
            sp["rate"] = law["k"]
            sp["preload"] = r6(P - law["k"] * (L_ref - L0))
        else:
            pts = sorted(law["k_curve"])
            sp["rate_curve"] = [[r6(L0 + x), r6(P - f)] for x, f in pts]
            if not any(abs(x) < 1e-12 for x, _ in pts):
                rep.add("assumed", "suspension", f"{cid}: spring curve has no point at zero deflection")
            rep.rate_curve_note = True
        sp["free_length"] = L0
        sp["installed_length"] = r6(L_ref)
        out.append(sp)
        rep.add("converted", "suspension", "spring force law F = P - k (L - L0) (positive = tension in Chrono) -> SVJ F = preload + rate (L_ref - L) "
                                           "(positive = pushing apart); preload is the force at the installed length")
    if law.get("stops"):
        lo, hi = law["stops"]
        pts = [[r6(lo - d), r6(f)] for d, f in reversed(DEFAULT_STOP_CURVE) if d > 0]
        pts += [[r6(lo), 0.0], [r6(hi), 0.0]]
        pts += [[r6(hi + d), r6(-f)] for d, f in DEFAULT_STOP_CURVE if d > 0]
        out.append(dict(base, id="stop_" + cid, spring_type="rubber", rate_curve=pts, free_length=r6((lo + hi) / 2)))
        rep.add("converted", "suspension", "TSDA Minimum/Maximum Length stops -> a separate spring with the force curve of Chrono's default "
                                           "bump/rebound stop table (ADAMS/Car example, as hard-coded in ChForceFunctors.cpp)")
    return out


def _damper_constraint(cid, e, shift, rep, a, b):
    law = e.data
    if not any(k in law for k in ("c", "c_curve")):
        return None
    d = {"id": cid, "type": "damper", "body_a": a, "frame_a": {"position": rv(vsub(e.p1, shift)), "orientation": [0, 0, 0, 1]},
         "body_b": b, "frame_b": {"position": rv(vsub(e.p2, shift)), "orientation": [0, 0, 0, 1]}}
    if "c_curve" in law:
        pts = sorted(law["c_curve"])
        reb = [[r6(v), r6(f)] for v, f in pts if v >= 0]
        bump = [[r6(-v), r6(-f)] for v, f in reversed(pts) if v < 0]
        if not reb or reb[0][0] != 0:
            reb.insert(0, [0.0, 0.0])
        if not bump or bump[0][0] != 0:
            bump.insert(0, [0.0, 0.0])
        d["rebound_curve"], d["bump_curve"] = reb, bump
    elif "degr" in law:
        dc, de = law["degr"]
        c = law["c"]
        vs = [0.0, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
        d["rebound_curve"] = [[v, r6(c * v / (1 + de * v))] for v in vs]
        d["bump_curve"] = [[v, r6(c * v / (1 + dc * v))] for v in vs]
        rep.add("converted", "suspension", "degressive damper F = c v / (1 + d v) sampled to bump and rebound curves (8 points, 0 to 1 m/s)")
    else:
        d["damping"] = law["c"]
    return d


def _assemble(data, V, chassis, steers, stations, tire, engine_file, transmission_file, rep):
    # ---- all bodies, for the mass properties ------------------------------------------------------------------
    wheel_files = {}
    for st in stations:
        key = "Left Wheel Input File" if st["side"] == "L" else "Right Wheel Input File"
        wd = data.read(st["ax"][key])
        wheel_files[(st["axle"], st["side"])] = wd
    allb = []        # (mass, pos, I_vehicle_axes)
    for st in stations:
        S, wd = st["susp"], wheel_files[(st["axle"], st["side"])]
        for b in S.bodies:
            allb.append((b.mass, b.pos, b.I))
        w = S.wheel
        Rsp = w["R"]
        Iw = [[0.0] * 3 for _ in range(3)]
        diag = [w["inertia"][i] + wd["Inertia"][i] + tire["inertia"][i] for i in range(3)]
        diag[1] += w["axle_inertia"]
        Iw = rotate_inertia(inertia_matrix(diag, None), Rsp)
        mass = w["mass"] + wd["Mass"] + tire["mass"]
        w["total_mass"], w["total_I"], w["diag"] = mass, Iw, diag
        allb.append((mass, w["pos"], Iw))
    for s in steers:
        for b in s.bodies:
            allb.append((b.mass, b.pos, b.I))
    m_tot = chassis["mass"] + sum(m for m, _, _ in allb)
    com = vscale(vadd(vscale(chassis["com"], chassis["mass"]), (lambda acc: acc)(
        [sum(m * p[i] for m, p, _ in allb) for i in range(3)])), 1.0 / m_tot)
    I = madd(chassis["I"], parallel_axis(chassis["mass"], vsub(chassis["com"], com)))
    for m, p, Ib in allb:
        I = madd(I, madd(Ib, parallel_axis(m, vsub(p, com))))

    # ---- origin: front axle wheel centre, ground from the loaded tyre radius -------------------------------------
    ranks = sorted({st["axle"] for st in stations}, key=lambda a: -stations[[s["axle"] for s in stations].index(a)]["susp"].wheel["pos"][0])
    ax_x = {a: stations[[s["axle"] for s in stations].index(a)]["susp"].wheel["pos"][0] for a in ranks}
    x0 = ax_x[ranks[0]]
    loads = _min_norm_loads([ax_x[a] for a in ranks], m_tot, com[0])
    axle_load = {a: f for a, f in zip(ranks, loads)}
    zg_list = []
    for st in stations:
        fz = axle_load[st["axle"]] / 2
        defl = tire_deflection(tire, fz)
        st["r_loaded"] = tire["radius"] - defl
        st["fz"] = fz
        zg_list.append(st["susp"].wheel["pos"][2] - st["r_loaded"])
    zg = sum(zg_list) / len(zg_list)
    spread = max(zg_list) - min(zg_list)
    shift = [x0, 0.0, zg]
    rep.add("assumed", "frame", f"SVJ origin: front axle wheel centre x = {x0:.4f} m (Chrono chassis frame), ground at z = {zg:.4f} m = wheel centre "
                                f"height minus the loaded tyre radius (static load from mass and CG, vertical stiffness of the tyre); "
                                f"spread between wheels {spread * 1000:.1f} mm")
    rep.shift = shift
    P = lambda p: vsub(p, shift)

    suffix = lambda st: st["id"].lower()
    mass_bodies, constraints, wstations = [], [], []
    shared = {b.name for s in steers for b in s.bodies}
    for s in steers:
        for b in s.bodies:
            mb = {"id": b.name, "mass": b.mass if not b.x_derived else 0.0, "position": rv(P(b.pos)), "category": "structural",
                  "inertia": inertia_to_svj(b.I), "parent": "chassis"}
            if b.x_derived:
                mb["x_derived"] = True
                mb.pop("inertia")
            mass_bodies.append(mb)
        for j in s.joints:
            constraints.append(_joint_dict(j, shift, rep, lambda n: n, j.name))
    for st in stations:
        S, sfx = st["susp"], suffix(st)
        ren = lambda n, sfx=sfx: n if (n == "chassis" or n in shared) else f"{n}_{sfx}"
        for b in S.bodies:
            mb = {"id": ren(b.name), "mass": b.mass if not b.x_derived else 0.0, "position": rv(P(b.pos)),
                  "category": "structural", "parent": "chassis"}
            if b.x_derived:
                mb["x_derived"] = True
            else:
                mb["inertia"] = inertia_to_svj(b.I)
            if b.kind == "upright" or b.name == S.wheel["upright"]:
                mb["markers"] = {"wheel_center": {"position": rv(P(S.wheel["pos"]))}}
            mass_bodies.append(mb)
        w = S.wheel
        wname = f"wheel_{sfx}"
        mass_bodies.append({"id": wname, "name": f"Wheel {st['id']}", "description": "Spindle + rim + tyre (rotating mass)", "category": "structural",
                            "mass": r6(w["total_mass"]), "position": rv(P(w["pos"])), "inertia": inertia_to_svj(w["total_I"]),
                            "x_derived": True})
        for j in S.joints:
            nm = j.name + "_" + sfx if j.name != "hinge_wheel" else "hinge_wheel_" + sfx
            jj = Joint(nm, j.type, ren(j.a), ren(j.b) if j.b != "wheel" else wname, j.pos, j.R, j.bushing, j.x_derived)
            constraints.append(_joint_dict(jj, shift, rep, None, nm))
        for e in S.elements:
            cid = f"{e.name}_{sfx}"
            a, b = ren(e.a), ren(e.b)
            if e.kind in ("spring", "damper", "tsda"):
                law = e.data
                if e.kind == "spring" or (e.kind == "tsda" and any(k in law for k in ("k", "k_curve", "map")) or law.get("stops")):
                    constraints += _spring_constraints(cid if e.kind != "tsda" else "spring_" + cid, e, shift, rep, a, b)
                if e.kind == "damper" or (e.kind == "tsda" and any(k in law for k in ("c", "c_curve"))):
                    dd = _damper_constraint(cid if e.kind != "tsda" else "damper_" + cid, e, shift, rep, a, b)
                    if dd:
                        constraints.append(dd)
            elif e.kind == "rsda":
                rep.add("lost", "suspension", f"RSDA {e.name} (rotational spring-damper) of axle {st['axle'] + 1}: not converted yet")
        wd = wheel_files[(st["axle"], st["side"])]
        Ixx_spin = w["diag"][1]
        wheel_blk = {"rim_diameter": r6(2 * (wd.get("Visualization", {}).get("Radius") or tire.get("rim_radius") or 0.0)) or None,
                     "rim_width": wd.get("Visualization", {}).get("Width"),
                     "tire_section_width": tire["width"],
                     "tire_aspect_ratio": r6((tire["radius"] - (tire.get("rim_radius") or wd.get("Visualization", {}).get("Radius") or 0)) / tire["width"]),
                     "mass": r6(wd["Mass"] + tire["mass"]), "rotational_inertia": r6(Ixx_spin), "loaded_radius": r6(st["r_loaded"]),
                     "set_ref": "tire"}
        wheel_blk = {k: v for k, v in wheel_blk.items() if v is not None}
        ws = {"id": st["id"], "wheel_body": wname, "upright_body": ren(S.wheel["upright"]), "wheel_center_marker": "wheel_center",
              "axle": f"A{ranks.index(st['axle']) + 1}", "side": st["side"], "topology_hint": st["tpl"].lower(),
              "wheel": wheel_blk, "tire": {"set_ref": "tire"}}
        steer = st["steer"]
        if steer is not None:
            ws["steering_joint"] = steer.gear_joint
        camber = math.radians(st["sd"].get("Camber Angle (deg)", 0.0))
        toe = math.radians(st["sd"].get("Toe Angle (deg)", 0.0))
        ws["alignment"] = {"camber": r6(camber), "toe": r6(toe)}
        bk = _brake_block(data, st, rep)
        if bk:
            ws["brake"] = bk
        wstations.append(ws)

    # tyres
    tire_set = dict(tire["set"])
    tire_set["x_chrono"] = {"template": tire["template"], "file": tire["file"], **{k: v for k, v in (tire.get("chrono_keep") or {}).items() if v is not None}}

    # chassis block
    left = [st for st in stations if st["side"] == "L"]
    front, rear = [st for st in left if st["id"] == st["id"]][0], None
    ax_sorted = sorted(left, key=lambda s: -s["susp"].wheel["pos"][0])
    wheelbase = ax_sorted[0]["susp"].wheel["pos"][0] - ax_sorted[-1]["susp"].wheel["pos"][0]
    track = lambda s: 2 * abs(s["susp"].wheel["pos"][1])
    chassis_blk = {"mass_total": r6(m_tot), "wheelbase": r6(wheelbase), "track_front": r6(track(ax_sorted[0])),
                   "track_rear": r6(track(ax_sorted[-1])), "center_of_gravity": rv(P(com)), "inertia": inertia_to_svj(I),
                   "mass_bodies": mass_bodies}
    chassis_blk["mass_unsprung_per_corner"] = {}
    for st in stations:
        S = st["susp"]
        um = S.wheel["total_mass"] + sum(b.mass for b in S.bodies)
        chassis_blk["mass_unsprung_per_corner"][st["id"]] = r6(um)
    rep.add("converted", "chassis", "mass_unsprung_per_corner is the sum of the corner bodies (wheel assembly, upright, arms, rods); Chrono has no unsprung mass field")
    rep.add("converted", "chassis", "mass_total = Chrono chassis + suspension, steering and wheel bodies (Chrono's chassis file holds only the chassis); "
                                    "CG and inertia are the composite about the CG in vehicle axes; the chassis remainder is the Chrono chassis")

    # tree structure: parent = the body of the first joint that has the body as body_b; the joint that closes a loop is
    # marked x_derived like the loops the suspension migrator writes (spec 24.8, the checker treats a loop as over-constraint otherwise)
    mbs = {m["id"]: m for m in mass_bodies}
    seen = {}
    for c in constraints:
        if c.get("type") != "joint":
            continue
        b = c.get("body_b")
        if b in mbs:
            if b not in seen:
                seen[b] = c.get("body_a")
                mbs[b]["parent"] = c.get("body_a")
            elif not mbs[b].get("x_derived"):
                c["x_derived"] = True
    for m in mass_bodies:
        I = m.get("inertia")
        if I and not (min(I["Ixx"], I["Iyy"], I["Izz"]) > 0 and I["Ixx"] + I["Iyy"] >= I["Izz"] and I["Iyy"] + I["Izz"] >= I["Ixx"]
                      and I["Ixx"] + I["Izz"] >= I["Iyy"]):
            rep.add("assumed", m["id"], "the Chrono inertia violates the triangle inequality (not a physical rigid body); kept as given, the validator warns")

    meta = {"specification": "SVJ", "version": SVJ_VERSION, "coordinate_system": "ISO_8855", "units": "SI",
            "description": f"{V.get('Name', 'Chrono vehicle')} converted from a Project Chrono::Vehicle JSON model",
            "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "author": "chrono_convert.py", "source_format": "Chrono::Vehicle",
            "alignment_convention": "relative_to_centerline",
            "data_origin": {"type": "simulation", "confidence": "high",
                            "detail": "Converted from Project Chrono::Vehicle JSON files. Geometry, masses, inertias, spring and damper laws are the Chrono "
                                      "values; the SVJ origin and the ground plane are derived (see x_chrono.frame). Estimated values keep their Chrono "
                                      "origin and are not marked _est."}}
    if getattr(rep, "origin", "chrono") == "synthetic":
        meta["data_origin"] = {"type": "calculated", "confidence": "low",
                               "detail": "Synthetic Chrono::Vehicle JSON written for the converter's tests (hand-chosen numbers, not Chrono data and not a real "
                                         "vehicle), converted by chrono_convert.py. The format is Chrono's; the numbers are not."}
        meta.update({"license": "Apache-2.0", "attribution": "Synthetic test data of this repository; the file format is that of Project Chrono::Vehicle."})
    else:
        meta.update({"license": LICENSE_TEXT, "copyright": COPYRIGHT, "source_url": CHRONO_URL, "source_files": list(rep.sources),
                     "attribution": "Vehicle data from the Project Chrono distribution (data/vehicle), BSD-3-Clause; see NOTICE."})


    doc = {"_metadata": meta,
           "vehicle_info": {"model": V.get("Name"), "vehicle_class": "special", "drive_type": "none"},
           "chassis": chassis_blk,
           "reference_pose": {"condition": "other", "load_case": "kerb",
                              "note": "Chrono design configuration: hardpoints as given, springs at their installed length; Chrono states no load case"},
           "wheel_stations": wstations, "constraints": constraints,
           "tires": {"sets": {"tire": tire_set}}}
    rep.stations, rep.steers = stations, steers
    steer_raw = getattr(rep, "steer_raw", [])
    doc["steering"] = _steering_block(steers, stations, shift, rep) if steers else None
    if doc["steering"] is None:
        doc.pop("steering")
    x = {"source": {"vehicle_file": rep.sources[0] if rep.sources else None, "name": V.get("Name"),
                    "minimum_turning_radius": V.get("Minimum Turning Radius"), "maximum_steering_angle_deg": V.get("Maximum Steering Angle (deg)"),
                    "wheelbase": V.get("Wheelbase")},
         "frame": {"shift_to_svj_origin": rv(shift), "note": "p_svj = p_chrono - shift; the Chrono chassis frame is the reference frame of the chassis body"},
         "chassis": {k: chassis[k] for k in ("Driver Position", "Rear Connector Location") if k in chassis}}
    doc["x_chrono"] = x
    if steer_raw and steer_raw[0]["template"] == "PitmanArm":
        x["steering_subsystem"] = steer_raw[0]          # lets SVJ -> Chrono write the Pitman arm back unchanged
    if getattr(rep, "mesh_dir", None):
        attach_meshes(doc, data, V, stations, shift, rep, rep.mesh_dir, rep.asset_name)
    _powertrain_and_driveline(doc, data, V, engine_file, transmission_file, rep)
    _clean(doc)
    return doc, rep


def _clean(o):
    if isinstance(o, dict):
        for k in [k for k, v in o.items() if v is None]:
            del o[k]
        for v in o.values():
            _clean(v)
    elif isinstance(o, list):
        for v in o:
            _clean(v)


def _joint_dict(j, shift, rep, ren, name):
    fr = {"position": rv(vsub(j.pos, shift)), "orientation": svj_quat(j.R)}
    d = {"id": name, "type": "joint", "joint_type": j.type, "body_a": j.a, "frame_a": dict(fr), "body_b": j.b, "frame_b": dict(fr)}
    if j.x_derived:
        d["x_derived"] = True
    bu = _bushing_to_svj(j.bushing, j.type, rep, name)
    if bu:
        d["bushing"] = bu
        rep.add("converted", "suspension", "Chrono bushing data -> SVJ bushing (stiffness in the joint frame; rotational damping is not carried)")
    return d


def _brake_block(data, st, rep):
    key = "Left Brake Input File" if st["side"] == "L" else "Right Brake Input File"
    if key not in st["ax"]:
        return None
    b = data.read(st["ax"][key])
    t = b.get("Template")
    if t in ("BrakeSimple", "BrakeShafts"):
        out = {"model": "simple" if t == "BrakeSimple" else "shafts", "max_torque": b["Maximum Torque"]}
        if t == "BrakeShafts":
            out["shaft_inertia"] = b["Shaft Inertia"]
        rep.add("converted", "brake", "Chrono Maximum Torque -> brake.max_torque (an abstract brake with no disc geometry; the keys wheel_stations[].brake.model and max_torque are proposed in spec section 30.6)")
        return out
    rep.add("lost", "brake", f"brake template {t!r} is not supported")
    return None


# ---- steering block, powertrain, driveline ---------------------------------------------------------------------------

def _steering_block(steers, stations, shift, rep):
    s = steers[0]
    if len(steers) > 1:
        rep.add("lost", "steering", f"{len(steers) - 1} further steering subsystem(s): only the first is written as the primary gear; "
                                    "additional steered axles (spec 8.6) are not generated")
    P = lambda p: vsub(p, shift)
    if s.kind == "rack_and_pinion":
        travel = 2 * s.max_angle * s.pinion_radius
    else:
        arm = vsub(s.tip, s.pivot)
        arm = vsub(arm, vscale(s.axis, vdot(arm, s.axis)))
        travel = 2 * vnorm(arm) * math.sin(s.max_angle)
    blk = {"type": s.kind, "rack_position": rv(P(s.pivot)), "rack_travel": r6(travel), "overall_ratio": 1.0,
           "lock_to_lock": r6(2 * s.max_angle)}
    rep.add("assumed", "steering", "Chrono has no steering wheel or column: the pinion (rack) or the sector shaft (Pitman) takes the steering input directly, "
                                   "so lock_to_lock is twice the maximum pinion / sector angle and overall_ratio is that angle per road-wheel angle "
                                   "at the centre, from the loop solver; no steering wheel joint is generated")
    return blk


def finish_steering(doc, rep):
    """Fill steering.overall_ratio and x_chrono.steering from the loop solver (needs the whole document)."""
    if "steering" not in doc:
        return
    try:
        from svj import loopsolver as ls
        from svj import steeringcheck as sc
    except ImportError:
        import loop_solver as ls
        import steering_check as sc
    s = rep.steers[0]
    gj = s.gear_joint
    delta = 0.002 if s.kind == "rack_and_pinion" else 0.01          # m of rack travel or rad of sector angle
    res = ls.solve(doc, joint_values={gj: [delta]})
    if not res.get("converged"):
        rep.add("lost", "steering", f"loop solver did not close at steering {delta} ({res.get('residual')}); overall_ratio left at 1")
        return
    ang = {}
    for st in rep.stations:
        if st["steer"] is s:
            ang[st["id"]] = sc._right_steer(doc, st["id"], res["transforms"])
    avg_right = sum(ang.values()) / len(ang)            # positive = steers right
    gear_angle = delta / s.pinion_radius if s.kind == "rack_and_pinion" else delta
    ratio = abs(gear_angle / avg_right) if abs(avg_right) > 1e-9 else 1.0
    doc["steering"]["overall_ratio"] = r6(ratio)
    doc["steering"]["max_steer_angle"] = r6(s.max_angle / ratio)
    # sign: Chrono's steering input +1 is a left turn. +delta of the gear joint steers `avg_right` to the right.
    sign_left_pos = -1.0 if avg_right > 0 else 1.0            # gear coordinate sign that gives a LEFT turn
    doc["x_chrono"]["steering"] = {
        "input": "Chrono steering input s in [-1, 1], positive = left turn (ChSteering.h)",
        "gear_joint": gj, "gear_coordinate_range": r6(s.max_angle * (s.pinion_radius if s.kind == "rack_and_pinion" else 1.0)),
        "gear_coordinate_sign_for_left_turn": sign_left_pos,
        "solver_check": {"gear_coordinate": delta, "right_steer_rad": {k: r6(v) for k, v in ang.items()}}}
    rep.checks.append(f"steering: gear coordinate {delta:+g} turns the wheels {math.degrees(avg_right):+.3f} deg to the right "
                      f"(overall ratio {ratio:.3f}); Chrono's positive input (left) therefore drives the gear coordinate by "
                      f"{sign_left_pos:+.0f} x {abs(s.max_angle):.4f} rad-equivalent")
    return


def _interp(pts, x):
    pts = sorted(pts)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _powertrain_and_driveline(doc, data, V, engine_file, transmission_file, rep):
    pt = {}
    eng = trans = None
    if V.get("Powertrain"):
        engine_file = engine_file or V["Powertrain"].get("Engine Input File")
        transmission_file = transmission_file or V["Powertrain"].get("Transmission Input File")
    if engine_file:
        e = data.read(engine_file)
        t = e.get("Template")
        if t == "EngineSimpleMap":
            full, zero = e["Map Full Throttle"], e["Map Zero Throttle"]
            cut = lambda pts: [[0.0, r6(_interp(pts, 0.0))]] + [[x, y] for x, y in sorted(pts) if x > 0]
            pt["engine"] = {"torque_curve": cut(full), "torque_curve_closed": cut(zero),
                            "max_rpm": e["Maximal Engine Speed RPM"]}
            rep.add("converted", "powertrain", "EngineSimpleMap: full-throttle map -> torque_curve, zero-throttle map -> torque_curve_closed "
                                               "(points below 0 rpm dropped, a point at 0 rpm interpolated); Chrono interpolates the maps between throttle 0 and 1")
        elif t == "EngineSimple":
            tmax, pmax, nmax = e["Maximum Engine Torque"], e["Maximum Engine Power"], e["Maximum Engine Speed"]
            rpms = [0, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000]
            cur = [[r, r6(min(tmax, pmax / max(r * math.pi / 30, 1e-9)))] for r in rpms if r <= nmax]
            pt["engine"] = {"torque_curve": cur, "max_rpm": nmax}
            rep.add("assumed", "powertrain", "EngineSimple (max torque, max power): torque_curve synthesised as min(T_max, P_max / omega); "
                                             "Chrono's model has no speed-dependent shape")
        else:
            rep.add("lost", "powertrain", f"engine template {t!r} is not converted")
        pt.setdefault("engine", {})["_chrono"] = None
        pt["engine"].pop("_chrono")
        doc.setdefault("x_chrono", {})["engine"] = {"file": engine_file, "template": t}
    if transmission_file:
        tr = data.read(transmission_file)
        t = tr.get("Template")
        gb = tr.get("Gear Box")
        if gb and t in ("AutomaticTransmissionSimpleMap", "AutomaticTransmissionShafts", "ManualTransmissionShafts"):
            fwd = [r6(1.0 / x) for x in gb["Forward Gear Ratios"]]
            gearbox = {"type": "manual" if t.startswith("Manual") else "auto", "ratios": fwd}
            if gb.get("Reverse Gear Ratio"):
                gearbox["reverse_ratios"] = [r6(abs(1.0 / gb["Reverse Gear Ratio"]))]
            if "Shift Points Map RPM" in gb:
                gearbox["shift_points"] = [list(p) for p in gb["Shift Points Map RPM"]]
            rep.add("converted", "powertrain", "Chrono gear ratios are output/input speed; SVJ ratios are input/output: inverted (1/r)")
            if t != "AutomaticTransmissionSimpleMap":
                rep.add("lost", "powertrain", f"{t}: shaft inertias and torque-converter data are not converted yet")
            pt["gearbox"] = gearbox
        else:
            rep.add("lost", "powertrain", f"transmission template {t!r} is not converted")
        doc.setdefault("x_chrono", {})["transmission"] = {"file": transmission_file, "template": t}
    dl = V.get("Driveline")
    if dl:
        d = data.read(dl["Input File"])
        t = d.get("Template")
        driven = dl.get("Suspension Indexes", [])
        n = len(V["Axles"])
        if len(driven) == n:
            doc["vehicle_info"]["drive_type"] = "AWD"
        elif len(driven) >= 1:
            doc["vehicle_info"]["drive_type"] = "RWD" if driven[0] > 0 or max(driven) > 0 else "FWD"
        rear_front = lambda i: "front" if i == 0 else "rear"
        gear = None
        if "Gear Ratio" in d:
            gr = d["Gear Ratio"]
            gear = {k: v for k, v in gr.items()}
        elif "Front Conical Gear Ratio" in d:
            gear = {"Front Conical Gear": d["Front Conical Gear Ratio"], "Rear Conical Gear": d["Rear Conical Gear Ratio"]}
        diffs = []
        if gear:
            for i in driven:
                key = ("Front Conical Gear" if i == 0 else "Rear Conical Gear") if "Front Conical Gear" in gear or "Rear Conical Gear" in gear else "Conical Gear"
                if key in gear:
                    diffs.append({"id": f"diff_{rear_front(i)}", "location": rear_front(i), "type": "open", "final_drive": r6(1.0 / gear[key])})
        if diffs:
            pt["differentials"] = diffs
            rep.add("converted", "powertrain", "driveline conical gear ratio (output/input) -> differentials[].final_drive (inverted); the differential is written "
                                               "as type 'open': Chrono's locking limit (a clutch torque) and shaft inertias stay in x_chrono.driveline")
        doc.setdefault("x_chrono", {})["driveline"] = {"file": dl["Input File"], "template": t, "driven_axles": driven, "raw": d}
        if t.startswith("ShaftsDriveline") or t == "SimpleDriveline":
            rep.add("lost", "powertrain", f"driveline {t}: central/axle differential locking limits, shaft inertias and bias ratios are kept in x_chrono.driveline only")
    if pt:
        pt["layout"] = {"AWD": "AWD", "FWD": "FF"}.get(doc["vehicle_info"].get("drive_type"), "FR")
        doc["powertrain"] = pt


# ======================================================================================================================
# Command line
# ======================================================================================================================

# ======================================================================================================================
# SVJ -> Chrono::Vehicle JSON (a folder of files that Chrono reads with its data root set to the output folder)
# ======================================================================================================================

def _cq(frame):
    """Chrono quaternion [w, x, y, z] of an SVJ frame."""
    q = mat_to_q(mat_from_svj_quat((frame or {}).get("orientation", [0, 0, 0, 1])))
    return [round(float(c), 9) + 0.0 for c in q]


def _inertia_entries(I):
    """SVJ inertia object -> (Chrono moments, Chrono products = matrix entries)."""
    M = inertia_from_svj(I)
    return [r6(M[0][0]), r6(M[1][1]), r6(M[2][2])], [r6(M[0][1]), r6(M[0][2]), r6(M[1][2])]


def _component(adj, start, blocked):
    seen, todo = {start}, [start]
    while todo:
        n = todo.pop()
        for m in adj.get(n, ()):
            if m not in seen and m not in blocked:
                seen.add(m)
                todo.append(m)
    return seen


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write(chr(10))


def svj_to_chrono(doc, outdir, name=None, rep=None, svj_dir=None):
    """Write the Chrono::Vehicle JSON files of an SVJ vehicle under `outdir` (the Chrono data root); returns the vehicle file path.

    Suspensions become GenericWheeledSuspension (any topology of bodies, joints, tie rods and TSDAs); a rack on a slide becomes
    RackPinion; anything Chrono cannot express is listed in the report."""
    rep = rep or Report("svj->chrono")
    if not isinstance(doc.get("wheel_stations"), list) or not doc.get("constraints"):
        raise ConversionError("the SVJ file has no unified suspension (wheel_stations[] and constraints[]); migrate it with tools/migrate_suspension.py")
    name = name or re.sub(r"[^A-Za-z0-9]+", "_", str((doc.get("vehicle_info") or {}).get("model") or "svj_vehicle")).strip("_")
    ch = doc["chassis"]
    xc = doc.get("x_chrono") or {}
    shift = (xc.get("frame") or {}).get("shift_to_svj_origin") or [0.0, 0.0, 0.0]
    if not (xc.get("frame") or {}).get("shift_to_svj_origin"):
        rep.add("assumed", "frame", "no x_chrono.frame: the Chrono chassis reference frame is placed at the SVJ origin (front axle midpoint, ground level)")
    C = lambda p: vadd(list(p), shift)
    bodies = {m["id"]: m for m in ch.get("mass_bodies", [])}
    cons = doc["constraints"]
    joints = [c for c in cons if c["type"] == "joint"]
    adj = {}
    for j in joints:
        adj.setdefault(j["body_a"], set()).add(j["body_b"])
        adj.setdefault(j["body_b"], set()).add(j["body_a"])
    stations = doc["wheel_stations"]
    tire_set = next(iter((doc.get("tires") or {}).get("sets", {}).values()), None)

    def wheel_hinge(st):
        for j in joints:
            if j["body_b"] == st["wheel_body"] and j["joint_type"] == "revolute":
                return j
        raise ConversionError(f"station {st['id']}: no revolute joint to the wheel body")

    axles = {}
    for st in stations:
        axles.setdefault(st["axle"], {})[st["side"]] = st
    order = sorted(axles, key=lambda a: -wheel_hinge(next(iter(axles[a].values())))["frame_a"]["position"][0])

    # ---- classify bodies: station-local, shared (steering), chassis ---------------------------------------------------
    blocked0 = {"chassis", "ground"} | {s["wheel_body"] for s in stations}
    local, shared = {}, set()
    for a in order:
        if "L" in axles[a] and "R" in axles[a]:
            uL, uR = axles[a]["L"]["upright_body"], axles[a]["R"]["upright_body"]
            full = _component(adj, uL, blocked0)
            if uR not in full:
                continue
            best = None
            for b in sorted(full - {uL, uR}):
                cL = _component(adj, uL, blocked0 | {b})
                if uR not in cL:
                    cR = _component(adj, uR, blocked0 | {b})
                    key = (abs(len(cL) - len(cR)), -len(adj.get(b, ())))
                    if best is None or key < best[0]:
                        best = (key, b)             # the most central cut vertex: the steering link / rack
            if best:
                shared.add(best[1])
    cuts = set(shared)
    for a in order:
        comps = {sd: _component(adj, s["upright_body"], blocked0 | cuts) for sd, s in axles[a].items()}
        local[a] = comps
    # the rest of the steering system (Pitman and idler arms) hangs off the cut vertices
    todo = list(cuts)
    all_local = set().union(*[c for a in local for c in local[a].values()]) if local else set()
    while todo:
        n = todo.pop()
        for m in adj.get(n, ()):
            if m not in shared and m not in blocked0 and m not in all_local:
                shared.add(m)
                todo.append(m)
    # a steering system we can express: one shared body on a translational joint to the chassis along the lateral axis
    rack = None
    for b in shared:
        for j in joints:
            if j["joint_type"] == "translational" and {j["body_a"], j["body_b"]} == {"chassis", b}:
                z = mcol(mat_from_svj_quat(j["frame_a"].get("orientation", [0, 0, 0, 1])), 2)
                if abs(abs(z[1]) - 1.0) < 1e-3:
                    rack = (b, j)
    pitman = None
    sub = xc.get("steering_subsystem")
    if shared and not rack and sub and sub.get("template") == "PitmanArm":
        S0 = read_steering(sub["raw"], sub["location"], sub["orientation"], Report("tmp"))
        same = S0.ref in bodies and all(b.name in bodies and vnorm(vsub(C(bodies[b.name]["position"]), b.pos)) < 1e-4 and
                                        abs(bodies[b.name].get("mass", 0.0) - b.mass) < 1e-6
                                        for b in S0.bodies if not b.x_derived) and {b.name for b in S0.bodies} == shared
        if same:
            pitman, rack = sub, (S0.ref, None)
            rep.add("converted", "steering", "Pitman arm: the bodies are unchanged from the Chrono original, so its PitmanArm file is written back as it was "
                                             "(x_chrono.steering_subsystem); edits to the linkage are not carried")
        else:
            rep.add("lost", "steering", "the Pitman linkage differs from the Chrono original kept in x_chrono.steering_subsystem; it cannot be written")
    if shared and not rack:
        rep.add("lost", "steering", "the steering linkage (" + ", ".join(sorted(shared)) + ") is not a rack on a lateral slide; Chrono's Pitman arm "
                                    "template cannot be generated from bodies and joints, so the tie rods are attached to the chassis and the vehicle "
                                    "cannot steer")
    elif not shared:
        rep.add("assumed", "steering", "no steering linkage in the SVJ file: the vehicle is written without a steering subsystem")

    def cname(b, sfx):
        if b == "chassis" or b == "ground":
            return "Chassis"
        if rack and b == rack[0]:
            return "Steering"
        if shared and b in shared:
            return "Chassis"
        return b[: -len(sfx) - 1] if sfx and b.endswith("_" + sfx) else b

    out_files = {}
    wheel_by_axle = {}
    tire = {}
    veh_axles = []
    toe_cam = {}
    for ai, a in enumerate(order):
        sts = axles[a]
        st = sts.get("L") or sts.get("R")
        if "L" not in sts:
            rep.add("assumed", "suspension", f"axle {a}: only a right station is present; it is written as the (mirrored) left side")
        sfx = st["id"].lower()
        hinge = wheel_hinge(st)
        ax_x = hinge["frame_a"]["position"][0] + shift[0]
        A = [ax_x, 0.0, 0.0]
        P = lambda p: r6v(vsub(C(p), A))
        comp = local[a]["L" if "L" in sts else "R"]
        # rods: massless derived bodies with two spherical joints -> distance constraints
        rods = {}
        for b in comp:
            m = bodies.get(b, {})
            js = [j for j in joints if b in (j["body_a"], j["body_b"])]
            if m.get("x_derived") and not m.get("mass") and len(js) == 2 and all(j["joint_type"] == "spherical" for j in js):
                rods[b] = js
        body_list, joint_list, dist, tsdas = [], [], [], []
        steered = bool(rack) and any((j["body_a"] in comp and j["body_b"] in shared) or (j["body_b"] in comp and j["body_a"] in shared)
                                     for j in joints)
        for b in sorted(comp):
            if b in rods:
                continue
            m = bodies.get(b)
            if m is None:
                rep.add("lost", "suspension", f"body {b!r} is not in mass_bodies; skipped")
                continue
            mom, prod = _inertia_entries(m["inertia"]) if m.get("inertia") else ([0.01] * 3, [0.0] * 3)
            if not m.get("inertia"):
                rep.add("assumed", "suspension", f"{b}: no inertia tensor in the SVJ file; 0.01 kg m^2 used")
            body_list.append({"Name": cname(b, sfx), "Mirrored": True, "Position": P(m["position"]), "Rotation": [1, 0, 0, 0],
                              "Mass": m["mass"], "Moments of Inertia": mom, "Products of Inertia": prod})
        for j in joints:
            if j["body_b"] == st["wheel_body"] or j["body_a"] == st["wheel_body"]:
                continue
            ends = {j["body_a"], j["body_b"]}
            if ends & set(rods):
                continue
            if not (ends <= comp | {"chassis"} | ({rack[0]} if rack else set())) or not (ends & comp):
                continue
            ctype = {"revolute": "Revolute", "spherical": "Spherical", "translational": "Prismatic", "cylindrical": "Cylindrical",
                     "universal": "Universal", "fixed": "Lock"}[j["joint_type"]]
            if j.get("bushing"):
                rep.add("lost", "suspension", f"{j['id']}: bushing is not written (Chrono 'Bushing Data' needs the stiffness / damping split)")
            joint_list.append({"Name": j["id"][: -len(sfx) - 1] if j["id"].endswith("_" + sfx) else j["id"], "Type": ctype, "Mirrored": True,
                               "Body1": cname(j["body_a"], sfx), "Body2": cname(j["body_b"], sfx),
                               "Position": P(j["frame_a"]["position"]), "Rotation": _cq(j["frame_a"])})
        for b, js in rods.items():
            ends = []
            for j in js:
                o = j["body_a"] if j["body_b"] == b else j["body_b"]
                ends.append((o, j["frame_a"]["position"]))
            (b1, p1), (b2, p2) = ends
            dist.append({"Name": b[: -len(sfx) - 1] if b.endswith("_" + sfx) else b, "Mirrored": True, "Body1": cname(b1, sfx),
                         "Body2": cname(b2, sfx), "Point1": P(p1), "Point2": P(p2)})
        # springs and dampers whose ends are in this side
        side_ids = comp | {"chassis"} | ({rack[0]} if rack else set())
        stops = [c for c in cons if c["type"] == "spring" and (c.get("spring_type") == "rubber" or str(c["id"]).startswith("stop_"))]
        for c in cons:
            if c["type"] not in ("spring", "damper") or {c["body_a"], c["body_b"]} - side_ids or not ({c["body_a"], c["body_b"]} & comp):
                continue
            if c in stops:
                continue
            e = {"Name": c["id"][: -len(sfx) - 1] if c["id"].endswith("_" + sfx) else c["id"], "Mirrored": True,
                 "Body1": cname(c["body_a"], sfx), "Body2": cname(c["body_b"], sfx),
                 "Point1": P(c["frame_a"]["position"]), "Point2": P(c["frame_b"]["position"])}
            L_ref = vnorm(vsub(c["frame_a"]["position"], c["frame_b"]["position"]))
            if c["type"] == "spring":
                L0 = c.get("free_length", L_ref)
                e["Free Length"] = L0
                if "rate_curve" in c:
                    e["Spring Curve Data"] = [[r6(x - L0), r6(-f)] for x, f in c["rate_curve"]]
                    e["Preload"] = 0.0
                else:
                    e["Spring Coefficient"] = c["rate"]
                    e["Preload"] = r6(c.get("preload", 0.0) + c["rate"] * (L_ref - L0))
                for s in stops:
                    if {s["body_a"], s["body_b"]} == {c["body_a"], c["body_b"]} and s["frame_a"]["position"] == c["frame_a"]["position"]:
                        zero = [x for x, f in s["rate_curve"] if abs(f) < 1e-12]
                        if len(zero) >= 2:
                            e["Minimum Length"], e["Maximum Length"] = min(zero), max(zero)
                            rep.add("converted", "suspension", "stop spring -> Minimum / Maximum Length of the TSDA (Chrono applies its own default stop table; the SVJ stop curve is not carried)")
            else:
                if "damping" in c:
                    e["Damping Coefficient"] = c["damping"]
                else:
                    reb, bump = c.get("rebound_curve", [[0, 0]]), c.get("bump_curve", [[0, 0]])
                    pts = [[-v, -f] for v, f in reversed(bump) if v > 0] + [[0.0, 0.0]] + [[v, f] for v, f in reb if v > 0]
                    e["Damping Curve Data"] = [[r6(v), r6(f)] for v, f in pts]
            tsdas.append(e)
        sp = hinge["frame_a"]["position"]
        wb = bodies.get(st["wheel_body"], {})
        wh = st.get("wheel", {})
        tire_m = ((tire_set or {}).get("construction") or {}).get("mass", 0.0)
        spindle_m = max(wb.get("mass", 0.0) - wh.get("mass", 0.0), 1.0) if wb else 1.0
        if not wb:
            rep.add("assumed", "wheel", f"{st['id']}: no wheel body in mass_bodies; spindle mass 1 kg")
        rep.add("assumed", "wheel", "spindle / rim / tyre split of the wheel assembly: spindle mass = wheel body mass minus wheel.mass, spindle inertia of a "
                                    "solid cylinder (radius 0.1 m), rim inertia = rotational_inertia minus spindle and an annulus estimate of the tyre")
        r_spin = 0.1
        sp_spin = 0.5 * spindle_m * r_spin ** 2
        tire_spin = tire_m * 0.5 * ((((tire_set or {}).get("dimensions") or {}).get("overall_diameter", 0.8) / 2) ** 2 +
                                    (((tire_set or {}).get("rim") or {}).get("diameter", 0.4) / 2) ** 2)
        rim_spin = max(wh.get("rotational_inertia", 1.0) - sp_spin - tire_spin, 0.05)
        susp = {"Name": f"{name} axle {a}", "Type": "Suspension", "Template": "GenericWheeledSuspension", "Vehicle-Frame Inertia": False,
                "Independent": True, "Steerable": steered, "Camber Angle (deg)": 0, "Toe Angle (deg)": 0,
                "Spindle": {"Attachment Body": cname(st["upright_body"], sfx), "Mass": r6(spindle_m), "COM": P(sp),
                            "Inertia": [r6(sp_spin / 2), r6(sp_spin), r6(sp_spin / 2)], "Radius": r_spin, "Width": 0.06},
                "Bodies": body_list, "Joints": joint_list, "Distance Constraints": dist, "TSDAs": tsdas, "Axle": {"Inertia": 0.4}}
        rep.add("assumed", "suspension", "Axle inertia 0.4 kg m^2 (Chrono's axle shaft, not an SVJ quantity); camber and toe are carried by the hardpoints, so "
                                         "the template camber / toe angles are 0")
        # symmetry
        if "L" in sts and "R" in sts:
            dev = 0.0
            ssfx = sts["R"]["id"].lower()
            for b in local[a]["L"]:
                rb = b[: -len(sfx)] + ssfx if b.endswith(sfx) else None
                if rb in bodies and b in bodies:
                    pl, pr = bodies[b]["position"], bodies[rb]["position"]
                    dev = max(dev, vnorm(vsub([pl[0], -pl[1], pl[2]], pr)))
            if dev > 1e-3:
                rep.add("lost", "suspension", f"axle {a}: the right side differs from the mirrored left side by up to {dev * 1000:.1f} mm; Chrono mirrors the left "
                                              "definition, the right side is not written")
            toe_cam[a] = dev
        d = f"{name}/suspension/{name}_axle{ai + 1}.json"
        out_files[d] = susp
        # wheel + brake
        wheel = {"Name": f"{name} wheel", "Type": "Wheel", "Template": "Wheel", "Mass": r6(max(wh.get("mass", 20.0) - tire_m, 1.0)),
                 "Inertia": [r6(rim_spin / 2), r6(rim_spin), r6(rim_spin / 2)],
                 "Visualization": {"Radius": r6(wh.get("rim_diameter", 0.4) / 2), "Width": r6(wh.get("rim_width", 0.2))}}
        wf = f"{name}/wheel/{name}_wheel{ai + 1}.json"
        out_files[wf] = wheel
        wheel_by_axle[a] = wheel
        axle = {"Suspension Input File": d, "Suspension Location": [r6(ax_x), 0, 0], "Left Wheel Input File": wf, "Right Wheel Input File": wf}
        br = st.get("brake")
        if br and br.get("max_torque") is not None:
            bf = f"{name}/brake/{name}_brake{ai + 1}.json"
            out_files[bf] = {"Name": f"{name} brake", "Type": "Brake", "Template": "BrakeSimple", "Maximum Torque": br["max_torque"]}
            axle["Left Brake Input File"] = axle["Right Brake Input File"] = bf
        else:
            rep.add("lost", "brake", f"axle {a}: brake without max_torque (disc geometry / pad friction) cannot be turned into a Chrono brake; none written")
        if steered:
            axle["Steering Index"] = 0
        veh_axles.append(axle)
    # ---- steering ---------------------------------------------------------------------------------------------------
    veh_steer = []
    if pitman:
        sf = f"{name}/steering/{name}_pitman.json"
        out_files[sf] = pitman["raw"]
        veh_steer.append({"Input File": sf, "Location": r6v(pitman["location"]), "Orientation": pitman["orientation"]})
    elif rack:
        b, j = rack
        stg = doc.get("steering") or {}
        l2l = stg.get("lock_to_lock") or math.radians(60)
        travel = stg.get("rack_travel") or 0.2
        rb = bodies[b]
        span = 0.0
        for jj in joints:
            if b in (jj["body_a"], jj["body_b"]) and jj is not j:
                span = max(span, abs(jj["frame_a"]["position"][1]))
        steer = {"Name": f"{name} rack and pinion", "Type": "Steering", "Template": "RackPinion",
                 "Steering Link": {"Mass": rb["mass"], "COM": 0, "Inertia": [1, 1, 1], "Radius": 0.03, "Length": r6(max(2 * span, 0.1))},
                 "Pinion": {"Radius": r6(travel / l2l), "Maximum Angle (deg)": r6(math.degrees(l2l / 2))}}
        rep.add("assumed", "steering", "RackPinion: pinion radius = rack_travel / lock_to_lock, maximum angle = lock_to_lock / 2; the steering wheel, column and "
                                       "overall_ratio have no Chrono counterpart (the driver input is the pinion angle). Link inertia 1 kg m^2 (not in SVJ)")
        sf = f"{name}/steering/{name}_rackpinion.json"
        out_files[sf] = steer
        veh_steer.append({"Input File": sf, "Location": r6v(C(j["frame_a"]["position"])), "Orientation": [1, 0, 0, 0]})
    # ---- chassis (the remainder) ----------------------------------------------------------------------------------------
    M = ch["mass_total"]
    written = {s_["wheel_body"] for s_ in stations} | ({rack[0]} if rack else set()) | (shared if pitman else set())
    for a_ in local:
        for c_ in local[a_].values():
            written |= c_
    mbs = [m for k, m in bodies.items() if m.get("mass") and k in written]
    unwritten = [k for k, m in bodies.items() if m.get("mass") and k not in written]
    if unwritten:
        rep.add("lost", "chassis", "bodies not expressible in Chrono (" + ", ".join(unwritten) + ") stay in the chassis mass and inertia")
    mr = M - sum(m["mass"] for m in mbs)
    cg = ch["center_of_gravity"]
    if mr <= 0:
        raise ConversionError("the bodies in mass_bodies weigh more than mass_total; no chassis remainder")
    com = vscale(vsub(vscale(cg, M), [sum(m["mass"] * m["position"][k] for m in mbs) for k in range(3)]), 1.0 / mr)
    Itot = inertia_from_svj(ch["inertia"])
    Ir = Itot
    for m in mbs:
        Ii = inertia_from_svj(m["inertia"]) if m.get("inertia") else [[0.0] * 3 for _ in range(3)]
        Ir = [[Ir[i][k] - Ii[i][k] - parallel_axis(m["mass"], vsub(m["position"], cg))[i][k] for k in range(3)] for i in range(3)]
    Ir = [[Ir[i][k] - parallel_axis(mr, vsub(com, cg))[i][k] for k in range(3)] for i in range(3)]
    dr = (Ir[0][0], Ir[1][1], Ir[2][2])
    if min(dr) <= 0:
        rep.add("assumed", "chassis", "the remainder inertia is not positive after removing the bodies; the diagonal is clamped to 1 kg m^2")
        dr = tuple(max(v, 1.0) for v in dr)
    chassis = {"Name": f"{name} chassis", "Type": "Chassis", "Template": "RigidChassis",
               "Components": [{"Centroidal Frame": {"Location": r6v(C(com)), "Orientation": [1, 0, 0, 0]}, "Mass": r6(mr),
                               "Moments of Inertia": [r6(v) for v in dr], "Products of Inertia": [r6(Ir[0][1]), r6(Ir[0][2]), r6(Ir[1][2])],
                               "Void": False}],
               "Driver Position": (xc.get("chassis") or {}).get("Driver Position", {"Location": [0.0, 0.5, 1.2], "Orientation": [1, 0, 0, 0]})}
    cf = f"{name}/chassis/{name}_chassis.json"
    out_files[cf] = chassis
    rep.add("converted", "chassis", "Chrono chassis = SVJ total minus the bodies in mass_bodies (suspension, steering, wheel assemblies), by parallel-axis subtraction")
    # ---- tyre -----------------------------------------------------------------------------------------------------------
    if tire_set:
        dim, con = tire_set.get("dimensions", {}), tire_set.get("construction", {})
        R0 = dim.get("overall_diameter", 0.8) / 2
        Rr = (tire_set.get("rim") or {}).get("diameter", 0.4) / 2
        m_t = con.get("mass", 10.0)
        spin = m_t * 0.5 * (R0 ** 2 + Rr ** 2)
        tire = {"Name": f"{name} tire", "Type": "Tire", "Template": "TMeasyTire",
                "Design": {"Unloaded Radius [m]": r6(R0), "Mass [kg]": m_t, "Inertia [kg.m2]": [r6(spin / 2), r6(spin), r6(spin / 2)],
                           "Width [m]": r6(dim.get("section_width", 0.2)), "Rim Radius [m]": r6(Rr)},
                "Coefficient of Friction": r6((tire_set.get("pacejka", {}).get("lateral", {}) or {}).get("pDy1", 0.8)),
                "Rolling Resistance Coefficient": 0.015, "Vehicle Type": "Passenger",
                "Maximum Bearing Capacity [N]": (tire_set.get("reference") or {}).get("load", 4000.0)}
        tf = f"{name}/tire/{name}_tmeasy.json"
        out_files[tf] = tire
        rep.add("assumed", "tyre", "tyre written as TMeasyTire from the geometry, mass and friction (pDy1) of the SVJ set; Chrono derives its stiffness from the "
                                   "bearing capacity (the reference load), so vertical_stiffness, damping and the Pacejka coefficients are not carried. The tyre "
                                   "file is not referenced by the vehicle file (Chrono attaches tyres in code: ChWheeledVehicle::InitializeTire)")
        rep.add("lost", "tyre", "Pacejka coefficients: Pac02 export (.tir file with SAE signs, inverse of tire_model.to_iso_set) is not implemented")
    restore_meshes(doc, svj_dir, outdir, name, rep, chassis, wheel_by_axle, tire)
    # ---- driveline / powertrain -------------------------------------------------------------------------------------
    pt = doc.get("powertrain") or {}
    drv = {}
    diffs = pt.get("differentials") or []
    if diffs:
        raw = ((xc.get("driveline") or {}).get("raw")) or {}
        fd = diffs[0].get("final_drive")
        driveline = {"Name": f"{name} driveline", "Type": "Driveline", "Template": "ShaftsDriveline2WD",
                     "Shaft Direction": {"Motor Block": [1, 0, 0], "Axle": [0, 1, 0]},
                     "Shaft Inertia": raw.get("Shaft Inertia", {"Driveshaft": 0.5, "Differential Box": 0.6}),
                     "Gear Ratio": {"Conical Gear": r6(1.0 / fd) if fd else 0.2},
                     "Axle Differential Locking Limit": raw.get("Axle Differential Locking Limit", 100)}
        df = f"{name}/driveline/{name}_driveline.json"
        out_files[df] = driveline
        driven = (xc.get("driveline") or {}).get("driven_axles") or [len(order) - 1 if diffs[0].get("location") != "front" else 0]
        drv = {"Input File": df, "Suspension Indexes": driven}
        rep.add("converted", "powertrain", "differentials[0].final_drive -> ShaftsDriveline2WD conical gear (inverted: Chrono is output/input)")
        if len(diffs) > 1 or pt.get("layout") in ("AWD", "4WD"):
            rep.add("lost", "powertrain", "only a two-wheel-drive shafts driveline is written; further differentials / transfer case are not")
    else:
        rep.add("lost", "powertrain", "no differentials in the SVJ file: no driveline written")
    for k in ("engine", "transmission", "gearbox"):
        if pt.get(k):
            rep.add("lost", "powertrain", f"{k}: Chrono engine / transmission files (EngineSimpleMap, AutomaticTransmissionSimpleMap) are not generated")
    # ---- vehicle ------------------------------------------------------------------------------------------------------------
    veh = {"Name": name, "Type": "Vehicle", "Template": "WheeledVehicle", "Chassis": {"Input File": cf}, "Axles": veh_axles}
    if veh_steer:
        veh["Steering Subsystems"] = veh_steer
    veh["Wheelbase"] = ch.get("wheelbase")
    if drv:
        veh["Driveline"] = drv
    for k in ("anti_roll_bars",):
        if doc.get(k):
            rep.add("lost", "suspension", "anti_roll_bars[] are not written (Chrono's anti-roll bar is a separate subsystem attached in code)")
    out_files[f"{name}/vehicle/{name}_Vehicle.json"] = veh
    meta = doc.get("_metadata", {})
    for rel, obj in out_files.items():
        _write_json(os.path.join(outdir, rel), obj)
    notice = os.path.join(outdir, name, "README.txt")
    with open(notice, "w", encoding="utf-8") as f:
        f.write(f"Chrono::Vehicle JSON files generated from the SVJ file '{meta.get('description', name)}' by chrono_convert.py.\n"
                "Set the Chrono vehicle data path to this folder; the vehicle file is vehicle/" + name + "_Vehicle.json.\n"
                "Tyres are not referenced by the vehicle file; attach tire/" + name + "_tmeasy.json in code.\n"
                "Check the conversion report for what could not be written.\n")
    return os.path.join(outdir, f"{name}/vehicle/{name}_Vehicle.json")


def r6v(v):
    return [r6(c) for c in v]



# ======================================================================================================================
# Meshes: Wavefront OBJ (Chrono) <-> glTF binary (SVJ visual binding, spec section 22)
# ======================================================================================================================
# Vertices are stored in the mesh's own (Chrono, ISO) axes mapped to glTF Y-up / -Z forward (spec 22.4); the pose of the
# part is the node transform. Going back, the same map is undone, so a vertex survives a round trip to float32.

_P_GL = [[0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]]       # v_gltf = P v_iso   (x_g = -y, y_g = z, z_g = -x)
GLTF_FRAME = {"up": "Y", "forward": "-Z", "handedness": "right"}


def _to_gl(v): return [-v[1], v[2], -v[0]]
def _from_gl(g): return [-g[2], -g[0], g[1]]


def read_mtl(path):
    """Wavefront .mtl -> {material: (r, g, b, a)} (diffuse colour and dissolve; textures are not read)."""
    out, cur = {}, None
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            if t[0] == "newmtl" and len(t) > 1:
                cur = t[1]
                out[cur] = [0.8, 0.8, 0.8, 1.0]
            elif cur and t[0] == "Kd" and len(t) >= 4:
                out[cur][:3] = [float(x) for x in t[1:4]]
            elif cur and t[0] == "d" and len(t) >= 2:
                out[cur][3] = float(t[1])
    return {k: tuple(v) for k, v in out.items()}


def read_obj(path):
    """Wavefront OBJ -> {'prims': [{'mat': name, 'color': rgba, 'pos': [[x,y,z]..], 'nrm': [...] or None, 'idx': [i..]}], 'textures': bool}.
    One primitive per material; vertices are unified on (position, normal); polygons are fan-triangulated."""
    P, N = [], []
    groups, order = {}, []
    mat, mtl = "default", {}
    textured = False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line or line[0] == "#":
                continue
            t = line.split()
            if not t:
                continue
            k = t[0]
            if k == "v":
                P.append((float(t[1]), float(t[2]), float(t[3])))
            elif k == "vn":
                N.append((float(t[1]), float(t[2]), float(t[3])))
            elif k == "usemtl" and len(t) > 1:
                mat = t[1]
            elif k == "mtllib" and len(t) > 1:
                mp = os.path.join(os.path.dirname(path), t[1])
                mtl.update(read_mtl(mp))
                if os.path.exists(mp) and any(l.lstrip().lower().startswith("map_") for l in open(mp, encoding="utf-8", errors="replace")):
                    textured = True
            elif k == "f":
                g = groups.get(mat)
                if g is None:
                    g = groups[mat] = {"pos": [], "nrm": [], "idx": [], "map": {}, "has_n": True}
                    order.append(mat)
                refs = []
                for tok in t[1:]:
                    a = tok.split("/")
                    vi = int(a[0])
                    vi = vi - 1 if vi > 0 else len(P) + vi
                    ni = None
                    if len(a) > 2 and a[2]:
                        ni = int(a[2])
                        ni = ni - 1 if ni > 0 else len(N) + ni
                    key = (vi, ni)
                    j = g["map"].get(key)
                    if j is None:
                        j = len(g["pos"])
                        g["map"][key] = j
                        g["pos"].append(P[vi])
                        if ni is None:
                            g["has_n"] = False
                            g["nrm"].append((0.0, 0.0, 1.0))
                        else:
                            g["nrm"].append(N[ni])
                    refs.append(j)
                for i in range(1, len(refs) - 1):
                    g["idx"] += [refs[0], refs[i], refs[i + 1]]
    prims = []
    for m in order:
        g = groups[m]
        prims.append({"mat": m, "color": mtl.get(m, (0.8, 0.8, 0.8, 1.0)), "pos": [list(p) for p in g["pos"]],
                      "nrm": [list(n) for n in g["nrm"]] if g["has_n"] else None, "idx": g["idx"]})
    return {"prims": prims, "textures": textured}


def write_obj(path, prims, mtl_name=None):
    """Write primitives back to an OBJ (+ .mtl with the diffuse colours)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    mtl_name = mtl_name or stem + ".mtl"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"mtllib {mtl_name}\n")
        base_v = base_n = 0
        for p in prims:
            f.write(f"usemtl {p['mat']}\n")
            for v in p["pos"]:
                f.write("v %.9g %.9g %.9g\n" % tuple(v))
            if p["nrm"]:
                for n in p["nrm"]:
                    f.write("vn %.9g %.9g %.9g\n" % tuple(n))
            idx = p["idx"]
            for i in range(0, len(idx), 3):
                tri = [idx[i] + 1 + base_v, idx[i + 1] + 1 + base_v, idx[i + 2] + 1 + base_v]
                if p["nrm"]:
                    f.write("f " + " ".join(f"{a}//{a - base_v + base_n}" for a in tri) + "\n")
                else:
                    f.write("f " + " ".join(str(a) for a in tri) + "\n")
            base_v += len(p["pos"])
            base_n += len(p["nrm"]) if p["nrm"] else 0
    with open(os.path.join(os.path.dirname(path), mtl_name), "w", encoding="utf-8", newline="\n") as f:
        for p in prims:
            r, g, b, a = p["color"]
            f.write(f"newmtl {p['mat']}\nKd {r:.6g} {g:.6g} {b:.6g}\nd {a:.6g}\n\n")


def _pad4(b, fill=b"\0"):
    return b + fill * (-len(b) % 4)


def pose_to_gl_node(pos, R):
    """glTF node transform of an ISO pose (position, 3x3 rotation): translation P p, rotation P R P^T."""
    P = _P_GL
    Rg = mmul(mmul(P, R), mT(P))
    w, x, y, z = mat_to_q(Rg)
    return {"translation": [r6(c) for c in _to_gl(pos)], "rotation": [round(x, 9), round(y, 9), round(z, 9), round(w, 9)]}


def write_glb(meshes, nodes):
    """meshes: [{'name', 'prims': [...]}]; nodes: [{'name', 'pose': (pos, R) | None, 'mesh': index | None, 'extras': {...}, 'children': [node...]}]
    (root nodes). Returns the bytes of a .glb."""
    binbuf = bytearray()
    views, accs, mats, gl_meshes, mat_ix = [], [], [], [], {}

    def add_view(data, target):
        off = len(binbuf)
        binbuf.extend(_pad4(bytes(data)))
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(views) - 1

    for m in meshes:
        prims = []
        for p in m["prims"]:
            pos = [_to_gl(v) for v in p["pos"]]
            flat = [c for v in pos for c in v]
            lo = [min(v[i] for v in pos) for i in range(3)]
            hi = [max(v[i] for v in pos) for i in range(3)]
            accs.append({"bufferView": add_view(struct.pack(f"<{len(flat)}f", *flat), 34962), "componentType": 5126,
                         "count": len(pos), "type": "VEC3", "min": lo, "max": hi})
            attrs = {"POSITION": len(accs) - 1}
            if p["nrm"]:
                nf = [c for v in p["nrm"] for c in _to_gl(v)]
                accs.append({"bufferView": add_view(struct.pack(f"<{len(nf)}f", *nf), 34962), "componentType": 5126,
                             "count": len(p["nrm"]), "type": "VEC3"})
                attrs["NORMAL"] = len(accs) - 1
            idx = p["idx"]
            accs.append({"bufferView": add_view(struct.pack(f"<{len(idx)}I", *idx), 34963), "componentType": 5125,
                         "count": len(idx), "type": "SCALAR"})
            key = (p["mat"], tuple(p["color"]))
            if key not in mat_ix:
                mat_ix[key] = len(mats)
                r, g, b, a = p["color"]
                mats.append({"name": p["mat"], "pbrMetallicRoughness": {"baseColorFactor": [r, g, b, a], "metallicFactor": 0.0, "roughnessFactor": 0.9},
                             **({"alphaMode": "BLEND"} if a < 1.0 else {})})
            prims.append({"attributes": attrs, "indices": len(accs) - 1, "material": mat_ix[key]})
        gl_meshes.append({"name": m["name"], "primitives": prims})

    gl_nodes, roots = [], []

    def emit(n):
        d = {"name": n["name"]}
        if n.get("pose") is not None:
            d.update(pose_to_gl_node(*n["pose"]))
        if n.get("mesh") is not None:
            d["mesh"] = n["mesh"]
        if n.get("extras"):
            d["extras"] = n["extras"]
        ix = len(gl_nodes)
        gl_nodes.append(d)
        kids = [emit(c) for c in n.get("children", [])]
        if kids:
            d["children"] = kids
        return ix

    for n in nodes:
        roots.append(emit(n))
    doc = {"asset": {"version": "2.0", "generator": "chrono_convert.py"}, "scene": 0, "scenes": [{"nodes": roots}], "nodes": gl_nodes,
           "meshes": gl_meshes, "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(binbuf)}]}
    js = _pad4(json.dumps(doc, separators=(",", ":")).encode("utf-8"), b" ")
    bn = bytes(binbuf)
    total = 12 + 8 + len(js) + 8 + len(bn)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js +
            struct.pack("<I4s", len(bn), b"BIN\0") + bn)


def read_glb(data):
    """Read a .glb written by write_glb (triangle primitives, float32 positions / normals, uint16 / uint32 indices).
    Returns (json, [{'name', 'extras', 'pos', 'rot', 'prims': [...]}] for every node that has a mesh, in ISO axes: positions are mapped back)."""
    if data[:4] != b"glTF":
        raise ConversionError("not a binary glTF (.glb) file")
    jl = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + jl].decode("utf-8"))
    bl = struct.unpack_from("<I", data, 20 + jl)[0]
    bn = data[28 + jl:28 + jl + bl]

    def acc(i):
        a = js["accessors"][i]
        v = js["bufferViews"][a["bufferView"]]
        off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        ct = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2)}[a["componentType"]]
        n = a["count"] * {"SCALAR": 1, "VEC3": 3}[a["type"]]
        vals = struct.unpack_from(f"<{n}{ct[0]}", bn, off)
        return vals if a["type"] == "SCALAR" else [list(vals[k:k + 3]) for k in range(0, n, 3)]

    out = []

    def world(ix, parent):
        n = js["nodes"][ix]
        t = n.get("translation", [0, 0, 0])
        q = n.get("rotation", [0, 0, 0, 1])
        Rl = q_to_mat([q[3], q[0], q[1], q[2]])
        pos = [parent[0][i] + sum(parent[1][i][k] * t[k] for k in range(3)) for i in range(3)]
        R = mmul(parent[1], Rl)
        if "mesh" in n:
            prims = []
            for p in js["meshes"][n["mesh"]]["primitives"]:
                m = js["materials"][p["material"]] if "material" in p else {"name": "default"}
                col = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.8, 0.8, 0.8, 1.0])
                prims.append({"mat": m.get("name", "default"), "color": tuple(col),
                              "pos": [_from_gl(v) for v in acc(p["attributes"]["POSITION"])],
                              "nrm": [_from_gl(v) for v in acc(p["attributes"]["NORMAL"])] if "NORMAL" in p["attributes"] else None,
                              "idx": list(acc(p["indices"]))})
            out.append({"name": n.get("name"), "extras": n.get("extras", {}), "world_gl": (pos, R), "prims": prims, "node": ix})
        for c in n.get("children", []):
            world(c, (pos, R))

    for r in js["scenes"][js.get("scene", 0)]["nodes"]:
        world(r, ([0.0, 0.0, 0.0], eye()))
    return js, out


def iso_pose_of_gl(world_gl):
    """(position, rotation) of a glTF world pose back in ISO axes."""
    pos, R = world_gl
    P = _P_GL
    return _from_gl(pos), mmul(mmul(mT(P), R), P)


def find_mesh_file(root, rel):
    """Chrono names meshes relative to the vehicle data folder or to the data folder above it."""
    cands = [os.path.join(root, rel), os.path.join(os.path.dirname(os.path.abspath(root)), rel), os.path.join(root, "..", "..", rel)]
    if rel.replace(chr(92), "/").startswith("vehicle/"):
        cands.insert(0, os.path.join(root, rel[len("vehicle/"):]))
    for p in cands:
        p = os.path.normpath(p)
        if os.path.exists(p):
            return p
    return None


def _wheel_node_name(sid):
    return f"SVJ::wheel::wheel_{sid.lower()}"


def attach_meshes(doc, data, V, stations, shift, rep, mesh_dir, asset_name):
    """Read the Chrono chassis, rim and tyre meshes, write one .glb and add assets / visual bindings / x_chrono.meshes."""
    chassis = data.read(V["Chassis"]["Input File"])
    cm = (chassis.get("Visualization") or {}).get("Mesh")
    # per-station wheel and tyre mesh files
    rim_rel, tire_rel = {}, {}
    for st in stations:
        ax = st["ax"]
        wf = ax.get("Left Wheel Input File" if st["side"] == "L" else "Right Wheel Input File")
        if wf:
            rim_rel[st["id"]] = (data.read(wf).get("Visualization") or {}).get("Mesh Filename")
    tj = getattr(data, "tire_json", None) or {}
    tv = tj.get("Visualization") or {}
    for st in stations:
        tire_rel[st["id"]] = tv.get("Mesh Filename Left" if st["side"] == "L" else "Mesh Filename Right") or tv.get("Mesh Filename")
    cache = {}
    textured = []

    def load(rel):
        if not rel:
            return None
        if rel in cache:
            return cache[rel]
        p = find_mesh_file(data.root, rel)
        if not p:
            rep.add("lost", "mesh", f"mesh file {rel} named by the Chrono data is not in the data folder")
            cache[rel] = None
            return None
        m = read_obj(p)
        if m["textures"]:
            textured.append(rel)
        cache[rel] = m
        return m

    meshes, mesh_ix, nodes = [], {}, []
    names = {}

    def mesh_of(rel):
        m = load(rel)
        if m is None:
            return None
        if rel not in mesh_ix:
            mesh_ix[rel] = len(meshes)
            meshes.append({"name": os.path.splitext(os.path.basename(rel))[0], "prims": m["prims"]})
        return mesh_ix[rel]

    kept = {"chassis": None, "rim": {}, "tire": {}}
    ci = mesh_of(cm)
    if ci is not None:
        nodes.append({"name": "SVJ::body::chassis", "pose": (vscale(shift, -1.0), eye()), "mesh": ci,
                      "extras": {"svj_node": "SVJ::body::chassis", "chrono_mesh": cm}})
        kept["chassis"] = cm
    wheel_nodes = {}
    for st in stations:
        S = st["susp"]
        side_rot = eye() if st["side"] == "L" else rot_z(math.pi)
        pose = (vsub(S.wheel["pos"], shift), mmul(S.wheel["R"], side_rot))
        kids = []
        for kind, rel in (("rim", rim_rel.get(st["id"])), ("tire", tire_rel.get(st["id"]))):
            mi = mesh_of(rel)
            if mi is not None:
                kids.append({"name": f"wheel_{st['id'].lower()}_{kind}", "mesh": mi,
                             "extras": {"chrono_mesh": rel, "chrono_role": kind, "chrono_part_of": _wheel_node_name(st["id"])}})
                kept[kind][st["id"]] = rel
        if kids:
            nm = _wheel_node_name(st["id"])
            nodes.append({"name": nm, "pose": pose, "extras": {"svj_node": nm}, "children": kids})
            wheel_nodes[st["id"]] = nm
    if not nodes:
        return
    glb = write_glb(meshes, nodes)
    os.makedirs(mesh_dir, exist_ok=True)
    path = os.path.join(mesh_dir, asset_name + ".glb")
    if os.path.exists(path) and open(path, "rb").read() != glb:
        asset_name += "_" + hashlib.sha1(glb).hexdigest()[:6]            # same name, different content: keep both
        path = os.path.join(mesh_dir, asset_name + ".glb")
    with open(path, "wb") as f:
        f.write(glb)
    uri = f"meshes/{asset_name}.glb"
    doc["assets"] = {"meshes": [{"id": asset_name, "uri": uri, "description": "Chrono OBJ meshes converted by chrono_convert.py (chassis, rims, tyres)"}]}
    if kept["chassis"]:
        doc["chassis"]["visual"] = {"mesh_ref": asset_name, "node": "SVJ::body::chassis"}
    for w in doc["wheel_stations"]:
        if w["id"] in wheel_nodes:
            w["wheel"]["visual"] = {"mesh_ref": asset_name, "node": wheel_nodes[w["id"]]}
    doc["_metadata"]["coordinate_system"] = dict(GLTF_FRAME)
    doc["_metadata"]["physics_frame"] = "ISO_8855"
    doc["x_chrono"]["meshes"] = {"chassis": kept["chassis"], "rim": kept["rim"], "tire": kept["tire"],
                                 "note": "Chrono mesh files as named in the Chrono JSON; the right-side rim and tyre are rotated pi about the spindle Z axis (ChWheel.cpp, ChTire.cpp)"}
    rep.add("converted", "mesh", f"{len(meshes)} OBJ mesh(es) -> {uri}: vertices mapped to glTF axes, each mesh placed by a node transform (chassis at the chassis "
                                 "frame, rim and tyre at the spindle; right side rotated pi about the spindle Z axis as Chrono does); materials keep the diffuse colour")
    if textured:
        rep.add("lost", "mesh", "texture maps (map_Kd ...) of the materials are not carried, only the diffuse colour; UV coordinates are dropped: " + ", ".join(sorted(set(textured))))
    rep.add("lost", "mesh", "Chrono draws suspension arms, rods, springs and the steering with primitives (cylinders, spheres): no mesh, so no visual binding for them")


def restore_meshes(doc, svj_dir, outdir, name, rep, chassis_json, wheel_jsons, tire_json):
    """SVJ -> Chrono: write the OBJ files of the bound glTF meshes under <outdir>/<name>/meshes and set the Chrono visualization entries."""
    assets = {a["id"]: a for a in (doc.get("assets") or {}).get("meshes", [])}
    if not assets:
        return
    keep = (doc.get("x_chrono") or {}).get("meshes") or {}
    files = {}

    def glb_of(ref):
        if ref not in files:
            a = assets.get(ref)
            p = os.path.join(svj_dir or ".", a["uri"]) if a else None
            if not p or not os.path.exists(p) or not p.lower().endswith(".glb"):
                rep.add("lost", "mesh", f"asset {ref!r} is not a readable .glb next to the SVJ file; meshes not written")
                files[ref] = None
            else:
                files[ref] = read_glb(open(p, "rb").read())[1]
        return files[ref]

    def write_part(rel_hint, prims, tag):
        stem = os.path.splitext(os.path.basename(rel_hint or tag))[0]
        rel = f"{name}/meshes/{stem}.obj"
        write_obj(os.path.join(outdir, rel), prims)
        return rel

    vis = (doc["chassis"].get("visual") or {})
    if vis.get("node") and glb_of(vis.get("mesh_ref") or next(iter(assets))):
        for nd in glb_of(vis.get("mesh_ref") or next(iter(assets))):
            if nd["name"] == vis["node"]:
                pos, R = iso_pose_of_gl(nd["world_gl"])
                shift = (doc.get("x_chrono", {}).get("frame") or {}).get("shift_to_svj_origin") or [0, 0, 0]
                prims = nd["prims"]
                off = vadd(pos, shift)
                if vnorm(off) > 1e-9 or any(abs(R[i][j] - (i == j)) > 1e-9 for i in range(3) for j in range(3)):
                    prims = [{**p, "pos": [vadd(mvec(R, v), off) for v in p["pos"]],
                              "nrm": [mvec(R, n) for n in p["nrm"]] if p["nrm"] else None} for p in prims]
                rel = write_part(keep.get("chassis"), prims, "chassis")
                chassis_json["Visualization"] = {**(chassis_json.get("Visualization") or {}), "Mesh": "vehicle/" + rel}
                rep.add("converted", "mesh", "chassis mesh: the node is baked back into the Chrono chassis reference frame and written as OBJ")
    for st in doc["wheel_stations"]:
        v = (st.get("wheel") or {}).get("visual") or {}
        nodes = glb_of(v.get("mesh_ref") or next(iter(assets))) if v.get("node") else None
        if not nodes:
            continue
        for nd in nodes:
            if nd["extras"].get("chrono_part_of") != v["node"]:
                continue
            role = nd["extras"].get("chrono_role")
            rel_old = nd["extras"].get("chrono_mesh")
            rel = write_part(rel_old, nd["prims"], f"{st['id'].lower()}_{role}")
            side = st["side"]
            if role == "rim":
                wheel_jsons.setdefault(st["axle"], {}).setdefault("Visualization", {})["Mesh Filename"] = rel
            elif role == "tire":
                tire_json.setdefault("Visualization", {})["Mesh Filename Left" if side == "L" else "Mesh Filename Right"] = rel
    if any(files.values()):
        rep.add("converted", "mesh", "rim and tyre meshes written as OBJ in the spindle frame (the node pose carries the spindle; the right side keeps the pi rotation Chrono applies)")



def main(argv=None):
    ap = argparse.ArgumentParser(description="SVJ <-> Chrono::Vehicle JSON converter")
    ap.add_argument("--to", choices=("svj", "chrono"), required=True)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--data-root", help="Chrono vehicle data directory (the folder that holds hmmwv/, sedan/, ...)")
    ap.add_argument("--tire", help="Chrono tyre JSON (relative to the data root)")
    ap.add_argument("--engine")
    ap.add_argument("--transmission")
    ap.add_argument("--name", help="--to chrono: name of the generated vehicle folder")
    ap.add_argument("--tyre-camber", choices=("physical", "faithful"), default="physical",
                    help="Pac02 camber sign: 'physical' passes the tyre sign oracle (default), 'faithful' keeps Chrono's literal sign")
    ap.add_argument("--synthetic", action="store_true", help="the input is synthetic test data, not Chrono data: no Chrono attribution in _metadata")
    ap.add_argument("--no-meshes", action="store_true", help="do not convert the OBJ meshes to glTF (Chrono to SVJ)")
    ap.add_argument("--report", help="write the conversion report as JSON")
    args = ap.parse_args(argv)
    try:
        if args.to == "svj":
            doc, rep = chrono_to_svj(args.input, args.data_root, args.tire, args.engine, args.transmission, camber=args.tyre_camber, origin="synthetic" if args.synthetic else "chrono",
                                      mesh_dir=None if args.no_meshes else os.path.join(os.path.dirname(os.path.abspath(args.output)), "meshes"))
            finish_steering(doc, rep)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
                f.write(chr(10))
        else:
            with open(args.input, encoding="utf-8") as f:
                svj = json.load(f)
            rep = Report("svj->chrono")
            vf = svj_to_chrono(svj, args.output, args.name, rep, svj_dir=os.path.dirname(os.path.abspath(args.input)))
            print("vehicle file:", vf)
    except (ConversionError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(rep.text())
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(rep.to_json(), f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
