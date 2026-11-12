"""SAE J670 <-> ISO 8855 frame conversion (ISO migration, step 1)."""

import copy
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.frame import ISO, SAE, convert, flip_vector, frame_of, quat_to_iso, quat_to_sae   # noqa: E402

FILES = sorted(list((REPO_ROOT / "examples").glob("*.svj.json")) + list((REPO_ROOT / "templates").glob("*.svj.json")))


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def rotate(q, v):
    """Rotate vector v by unit quaternion q = [x, y, z, w]."""
    x, y, z, w = q
    t = [2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])]
    return [v[0] + w * t[0] + (y * t[2] - z * t[1]), v[1] + w * t[1] + (z * t[0] - x * t[2]),
            v[2] + w * t[2] + (x * t[1] - y * t[0])]


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "convert_frame.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "frame.py").read_text()


def test_vector_and_declaration():
    assert flip_vector([1.0, 2.0, -3.0]) == [1.0, -2.0, 3.0]
    assert flip_vector([1, 0, 0]) == [1, 0, 0] and str(flip_vector([1, 0.0, 0.0])[1]) == "0.0"      # no negative zero
    assert frame_of({}) == SAE and frame_of({"_metadata": {"coordinate_system": "SAE_J670"}}) == SAE
    assert frame_of({"_metadata": {"coordinate_system": "ISO_8855"}}) == ISO


def test_quaternion_matches_the_rotated_frame():
    """q is the orientation of a frame (frame axes -> vehicle axes). The frame keeps its physical identity, so each
    of its axes, expressed in ISO, is the SAE axis with Y and Z flipped: R(q') v = S R(q) v."""
    for q in ([0.1, 0.2, 0.3, math.sqrt(1 - 0.14)], [0, 0, math.sin(0.4), math.cos(0.4)], [math.sin(0.3), 0, 0, math.cos(0.3)]):
        qi = quat_to_iso(q)
        for v in ([1, 0, 0], [0, 1, 0], [0, 0, 1], [0.3, -0.5, 0.8]):
            sae_result = rotate(q, v)
            assert rotate(qi, v) == pytest.approx(flip_vector(sae_result), abs=1e-12)
        assert quat_to_sae(qi) == pytest.approx(q, abs=1e-15)


def test_inertia_products_follow_S_T_S():
    doc = {"_metadata": {"coordinate_system": "SAE_J670"},
           "chassis": {"inertia": {"Ixx": 500, "Iyy": 2000, "Izz": 2300, "Ixy": 7.0, "Ixz": -40.0, "Iyz": 3.0}},
           "mass_bodies": [{"id": "b", "inertia": {"Ixx": 1, "Iyy": 2, "Izz": 3, "Ixy": 0.5, "Ixz": 0.2, "Iyz": 0.1},
                            "inertia_orientation": [0, 0, 0, 1]}]}
    out, _ = convert(doc, ISO)
    i = out["chassis"]["inertia"]
    assert (i["Ixy"], i["Ixz"], i["Iyz"], i["Ixx"]) == (-7.0, 40.0, 3.0, 500)
    assert out["mass_bodies"][0]["inertia"]["Ixy"] == 0.5          # tensor in the body frame stays, orientation moves
    assert out["mass_bodies"][0]["inertia_orientation"] == [1, 0, 0, 0] or out["mass_bodies"][0]["inertia_orientation"] == [1, -0.0, 0, -0.0]


def test_fields_outside_the_allow_list_are_untouched():
    doc = {"_metadata": {"coordinate_system": "SAE_J670"}, "x_man_bodybuilder_dimensions_mm": {"L1_wheelbase": [3600, 3900, 4200]},
           "adjustments": {"values": [400.0, 600.0, 800.0]}, "chassis": {"center_of_gravity": [1.0, 0.0, -0.5]},
           "anti_roll_bars": {"drop_link_mounts": {"FL": [0.0, -0.4, -0.1], "FR": [0.0, 0.4, -0.1]}}}
    out, notes = convert(doc, ISO)
    assert out["x_man_bodybuilder_dimensions_mm"] == doc["x_man_bodybuilder_dimensions_mm"] and out["adjustments"] == doc["adjustments"]
    assert out["chassis"]["center_of_gravity"] == [1.0, 0.0, 0.5]                      # CG z becomes positive: above ground
    assert out["anti_roll_bars"]["drop_link_mounts"]["FL"] == [0.0, 0.4, 0.1]          # the front-left mount is now at +Y (left)
    assert out["_metadata"]["coordinate_system"] == ISO and "SAE_J670 -> ISO_8855" in notes[-1]
    assert convert(out, ISO)[1] == ["already ISO_8855: nothing to do"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_round_trip_is_exact_on_every_shipped_file(path):
    iso = load(path)                                       # shipped in ISO since 0.109
    sae, _ = convert(iso, SAE)
    assert sae != iso
    back, _ = convert(sae, ISO)
    assert back == iso
    assert convert(back, SAE)[0] == sae


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_physical_invariants_on_every_shipped_file(path):
    """Distances between points, quaternion norms and all scalars survive; every Y and Z of a position flips."""
    iso = load(path)
    doc, _ = convert(iso, SAE)

    def positions(node, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "position" and isinstance(v, list) and len(v) == 3:
                    acc.append(v)
                else:
                    positions(v, acc)
        elif isinstance(node, list):
            for v in node:
                positions(v, acc)
        return acc

    a, b = positions(doc, []), positions(iso, [])
    assert len(a) == len(b)
    if not a:
        pytest.skip('no vehicle positions in this file (tyre-only)')
    for pa, pb in zip(a, b):
        assert pb[0] == pa[0] and pb[1] == pytest.approx(-pa[1]) and pb[2] == pytest.approx(-pa[2])
    for i in range(0, min(len(a) - 1, 60)):                  # pairwise distances are frame-free
        assert math.dist(a[i], a[i + 1]) == pytest.approx(math.dist(b[i], b[i + 1]))
    assert doc["_metadata"]["version"] == iso["_metadata"]["version"]


def test_frame_declaration_rules():
    from svj.frame import frame_findings
    assert frame_of({"_metadata": {"version": "0.108"}}) == SAE and frame_of({"_metadata": {"version": "0.99.5"}}) == SAE
    assert frame_of({"_metadata": {"version": "0.109"}}) == ISO and frame_of({"_metadata": {"version": "0.110"}}) == ISO
    assert frame_of({"_metadata": {"version": "0.100", "coordinate_system": "ISO_8855"}}) == ISO
    gltf = {"up": "Y", "forward": "-Z", "handedness": "right"}
    assert frame_of({"_metadata": {"version": "0.109", "coordinate_system": gltf}}) == ISO
    assert frame_of({"_metadata": {"version": "0.109", "coordinate_system": gltf, "physics_frame": "SAE_J670"}}) == SAE
    doc = {"_metadata": {"version": "0.108", "coordinate_system": gltf}, "chassis": {"center_of_gravity": [-1, 0, -0.5]}}
    out, _ = convert(doc, ISO)
    assert out["_metadata"]["coordinate_system"] == gltf and out["_metadata"]["physics_frame"] == ISO
    assert convert(out, SAE)[0]["_metadata"]["physics_frame"] == SAE
    assert frame_findings(doc) == [] and frame_findings(out) == []
    wc = lambda z: {"position": [0, 0.7, z]}
    sae_wrong = {"_metadata": {"coordinate_system": "SAE_J670"}, "chassis": {"center_of_gravity": [-1, 0, 0.5]}, "w": {"wheel_center": wc(0.3)}}
    assert "looks like ISO_8855" in frame_findings(sae_wrong)[0]
    iso_wrong = {"_metadata": {"coordinate_system": "ISO_8855"}, "chassis": {"center_of_gravity": [-1, 0, -0.5]}, "w": {"wheel_center": wc(-0.3)}}
    assert frame_findings(iso_wrong)
    assert frame_findings({"_metadata": {"coordinate_system": "SAE_J670"}, "chassis": {"center_of_gravity": [1, 0, 0.1]}}) == []   # no wheels: no verdict


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_shipped_files_agree_with_their_declared_frame(path):
    from svj.frame import frame_findings
    assert frame_findings(load(path)) == []


def test_schema_accepts_both_frames_and_the_tyre_declaration():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "schema" / "svj.schema.json").read_text(encoding="utf-8"))
    path = next(p for p in FILES if "mx5" in p.name)
    doc = load(path)
    doc["_metadata"]["version"] = "0.109"
    v = jsonschema.Draft7Validator(schema)
    mine = lambda d: [e.message for e in v.iter_errors(d) if {"_metadata", "pacejka"} & set(map(str, e.absolute_path))]
    for cs in ("ISO_8855", "SAE_J670"):
        d = copy.deepcopy(doc)
        d["_metadata"]["coordinate_system"] = cs
        assert mine(d) == []
    d = copy.deepcopy(doc)
    d["_metadata"]["coordinate_system"] = {"up": "Y", "forward": "-Z", "handedness": "right"}
    d["_metadata"]["physics_frame"] = "ISO_8855"
    next(iter(d["tires"]["sets"].values()))["pacejka"]["axis_system"] = "ISO_8855"
    assert mine(d) == []
    d["_metadata"]["physics_frame"] = "NED"
    next(iter(d["tires"]["sets"].values()))["pacejka"]["axis_system"] = "XYZ"
    assert len(mine(d)) >= 2


def test_tyres_to_iso_rewrites_only_sae_signed_sets():
    from svj.frame import tyres_to_iso
    from svj.tiremodel import params, forces, to_iso_set
    iso_doc = load(REPO_ROOT / "examples" / "tire_mf62_245_40r18.svj.json")
    name = next(iter(iso_doc["tires"]["sets"]))
    legacy = copy.deepcopy(iso_doc)
    legacy["_metadata"]["version"] = "0.108"
    legacy["tires"]["sets"][name]["pacejka"] = to_iso_set(iso_doc["tires"]["sets"][name]["pacejka"])
    legacy["tires"]["sets"][name]["pacejka"].pop("axis_system")            # undeclared, pKy1 < 0: the old Pacejka signs
    assert legacy["tires"]["sets"][name]["pacejka"]["lateral"]["pKy1"] < 0
    new, done = tyres_to_iso(legacy)
    assert done == [name] and "axis_system" not in new["tires"]["sets"][name]["pacejka"]
    assert new["tires"]["sets"][name]["pacejka"] == iso_doc["tires"]["sets"][name]["pacejka"]
    assert tyres_to_iso(iso_doc)[1] == []
    a, b = params(new["tires"]["sets"][name]), params(iso_doc["tires"]["sets"][name])
    assert forces(a, 4000, 0.02, 0.05, 0.02)["Fy"] == forces(b, 4000, 0.02, 0.05, 0.02)["Fy"]
