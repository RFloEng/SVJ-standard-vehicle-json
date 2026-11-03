#!/usr/bin/env python3
"""
glTF / GLB -> OpenUSD converter for SVJ assets (spec §22.10).

Writes a USD stage that follows the SVJ rules for USD assets:
  * metersPerUnit = 1, upAxis = Y (glTF's own axes; nothing is rotated or scaled),
  * the node hierarchy as Xform prims with the node transforms,
  * a node named `SVJ::category::id` becomes the prim `SVJ__category__id` carrying the attribute
    `svj:node = "SVJ::category::id"` (also taken from a node's `extras.svj_node`),
  * triangle meshes (modes 4, 5, 6) as UsdGeomMesh with normals and the first UV set,
  * the base colour, metallic and roughness factors as a UsdPreviewSurface material,
  * textures (base colour, normal, metallic-roughness, occlusion, emissive) as UsdUVTexture shaders wired into that material:
    the images are written to `<name>_textures/` beside a .usd / .usda / .usdc file, or packed inside a .usdz.

glTF animations are NOT carried over: animation, poses and solids in a USD asset may only be copies of data already in the
SVJ JSON (spec §22.10), so a converter must first put them in the JSON (joints, `poses[]`).

Needs the `usd-core` library: pip install usd-core.

Usage:
    python tools/gltf2usd.py car.glb car.usdc [--root Car]
    python tools/gltf2usd.py car.glb car.usda
"""

import base64
import json
import math
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesh_check as mc                         # noqa: E402  (node transforms of glTF)

_COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


class ConvertError(ValueError):
    pass


def read_glb(path):
    """(glTF JSON dict, binary chunk bytes or None) of a .glb or .gltf file."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return json.loads(data.decode("utf-8")), None
    offset, js, binary = 12, None, None
    while offset + 8 <= len(data):
        clen, ctype = struct.unpack("<II", data[offset:offset + 8])
        chunk = data[offset + 8:offset + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942 and binary is None:
            binary = chunk
        offset += 8 + clen
    if js is None:
        raise ConvertError("GLB has no JSON chunk")
    return js, binary


def _buffers(gltf, glb_bin, base_dir):
    out = []
    for i, b in enumerate(gltf.get("buffers") or []):
        uri = b.get("uri")
        if uri is None:
            if glb_bin is None:
                raise ConvertError(f"buffer {i} has no data (no GLB binary chunk)")
            out.append(glb_bin)
        elif uri.startswith("data:"):
            out.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            with open(os.path.join(base_dir, uri), "rb") as f:
                out.append(f.read())
    return out


def read_accessor(gltf, buffers, index):
    """The elements of an accessor as a list of tuples (a flat list of numbers for SCALAR)."""
    acc = gltf["accessors"][index]
    if acc.get("sparse"):
        raise ConvertError("sparse accessors are not supported")
    fmt, size = _COMPONENT[acc["componentType"]]
    n = _NCOMP[acc["type"]]
    count = acc["count"]
    if acc.get("bufferView") is None:
        return [tuple([0] * n)] * count if n > 1 else [0] * count
    bv = gltf["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or size * n
    buf = buffers[bv["buffer"]]
    norm = acc.get("normalized") and acc["componentType"] in _NORM
    out = []
    for i in range(count):
        vals = struct.unpack_from("<" + fmt * n, buf, base + i * stride)
        if norm:
            d = _NORM[acc["componentType"]]
            vals = tuple(max(v / d, -1.0) for v in vals)
        out.append(vals[0] if n == 1 else vals)
    return out


def _prim_name(name, fallback, taken):
    """A legal prim name: letters, digits and underscore, not starting with a digit, unique among siblings."""
    m = re.match(r"^SVJ::([a-z]+)::(.+)$", name or "")
    base = f"SVJ__{m.group(1)}__{m.group(2)}" if m else re.sub(r"[^A-Za-z0-9_]", "_", name or "") or fallback
    if not re.match(r"^[A-Za-z_]", base):
        base = "_" + base
    cand, k = base, 2
    while cand in taken:
        cand, k = f"{base}_{k}", k + 1
    taken.add(cand)
    return cand


def convert(src, dst, root_name="Root"):
    """Convert `src` (.glb / .gltf) to the USD file `dst` (.usd, .usda, .usdc or .usdz). Returns a summary dict."""
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
    gltf, glb_bin = read_glb(src)
    buffers = _buffers(gltf, glb_bin, os.path.dirname(os.path.abspath(src)))
    nodes = gltf.get("nodes") or []
    notes = []
    ext = os.path.splitext(dst)[1].lower()
    target = dst if ext != ".usdz" else dst[:-5] + ".usdc"
    stage = Usd.Stage.CreateNew(target)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, "Y")
    stage.GetRootLayer().customLayerData = {"svj": {"converted_from": os.path.basename(src), "tool": "tools/gltf2usd.py"}}
    tex_dir = os.path.splitext(target)[0] + "_textures"
    images = {}                                                  # glTF image index -> path relative to the stage file
    root = UsdGeom.Xform.Define(stage, "/" + root_name)
    stage.SetDefaultPrim(root.GetPrim())
    materials, stats = {}, {"nodes": 0, "meshes": 0, "triangles": 0, "named": 0}

    def image_file(img_index):
        """Write glTF image `img_index` next to the stage and return its relative path, or None."""
        if img_index in images:
            return images[img_index]
        imgs = gltf.get("images") or []
        im = imgs[img_index] if isinstance(img_index, int) and 0 <= img_index < len(imgs) else None
        data, ext = None, None
        if im:
            uri = im.get("uri")
            mime = im.get("mimeType") or ""
            if uri is None and im.get("bufferView") is not None:
                bv = gltf["bufferViews"][im["bufferView"]]
                data = bytes(buffers[bv["buffer"]][bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]])
            elif uri and uri.startswith("data:"):
                head, payload = uri.split(",", 1)
                mime = mime or head[5:].split(";")[0]
                data = base64.b64decode(payload)
            elif uri:
                with open(os.path.join(os.path.dirname(os.path.abspath(src)), uri), "rb") as f:
                    data = f.read()
                ext = os.path.splitext(uri)[1].lower()
            ext = ext or {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
        if data is None:
            notes.append(f"image {img_index} could not be read; texture skipped")
            images[img_index] = None
            return None
        if ext == ".webp":
            notes.append(f"image {img_index} is WebP; USD viewers read PNG and JPEG, convert it first")
        os.makedirs(tex_dir, exist_ok=True)
        fname = f"image_{img_index}{ext}"
        with open(os.path.join(tex_dir, fname), "wb") as f:
            f.write(data)
        images[img_index] = f"./{os.path.basename(tex_dir)}/{fname}"
        return images[img_index]

    def texture(mat, slot, info, outputs, scale=None, bias=None, srgb=False):
        """Add a UsdUVTexture for the glTF textureInfo `info`; returns the shader or None."""
        texs = gltf.get("textures") or []
        tex = texs[info["index"]] if isinstance(info, dict) and isinstance(info.get("index"), int) and info["index"] < len(texs) else None
        if not tex or tex.get("source") is None:
            if info:
                notes.append(f"material texture '{slot}' has no usable image source; skipped")
            return None
        rel = image_file(tex["source"])
        if rel is None:
            return None
        if info.get("texCoord", 0):
            notes.append(f"texture '{slot}' uses TEXCOORD_{info['texCoord']}; only the first UV set is converted")
        if (info.get("extensions") or {}).get("KHR_texture_transform"):
            notes.append(f"texture '{slot}': KHR_texture_transform is not converted")
        base = str(mat.GetPath())
        reader = UsdShade.Shader.Define(stage, f"{base}/st_reader")
        if not reader.GetPrim().GetAttribute("inputs:varname"):
            reader.CreateIdAttr("UsdPrimvarReader_float2")
            reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
            reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        samplers = gltf.get("samplers") or []
        sampler = samplers[tex["sampler"]] if isinstance(tex.get("sampler"), int) and tex["sampler"] < len(samplers) else {}
        wrap = {33071: "clamp", 33648: "mirror"}
        t = UsdShade.Shader.Define(stage, f"{base}/tex_{slot}")
        t.CreateIdAttr("UsdUVTexture")
        t.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(rel))
        t.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), "result")
        t.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB" if srgb else "raw")
        t.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set(wrap.get(sampler.get("wrapS"), "repeat"))
        t.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set(wrap.get(sampler.get("wrapT"), "repeat"))
        if scale:
            t.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*scale))
        if bias:
            t.CreateInput("bias", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*bias))
        for o, typ in outputs.items():
            t.CreateOutput(o, typ)
        stats["textures"] = stats.get("textures", 0) + 1
        return t

    def material(index):
        if index in materials:
            return materials[index]
        m = (gltf.get("materials") or [{}])[index] if index is not None and index < len(gltf.get("materials") or []) else {}
        pbr = m.get("pbrMetallicRoughness") or {}
        col = pbr.get("baseColorFactor") or [1.0, 1.0, 1.0, 1.0]
        mat = UsdShade.Material.Define(stage, f"/{root_name}/Materials/mat_{index if index is not None else 'default'}")
        sh = UsdShade.Shader.Define(stage, f"{mat.GetPath()}/Surface")
        sh.CreateIdAttr("UsdPreviewSurface")
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*col[:3]))
        sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(float(col[3]))
        sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(float(pbr.get("metallicFactor", 1.0)))
        sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(float(pbr.get("roughnessFactor", 1.0)))
        if m.get("emissiveFactor"):
            sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*m["emissiveFactor"][:3]))
        mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
        F3, F1 = Sdf.ValueTypeNames.Float3, Sdf.ValueTypeNames.Float

        def wire(name, tex, out, typ):
            inp = sh.GetInput(name) or sh.CreateInput(name, typ)
            inp.ConnectToSource(tex.ConnectableAPI(), out)

        t = texture(mat, "baseColor", pbr.get("baseColorTexture"), {"rgb": F3, "a": F1}, scale=(*col[:3], 1.0), srgb=True)
        if t:
            wire("diffuseColor", t, "rgb", Sdf.ValueTypeNames.Color3f)
            if m.get("alphaMode", "OPAQUE") != "OPAQUE":
                wire("opacity", t, "a", F1)
        t = texture(mat, "metallicRoughness", pbr.get("metallicRoughnessTexture"), {"g": F1, "b": F1})
        if t:                                                 # glTF packs roughness in G and metallic in B, each times its factor
            t.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(1.0, float(pbr.get("roughnessFactor", 1.0)), float(pbr.get("metallicFactor", 1.0)), 1.0))
            wire("roughness", t, "g", F1)
            wire("metallic", t, "b", F1)
        nt = m.get("normalTexture")
        k = 2.0 * (nt or {}).get("scale", 1.0)
        t = texture(mat, "normal", nt, {"rgb": F3}, scale=(k, k, 2.0, 1.0), bias=(-1.0, -1.0, -1.0, 0.0))
        if t:
            wire("normal", t, "rgb", Sdf.ValueTypeNames.Normal3f)
        t = texture(mat, "occlusion", m.get("occlusionTexture"), {"r": F1})
        if t:
            wire("occlusion", t, "r", F1)
        t = texture(mat, "emissive", m.get("emissiveTexture"), {"rgb": F3}, scale=(*(m.get("emissiveFactor") or [1.0, 1.0, 1.0])[:3], 1.0), srgb=True)
        if t:
            wire("emissiveColor", t, "rgb", Sdf.ValueTypeNames.Color3f)
        materials[index] = (mat, col)
        return materials[index]

    def add_mesh(parent_path, mesh_index):
        for j, prim in enumerate((gltf.get("meshes") or [])[mesh_index].get("primitives") or []):
            mode = prim.get("mode", 4)
            attrs = prim.get("attributes") or {}
            if mode not in (4, 5, 6) or "POSITION" not in attrs:
                notes.append(f"mesh {mesh_index} primitive {j}: mode {mode} is not a triangle mode; skipped")
                continue
            pts = read_accessor(gltf, buffers, attrs["POSITION"])
            idx = read_accessor(gltf, buffers, prim["indices"]) if prim.get("indices") is not None else list(range(len(pts)))
            if mode == 5:
                idx = [t for i in range(len(idx) - 2) for t in ((idx[i], idx[i + 1], idx[i + 2]) if i % 2 == 0 else (idx[i + 1], idx[i], idx[i + 2]))]
            elif mode == 6:
                idx = [t for i in range(1, len(idx) - 1) for t in (idx[0], idx[i], idx[i + 1])]
            ntri = len(idx) // 3
            idx = [int(i) for i in idx[:ntri * 3]]
            nrm = read_accessor(gltf, buffers, attrs["NORMAL"]) if "NORMAL" in attrs else None
            uv = read_accessor(gltf, buffers, attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else None
            used = sorted(set(idx))
            if len(used) < len(pts):                      # primitives often share one vertex buffer: keep only the vertices this one uses
                remap = {old: new for new, old in enumerate(used)}
                pts = [pts[i] for i in used]
                nrm = [nrm[i] for i in used] if nrm else None
                uv = [uv[i] for i in used] if uv else None
                idx = [remap[i] for i in idx]
            mesh = UsdGeom.Mesh.Define(stage, f"{parent_path}/mesh_{j}")
            mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * ntri))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
            mesh.CreateSubdivisionSchemeAttr("none")
            lo = [min(p[k] for p in pts) for k in range(3)]
            hi = [max(p[k] for p in pts) for k in range(3)]
            mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*lo), Gf.Vec3f(*hi)]))
            if nrm:
                mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*n) for n in nrm]))
                mesh.SetNormalsInterpolation("vertex")
            if uv:
                st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
                st.Set(Vt.Vec2fArray([Gf.Vec2f(u, 1.0 - v) for u, v in uv]))          # glTF's V runs down, USD's up
            mat, col = material(prim.get("material"))
            UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
            mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*col[:3])]))
            stats["meshes"] += 1
            stats["triangles"] += ntri

    def add_node(i, parent_path, taken, depth=0):
        if depth > 64:
            raise ConvertError("node hierarchy too deep or cyclic")
        n = nodes[i]
        raw = n.get("name") if isinstance(n.get("name"), str) else None
        extras = (n.get("extras") or {}).get("svj_node") if isinstance(n.get("extras"), dict) else None
        logical = raw if raw and raw.startswith("SVJ::") else (extras if isinstance(extras, str) else None)
        name = _prim_name(raw if (raw and raw.startswith("SVJ::")) else (raw or ""), f"node_{i}", taken)
        path = f"{parent_path}/{name}"
        x = UsdGeom.Xform.Define(stage, path)
        m = mc._local(n)
        if m != mc._ident():
            x.AddTransformOp().Set(Gf.Matrix4d([[m[j][k] for j in range(4)] for k in range(4)]))      # USD uses row vectors: transpose
        if logical:
            x.GetPrim().CreateAttribute("svj:node", Sdf.ValueTypeNames.String, custom=True).Set(logical)
            stats["named"] += 1
        stats["nodes"] += 1
        if isinstance(n.get("mesh"), int):
            add_mesh(path, n["mesh"])
        child_taken = set()
        for c in n.get("children") or []:
            add_node(c, path, child_taken, depth + 1)

    has_parent = {c for n in nodes for c in (n.get("children") or [])}
    scene = (gltf.get("scenes") or [{}])[gltf.get("scene", 0)] if gltf.get("scenes") else {}
    roots = [i for i in (scene.get("nodes") or []) if isinstance(i, int)] or [i for i in range(len(nodes)) if i not in has_parent]
    taken = set(["Materials"])
    for i in roots:
        add_node(i, "/" + root_name, taken)
    if gltf.get("animations"):
        notes.append(f"{len(gltf['animations'])} glTF animation(s) are not converted: animation must first be defined in the SVJ JSON (joints, poses[]), spec 22.10")
    stage.GetRootLayer().Save()
    if ext == ".usdz":
        from pxr import UsdUtils
        UsdUtils.CreateNewUsdzPackage(target, dst)
        os.remove(target)
        shutil.rmtree(tex_dir, ignore_errors=True)               # the textures now live inside the package
    stats["notes"] = notes
    return stats


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = argv[argv.index("--root") + 1] if "--root" in argv else "Root"
    try:
        r = convert(argv[0], argv[1], root)
    except ImportError:
        print("error: this needs the usd-core library (pip install usd-core)")
        return 1
    except (ConvertError, OSError, KeyError, json.JSONDecodeError) as e:
        print(f"error: {e}")
        return 1
    print(f"{argv[1]}: {r['nodes']} nodes, {r['meshes']} meshes, {r['triangles']} triangles, {r['named']} SVJ nodes, {r.get('textures', 0)} textures")
    for n in r["notes"]:
        print(f"  note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
