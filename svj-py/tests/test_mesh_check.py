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
    doc["assets"]["meshes"][0]["uri"] = "car.fbx"
    errors, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert w == [] and any("not a glTF or OpenUSD asset" in n for n in notes)


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


# ── OpenUSD assets (spec 22.10) ───────────────────────────────────────────────
try:
    from pxr import Gf, Sdf, Usd, UsdGeom
    HAVE_USD = True
except ImportError:                      # usd-core is optional: the USD tests are skipped without it
    HAVE_USD = False
needs_usd = pytest.mark.skipif(not HAVE_USD, reason="usd-core is not installed")


def make_usd(path, parts=PARTS, meters_per_unit=1.0, up="Z", by="attr", shift=(0.0, 0.0, 0.0), scale=1.0):
    """A USD stage with one Xform + Cube per part, centred on the SVJ position (SAE axes, stage up Z so no conversion)."""
    stage = Usd.Stage.CreateNew(str(path))
    if meters_per_unit is not None:
        UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)
    UsdGeom.SetStageUpAxis(stage, up)
    UsdGeom.Xform.Define(stage, "/Car")
    for name, (pos, half) in parts.items():
        pname = name.replace("::", "__") if by == "name" else "part_" + name.split("::")[2]
        prim = UsdGeom.Xform.Define(stage, f"/Car/{pname}")
        cube = UsdGeom.Cube.Define(stage, f"/Car/{pname}/shape")
        cube.GetSizeAttr().Set(2.0)
        UsdGeom.XformCommonAPI(cube).SetScale(Gf.Vec3f(*[h * scale for h in half]))
        UsdGeom.XformCommonAPI(prim).SetTranslate(Gf.Vec3d(*[(p + s) * scale for p, s in zip(pos, shift)]))
        if by == "attr":
            prim.GetPrim().CreateAttribute("svj:node", Sdf.ValueTypeNames.String, custom=True).Set(name)
    stage.GetRootLayer().Save()


def usd_run(tmp_path, doc=None, **kw):
    make_usd(tmp_path / "car.usda", **kw)
    doc = doc or make_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    errors, warnings, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert errors == []
    return warnings, notes


@needs_usd
def test_usd_binding_by_attribute_and_by_prim_name(tmp_path):
    assert usd_run(tmp_path, by="attr") == ([], [])
    assert usd_run(tmp_path, by="name") == ([], [])


@needs_usd
def test_usd_missing_node_orphan_and_duplicate(tmp_path):
    parts = dict(PARTS)
    w, _ = usd_run(tmp_path, parts={k: v for k, v in PARTS.items() if k != "SVJ::wheel::wheel_fl"})
    assert any("'SVJ::wheel::wheel_fl' does not exist" in x for x in w)
    parts["SVJ::wheel::wheel_xx"] = ([5.0, 0.0, 0.0], [0.1, 0.1, 0.1])
    w, _ = usd_run(tmp_path, parts=parts)
    assert any("'SVJ::wheel::wheel_xx'" in x and "not bound" in x for x in w)
    make_usd(tmp_path / "car.usda")
    stage = Usd.Stage.Open(str(tmp_path / "car.usda"))
    dup = UsdGeom.Xform.Define(stage, "/Car/copy_of_fl")
    dup.GetPrim().CreateAttribute("svj:node", Sdf.ValueTypeNames.String, custom=True).Set("SVJ::wheel::wheel_fl")
    stage.GetRootLayer().Save()
    doc = make_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("occurs 2 times" in x for x in w)


@needs_usd
def test_usd_units_declaration_and_conversion(tmp_path):
    w, _ = usd_run(tmp_path, meters_per_unit=None)
    assert any("does not author metersPerUnit" in x for x in w)
    w, _ = usd_run(tmp_path, meters_per_unit=0.01, scale=100.0)                 # a centimetre stage: right size, wrong declaration
    assert any("metersPerUnit = 0.01" in x for x in w) and not any("times the size" in x for x in w)
    w, _ = usd_run(tmp_path, meters_per_unit=1.0, scale=1000.0)                 # geometry 1000 times too large
    assert any("times the size" in x for x in w)


@needs_usd
def test_usd_placement_shift_and_y_up_axes(tmp_path):
    w, _ = usd_run(tmp_path, shift=(2.5, 0.0, 0.0))
    assert len(w) == 1 and "appears shifted by (+2.500" in w[0]
    # a Y-up Blender-style stage with its convention declared
    parts = {n: ([p[1], -p[2], -p[0]], [h[1], h[2], h[0]]) for n, (p, h) in PARTS.items()}
    make_usd(tmp_path / "car.usda", parts=parts, up="Y")
    doc = make_doc(coordinate_system={"up": "Y", "forward": "-Z", "handedness": "right"})
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert w == []


@needs_usd
def test_usd_unreadable_and_skipped_without_library(tmp_path, monkeypatch):
    (tmp_path / "car.usda").write_text("this is not usd", encoding="utf-8")
    doc = make_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda"})
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("not readable as OpenUSD" in x for x in w)
    make_usd(tmp_path / "car.usda")
    monkeypatch.setitem(sys.modules, "pxr", None)                               # simulates a missing usd-core
    _, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert w == [] and any("needs the usd-core library" in n for n in notes)


def test_preview_copy_of_a_usd_asset(tmp_path):
    """spec 22.10: the `preview` glTF of an OpenUSD asset exists and carries the bound nodes (needs no usd-core)."""
    write_glb(tmp_path / "car.preview.glb", make_gltf())
    doc = make_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usdc", "format": "usd", "preview": "car.preview.glb"})
    _, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert w == [] or all("car.usdc" in x for x in w)                          # the USD itself may be missing / unreadable here, the preview is fine
    assert not any("preview" in x for x in w)
    g = make_gltf()
    g["nodes"][1]["name"] = "SVJ::wheel::wheel_xx"
    write_glb(tmp_path / "car.preview.glb", g)
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("preview car.preview.glb does not contain the bound node 'SVJ::wheel::wheel_fl'" in x for x in w)
    (tmp_path / "car.preview.glb").unlink()
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("preview car.preview.glb: file not found" in x and "usd2gltf" in x for x in w)
    doc["assets"]["meshes"][0]["preview"] = "car.preview.usd"
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("is not a .glb or .gltf file" in x for x in w)
    doc["assets"]["meshes"][0].update({"uri": "car.glb", "format": "gltf", "preview": "car.preview.glb"})
    _, _, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("only applies to OpenUSD assets" in n for n in notes)


@needs_usd
def test_usd_physics_and_animation_must_be_copies_of_the_json(tmp_path):
    """spec 22.10 rule 8: nothing physical or kinematic in the asset that the JSON does not have first."""
    from pxr import UsdPhysics
    make_usd(tmp_path / "car.usda")
    stage = Usd.Stage.Open(str(tmp_path / "car.usda"))
    fl = stage.GetPrimAtPath("/Car/part_wheel_fl")
    UsdPhysics.RigidBodyAPI.Apply(fl)
    UsdPhysics.MassAPI.Apply(fl).CreateMassAttr(12.5)                       # the JSON says 10 kg
    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath("/Car/part_wheel_fr/shape"))
    xf = UsdGeom.Xform(stage.GetPrimAtPath("/Car/part_wheel_rl"))
    op = xf.AddRotateYOp()
    op.Set(0.0, Usd.TimeCode(0))
    op.Set(90.0, Usd.TimeCode(24))                                          # an animation, and the JSON has no joint for wheel_rl
    stage.GetRootLayer().Save()
    doc = make_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    _, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("differs from the JSON (10 kg); the JSON wins" in x and "12.5" in x for x in w)
    assert any("collision shape that the JSON has no `collision` proxy" in x and "wheel_fr" in x for x in w)
    assert any("animated" in x and "wheel_rl" in x and "no joint" in x for x in w)
    # the JSON has the data first: same mass, a collision proxy, a joint that moves the part
    for b in doc["chassis"]["mass_bodies"]:
        if b["id"] == "wheel_fr":
            b["collision"] = [{"id": "c", "type": "sphere", "radius": 0.3, "position": b["position"]}]
    doc["constraints"] = [{"id": "hinge_rl", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "wheel_rl"}]
    for b in doc["chassis"]["mass_bodies"]:
        if b["id"] == "wheel_fl":
            b["mass"] = 12.5
    _, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert not any("differs" in x or "collision shape" in x or "no joint" in x for x in w)
    assert any("the JSON wins, the asset's animation is ignored" in n for n in notes)


# ── unified files: bindings on wheel_stations[] and constraints[]; animation attributed to the nearest bound node ──────────
def unified_doc():
    """The structure an AC_to_SVJ conversion writes: chassis, upright, wheel and a door as bodies; the carrier and the disc bound on
    wheel_stations[]; the door moved by its own joint and pose."""
    body = lambda i, pos, **kw: dict({"id": i, "mass": 10.0, "position": pos}, **kw)
    vis = lambda node: {"mesh_ref": "x", "node": node}
    return {"_metadata": {"version": "0.106"}, "assets": {"meshes": [{"id": "x", "uri": "car.glb"}]},
            "chassis": {"mass_total": 1000.0, "center_of_gravity": [-1.2, 0.0, -0.4], "visual": vis("SVJ::body::chassis"),
                        "mass_bodies": [body("upright_fl", [0.0, -0.8, -0.3]),
                                        body("wheel_fl", [0.0, -0.8, -0.3], visual=vis("SVJ::wheel::wheel_fl")),
                                        body("door_fl", [-1.0, -0.9, -0.6], visual=vis("SVJ::body::door_fl"))]},
            "wheel_stations": [{"id": "FL", "upright_body": "upright_fl", "wheel_body": "wheel_fl",
                                "visual": vis("SVJ::suspension::upright_fl"),
                                "brake": {"disc": {"visual": vis("SVJ::brake::disc_fl")}}}],
            "constraints": [{"id": "hinge_door_fl", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "door_fl"}],
            "poses": [{"id": "door_fl_open", "values": {"hinge_door_fl": 1.0}}]}


UNIFIED_PARTS = {
    "SVJ::body::chassis": ([-1.2, 0.0, -0.4], [2.2, 0.9, 0.6]),
    "SVJ::suspension::upright_fl": ([0.0, -0.8, -0.3], [0.1, 0.1, 0.2]),
    "SVJ::wheel::wheel_fl": ([0.0, -0.8, -0.3], [0.3, 0.12, 0.3]),
    "SVJ::brake::disc_fl": ([0.0, -0.8, -0.3], [0.15, 0.02, 0.15]),
    "SVJ::body::door_fl": ([-1.0, -0.9, -0.6], [0.5, 0.05, 0.4]),
}


def test_unified_bindings_on_stations_are_collected_and_checked(tmp_path):
    doc = unified_doc()
    b = {x["location"]: x for x in ic.collect_bindings(doc)}
    assert set(b) >= {"chassis", "wheel_stations[FL]", "wheel_stations[FL].brake.disc", "chassis.mass_bodies[wheel_fl]"}
    assert b["wheel_stations[FL]"]["ids"] == {"upright_fl"} and b["wheel_stations[FL]"]["pos"] == [0.0, -0.8, -0.3]    # the upright body's position
    assert {"disc_fl", "disc"} <= b["wheel_stations[FL].brake.disc"]["ids"]
    # 1. nothing is an orphan; a node bound nowhere still is
    g = make_gltf(parts=UNIFIED_PARTS)
    g["nodes"].append({"name": "SVJ::brake::caliper_fl"})
    w, _ = run(tmp_path, g, doc=doc)
    assert [x for x in w if "not bound" in x] == ["[mesh 'x'] node 'SVJ::brake::caliper_fl' in car.glb is not bound by any part of this file"]
    assert not any("upright_fl" in x or "disc_fl" in x for x in w)
    # the placement check covers the station-level bindings too: move the upright 1 m forward
    g = make_gltf(parts=UNIFIED_PARTS)
    i = [n["name"] for n in g["nodes"]].index("SVJ::suspension::upright_fl")
    acc = g["accessors"][g["nodes"][i]["mesh"]]
    acc["min"][0] += 1.0
    acc["max"][0] += 1.0
    w, _ = run(tmp_path, g, doc=doc)
    assert any("SVJ::suspension::upright_fl" in x and "outside the node's box" in x for x in w)


def test_station_binding_id_rule_and_uniqueness(tmp_path, capsys):
    doc = unified_doc()
    doc["wheel_stations"][0]["visual"]["node"] = "SVJ::suspension::upright_rl"           # the wrong station
    f = tmp_path / "u.svj.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    assert ic.check(str(f)) is False
    out = capsys.readouterr().out
    assert "[wheel_stations[FL]] Binding mismatch" in out and "upright_rl" in out
    # one node bound from wheel_stations[] and from mass_bodies[] is a duplicate
    doc = unified_doc()
    doc["chassis"]["mass_bodies"][0]["visual"] = {"mesh_ref": "x", "node": "SVJ::suspension::upright_fl"}
    f.write_text(json.dumps(doc), encoding="utf-8")
    assert ic.check(str(f)) is False
    assert "Duplicate node 'SVJ::suspension::upright_fl'" in capsys.readouterr().out
    # constraints[] elements are bound under their own id
    doc = unified_doc()
    doc["constraints"].append({"id": "spring_fl", "type": "spring", "visual": {"mesh_ref": "x", "node": "SVJ::suspension::spring_fl"}})
    assert {x["location"]: x["ids"] for x in ic.collect_bindings(doc)}["constraints[spring_fl]"] == {"spring_fl"}


def gltf_with_door(animated_door=True, door_name="SVJ::body::door_fl", other_animated=False):
    """chassis node with a door node below it (and an unnamed flap), the door animated, plus the station parts."""
    accessors, meshes = [], []
    mk = lambda pos, half: box_mesh(accessors, meshes, [p - h for p, h in zip(pos, half)], [p + h for p, h in zip(pos, half)])
    nodes = [{"name": "SVJ::body::chassis", "mesh": mk(*UNIFIED_PARTS["SVJ::body::chassis"]), "children": [1, 2]},
             {"name": door_name, "mesh": mk(*UNIFIED_PARTS["SVJ::body::door_fl"])},
             {"name": "flap", "mesh": mk([-2.0, 0.0, -0.9], [0.1, 0.3, 0.02])}]
    for n in ("SVJ::suspension::upright_fl", "SVJ::wheel::wheel_fl", "SVJ::brake::disc_fl"):
        nodes.append({"name": n, "mesh": mk(*UNIFIED_PARTS[n])})
    targets = ([1] if animated_door else []) + ([2] if other_animated else [])
    anim = [{"samplers": [{"input": 0, "output": 0}], "channels": [{"sampler": 0, "target": {"node": t, "path": "rotation"}} for t in targets]}] if targets else []
    g = {"asset": {"version": "2.0"}, "nodes": nodes, "meshes": meshes, "accessors": accessors, "scenes": [{"nodes": [0, 3, 4, 5]}]}
    if anim:
        g["animations"] = anim
    return g


def test_animation_belongs_to_the_nearest_bound_node_gltf(tmp_path):
    doc = unified_doc()
    # 4. the animated descendant is bound to door_fl, which has a joint: nothing against the chassis, the JSON-wins note for the door
    w, notes = run(tmp_path, gltf_with_door(), doc=doc)
    assert not any("animated" in x for x in w)
    assert any("SVJ::body::door_fl" in n and "JSON wins" in n for n in notes) and not any("SVJ::body::chassis" in n and "JSON wins" in n for n in notes)
    # an animated descendant bound to nothing (an unnamed flap) is still reported against the chassis
    w, _ = run(tmp_path, gltf_with_door(animated_door=False, other_animated=True), doc=doc)
    assert any("'SVJ::body::chassis' is animated" in x and "no joint" in x for x in w)
    # a bound door the JSON has no joint for is reported against the door, not the chassis
    doc["constraints"] = []
    w, _ = run(tmp_path, gltf_with_door(), doc=doc)
    assert any("'SVJ::body::door_fl' is animated" in x for x in w) and not any("'SVJ::body::chassis' is animated" in x for x in w)
    # the door node is in the asset but no part binds it: its animation falls back to the chassis
    doc = unified_doc()
    doc["chassis"]["mass_bodies"] = [b for b in doc["chassis"]["mass_bodies"] if b["id"] != "door_fl"]
    w, _ = run(tmp_path, gltf_with_door(), doc=doc)
    assert any("'SVJ::body::chassis' is animated" in x for x in w) and any("'SVJ::body::door_fl'" in x and "not bound" in x for x in w)


def make_usd_unified(path, door_animated=True, flap_animated=False, door_name="door"):
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/Car")

    def part(prim_path, node, pos, half, animate=False):
        x = UsdGeom.Xform.Define(stage, prim_path)
        x.GetPrim().CreateAttribute("svj:node", Sdf.ValueTypeNames.String, custom=True).Set(node) if node else None
        UsdGeom.XformCommonAPI(x).SetTranslate(Gf.Vec3d(*pos))
        cube = UsdGeom.Cube.Define(stage, prim_path + "/shape")
        cube.GetSizeAttr().Set(2.0)
        UsdGeom.XformCommonAPI(cube).SetScale(Gf.Vec3f(*half))
        if animate:
            op = x.AddRotateYOp()
            op.Set(0.0, Usd.TimeCode(0))
            op.Set(80.0, Usd.TimeCode(24))
    part("/Car/body", "SVJ::body::chassis", [0, 0, 0], [0.01, 0.01, 0.01])
    stage.GetPrimAtPath("/Car/body").GetAttribute("svj:node")
    for n, (pos, half) in UNIFIED_PARTS.items():
        if n in ("SVJ::body::door_fl",):
            continue
        if n == "SVJ::body::chassis":
            continue
        part("/Car/" + n.split("::")[2], n, pos, half)
    part("/Car/body/" + door_name, "SVJ::body::door_fl" if door_name == "door" else None, UNIFIED_PARTS["SVJ::body::door_fl"][0], UNIFIED_PARTS["SVJ::body::door_fl"][1], animate=door_animated)
    part("/Car/body/flap", None, [-2.0, 0.0, -0.9], [0.1, 0.3, 0.02], animate=flap_animated)
    stage.GetRootLayer().Save()


@needs_usd
def test_station_bindings_and_animation_ownership_usd(tmp_path):
    doc = unified_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    make_usd_unified(tmp_path / "car.usda")
    errors, w, notes = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert errors == [] and not any("not bound" in x for x in w) and not any("animated" in x for x in w)
    assert any("SVJ::body::door_fl" in n and "JSON wins" in n for n in notes)
    # an animated flap bound to nothing is reported against the chassis
    make_usd_unified(tmp_path / "car.usda", door_animated=False, flap_animated=True)
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("'SVJ::body::chassis' is animated" in x and "no joint" in x for x in w)
    # a door without a joint in the JSON is reported against the door only
    doc["constraints"] = []
    make_usd_unified(tmp_path / "car.usda")
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert any("'SVJ::body::door_fl' is animated" in x for x in w) and not any("'SVJ::body::chassis' is animated" in x for x in w)
    # physics data in a bound descendant is attributed the same way: the door's mass is checked against the door body, not the chassis
    from pxr import UsdPhysics
    doc = unified_doc()
    doc["assets"]["meshes"][0].update({"uri": "car.usda", "format": "usd"})
    make_usd_unified(tmp_path / "car.usda", door_animated=False)
    stage = Usd.Stage.Open(str(tmp_path / "car.usda"))
    UsdPhysics.MassAPI.Apply(stage.GetPrimAtPath("/Car/body/door")).CreateMassAttr(10.0)           # the JSON door is 10 kg
    stage.GetRootLayer().Save()
    _, w, _ = mc.check_meshes(doc, ic.collect_bindings(doc), str(tmp_path))
    assert not any("differs from the JSON" in x or "carries a mass" in x for x in w)
