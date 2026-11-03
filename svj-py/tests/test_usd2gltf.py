"""tools/usd2gltf.py: OpenUSD -> GLB preview copy (spec §22.10, §22.2 `preview`). Needs the optional usd-core library."""

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

pytest.importorskip("pxr", reason="usd-core is not installed")
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt   # noqa: E402

import gltf2usd as g2u      # noqa: E402
import mesh_check as mc     # noqa: E402
import usd2gltf as u2g      # noqa: E402
from tests.test_gltf2usd import triangle_glb   # noqa: E402


def new_stage(path, up="Z"):
    st = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    UsdGeom.SetStageUpAxis(st, up)
    return st


def read(path):
    return mc.read_gltf(path)


def test_nurbs_surface_evaluation():
    # a bilinear patch (order 2 in both directions) is the quad through its four corners
    pts = [(0, 0, 0), (2, 0, 0), (0, 3, 0), (2, 3, 1)]
    g, dims = u2g.tessellate_nurbs(2, 2, [0, 0, 1, 1], [0, 0, 1, 1], 2, 2, pts, None, None, None, nsteps=4)
    assert dims == (5, 5) and len(g) == 25
    assert g[0] == pytest.approx((0, 0, 0)) and g[4] == pytest.approx((2, 0, 0)) and g[20] == pytest.approx((0, 3, 0)) and g[24] == pytest.approx((2, 3, 1))
    assert g[12] == pytest.approx((1.0, 1.5, 0.25))                                   # the centre is the mean of the four corners
    # a rational quarter circle (order 3, weights 1, sqrt(2)/2, 1) stays on the circle
    circ = [(1, 0, 0), (1, 1, 0), (0, 1, 0)] * 2
    w = [1, math.sqrt(2) / 2, 1] * 2
    g, _ = u2g.tessellate_nurbs(3, 2, [0, 0, 0, 1, 1, 1], [0, 0, 1, 1], 3, 2, circ[:3] + [(1, 0, 1), (1, 1, 1), (0, 1, 1)], w, None, None, nsteps=8)
    assert all(math.hypot(p[0], p[1]) == pytest.approx(1.0, abs=1e-9) for p in g)
    with pytest.raises(u2g.ConvertError):
        u2g.tessellate_nurbs(2, 2, [0, 0, 1], [0, 0, 1, 1], 2, 2, pts, None, None, None)


def test_mesh_quads_names_colour_and_transform(tmp_path):
    st = new_stage(tmp_path / "a.usda")
    UsdGeom.Xform.Define(st, "/Car")
    w = UsdGeom.Xform.Define(st, "/Car/SVJ__wheel__wheel_fl")
    UsdGeom.XformCommonAPI(w).SetTranslate(Gf.Vec3d(0.0, -0.8, -0.3))
    m = UsdGeom.Mesh.Define(st, "/Car/SVJ__wheel__wheel_fl/rim")
    m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(-0.3, -0.1, 0), Gf.Vec3f(0.3, -0.1, 0), Gf.Vec3f(0.3, 0.1, 0), Gf.Vec3f(-0.3, 0.1, 0)]))
    m.CreateFaceVertexCountsAttr([4])
    m.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    m.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(0.2, 0.4, 0.6)]))
    other = UsdGeom.Xform.Define(st, "/Car/plain")
    other.GetPrim().CreateAttribute("svj:node", Sdf.ValueTypeNames.String, custom=True).Set("SVJ::body::chassis")
    st.GetRootLayer().Save()
    r = u2g.convert(str(tmp_path / "a.usda"), str(tmp_path / "a.glb"))
    assert r["triangles"] == 2 and r["named"] == 2
    g = read(tmp_path / "a.glb")
    names = [n["name"] for n in g["nodes"]]
    assert "SVJ::wheel::wheel_fl" in names and "SVJ::body::chassis" in names          # both naming forms become the logical name
    assert next(n for n in g["nodes"] if n["name"] == "SVJ::wheel::wheel_fl")["extras"]["svj_node"] == "SVJ::wheel::wheel_fl"
    assert g["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"][:3] == pytest.approx([0.2, 0.4, 0.6])
    box = mc.node_boxes(g)[names.index("SVJ::wheel::wheel_fl")]                       # the node translation and the mesh bounds survive
    assert box[0] == pytest.approx([-0.3, -0.9, -0.3]) and box[1] == pytest.approx([0.3, -0.7, -0.3])
    assert g["asset"]["extras"]["svj_up_axis"] == "Z"


def test_gprims_and_nurbs_patch_and_preview_passes_the_mesh_check(tmp_path):
    st = new_stage(tmp_path / "b.usda")
    UsdGeom.Xform.Define(st, "/Car")
    cube = UsdGeom.Cube.Define(st, "/Car/SVJ__body__chassis")
    cube.GetSizeAttr().Set(2.0)
    UsdGeom.XformCommonAPI(cube).SetScale(Gf.Vec3f(2.2, 0.9, 0.6))
    UsdGeom.XformCommonAPI(cube).SetTranslate(Gf.Vec3d(-1.2, 0, -0.4))
    sph = UsdGeom.Sphere.Define(st, "/Car/SVJ__wheel__wheel_fl")
    sph.GetRadiusAttr().Set(0.3)
    UsdGeom.XformCommonAPI(sph).SetTranslate(Gf.Vec3d(0.0, -0.8, -0.3))
    cyl = UsdGeom.Cylinder.Define(st, "/Car/SVJ__wheel__wheel_fr")
    cyl.GetRadiusAttr().Set(0.3)
    cyl.GetHeightAttr().Set(0.24)
    cyl.GetAxisAttr().Set("Y")
    UsdGeom.XformCommonAPI(cyl).SetTranslate(Gf.Vec3d(0.0, 0.8, -0.3))
    patch = UsdGeom.NurbsPatch.Define(st, "/Car/SVJ__aero__front_wing")
    patch.CreateUOrderAttr(2)
    patch.CreateVOrderAttr(2)
    patch.CreateUVertexCountAttr(2)
    patch.CreateVVertexCountAttr(2)
    patch.CreateUKnotsAttr([0, 0, 1, 1])
    patch.CreateVKnotsAttr([0, 0, 1, 1])
    patch.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(0.8, -0.6, 0.1), Gf.Vec3f(0.8, 0.6, 0.1), Gf.Vec3f(1.1, -0.6, 0.1), Gf.Vec3f(1.1, 0.6, 0.1)]))
    st.GetRootLayer().Save()
    r = u2g.convert(str(tmp_path / "b.usda"), str(tmp_path / "b.glb"))
    assert r["meshes"] == 4 and r["triangles"] > 100
    g = read(tmp_path / "b.glb")
    boxes = mc.node_boxes(g)
    by = {n["name"]: boxes[i] for i, n in enumerate(g["nodes"])}
    assert by["SVJ::body::chassis"][0] == pytest.approx([-3.4, -0.9, -1.0]) and by["SVJ::body::chassis"][1] == pytest.approx([1.0, 0.9, 0.2])
    assert by["SVJ::wheel::wheel_fr"][0][1] == pytest.approx(0.68) and by["SVJ::wheel::wheel_fr"][1][1] == pytest.approx(0.92)      # cylinder axis Y
    assert by["SVJ::aero::front_wing"][1] == pytest.approx([1.1, 0.6, 0.1])
    # the preview carries the same binding names, so a binding resolves in both files
    import integrity_check as ic
    doc = {"assets": {"meshes": [{"id": "m", "uri": "b.usda", "format": "usd", "preview": "b.glb"}]},
           "chassis": {"mass_total": 1000.0, "center_of_gravity": [-1.2, 0, -0.4], "visual": {"mesh_ref": "m", "node": "SVJ::body::chassis"},
                       "mass_bodies": [{"id": "wheel_fl", "mass": 10.0, "position": [0.0, -0.8, -0.3], "visual": {"mesh_ref": "m", "node": "SVJ::wheel::wheel_fl"}}]}}
    _, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert [x for x in w if "not bound" not in x] == []                           # every bound node resolves; the two unbound ones are only listed


def test_roundtrip_from_gltf_keeps_geometry_and_names(tmp_path):
    triangle_glb(tmp_path / "a.glb")
    g2u.convert(str(tmp_path / "a.glb"), str(tmp_path / "a.usdc"), "Car")
    r = u2g.convert(str(tmp_path / "a.usdc"), str(tmp_path / "back.glb"))
    assert r["triangles"] == 2 and r["named"] == 2
    before, after = read(tmp_path / "a.glb"), read(tmp_path / "back.glb")
    key = lambda n: n["name"] if n["name"].startswith("SVJ::") else n.get("extras", {}).get("svj_node")        # a renamed node keeps its id in extras
    nb, na = {key(n): i for i, n in enumerate(before["nodes"]) if key(n)}, {key(n): i for i, n in enumerate(after["nodes"]) if key(n)}
    assert set(nb) == set(na) == {"SVJ::wheel::wheel_fl", "SVJ::wheel::wheel_fr"}
    bb, ba = mc.node_boxes(before), mc.node_boxes(after)
    for name in nb:
        for k in (0, 1):
            assert ba[na[name]][k] == pytest.approx(bb[nb[name]][k], abs=1e-6)
    assert after["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"][:3] == pytest.approx([0.8, 0.1, 0.1])


def test_face_varying_normals_units_and_unsupported_prims(tmp_path):
    st = Usd.Stage.CreateNew(str(tmp_path / "c.usda"))
    UsdGeom.SetStageUpAxis(st, "Y")
    UsdGeom.SetStageMetersPerUnit(st, 0.01)                                     # a centimetre stage
    UsdGeom.Xform.Define(st, "/Car")
    m = UsdGeom.Mesh.Define(st, "/Car/part")
    m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 0), Gf.Vec3f(100, 0, 0), Gf.Vec3f(0, 100, 0), Gf.Vec3f(100, 100, 0)]))
    m.CreateFaceVertexCountsAttr([3, 3])
    m.CreateFaceVertexIndicesAttr([0, 1, 2, 1, 3, 2])
    m.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 1)] * 6))
    m.SetNormalsInterpolation("faceVarying")
    UsdGeom.BasisCurves.Define(st, "/Car/curve")
    st.GetRootLayer().Save()
    r = u2g.convert(str(tmp_path / "c.usda"), str(tmp_path / "c.glb"))
    g = read(tmp_path / "c.glb")
    assert g["nodes"][-1]["scale"] == [0.01] * 3                                 # the unit scale sits on a root node
    boxes = mc.node_boxes(g)
    top = len(g["nodes"]) - 1
    assert boxes[top][1] == pytest.approx([1.0, 1.0, 0.0])                         # 100 cm are 1 m
    assert any("BasisCurves is not converted" in n for n in r["notes"]) and any("metersPerUnit 0.01" in n for n in r["notes"])
    assert len(g["accessors"]) == 3 and g["accessors"][0]["count"] == 6            # positions, normals, indices; unrolled: one vertex per triangle corner


def test_cli_and_errors(tmp_path, capsys):
    triangle_glb(tmp_path / "a.glb")
    g2u.convert(str(tmp_path / "a.glb"), str(tmp_path / "a.usda"), "Car")
    assert u2g.main([str(tmp_path / "a.usda"), str(tmp_path / "p.glb")]) == 0
    assert "SVJ nodes" in capsys.readouterr().out and (tmp_path / "p.glb").exists()
    (tmp_path / "bad.usda").write_text("not usd", encoding="utf-8")
    assert u2g.main([str(tmp_path / "bad.usda"), str(tmp_path / "x.glb")]) == 1


def test_textures_survive_usd_to_glb_from_usdz_and_folder(tmp_path):
    from tests.test_gltf2usd import textured_glb, tiny_png
    textured_glb(tmp_path / "t.glb")
    for ext in (".usda", ".usdz"):
        g2u.convert(str(tmp_path / "t.glb"), str(tmp_path / ("t" + ext)), "Car")
        r = u2g.convert(str(tmp_path / ("t" + ext)), str(tmp_path / "out.glb"))
        assert r["textures"] == 1 and not any("texture" in n for n in r["notes"])
        g = read(tmp_path / "out.glb")
        mat = g["materials"][0]
        assert "baseColorTexture" in mat["pbrMetallicRoughness"] and "metallicRoughnessTexture" in mat["pbrMetallicRoughness"]
        assert mat["normalTexture"]["scale"] == pytest.approx(0.5)
        assert g["samplers"][0]["wrapS"] == 33071
        bv = g["bufferViews"][g["images"][0]["bufferView"]]
        _, binary = g2u.read_glb(str(tmp_path / "out.glb"))
        assert binary[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]] == tiny_png()


def test_unusable_texture_is_a_note_not_a_failure(tmp_path):
    from tests.test_gltf2usd import textured_glb
    import shutil
    textured_glb(tmp_path / "t.glb")
    g2u.convert(str(tmp_path / "t.glb"), str(tmp_path / "t.usda"), "Car")
    shutil.rmtree(tmp_path / "t_textures")
    r = u2g.convert(str(tmp_path / "t.usda"), str(tmp_path / "out.glb"))
    assert r["textures"] == 0 and any("missing or not PNG" in n for n in r["notes"])
