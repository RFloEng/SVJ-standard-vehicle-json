"""tools/gltf2usd.py: GLB -> OpenUSD conversion following spec §22.10 (needs the optional usd-core library)."""

import json
import struct
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

pxr = pytest.importorskip("pxr", reason="usd-core is not installed")
from pxr import Usd, UsdGeom, UsdShade   # noqa: E402

import gltf2usd as g2u      # noqa: E402
import integrity_check as ic  # noqa: E402
import mesh_check as mc     # noqa: E402


def write_glb_with_bin(path, gltf, binary):
    js = json.dumps(gltf).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body)


def triangle_glb(path, half=0.3):
    """A GLB with a wheel group node 'SVJ::wheel::wheel_fl' (translated) holding a child node with one triangle mesh."""
    pos = [(-half, -half, 0.0), (half, -half, 0.0), (0.0, half, 0.0)]
    nrm = [(0.0, 0.0, 1.0)] * 3
    uv = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    binary = b"".join(struct.pack("<3f", *p) for p in pos) + b"".join(struct.pack("<3f", *n) for n in nrm) \
        + b"".join(struct.pack("<2f", *u) for u in uv) + struct.pack("<3H", 0, 1, 2)
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0, 3]}],
            "nodes": [{"name": "SVJ::wheel::wheel_fl", "translation": [0.0, -0.8, -0.3], "children": [1]},
                      {"name": "rim", "mesh": 0},
                      {"name": "unused"},
                      {"name": "Wheel.001", "extras": {"svj_node": "SVJ::wheel::wheel_fr"}, "translation": [0.0, 0.8, -0.3], "mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0}]}],
            "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.1, 0.1, 1.0], "metallicFactor": 0.9, "roughnessFactor": 0.3}}],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}, {"buffer": 0, "byteOffset": 36, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 72, "byteLength": 24}, {"buffer": 0, "byteOffset": 96, "byteLength": 6}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [-half, -half, 0.0], "max": [half, half, 0.0]},
                          {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
                          {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC2"},
                          {"bufferView": 3, "componentType": 5123, "count": 3, "type": "SCALAR"}]}
    write_glb_with_bin(path, gltf, binary)


def test_converts_hierarchy_names_attributes_and_geometry(tmp_path):
    triangle_glb(tmp_path / "a.glb")
    r = g2u.convert(str(tmp_path / "a.glb"), str(tmp_path / "a.usda"), "Car")
    assert r["meshes"] == 2 and r["triangles"] == 2 and r["named"] == 2
    stage = Usd.Stage.Open(str(tmp_path / "a.usda"))
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0 and UsdGeom.GetStageUpAxis(stage) == "Y"
    wheel = stage.GetPrimAtPath("/Car/SVJ__wheel__wheel_fl")
    assert wheel and wheel.GetAttribute("svj:node").Get() == "SVJ::wheel::wheel_fl"
    renamed = stage.GetPrimAtPath("/Car/Wheel_001")                          # a renamed node keeps its binding name from extras
    assert renamed and renamed.GetAttribute("svj:node").Get() == "SVJ::wheel::wheel_fr"
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath("/Car/SVJ__wheel__wheel_fl/rim/mesh_0"))
    assert len(mesh.GetPointsAttr().Get()) == 3 and list(mesh.GetFaceVertexIndicesAttr().Get()) == [0, 1, 2]
    assert len(mesh.GetNormalsAttr().Get()) == 3
    cache = UsdGeom.XformCache()
    t = cache.GetLocalToWorldTransform(mesh.GetPrim()).ExtractTranslation()
    assert (t[0], t[1], t[2]) == pytest.approx((0.0, -0.8, -0.3))             # the node translation survives
    mat = UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0]
    assert mat and tuple(UsdShade.Shader(stage.GetPrimAtPath(str(mat.GetPath()) + "/Surface")).GetInput("diffuseColor").Get()) == pytest.approx((0.8, 0.1, 0.1))


def test_converted_asset_passes_the_mesh_check(tmp_path):
    triangle_glb(tmp_path / "a.glb")
    g2u.convert(str(tmp_path / "a.glb"), str(tmp_path / "a.usdc"), "Car")
    doc = {"assets": {"meshes": [{"id": "m", "uri": "a.usdc"}]},
           "chassis": {"mass_total": 1000.0, "center_of_gravity": [-1.0, 0.0, -0.4],
                       "mass_bodies": [{"id": "wheel_fl", "mass": 10.0, "position": [0.0, -0.8, -0.3], "visual": {"mesh_ref": "m", "node": "SVJ::wheel::wheel_fl"}},
                                       {"id": "wheel_fr", "mass": 10.0, "position": [0.0, 0.8, -0.3], "visual": {"mesh_ref": "m", "node": "SVJ::wheel::wheel_fr"}}]}}
    # the asset is in glTF axes (Y up); declare that and the two wheels sit where SVJ says
    doc["_metadata"] = {"coordinate_system": {"up": "Y", "forward": "-Z", "handedness": "right"}}
    doc["chassis"]["mass_bodies"][0]["position"] = [0.0, -0.8, -0.3]
    errors, warnings, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert errors == [] and not any("does not exist" in w or "metersPerUnit" in w for w in warnings)


def test_usdz_package_and_cli(tmp_path, capsys):
    triangle_glb(tmp_path / "a.glb")
    assert g2u.main([str(tmp_path / "a.glb"), str(tmp_path / "a.usdz"), "--root", "Car"]) == 0
    assert (tmp_path / "a.usdz").exists() and not (tmp_path / "a.usdc").exists()
    assert "2 meshes" in capsys.readouterr().out
    assert Usd.Stage.Open(str(tmp_path / "a.usdz")).GetPrimAtPath("/Car/SVJ__wheel__wheel_fl")
    assert g2u.main([str(tmp_path / "missing.glb"), str(tmp_path / "b.usda")]) == 1


def test_triangle_strips_and_fans_and_unsupported_accessors(tmp_path):
    triangle_glb(tmp_path / "a.glb")
    js, binary = g2u.read_glb(str(tmp_path / "a.glb"))
    js["meshes"][0]["primitives"][0]["mode"] = 6                              # a fan with 3 indices: one triangle
    write_glb_with_bin(tmp_path / "b.glb", js, binary)
    assert g2u.convert(str(tmp_path / "b.glb"), str(tmp_path / "b.usda"))["triangles"] == 2
    js["meshes"][0]["primitives"][0]["mode"] = 1                              # lines: skipped with a note
    write_glb_with_bin(tmp_path / "c.glb", js, binary)
    r = g2u.convert(str(tmp_path / "c.glb"), str(tmp_path / "c.usda"))
    assert r["meshes"] == 0 and any("not a triangle mode" in n for n in r["notes"])
    js["accessors"][0]["sparse"] = {"count": 1}
    write_glb_with_bin(tmp_path / "d.glb", js, binary)
    with pytest.raises(g2u.ConvertError):
        js["meshes"][0]["primitives"][0]["mode"] = 4
        write_glb_with_bin(tmp_path / "d.glb", js, binary)
        g2u.convert(str(tmp_path / "d.glb"), str(tmp_path / "d.usda"))


def test_glb_animations_are_not_carried_into_the_usd(tmp_path):
    """spec 22.10 rule 8: animation may only be a copy of data the JSON has first, so the converter leaves it out and says so."""
    triangle_glb(tmp_path / "a.glb")
    js, binary = g2u.read_glb(str(tmp_path / "a.glb"))
    js["animations"] = [{"name": "spin", "samplers": [{"input": 0, "output": 1}], "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}]}]
    write_glb_with_bin(tmp_path / "b.glb", js, binary)
    r = g2u.convert(str(tmp_path / "b.glb"), str(tmp_path / "b.usda"), "Car")
    assert any("1 glTF animation(s) are not converted" in n and "JSON" in n for n in r["notes"])
    stage = Usd.Stage.Open(str(tmp_path / "b.usda"))
    assert not any(UsdGeom.Xformable(p) and UsdGeom.Xformable(p).TransformMightBeTimeVarying() for p in stage.Traverse())
