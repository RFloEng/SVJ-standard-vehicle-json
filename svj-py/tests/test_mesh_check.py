"""Spec §22.9: the mesh-side binding checks (tools/mesh_check.py, run through tools/integrity_check.py --meshes)."""

import json
import struct
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import integrity_check as ic          # noqa: E402
import mesh_check as mc               # noqa: E402


def write_glb(path, gltf):
    """A GLB with the given glTF JSON and an empty binary chunk (the checker never reads buffers)."""
    js = json.dumps(gltf).encode("utf-8")
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", 0, 0x004E4942)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body)


def box_mesh(accessors, meshes, lo, hi):
    """Adds a mesh whose POSITION accessor has the bounds lo..hi; returns the mesh index."""
    accessors.append({"componentType": 5126, "count": 8, "type": "VEC3", "min": list(lo), "max": list(hi)})
    meshes.append({"primitives": [{"attributes": {"POSITION": len(accessors) - 1}}]})
    return len(meshes) - 1


PARTS = {  # node name -> (SVJ position, half size) in SAE axes: x forward, y right, z down
    "SVJ::body::chassis": ([-1.2, 0.0, -0.4], [2.2, 0.9, 0.6]),
    "SVJ::wheel::wheel_fl": ([0.0, -0.8, -0.3], [0.3, 0.12, 0.3]),
    "SVJ::wheel::wheel_fr": ([0.0, 0.8, -0.3], [0.3, 0.12, 0.3]),
    "SVJ::wheel::wheel_rl": ([-2.6, -0.8, -0.3], [0.3, 0.12, 0.3]),
}


def make_gltf(parts=PARTS, transform=None, extras=None, names=None):
    """glTF with one node per part, geometry centred on the SVJ position. `transform(pos, half)` -> (lo, hi) bounds."""
    accessors, meshes, nodes = [], [], []
    for name, (pos, half) in parts.items():
        lo, hi = ([p - h for p, h in zip(pos, half)], [p + h for p, h in zip(pos, half)]) if transform is None else transform(pos, half)
        n = {"name": (names or {}).get(name, name), "mesh": box_mesh(accessors, meshes, lo, hi)}
        if extras and name in extras:
            n["extras"] = extras[name]
        nodes.append(n)
    return {"asset": {"version": "2.0"}, "nodes": nodes, "meshes": meshes, "accessors": accessors, "scenes": [{"nodes": list(range(len(nodes)))}]}


def make_doc(parts=PARTS, **meta):
    mass_bodies = [{"id": n.split("::")[2], "mass": 10.0, "position": pos, "visual": {"mesh_ref": "m", "node": n}}
                   for n, (pos, _) in parts.items() if not n.endswith("chassis")]
    return {"_metadata": dict(meta), "assets": {"meshes": [{"id": "m", "uri": "car.glb"}]},
            "chassis": {"mass_total": 1000.0, "center_of_gravity": parts["SVJ::body::chassis"][0],
                        "visual": {"mesh_ref": "m", "node": "SVJ::body::chassis"}, "mass_bodies": mass_bodies}}


def run(tmp_path, gltf, doc=None, entry=None):
    write_glb(tmp_path / "car.glb", gltf)
    doc = doc or make_doc()
    if entry:
        doc["assets"]["meshes"][0].update(entry)
    bindings = ic.collect_bindings(doc)
    errors, warnings, notes = mc.check_meshes(doc, bindings, str(tmp_path))
    assert errors == []                                     # mesh problems are never errors
    return warnings, notes


def test_reads_glb_and_gltf_and_rejects_garbage(tmp_path):
    write_glb(tmp_path / "a.glb", {"asset": {"version": "2.0"}, "nodes": [{"name": "x"}]})
    assert mc.read_gltf(tmp_path / "a.glb")["nodes"][0]["name"] == "x"
    (tmp_path / "b.gltf").write_text('{"asset": {"version": "2.0"}}', encoding="utf-8")
    assert mc.read_gltf(tmp_path / "b.gltf")["asset"]["version"] == "2.0"
    (tmp_path / "c.glb").write_bytes(b"not a model")
    with pytest.raises(mc.MeshError):
        mc.read_gltf(tmp_path / "c.glb")
    with pytest.raises(mc.MeshError, match="not found"):
        mc.read_gltf(tmp_path / "missing.glb")


def test_clean_asset_has_no_findings(tmp_path):
    assert run(tmp_path, make_gltf()) == ([], [])


def test_missing_duplicate_and_orphan_nodes(tmp_path):
    g = make_gltf()
    g["nodes"][1]["name"] = "SVJ::wheel::wheel_xx"                      # the bound wheel_fl is gone, an unbound one appears
    g["nodes"].append(dict(g["nodes"][2]))                              # wheel_fr twice
    w, _ = run(tmp_path, g)
    assert any("'SVJ::wheel::wheel_fl' does not exist" in x for x in w)
    assert any("'SVJ::wheel::wheel_fr' occurs 2 times" in x for x in w)
    assert any("'SVJ::wheel::wheel_xx'" in x and "not bound" in x for x in w)


def test_extras_id_survives_a_rename_in_the_asset(tmp_path):
    g = make_gltf(names={"SVJ::wheel::wheel_fl": "Wheel.001"}, extras={"SVJ::wheel::wheel_fl": {"svj_node": "SVJ::wheel::wheel_fl"}})
    w, notes = run(tmp_path, g)
    assert w == []
    assert any("found through extras.svj_node" in n for n in notes)
    g = make_gltf(extras={"SVJ::wheel::wheel_fl": {"svj_node": "SVJ::wheel::wheel_fr"}})        # name and extras disagree
    w, _ = run(tmp_path, g)
    assert any("name and extras disagree" in x for x in w)


def test_missing_file_and_other_formats(tmp_path):
    doc = make_doc()
    errors, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert errors == [] and any("file not found" in x for x in w)
    doc["assets"]["meshes"][0]["uri"] = "car.usdz"
    errors, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert w == [] and any("not a glTF asset" in n for n in notes)


def test_units_millimetres_are_reported(tmp_path):
    g = make_gltf(transform=lambda pos, half: ([(p - h) * 1000 for p, h in zip(pos, half)], [(p + h) * 1000 for p, h in zip(pos, half)]))
    w, _ = run(tmp_path, g)
    assert any("1e+03 times" in x or "1000 times" in x for x in w) and any("millimetres" in x for x in w)
    # x_transform.scale repairs it
    w, _ = run(tmp_path, g, entry={"x_transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [0.001, 0.001, 0.001]}})
    assert w == []


def blender_gltf():
    """The same car with the geometry in Blender axes: SAE x -> -z, y -> x, z -> -y."""
    def tf(pos, half):
        c = [pos[1], -pos[2], -pos[0]]
        h = [half[1], half[2], half[0]]
        return [a - b for a, b in zip(c, h)], [a + b for a, b in zip(c, h)]
    return make_gltf(transform=tf)


def test_axes_declared_and_undeclared(tmp_path):
    g = blender_gltf()
    w, _ = run(tmp_path, g, doc=make_doc(coordinate_system={"up": "Y", "forward": "-Z", "handedness": "right"}))
    assert w == []                                                      # declared correctly
    w, _ = run(tmp_path, g)                                             # not declared: SAE assumed, Blender fits better
    assert any("fits Y-up, -Z forward (Blender export) better" in x for x in w)
    w, _ = run(tmp_path, g, doc=make_doc(coordinate_system={"up": "Z", "forward": "X", "handedness": "right"}))
    assert any("better than the declared coordinate_system" in x for x in w)


def test_common_shift_is_one_message(tmp_path):
    g = make_gltf(transform=lambda pos, half: ([p - h + (2.5 if k == 0 else 0) for k, (p, h) in enumerate(zip(pos, half))],
                                               [p + h + (2.5 if k == 0 else 0) for k, (p, h) in enumerate(zip(pos, half))]))
    w, _ = run(tmp_path, g)
    assert len(w) == 1 and "appears shifted by (+2.500" in w[0] and "x_transform.position to about (-2.500" in w[0]
    w, _ = run(tmp_path, g, entry={"x_transform": {"position": [-2.5, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}})
    assert w == []


def test_one_misplaced_part_is_named(tmp_path):
    parts = dict(PARTS)
    g = make_gltf()
    g["accessors"][3]["min"] = [-2.6 - 0.3 + 3, -0.92, -0.6]            # wheel_rl moved 3 m forward
    g["accessors"][3]["max"] = [-2.6 + 0.3 + 3, -0.68, 0.0]
    w, _ = run(tmp_path, g)
    assert len(w) == 1 and "SVJ::wheel::wheel_rl" in w[0] and "outside the node's box" in w[0]


def test_group_node_uses_its_children_and_transforms(tmp_path):
    accessors, meshes = [], []
    m = box_mesh(accessors, meshes, [-0.3, -0.12, -0.3], [0.3, 0.12, 0.3])
    g = {"asset": {"version": "2.0"}, "accessors": accessors, "meshes": meshes,
         "nodes": [{"name": "SVJ::wheel::wheel_fl", "translation": [0.0, -0.8, -0.3], "children": [1]}, {"name": "rim", "mesh": m}],
         "scenes": [{"nodes": [0]}]}
    boxes = mc.node_boxes(g)
    assert boxes[0] == pytest.approx(([-0.3, -0.92, -0.6], [0.3, -0.68, 0.0])) or boxes[0] == ([-0.3, -0.92, -0.6], [0.3, -0.68, 0.0])
    # a rotation about x by 90 degrees swaps the y and z extents
    g["nodes"][0]["rotation"] = [0.7071068, 0, 0, 0.7071068]
    lo, hi = mc.node_boxes(g)[0]
    assert (hi[1] - lo[1]) == pytest.approx(0.6) and (hi[2] - lo[2]) == pytest.approx(0.24)


def test_integrity_check_flag_and_strict(tmp_path, capsys):
    write_glb(tmp_path / "car.glb", make_gltf())
    f = tmp_path / "car.svj.json"
    f.write_text(json.dumps(make_doc()), encoding="utf-8")
    assert ic.check(str(f), meshes=True) is True
    g = make_gltf()
    g["nodes"][1]["name"] = "SVJ::wheel::wheel_xx"
    write_glb(tmp_path / "car.glb", g)
    assert ic.check(str(f), meshes=True) is True                        # warnings only
    assert ic.check(str(f), strict=True, meshes=True) is False          # --strict fails on them
    assert ic.check(str(f), strict=True, meshes=False) is True          # without --meshes the mesh is not opened
    assert "does not exist in car.glb" in capsys.readouterr().out
