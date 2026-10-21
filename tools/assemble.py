#!/usr/bin/env python3
"""
SVJ attachments and combinations (spec §27) — fit units onto a vehicle and build one composite document.

A unit is an ordinary SVJ file: a tractor, a front loader, a mower, a tipper body, a trailer. A unit declares
`interfaces[]` (named frames with a role and a size); two interfaces whose roles mate can be joined. The
join is a `joint` object, so the fitted unit moves like any other part (a rigid mount is `fixed`, a fifth wheel
is a `spherical` or `universal` joint, a drawbar eye a `spherical` joint...).

A combination is either
  * a `*.svj-combination.json` file listing `units[]`, `connections[]` and optional `poses[]`, or
  * a vehicle file with `attachments[]` (the shorthand: file path + the connections to this vehicle).

`assemble()` turns it into one SVJ document in the root unit's coordinates:
  * the root unit keeps its ids; every other unit's ids are qualified `unit.id` ('.' is reserved for this);
  * a unit is placed so the frames of its connected interfaces coincide (the reference pose);
  * a unit's chassis becomes a body `unit.chassis` carrying the mass not described by its `mass_bodies`;
  * every connection becomes a `joint` constraint; unit poses are kept as `unit.pose`;
  * mass_total and center_of_gravity are the combination's.
All the machinery of §24 (poses, CG and inertia per pose, element lengths, contacts, loop solver) then
works on the composite, and `x_assembled: true` marks it.

Usage:
    python tools/assemble.py combination.svj-combination.json [-o composite.svj.json]
    python tools/assemble.py vehicle_with_attachments.svj.json  [-o composite.svj.json]
"""

import copy
import json
import math
import os
import sys

try:                                           # inside svj-py
    from svj import constraints as cc
except ImportError:                            # running from tools/
    import constraints_check as cc

# ── interface vocabulary ──────────────────────────────────────────────────────
# role -> the role it mates with. A symmetric role mates with itself.
ROLE_MATES = {
    # road trailers and heavy haulage
    "fifth_wheel": "kingpin", "kingpin": "fifth_wheel",
    "drawbar_eye": "pintle_hook", "pintle_hook": "drawbar_eye",
    "ball_coupling": "ball_hitch", "ball_hitch": "ball_coupling",
    "gooseneck_ball": "gooseneck_coupler", "gooseneck_coupler": "gooseneck_ball",
    "turntable": "turntable",
    # agriculture
    "three_point_lower_link": "three_point_lower_pin", "three_point_lower_pin": "three_point_lower_link",
    "three_point_top_link": "three_point_top_pin", "three_point_top_pin": "three_point_top_link",
    "drawbar_clevis": "drawbar_pin", "drawbar_pin": "drawbar_clevis",
    "pto_shaft": "pto_stub", "pto_stub": "pto_shaft",
    "loader_mount": "loader_mount",
    # earthmoving and handling
    "quick_coupler": "quick_coupler_pin", "quick_coupler_pin": "quick_coupler",
    "fork_carriage": "fork_carriage", "boom_tip": "boom_tip",
    "crane_mount": "crane_mount", "body_mount": "body_mount",
    "bed_mount": "bed_mount", "pallet_fork_mount": "pallet_fork_mount",
    # military and construction
    "winch_mount": "winch_mount", "weapon_mount": "weapon_mount", "ring_mount": "ring_mount",
    "bridge_interface": "bridge_interface", "container_corner_casting": "container_twist_lock",
    "container_twist_lock": "container_corner_casting", "plough_blade_mount": "plough_blade_mount",
    "dozer_blade_mount": "dozer_blade_mount",
    # supply lines (hydraulics, air, electrics, data)
    "hydraulic_coupler": "hydraulic_coupler", "air_line_coupler": "air_line_coupler", "electrical_connector": "electrical_connector",
    # generic
    "generic_mount": "generic_mount",
}
GENDERS = ("socket", "plug", "symmetric")
SIZE_TOL = 0.0005            # m, for dimensions of the same name on both sides of a connection
_SIZE_EXACT = ("category", "class", "type", "standard")


# ── rotations and frames ──────────────────────────────────────────────────────
def qmul(a, b):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    return [w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2]


def mat_to_quat(R):
    tr = R[0][0] + R[1][1] + R[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = [(R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s]
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        q = [0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s, (R[2][1] - R[1][2]) / s]
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        q = [(R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s, (R[0][2] - R[2][0]) / s]
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
        q = [(R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s, (R[1][0] - R[0][1]) / s]
    n = math.sqrt(sum(v * v for v in q)) or 1.0
    return [v / n for v in q]


def _round(v, n=9):
    return [round(float(x), n) + 0.0 for x in v]


def _place_frame(T, pos, ori):
    """A frame (position, orientation quaternion) mapped through the rigid transform T = (R, t)."""
    R, t = T
    p = cc.apply(T, tuple(pos))
    q = qmul(mat_to_quat(R), list(ori or [0, 0, 0, 1]))
    return _round(p), _round(q)


def _inv(T):
    Rt = cc._tr(T[0])
    return Rt, tuple(-v for v in cc._mv(Rt, T[1]))


# ── interfaces ────────────────────────────────────────────────────────────────
def interfaces(doc):
    return {i.get("id"): i for i in (doc.get("interfaces") or []) if isinstance(i, dict)}


def interface_body(iface):
    return iface.get("body") or "chassis"


def interface_frame(doc, iface):
    """(position, orientation) of an interface in its own file's coordinates, or None."""
    fr = iface.get("frame")
    if isinstance(fr, dict) and isinstance(fr.get("position"), list):
        return list(fr["position"]), list(fr.get("orientation") or [0, 0, 0, 1])
    mk = iface.get("marker")
    if mk is not None:
        m = cc._marker(doc, interface_body(iface), mk)
        if m:
            return list(m["position"]), list(m.get("orientation") or [0, 0, 0, 1])
    return None


def mates(a, b):
    """(ok, reasons): whether two interfaces can be joined (roles mate, genders oppose, same-named sizes agree)."""
    why = []
    ra, rb = a.get("role"), b.get("role")
    if ROLE_MATES.get(ra) != rb:
        why.append(f"role '{ra}' does not mate with '{rb}'" + (f" (expects '{ROLE_MATES[ra]}')" if ra in ROLE_MATES else ""))
    ga, gb = a.get("gender", "symmetric"), b.get("gender", "symmetric")
    if ga == gb and ga != "symmetric":
        why.append(f"both interfaces are '{ga}'")
    sa, sb = a.get("size") or {}, b.get("size") or {}
    for k in sorted(set(sa) & set(sb)):
        va, vb = sa[k], sb[k]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if k.endswith("_max") or k.endswith("_min"):
                continue
            if abs(va - vb) > SIZE_TOL:
                why.append(f"size '{k}' differs ({va} vs {vb})")
        elif k in _SIZE_EXACT and va != vb:
            why.append(f"size '{k}' differs ({va} vs {vb})")
    return (not why), why


def check_interfaces(doc, where="interfaces"):
    """(errors, warnings) for the interfaces[] of one file."""
    errors, warnings = [], []
    seen = set()
    bodies = cc._bodies(doc)
    for i, ifc in enumerate(doc.get("interfaces") or []):
        w = f"{where}[{i}]"
        if not isinstance(ifc, dict):
            errors.append(f"{w}: must be an object")
            continue
        iid = ifc.get("id")
        if not isinstance(iid, str) or not iid:
            errors.append(f"{w}: missing id")
            continue
        w = f"{where} '{iid}'"
        if iid in seen:
            errors.append(f"{w}: duplicate id")
        seen.add(iid)
        if "." in iid:
            errors.append(f"{w}: '.' is reserved for qualified ids")
        role = ifc.get("role")
        if role not in ROLE_MATES:
            warnings.append(f"{w}: role '{role}' is not in the interface vocabulary (spec §27.2)")
        if ifc.get("gender", "symmetric") not in GENDERS:
            errors.append(f"{w}: gender must be one of {', '.join(GENDERS)}")
        body = interface_body(ifc)
        if body != "chassis" and body not in bodies:
            errors.append(f"{w}: body '{body}' is not a mass_bodies id")
        if interface_frame(doc, ifc) is None:
            errors.append(f"{w}: needs a `frame` or a `marker` that exists on body '{body}'")
    return errors, warnings


# ── combination model ─────────────────────────────────────────────────────────
def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _split(ref):
    unit, _, name = ref.partition(".")
    return unit, name


def combination_from_vehicle(doc, base_dir):
    """Turn a vehicle file with attachments[] into the combination model (units + connections)."""
    root_id = "host"
    units = [{"id": root_id, "doc": doc, "root": True}]
    conns = []
    for a in doc.get("attachments") or []:
        uid = a.get("id")
        path = os.path.join(base_dir, a.get("file", ""))
        units.append({"id": uid, "doc": _load(path), "file": a.get("file")})
        for k, c in enumerate(a.get("connections") or []):
            conns.append({"id": c.get("id") or f"{uid}_mount" + ("" if k == 0 else f"_{k + 1}"),
                          "a": f"{c.get('to_unit', root_id)}.{c.get('interface')}",
                          "b": f"{uid}.{c.get('attachment_interface')}",
                          "joint": c.get("joint") or {"joint_type": "fixed"}})
    return {"units": units, "connections": conns, "poses": [], "host_is_root_id": root_id}


def combination_from_file(path):
    comb = _load(path)
    base = os.path.dirname(os.path.abspath(path))
    units = []
    for u in comb.get("units") or []:
        units.append({"id": u.get("id"), "doc": _load(os.path.join(base, u.get("file", ""))), "file": u.get("file"),
                      "root": bool(u.get("root"))})
    if units and not any(u["root"] for u in units):
        units[0]["root"] = True
    return {"units": units, "connections": comb.get("connections") or [], "poses": comb.get("poses") or [],
            "name": comb.get("name"), "id": comb.get("id")}


def load_combination(path):
    doc = _load(path)
    if (doc.get("_metadata") or {}).get("format") == "svj-combination" or "units" in doc:
        return combination_from_file(path)
    return combination_from_vehicle(doc, os.path.dirname(os.path.abspath(path)))


def supply_shortfalls(a, b):
    """Messages for every quantity one interface demands (`demand`) that the other offers (`supply`) in a smaller amount."""
    out = []
    for x, y in ((a, b), (b, a)):
        for key, need in (x.get("demand") or {}).items():
            have = (y.get("supply") or {}).get(key)
            if isinstance(need, (int, float)) and isinstance(have, (int, float)) and need > have:
                out.append(f"'{x.get('id')}' demands {key} {need:g}, '{y.get('id')}' supplies {have:g}")
    return out


def check_combination(comb):
    """(errors, warnings) for a combination model: units, interfaces, roles, sizes, tree shape."""
    errors, warnings = [], []
    units = {u["id"]: u for u in comb["units"]}
    if len(units) != len(comb["units"]):
        errors.append("combination: duplicate unit ids")
    roots = [u for u in comb["units"] if u.get("root")]
    if len(roots) != 1:
        errors.append(f"combination: exactly one root unit is required, found {len(roots)}")
    for u in comb["units"]:
        if "." in str(u["id"]):
            errors.append(f"unit '{u['id']}': '.' is reserved for qualified ids")
        e, w = check_interfaces(u["doc"], f"unit '{u['id']}' interfaces")
        errors += e
        warnings += w
    seen, edges = set(), []
    for c in comb["connections"]:
        cid = c.get("id")
        w = f"connection '{cid}'"
        if cid in seen:
            errors.append(f"{w}: duplicate id")
        seen.add(cid)
        ends = []
        for side in ("a", "b"):
            ref = c.get(side)
            if not isinstance(ref, str) or "." not in ref:
                errors.append(f"{w}: '{side}' must be 'unit.interface'")
                ends.append(None)
                continue
            uid, iname = _split(ref)
            ifc = interfaces((units.get(uid) or {}).get("doc", {})).get(iname)
            if uid not in units:
                errors.append(f"{w}: unit '{uid}' is not listed in units")
                ends.append(None)
            elif ifc is None:
                errors.append(f"{w}: unit '{uid}' has no interface '{iname}'")
                ends.append(None)
            else:
                ends.append((uid, ifc))
        if all(ends):
            if ends[0][0] == ends[1][0]:
                errors.append(f"{w}: both ends are on unit '{ends[0][0]}'")
            ok, why = mates(ends[0][1], ends[1][1])
            for r in why:
                errors.append(f"{w}: {r}")
            warnings += [f"{w}: {m}" for m in supply_shortfalls(ends[0][1], ends[1][1])]
            edges.append((ends[0][0], ends[1][0]))
        j = c.get("joint") or {"joint_type": "fixed"}
        if j.get("joint_type", "fixed") not in cc.DOF:
            errors.append(f"{w}: joint_type '{j.get('joint_type')}' is not a joint type")
    # tree: every unit reachable from the root, no loop between units
    if roots and not errors:
        adj = {u: set() for u in units}
        for a, b in edges:
            adj[a].add(b)
            adj[b].add(a)
        seen_u, stack = {roots[0]["id"]}, [roots[0]["id"]]
        while stack:
            for y in adj[stack.pop()]:
                if y not in seen_u:
                    seen_u.add(y)
                    stack.append(y)
        for u in units:
            if u not in seen_u:
                errors.append(f"unit '{u}' is not connected to the root unit")
        if len(edges) > len(units) - 1:
            warnings.append("combination: more connections than units - 1 (a closed loop between units); "
                            "the loop is assembled but not solved (§26 solves one mechanism at a time)")
        else:
            warnings += _capacity_warnings(comb, units, roots[0]["id"])
    return errors, warnings


G = 9.80665


def _capacity_warnings(comb, units, root):
    """Static check of `max_load.vertical_N`: the weight of everything hanging off a connection (the units on its far side
    from the root, for units that have no wheels of their own) against the smaller vertical rating of its two interfaces. A warning, not an error: it is a static
    estimate, and a rating may be a design figure the operator knowingly exceeds."""
    adj = {u: [] for u in units}
    for c in comb["connections"]:
        a, b = _split(c["a"])[0], _split(c["b"])[0]
        adj[a].append((b, c))
        adj[b].append((a, c))
    order, parent, stack = [], {root: None}, [root]
    while stack:
        u = stack.pop()
        order.append(u)
        for v, c in adj[u]:
            if v not in parent:
                parent[v] = (u, c)
                stack.append(v)
    mass = {u: float((units[u]["doc"].get("chassis") or {}).get("mass_total") or 0.0) for u in units}
    for u in reversed(order):
        if parent[u] is not None:
            mass[parent[u][0]] += mass[u]
    out = []
    for u in order:
        if parent[u] is None:
            continue
        c = parent[u][1]
        if units[u]["doc"].get("wheel_stations") or units[u]["doc"].get("axles"):
            continue                                    # a unit on its own wheels (a semi-trailer) carries most of its weight itself
        rated = []
        for side in ("a", "b"):
            uid, iname = _split(c[side])
            lim = ((interfaces(units[uid]["doc"]).get(iname) or {}).get("max_load") or {}).get("vertical_N")
            if isinstance(lim, (int, float)):
                rated.append(lim)
        if rated and mass[u] * G > min(rated):
            out.append(f"connection '{c.get('id')}': the {mass[u]:.0f} kg beyond it weighs {mass[u] * G:.0f} N, above the "
                       f"interface rating max_load.vertical_N {min(rated):.0f} N")
    return out


# ── assembly ──────────────────────────────────────────────────────────────────
def _placements(comb):
    """{unit_id: (R, t)}: each unit placed so its connected interface frames coincide with the host's."""
    units = {u["id"]: u for u in comb["units"]}
    root = next(u["id"] for u in comb["units"] if u.get("root"))
    T = {root: cc.IDENT}
    pending = list(comb["connections"])
    progress = True
    while pending and progress:
        progress = False
        for c in list(pending):
            ua, ia = _split(c["a"])
            ub, ib = _split(c["b"])
            if ua in T and ub not in T:
                known, other, ik, io = ua, ub, ia, ib
            elif ub in T and ua not in T:
                known, other, ik, io = ub, ua, ib, ia
            else:
                if ua in T and ub in T:
                    pending.remove(c)
                    progress = True
                continue
            fk = interface_frame(units[known]["doc"], interfaces(units[known]["doc"])[ik])
            fo = interface_frame(units[other]["doc"], interfaces(units[other]["doc"])[io])
            pw, qw = _place_frame(T[known], fk[0], fk[1])
            Rw = cc.quat_to_mat(qw)
            Ro = cc._mm(Rw, cc._tr(cc.quat_to_mat(fo[1])))
            T[other] = (Ro, cc._sub(tuple(pw), cc._mv(Ro, tuple(fo[0]))))
            pending.remove(c)
            progress = True
    return T


def _qid(uid, name):
    return f"{uid}.{name}"


def _map_body(uid, name):
    if name in (None, "ground"):
        return name
    return _qid(uid, name)


def _chassis_remainder(doc):
    """(mass, cg) of the chassis not described by mass_bodies, or (0, cg)."""
    ch = doc.get("chassis") or {}
    total = float(ch.get("mass_total") or 0.0)
    cg = list(ch.get("center_of_gravity") or [0.0, 0.0, 0.0])
    bodies = ch.get("mass_bodies") or []
    sm = sum(float(b.get("mass") or 0.0) for b in bodies if not b.get("x_derived") or b.get("mass"))
    rem = total - sm
    if rem <= 1e-6:
        return 0.0, cg
    mom = [total * cg[i] - sum(float(b.get("mass") or 0.0) * b["position"][i] for b in bodies if b.get("position")) for i in range(3)]
    return rem, [mom[i] / rem for i in range(3)]


def _place_collision(uid, proxies, T):
    """Collision proxies of a unit's body moved by T, ids qualified (spec 28)."""
    res = []
    for s in proxies or []:
        n = copy.deepcopy(s)
        n["id"] = _qid(uid, s["id"])
        p, q = _place_frame(T, s["position"], s.get("orientation"))
        n["position"], n["orientation"] = p, q
        res.append(n)
    return res


def _place_unit(uid, doc, T, out):
    """Append a non-root unit's bodies, constraints and poses to `out` (the composite), transformed by T."""
    ch = doc.get("chassis") or {}
    rem, cg = _chassis_remainder(doc)
    cid = _qid(uid, "chassis")
    pw, _ = _place_frame(T, cg, None)
    markers = {}
    for k, m in (ch.get("markers") or {}).items():
        p, q = _place_frame(T, m["position"], m.get("orientation"))
        markers[k] = {"position": p, "orientation": q}
    body = {"id": cid, "name": f"{uid} chassis", "category": "attachment", "mass": round(rem, 6), "position": pw}
    body["x_derived"] = True                 # generated from the unit's chassis: no tensor of its own
    if markers:
        body["markers"] = markers
    if ch.get("collision"):
        body["collision"] = _place_collision(uid, ch["collision"], T)
    out["chassis"]["mass_bodies"].append(body)
    for b in ch.get("mass_bodies") or []:
        nb = copy.deepcopy(b)
        nb["id"] = _qid(uid, b["id"])
        par = b.get("parent")
        nb["parent"] = cid if par in (None, "chassis") else _qid(uid, par)
        if b.get("position"):
            nb["position"] = _place_frame(T, b["position"], None)[0]
        nb["markers"] = {}
        for k, m in (b.get("markers") or {}).items():
            p, q = _place_frame(T, m["position"], m.get("orientation"))
            nb["markers"][k] = {"position": p, "orientation": q}
        if not nb["markers"]:
            nb.pop("markers")
        if b.get("inertia_orientation"):
            nb["inertia_orientation"] = _round(qmul(mat_to_quat(T[0]), b["inertia_orientation"]))
        nb.pop("visual", None)
        if b.get("collision"):
            nb["collision"] = _place_collision(uid, b["collision"], T)
        out["chassis"]["mass_bodies"].append(nb)
    for pair in doc.get("collision_ignore") or []:
        out.setdefault("collision_ignore", []).append([_qid(uid, x) for x in pair])
    for c in doc.get("constraints") or []:
        nc = copy.deepcopy(c)
        nc["id"] = _qid(uid, c["id"])
        for k in ("body_a", "body_b"):
            if k in nc:
                nc[k] = _map_body(uid, nc[k])
        for k in ("frame_a", "frame_b"):
            if isinstance(nc.get(k), dict):
                p, q = _place_frame(T, nc[k]["position"], nc[k].get("orientation"))
                nc[k] = {"position": p, "orientation": q}
        for k in ("joint_ref", "joint_a", "joint_b"):
            if isinstance(nc.get(k), str):
                nc[k] = _qid(uid, nc[k])
        out["constraints"].append(nc)
    for st in doc.get("wheel_stations") or []:
        ns = copy.deepcopy(st)
        ns["id"] = _qid(uid, st["id"])
        for k in ("wheel_body", "upright_body"):
            if isinstance(ns.get(k), str):
                ns[k] = _qid(uid, ns[k])
        if isinstance(ns.get("steering_joint"), str):
            ns["steering_joint"] = _qid(uid, ns["steering_joint"])
        ns.pop("coupling_ref", None)
        out.setdefault("wheel_stations", []).append(ns)
    for p in doc.get("poses") or []:
        np_ = copy.deepcopy(p)
        np_["id"] = _qid(uid, p["id"])
        np_["values"] = {_qid(uid, k): v for k, v in (p.get("values") or {}).items()}
        out["poses"].append(np_)
    return rem


def assemble(comb):
    """Build the composite SVJ document of a combination model. Returns (doc, notes)."""
    errors, _ = check_combination(comb)
    if errors:
        raise ValueError("invalid combination: " + "; ".join(errors[:5]))
    notes = []
    units = {u["id"]: u for u in comb["units"]}
    root = next(u for u in comb["units"] if u.get("root"))
    T = _placements(comb)
    out = copy.deepcopy(root["doc"])
    for k in ("interfaces", "attachments"):
        out.pop(k, None)
    out.setdefault("chassis", {}).setdefault("mass_bodies", [])
    out.setdefault("constraints", [])
    out.setdefault("poses", [])
    ch = out["chassis"]
    mass0 = float(ch.get("mass_total") or 0.0)
    cg0 = list(ch.get("center_of_gravity") or [0.0, 0.0, 0.0])
    msum, mom = mass0, [mass0 * v for v in cg0]
    parts = []          # (mass, cg in composite axes, inertia matrix about that cg in composite axes or None)
    i_root = cc._inertia_mat(ch.get("inertia"))
    parts.append((mass0, cg0, i_root))
    for u in comb["units"]:
        if u is root:
            continue
        doc = u["doc"]
        _place_unit(u["id"], doc, T[u["id"]], out)
        m = float((doc.get("chassis") or {}).get("mass_total") or 0.0)
        cg = _place_frame(T[u["id"]], (doc.get("chassis") or {}).get("center_of_gravity") or [0, 0, 0], None)[0]
        msum += m
        mom = [mom[i] + m * cg[i] for i in range(3)]
        iu = cc._inertia_mat((doc.get("chassis") or {}).get("inertia"))
        R = T[u["id"]][0]
        parts.append((m, cg, cc._mm(cc._mm(R, iu), cc._tr(R)) if iu is not None else None))
        for key in ("suspension", "powertrain", "tires", "brakes", "axles", "suspension_couplings"):
            if doc.get(key):
                notes.append(f"unit '{u['id']}': section '{key}' is not carried into the composite")
    ch["mass_total"] = round(msum, 6)
    ch["center_of_gravity"] = _round([v / msum for v in mom]) if msum else cg0
    ch.pop("inertia", None)
    if all(pt[2] is not None for pt in parts) and msum:
        cgc = ch["center_of_gravity"]
        acc = ((0.0,) * 3,) * 3
        for m, cg, im in parts:
            acc = cc._madd(acc, cc._madd(im, cc._steiner(m, cc._sub(tuple(cg), tuple(cgc)))))
        ch["inertia"] = cc._inertia_obj(acc)
    else:
        notes.append("chassis.inertia is not given for every unit: the composite has none, so pose_inertia() is unavailable")
    for c in comb["connections"]:
        ua, ia = _split(c["a"])
        ub, ib = _split(c["b"])
        ifa = interfaces(units[ua]["doc"])[ia]
        ifb = interfaces(units[ub]["doc"])[ib]
        fa = interface_frame(units[ua]["doc"], ifa)
        pw, qw = _place_frame(T[ua], fa[0], fa[1])
        j = copy.deepcopy(c.get("joint") or {"joint_type": "fixed"})
        j.setdefault("joint_type", "fixed")
        con = {"id": c["id"], "type": "joint", "body_a": _map_body(ua, interface_body(ifa)) if ua != root["id"] else interface_body(ifa),
               "body_b": _map_body(ub, interface_body(ifb)) if ub != root["id"] else interface_body(ifb),
               "frame_a": {"position": pw, "orientation": qw}, "frame_b": {"position": pw, "orientation": qw}}
        con.update(j)
        if c.get("name"):
            con["name"] = c["name"]
        out["constraints"].append(con)
    for p in comb.get("poses") or []:
        out["poses"].append(copy.deepcopy(p))
    if not out["poses"]:
        del out["poses"]
    out["x_assembled"] = True
    md = out.setdefault("_metadata", {})
    md["version"] = "0.101"
    vi = out.setdefault("vehicle_info", {})
    if comb.get("name"):
        vi["model"] = comb["name"]
    return out, notes


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    out_path = None
    args = list(argv)
    if "-o" in args:
        i = args.index("-o")
        out_path = args[i + 1]
        del args[i:i + 2]
    comb = load_combination(args[0])
    errors, warnings = check_combination(comb)
    for w in warnings:
        print("  WARN ", w)
    for e in errors:
        print("  ERROR", e)
    if errors:
        return 1
    doc, notes = assemble(comb)
    for n in notes:
        print("  note ", n)
    errs, warns = cc.check(doc)
    for w in warns:
        print("  WARN ", w)
    for e in errs:
        print("  ERROR", e)
    print(f"assembled {len(comb['units'])} units, {len(doc['chassis']['mass_bodies'])} bodies, "
          f"{len(doc['constraints'])} constraints, mass {doc['chassis']['mass_total']:.1f} kg")
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
