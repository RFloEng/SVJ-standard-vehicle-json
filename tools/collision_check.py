#!/usr/bin/env python3
"""SVJ collision proxies: clearance between the proxy shapes of different bodies in a pose (spec section 28).

A body (or the chassis) carries `collision[]`: sphere / box / cylinder proxies given in vehicle coordinates at the
reference pose. Two proxies are compared when their bodies can move relative to each other: not when the bodies are in the
same rigid group (welded through `parent`), not when a joint connects them directly, not when the pair is listed in the
top-level `collision_ignore`. The separation is positive when apart and negative when overlapping (the penetration depth).

  clashes(doc, pose=None, tolerance=0.0)   -> [{pose, a, b, body_a, body_b, separation}] for separation < tolerance
  check(doc)                               -> (errors, warnings): proxy structure, and overlaps in the reference pose / poses
  python collision_check.py file.svj.json [--pose ID] [--margin M]

Approximations: a cylinder is its bounding box; the separation of two separated boxes is the largest gap along their face
and edge normals (exact for face contact, a lower bound of the distance otherwise); `margin` of each proxy is subtracted.
"""
import json
import math
import sys

try:                                           # inside svj-py
    from svj import constraints as cc
except ImportError:                            # running from tools/
    import constraints_check as cc

TYPES = ("sphere", "box", "cylinder")
OVERLAP_WARN = 1e-3                            # m; interpenetration beyond this in a pose is reported


def _dims_issue(s):
    t = s.get("type")
    if t not in TYPES:
        return f"type '{t}' is not one of {', '.join(TYPES)}"
    return cc._shape_issue(s)


def proxies(doc):
    """[{id, body, shape, position, R, margin}] of every collision proxy in the file (well-formed or not)."""
    out = []
    ch = doc.get("chassis") or {}
    owners = [("chassis", ch)] + [(b.get("id"), b) for b in (ch.get("mass_bodies") or []) if isinstance(b, dict)]
    for bid, owner in owners:
        for i, s in enumerate(owner.get("collision") or []):
            if not isinstance(s, dict):
                continue
            out.append({"id": s.get("id", f"{bid}#{i}"), "body": bid, "shape": s,
                        "position": s.get("position") if isinstance(s.get("position"), list) else None,
                        "R": cc.quat_to_mat(s.get("orientation") or [0, 0, 0, 1]),
                        "margin": float(s.get("margin") or 0.0)})
    return out


def rigid_groups(doc):
    """{body_id: root}: bodies welded together through `parent` (and not the child of a joint) share a root; a body that is
    the child of a joint is its own root, and so is every body welded to nothing movable the chassis."""
    bodies = cc._bodies(doc)
    jointed = {c.get("body_b") for c in cc._constraints(doc, "joint")}
    root = {}

    def find(bid, seen=()):
        if bid == "chassis" or bid in jointed or bid in seen:
            return bid
        if bid not in root:
            parent = (bodies.get(bid) or {}).get("parent", "chassis")
            root[bid] = find(parent, seen + (bid,)) if parent in bodies or parent == "chassis" else bid
        return root[bid]

    return {bid: find(bid) for bid in list(bodies) + ["chassis"]}


def _skipped(doc):
    adj = set()
    for c in cc._constraints(doc, "joint"):
        adj.add(frozenset((c.get("body_a"), c.get("body_b"))))
    ignore = set()
    for pair in doc.get("collision_ignore") or []:
        if isinstance(pair, list) and len(pair) == 2:
            ignore.add(frozenset(pair))
    return adj | ignore


def _world(p, X):
    t = X.get(p["body"], cc.IDENT)
    return cc.apply(t, p["position"]), cc._mm(t[0], p["R"])


def _as_box(s):
    if s["type"] == "box":
        return [x / 2 for x in s["size"]]
    return [s["radius"], s["radius"], s["length"] / 2]          # a cylinder as its bounding box


def _box_box(pa, Ra, ha, pb, Rb, hb):
    axes = [[Ra[i][k] for i in range(3)] for k in range(3)] + [[Rb[i][k] for i in range(3)] for k in range(3)]
    for u in axes[:3]:
        for v in axes[3:]:
            c = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            n = math.sqrt(sum(x * x for x in c))
            if n > 1e-9:
                axes.append([x / n for x in c])
    d = [pb[i] - pa[i] for i in range(3)]
    best = -math.inf
    for n in axes:
        ra = sum(ha[k] * abs(sum(Ra[i][k] * n[i] for i in range(3))) for k in range(3))
        rb = sum(hb[k] * abs(sum(Rb[i][k] * n[i] for i in range(3))) for k in range(3))
        best = max(best, abs(sum(d[i] * n[i] for i in range(3))) - ra - rb)
    return best


def separation(a, b, X):
    """Separation (m) of two proxies in the pose given by the body transforms X; positive = apart."""
    (pa, Ra), (pb, Rb) = _world(a, X), _world(b, X)
    sa, sb = a["shape"], b["shape"]
    ta, tb = sa["type"], sb["type"]
    if ta == "sphere" and tb == "sphere":
        gap = math.dist(pa, pb) - sa["radius"] - sb["radius"]
    elif "sphere" in (ta, tb):
        (ps, rs), (pbx, Rbx, shb) = ((pa, sa["radius"]), (pb, Rb, sb)) if ta == "sphere" else ((pb, sb["radius"]), (pa, Ra, sa))
        local = cc._mv(cc._tr(Rbx), cc._sub(ps, pbx))
        gap = cc._sd_box(local, _as_box(shb)) - rs
    else:
        gap = _box_box(pa, Ra, _as_box(sa), pb, Rb, _as_box(sb))
    return gap - a["margin"] - b["margin"]


def clashes(doc, pose=None, tolerance=0.0):
    """Pairs of proxies of relatively movable bodies whose separation is below `tolerance` (m) in `pose`."""
    X = cc.body_transforms(doc, pose)
    groups, skip = rigid_groups(doc), _skipped(doc)
    props = [p for p in proxies(doc) if p["position"] is not None and _dims_issue(p["shape"]) is None]
    out = []
    for i, a in enumerate(props):
        for b in props[i + 1:]:
            if a["body"] == b["body"] or groups.get(a["body"]) == groups.get(b["body"]) or frozenset((a["body"], b["body"])) in skip:
                continue
            s = separation(a, b, X)
            if s < tolerance:
                out.append({"pose": pose if isinstance(pose, str) else None, "a": a["id"], "b": b["id"],
                            "body_a": a["body"], "body_b": b["body"], "separation": s})
    return out


def check(doc):
    errors, warnings = [], []
    bodies = cc._bodies(doc)
    seen = set()
    for p in proxies(doc):
        w = f"collision proxy '{p['id']}' on '{p['body']}'"
        if p["id"] in seen:
            errors.append(f"{w}: duplicate proxy id")
        seen.add(p["id"])
        if p["position"] is None or len(p["position"]) != 3:
            errors.append(f"{w}: position must be three numbers")
        issue = _dims_issue(p["shape"])
        if issue:
            errors.append(f"{w}: {issue}")
    for pair in doc.get("collision_ignore") or []:
        if not (isinstance(pair, list) and len(pair) == 2 and all(x in bodies or x == "chassis" for x in pair)):
            errors.append(f"collision_ignore: {pair!r} is not a pair of existing body ids")
    if errors:
        return errors, warnings
    for pose in [None] + [p.get("id") for p in (doc.get("poses") or []) if isinstance(p, dict) and p.get("id")]:
        for k in clashes(doc, pose, -OVERLAP_WARN):
            warnings.append(f"collision: '{k['a']}' ({k['body_a']}) and '{k['b']}' ({k['body_b']}) overlap by "
                            f"{-k['separation'] * 1000:.1f} mm in {'the reference pose' if pose is None else 'pose ' + pose}")
    return errors, warnings


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="SVJ collision proxy clearances")
    ap.add_argument("file")
    ap.add_argument("--pose", help="pose id (default: the reference pose and every pose)")
    ap.add_argument("--margin", type=float, default=0.0, help="also list pairs closer than this (m)")
    a = ap.parse_args(argv)
    with open(a.file, encoding="utf-8") as fh:
        doc = json.load(fh)
    poses = [a.pose] if a.pose else [None] + [p.get("id") for p in (doc.get("poses") or []) if isinstance(p, dict)]
    n = 0
    for pose in poses:
        for k in sorted(clashes(doc, pose, a.margin if a.margin > 0 else 0.0), key=lambda r: r["separation"]):
            n += 1
            print(f"  {pose or 'reference':<14} {k['a']} - {k['b']}: {k['separation'] * 1000:+.1f} mm")
    e, _ = check(doc)
    for m in e:
        print("  ERROR", m)
    print(f"{n} close or overlapping pair(s), {len(e)} error(s)")
    return 1 if e else 0


if __name__ == "__main__":
    sys.exit(main())
