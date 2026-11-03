#!/usr/bin/env python3
"""
OpenUSD -> glTF (GLB) preview copy of an SVJ asset (spec §22.10).

The viewer shows glTF. This tool writes a GLB copy of a USD asset, to be listed as `preview` in `assets.meshes[]`
(spec §22.2). The USD asset stays the source; the copy is only for display and carries the same binding names, so a
`visual` binding resolves in both files.

What is converted:
  * the prim hierarchy as glTF nodes with their local transforms; a prim with `svj:node` (or named `SVJ__category__id`)
    becomes a node named `SVJ::category::id`, also stored in the node's `extras.svj_node`,
  * UsdGeomMesh (triangulated; vertex, face-varying and uniform normals; `st` texture coordinates), subdivision
    surfaces as their control mesh, Cube, Sphere and Cylinder,
  * NurbsPatch, tessellated on a grid (rational B-spline surface; trim curves are ignored),
  * colour: the bound UsdPreviewSurface (diffuseColor, opacity, metallic, roughness, emissiveColor), else displayColor.
Not converted (reported as notes): curves, points, textures, point instancers, Cone and Capsule.

Units are brought to metres (the stage's metersPerUnit becomes a scale on a root node when it is not 1); the axes are
left as the stage has them, as in glTF files made by `gltf2usd.py`.

Needs the `usd-core` library: pip install usd-core.

Usage:
    python tools/usd2gltf.py car.usdz car.preview.glb
"""

import itertools
import json
import math
import os
import re
import struct
import sys
from array import array

_USD_NAME = re.compile(r"^SVJ__([a-z]+)__(.+)$")


class ConvertError(ValueError):
    pass


# ── NURBS ─────────────────────────────────────────────────────────────────────
def _basis(i, p, u, knots):
    """Cox-de Boor B-spline basis function N_{i,p}(u)."""
    if p == 0:
        last = knots[i + 1] == knots[-1] and u == knots[-1] and knots[i] < knots[i + 1]
        return 1.0 if (knots[i] <= u < knots[i + 1]) or last else 0.0
    a = b = 0.0
    d1 = knots[i + p] - knots[i]
    d2 = knots[i + p + 1] - knots[i + 1]
    if d1 > 0:
        a = (u - knots[i]) / d1 * _basis(i, p - 1, u, knots)
    if d2 > 0:
        b = (knots[i + p + 1] - u) / d2 * _basis(i + 1, p - 1, u, knots)
    return a + b


def tessellate_nurbs(order_u, order_v, knots_u, knots_v, nu, nv, pts, weights, urange, vrange, nsteps=None):
    """Grid of points on a (rational) B-spline surface. pts[v * nu + u] is the control point (u varies fastest).
    Returns (points, (cols, rows))."""
    pu, pv = order_u - 1, order_v - 1
    if len(knots_u) != nu + order_u or len(knots_v) != nv + order_v or len(pts) != nu * nv:
        raise ConvertError("inconsistent NURBS patch (knot or point counts)")
    su = nsteps or max(12, min(48, 6 * nu))
    sv = nsteps or max(12, min(48, 6 * nv))
    u0, u1 = urange if urange else (knots_u[pu], knots_u[nu])
    v0, v1 = vrange if vrange else (knots_v[pv], knots_v[nv])
    out = []
    for j in range(sv + 1):
        v = v0 + (v1 - v0) * j / sv
        bv = [_basis(k, pv, v, knots_v) for k in range(nv)]
        for i in range(su + 1):
            u = u0 + (u1 - u0) * i / su
            bu = [_basis(k, pu, u, knots_u) for k in range(nu)]
            x = y = z = w = 0.0
            for kv in range(nv):
                if bv[kv] == 0.0:
                    continue
                for ku in range(nu):
                    f = bu[ku] * bv[kv]
                    if f == 0.0:
                        continue
                    wt = weights[kv * nu + ku] if weights else 1.0
                    p = pts[kv * nu + ku]
                    x += f * wt * p[0]
                    y += f * wt * p[1]
                    z += f * wt * p[2]
                    w += f * wt
            out.append((x / w, y / w, z / w) if w else (0.0, 0.0, 0.0))
    return out, (su + 1, sv + 1)


def grid_triangles(cols, rows):
    idx = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a, b, c, d = j * cols + i, j * cols + i + 1, (j + 1) * cols + i + 1, (j + 1) * cols + i
            idx += [a, b, c, a, c, d]
    return idx


# ── simple primitives ─────────────────────────────────────────────────────────
def cube_mesh(size):
    h = size / 2.0
    pts, idx = [], []
    faces = [((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)), ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
             ((0, -1, 0), (1, 0, 0), (0, 0, 1)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0))]
    nrm = []
    for n, a, b in faces:
        base = len(pts)
        for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(tuple(h * (n[k] + sa * a[k] + sb * b[k]) for k in range(3)))
            nrm.append(tuple(float(c) for c in n))
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    return pts, nrm, idx


def sphere_mesh(radius, nlat=16, nlon=32):
    pts, nrm, idx = [], [], []
    for i in range(nlat + 1):
        th = math.pi * i / nlat
        for j in range(nlon + 1):
            ph = 2 * math.pi * j / nlon
            n = (math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))
            pts.append(tuple(radius * c for c in n))
            nrm.append(n)
    for i in range(nlat):
        for j in range(nlon):
            a, b = i * (nlon + 1) + j, (i + 1) * (nlon + 1) + j
            idx += [a, b, a + 1, a + 1, b, b + 1]
    return pts, nrm, idx


def cylinder_mesh(radius, height, axis="Z", n=32):
    def to_axis(x, y, z):
        return {"X": (z, x, y), "Y": (y, z, x), "Z": (x, y, z)}.get(axis, (x, y, z))
    pts, nrm, idx = [], [], []
    h = height / 2.0
    for j in range(n + 1):
        a = 2 * math.pi * j / n
        c, s = math.cos(a), math.sin(a)
        for z in (-h, h):
            pts.append(to_axis(radius * c, radius * s, z))
            nrm.append(to_axis(c, s, 0.0))
    for j in range(n):
        a = 2 * j
        idx += [a, a + 2, a + 1, a + 1, a + 2, a + 3]
    for z, nz in ((-h, -1.0), (h, 1.0)):
        centre = len(pts)
        pts.append(to_axis(0.0, 0.0, z))
        nrm.append(to_axis(0.0, 0.0, nz))
        for j in range(n + 1):
            a = 2 * math.pi * j / n
            pts.append(to_axis(radius * math.cos(a), radius * math.sin(a), z))
            nrm.append(to_axis(0.0, 0.0, nz))
        for j in range(n):
            idx += [centre, centre + 1 + j, centre + 2 + j] if nz > 0 else [centre, centre + 2 + j, centre + 1 + j]
    return pts, nrm, idx


# ── GLB writing ───────────────────────────────────────────────────────────────
class _Builder:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors, self.meshes, self.nodes, self.materials = [], [], [], [], []
        self._mat_cache = {}

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        off = len(self.bin)
        self.bin += data
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            v["target"] = target
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, values, kind, comp, minmax=False, target=None):
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[kind]
        arr = array("f" if comp == 5126 else "I", itertools.chain.from_iterable(values) if n > 1 else values)
        if sys.byteorder != "little":
            arr.byteswap()
        data = arr.tobytes()
        a = {"bufferView": self._view(data, target), "componentType": comp, "count": len(values), "type": kind}
        if minmax and values:
            a["min"] = [min(v[k] for v in values) for k in range(n)]
            a["max"] = [max(v[k] for v in values) for k in range(n)]
        self.accessors.append(a)
        return len(self.accessors) - 1

    def material(self, base, alpha, metallic, rough, emissive):
        key = (tuple(round(c, 5) for c in base), round(alpha, 5), round(metallic, 5), round(rough, 5), tuple(round(c, 5) for c in emissive))
        if key not in self._mat_cache:
            m = {"pbrMetallicRoughness": {"baseColorFactor": [*base, alpha], "metallicFactor": metallic, "roughnessFactor": rough}}
            if any(emissive):
                m["emissiveFactor"] = list(emissive)
            if alpha < 1.0:
                m["alphaMode"] = "BLEND"
            self.materials.append(m)
            self._mat_cache[key] = len(self.materials) - 1
        return self._mat_cache[key]

    def mesh(self, pts, idx, normals, uvs, material):
        attrs = {"POSITION": self.accessor(pts, "VEC3", 5126, minmax=True, target=34962)}
        if normals:
            attrs["NORMAL"] = self.accessor(normals, "VEC3", 5126, target=34962)
        if uvs:
            attrs["TEXCOORD_0"] = self.accessor(uvs, "VEC2", 5126, target=34962)
        prim = {"attributes": attrs, "indices": self.accessor(idx, "SCALAR", 5125, target=34963), "mode": 4}
        if material is not None:
            prim["material"] = material
        self.meshes.append({"primitives": [prim]})
        return len(self.meshes) - 1

    def glb(self, scene_nodes, extras=None):
        gltf = {"asset": {"version": "2.0", "generator": "svj tools/usd2gltf.py"}, "scene": 0, "scenes": [{"nodes": scene_nodes}],
                "nodes": self.nodes, "buffers": [{"byteLength": len(self.bin)}]}
        if extras:
            gltf["asset"]["extras"] = extras
        for k, v in (("meshes", self.meshes), ("accessors", self.accessors), ("bufferViews", self.views), ("materials", self.materials)):
            if v:
                gltf[k] = v
        js = json.dumps(gltf).encode("utf-8")
        js += b" " * (-len(js) % 4)
        binary = bytes(self.bin) + b"\x00" * (-len(self.bin) % 4)
        body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binary), 0x004E4942) + binary
        return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


# ── conversion ────────────────────────────────────────────────────────────────
def convert(src, dst):
    """Convert the USD file `src` to the GLB `dst`. Returns a summary dict (nodes, meshes, triangles, named, notes)."""
    from pxr import Usd, UsdGeom, UsdShade
    try:
        stage = Usd.Stage.Open(src)
    except Exception:                                                        # pxr raises its own error type
        raise ConvertError("not readable as OpenUSD")
    if stage is None:
        raise ConvertError("not readable as OpenUSD")
    notes = []
    mpu = UsdGeom.GetStageMetersPerUnit(stage) if stage.HasAuthoredMetadata("metersPerUnit") else 1.0
    if not stage.HasAuthoredMetadata("metersPerUnit"):
        notes.append("the stage authors no metersPerUnit; metres assumed")
    up = UsdGeom.GetStageUpAxis(stage)
    xc = UsdGeom.XformCache()
    b = _Builder()
    stats = {"nodes": 0, "meshes": 0, "triangles": 0, "named": 0}
    pred = Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)

    def logical_name(prim):
        a = prim.GetAttribute("svj:node")
        v = a.Get() if a and a.HasAuthoredValue() else None
        if isinstance(v, str):
            return v
        m = _USD_NAME.match(prim.GetName())
        return f"SVJ::{m.group(1)}::{m.group(2)}" if m else None

    def colour(prim):
        """(base rgb, alpha, metallic, roughness, emissive rgb) of the bound UsdPreviewSurface, else displayColor."""
        base, alpha, metallic, rough, emis = (0.8, 0.8, 0.8), 1.0, 0.0, 0.6, (0.0, 0.0, 0.0)
        gp = UsdGeom.Gprim(prim)
        if gp:
            dc = gp.GetDisplayColorAttr().Get()
            if dc is not None and len(dc):
                base = tuple(float(c) for c in dc[0])
            op = gp.GetDisplayOpacityAttr().Get()
            if op is not None and len(op):
                alpha = float(op[0])
        try:
            mat = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
        except Exception:
            mat = None
        if mat:
            sh = mat.ComputeSurfaceSource()[0]
            if sh:
                def val(name, d):
                    inp = sh.GetInput(name)
                    if inp and not inp.HasConnectedSource():
                        v = inp.Get()
                        return v if v is not None else d
                    return d
                dcol = val("diffuseColor", None)
                base = tuple(float(c) for c in dcol) if dcol is not None else base
                alpha = float(val("opacity", alpha))
                metallic = float(val("metallic", metallic))
                rough = float(val("roughness", rough))
                e = val("emissiveColor", None)
                emis = tuple(float(c) for c in e) if e is not None else emis
        return base, alpha, metallic, rough, emis

    def geometry(prim):
        """(points, indices, normals, uvs) of a geometry prim, or None."""
        t = prim.GetTypeName()
        if t == "Mesh":
            m = UsdGeom.Mesh(prim)
            pts = [tuple(p) for p in (m.GetPointsAttr().Get() or [])]
            counts, fv = m.GetFaceVertexCountsAttr().Get() or [], m.GetFaceVertexIndicesAttr().Get() or []
            if not pts or not len(counts):
                return None
            flip = m.GetOrientationAttr().Get() == "leftHanded"
            tris, face_of, corner_of, k = [], [], [], 0
            for f, c in enumerate(counts):
                for q in range(1, c - 1):
                    tri = (k, k + q, k + q + 1)
                    tris.append(tri[::-1] if flip else tri)
                    face_of.append(f)
                k += c
            nattr = m.GetNormalsAttr().Get()
            ninterp = m.GetNormalsInterpolation()
            st = UsdGeom.PrimvarsAPI(prim).GetPrimvar("st")
            stv = st.Get() if st else None
            sinterp = st.GetInterpolation() if st else None
            vertex_ok = all(x is None or i in ("vertex", "varying") for x, i in ((nattr, ninterp), (stv, sinterp)))
            if vertex_ok and (nattr is None or len(nattr) == len(pts)) and (stv is None or len(stv) == len(pts)):
                idx = [fv[c] for tri in tris for c in tri]
                normals = [tuple(n) for n in nattr] if nattr is not None else None
                uvs = [(u, 1.0 - v) for u, v in stv] if stv is not None else None
                return pts, idx, normals, uvs
            # face-varying or uniform data: unroll to one vertex per triangle corner
            opts, onrm, ouv = [], [], []
            for tri, f in zip(tris, face_of):
                for c in tri:
                    opts.append(pts[fv[c]])
                    if nattr is not None:
                        i = {"faceVarying": c, "uniform": f, "vertex": fv[c], "varying": fv[c]}.get(ninterp)
                        onrm.append(tuple(float(x) for x in nattr[i]) if i is not None and i < len(nattr) else (0.0, 0.0, 1.0))
                    if stv is not None:
                        i = c if sinterp == "faceVarying" else fv[c]
                        u, v = stv[i] if i < len(stv) else (0.0, 0.0)
                        ouv.append((float(u), 1.0 - float(v)))
            return opts, list(range(len(opts))), onrm or None, ouv or None
        if t == "Cube":
            p, n, i = cube_mesh(float(UsdGeom.Cube(prim).GetSizeAttr().Get() or 2.0))
            return p, i, n, None
        if t == "Sphere":
            p, n, i = sphere_mesh(float(UsdGeom.Sphere(prim).GetRadiusAttr().Get() or 1.0))
            return p, i, n, None
        if t == "Cylinder":
            c = UsdGeom.Cylinder(prim)
            p, n, i = cylinder_mesh(float(c.GetRadiusAttr().Get() or 1.0), float(c.GetHeightAttr().Get() or 2.0), str(c.GetAxisAttr().Get() or "Z"))
            return p, i, n, None
        if t == "NurbsPatch":
            n = UsdGeom.NurbsPatch(prim)
            pts = [tuple(float(c) for c in p) for p in n.GetPointsAttr().Get()]
            w = n.GetPointWeightsAttr().Get()
            ur, vr = n.GetURangeAttr().Get(), n.GetVRangeAttr().Get()
            g, dims = tessellate_nurbs(n.GetUOrderAttr().Get(), n.GetVOrderAttr().Get(), list(n.GetUKnotsAttr().Get()), list(n.GetVKnotsAttr().Get()),
                                       n.GetUVertexCountAttr().Get(), n.GetVVertexCountAttr().Get(), pts, list(w) if w and len(w) else None,
                                       (ur[0], ur[1]) if ur is not None else None, (vr[0], vr[1]) if vr is not None else None)
            if n.GetTrimCurveCountsAttr().Get() is not None and len(n.GetTrimCurveCountsAttr().Get() or []):
                notes.append(f"{prim.GetPath()}: trim curves are ignored")
            return g, grid_triangles(*dims), None, None
        if t in ("NurbsCurves", "BasisCurves", "Points", "PointInstancer", "Cone", "Capsule"):
            notes.append(f"{prim.GetPath()}: {t} is not converted")
        return None

    def add(prim, depth=0):
        if depth > 64:
            raise ConvertError("prim hierarchy too deep")
        t = prim.GetTypeName()
        if t in ("Material", "Shader", "NodeGraph"):
            return None                                                      # shading data, not shapes
        img = UsdGeom.Imageable(prim)
        if img and img.ComputePurpose() in ("guide", "proxy"):
            return None
        node = {"name": prim.GetName()}
        ln = logical_name(prim)
        if ln:
            node["name"] = ln
            node["extras"] = {"svj_node": ln}
            stats["named"] += 1
        xf = UsdGeom.Xformable(prim)
        if xf:
            m = xc.GetLocalTransformation(prim)[0]
            flat = [m[i][j] for i in range(4) for j in range(4)]           # row-vector rows == glTF column-major
            if flat != [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]:
                node["matrix"] = flat
        g = geometry(prim)
        if g:
            pts, idx, normals, uvs = g
            b_, a_, me, ro, em = colour(prim)
            node["mesh"] = b.mesh(pts, idx, normals, uvs, b.material(b_, a_, me, ro, em))
            stats["meshes"] += 1
            stats["triangles"] += len(idx) // 3
        index = len(b.nodes)
        b.nodes.append(node)
        stats["nodes"] += 1
        kids = [k for k in (add(c, depth + 1) for c in prim.GetFilteredChildren(pred)) if k is not None]
        if kids:
            node["children"] = kids
        return index

    top = [i for i in (add(p) for p in stage.GetPseudoRoot().GetFilteredChildren(pred)) if i is not None]
    scene = top
    if abs(mpu - 1.0) > 1e-9:
        b.nodes.append({"name": "usd_units", "scale": [mpu] * 3, "children": top})
        scene = [len(b.nodes) - 1]
        notes.append(f"metersPerUnit {mpu:g} applied as a scale on the root node")
    data = b.glb(scene, {"svj_up_axis": up, "source": os.path.basename(src)})
    with open(dst, "wb") as f:
        f.write(data)
    stats["notes"] = notes
    return stats


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    try:
        r = convert(argv[0], argv[1])
    except ImportError:
        print("error: this needs the usd-core library (pip install usd-core)")
        return 1
    except (ConvertError, OSError) as e:
        print(f"error: {e}")
        return 1
    print(f"{argv[1]}: {r['nodes']} nodes, {r['meshes']} meshes, {r['triangles']} triangles, {r['named']} SVJ nodes")
    for n in r["notes"]:
        print(f"  note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
