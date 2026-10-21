"""Tests for the Vehicle class and loader."""

import json
import math
import pytest
from pathlib import Path

from svj import Vehicle, load, loads, validate


# Path to the template file (relative to repo root)
REPO_ROOT = Path(__file__).parent.parent.parent
TEMPLATE = REPO_ROOT / "templates" / "mazda_mx5_nd2_2024.svj.json"
FIXTURES = Path(__file__).parent / "fixtures"
# the three original corner-based files (deprecated suspension section), kept to test the migration and the deprecated path
LEGACY_BMW = FIXTURES / "legacy_bmw_e30.svj.json"
LEGACY_TRUCK = FIXTURES / "legacy_dump_truck_6x4.svj.json"
LEGACY_MX5 = FIXTURES / "legacy_mazda_mx5.svj.json"
SCHEMA = REPO_ROOT / "schema" / "svj.schema.json"
EXAMPLES_DIR = REPO_ROOT / "examples"


class TestVehicleFromString:
    """Test Vehicle with minimal inline data."""

    MINIMAL = json.dumps({
        "_metadata": {
            "specification": "SVJ",
            "version": "0.99",
            "coordinate_system": "SAE_J670",
            "units": "SI",
        },
        "vehicle_info": {
            "make": "Test",
            "model": "Car",
            "year": 2024,
            "drive_type": "RWD",
        },
        "chassis": {
            "mass_total": 1200.0,
            "wheelbase": 2.5,
            "track_front": 1.5,
            "track_rear": 1.5,
            "center_of_gravity": [-1.2, 0.0, -0.45],
        },
    })

    def test_loads_basic(self):
        v = loads(self.MINIMAL)
        assert isinstance(v, Vehicle)
        assert v.make == "Test"
        assert v.model == "Car"
        assert v.year == 2024

    def test_name(self):
        v = loads(self.MINIMAL)
        assert v.name == "Test Car 2024"

    def test_chassis(self):
        v = loads(self.MINIMAL)
        assert v.mass_total == 1200.0
        assert v.wheelbase == 2.5
        assert v.cg == [-1.2, 0.0, -0.45]

    def test_weight_distribution(self):
        v = loads(self.MINIMAL)
        wd = v.weight_distribution_front
        assert wd is not None
        # CG.x = -1.2, wheelbase = 2.5 → front = 1 + (-1.2/2.5) = 0.52
        assert abs(wd - 0.52) < 0.001

    def test_repr(self):
        v = loads(self.MINIMAL)
        assert "Test Car 2024" in repr(v)
        assert "SVJ v0.99" in repr(v)

    def test_get_dotpath(self):
        v = loads(self.MINIMAL)
        assert v.get("chassis.mass_total") == 1200.0
        assert v.get("vehicle_info.drive_type") == "RWD"
        assert v.get("nonexistent.path") is None
        assert v.get("nonexistent.path", "default") == "default"

    def test_has(self):
        v = loads(self.MINIMAL)
        assert v.has("chassis.mass_total")
        assert not v.has("suspension.FL")

    def test_sections(self):
        v = loads(self.MINIMAL)
        assert "chassis" in v.sections
        assert "vehicle_info" in v.sections

    def test_contains(self):
        v = loads(self.MINIMAL)
        assert "chassis" in v
        assert "suspension" not in v

    def test_to_json_roundtrip(self):
        v = loads(self.MINIMAL)
        text = v.to_json()
        v2 = loads(text)
        assert v2.mass_total == v.mass_total
        assert v2.name == v.name


@pytest.mark.skipif(not TEMPLATE.exists(), reason="Template file not found")
class TestLoadTemplate:
    """Test loading the real MX-5 ND2 template."""

    def test_load(self):
        v = load(TEMPLATE, validate_on_load=False)
        assert v.make == "Mazda"
        assert "MX-5" in v.model or "MX5" in v.model

    def test_mass(self):
        v = load(TEMPLATE, validate_on_load=False)
        assert v.mass_total > 900
        assert v.mass_total < 1500

    def test_topologies(self):
        v = load(TEMPLATE, validate_on_load=False)
        topos = v.topologies()
        assert len(topos) == 4
        assert topos["FL"] == "double_wishbone"

    def test_gear_ratios(self):
        v = load(TEMPLATE, validate_on_load=False)
        ratios = v.gear_ratios
        assert len(ratios) >= 5  # 6-speed

    def test_corners_iterator(self):
        v = load(TEMPLATE, validate_on_load=False)
        corners = list(v.corners())
        assert len(corners) == 4
        ids = [c[0] for c in corners]
        assert "FL" in ids and "RR" in ids

    def test_hardpoints(self):
        v = load(TEMPLATE, validate_on_load=False)
        hp = v.hardpoints("FL")
        assert len(hp) > 0
        # All points should be 3D
        for name, point in hp.items():
            assert len(point) == 3

    def test_query_nested(self):
        v = load(TEMPLATE, validate_on_load=False)
        st = v.get("steering.overall_ratio")
        assert st is not None and st > 0


@pytest.mark.skipif(not SCHEMA.exists(), reason="Schema file not found")
class TestValidation:
    """Test schema and consistency validation."""

    def test_valid_minimal(self):
        data = {
            "_metadata": {
                "specification": "SVJ",
                "version": "0.99",
                "coordinate_system": "SAE_J670",
                "units": "SI",
            }
        }
        errors = validate(data, schema_path=SCHEMA)
        assert len(errors) == 0

    def test_missing_metadata(self):
        data = {"chassis": {"mass_total": 100}}
        errors = validate(data, schema_path=SCHEMA)
        assert any("_metadata" in e for e in errors)

    def test_wrong_version(self):
        data = {
            "_metadata": {
                "specification": "SVJ",
                "version": "99.99",
                "coordinate_system": "SAE_J670",
                "units": "SI",
            }
        }
        errors = validate(data, schema_path=SCHEMA)
        assert any("version" in e for e in errors)

    @pytest.mark.skipif(not TEMPLATE.exists(), reason="Template not found")
    def test_template_validates(self):
        with open(TEMPLATE) as f:
            data = json.load(f)
        errors = validate(data, schema_path=SCHEMA)
        schema_errors = [e for e in errors if e.startswith("schema:")]
        assert len(schema_errors) == 0, f"Schema errors: {schema_errors}"


@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="Examples dir not found")
class TestExamples:
    """Test that all example files load correctly."""

    def test_all_examples_load(self):
        for f in EXAMPLES_DIR.glob("*.svj.json"):
            v = load(f, validate_on_load=False)
            assert v.version, f"No version in {f.name}"
            if "suspension" in v.data:
                assert len(list(v.corners())) > 0, f"No corners in {f.name}"


MULTI_AXLE = EXAMPLES_DIR / "skeleton_6x4_walking_beam_dump_truck.svj.json"


@pytest.mark.skipif(not MULTI_AXLE.exists(), reason="Multi-axle example not found")
class TestMultiAxle:
    """SVJ v0.99 wheel stations, axles, dual wheels and couplings."""

    def test_stations_ordered(self):
        v = load(MULTI_AXLE, validate_on_load=False)
        assert v.stations == ["A1L", "A1R", "A2L", "A2R", "A3L", "A3R"]
        assert [c for c, _ in v.corners()] == v.stations

    def test_axles_and_counts(self):
        v = load(MULTI_AXLE, validate_on_load=False)
        assert v.axle_count == 3 and v.is_multi_axle
        assert v.axle("A1")["steered"] is True
        assert v.stations_on_axle(3) == ["A3L", "A3R"]
        assert v.wheel_count("A2L") == 2
        assert v.tyre_count == 10
        assert v.wheel_formula == "6x4"

    def test_topologies_and_couplings(self):
        v = load(MULTI_AXLE, validate_on_load=False)
        assert v.topology("A3R") == "solid_axle"
        assert {c["type"] for c in v.suspension_couplings} == {"walking_beam"}

    def test_example_validates(self):
        with open(MULTI_AXLE) as f:
            data = json.load(f)
        assert validate(data, schema_path=SCHEMA) == []

    def test_legacy_aliases(self):
        v = loads(json.dumps({"suspension": {"FL": {"topology": {"system_type": "macpherson"}}}}))
        assert v.topology("A1L") == "macpherson"
        v2 = loads(json.dumps({"suspension": {"A1L": {"topology": {"system_type": "macpherson"}}}}))
        assert v2.topology("FL") == "macpherson"
        with pytest.raises(ValueError):
            v.corner("XX")

    def test_mixed_naming_rejected(self):
        data = {"_metadata": {"specification": "SVJ", "version": "0.99", "coordinate_system": "SAE_J670", "units": "SI"},
                "suspension": {"FL": {}, "A2L": {}}}
        errors = validate(data)
        assert any("mixes legacy corner names" in e for e in errors)

    def test_multiaxle_checker_in_sync(self):
        tools_copy = REPO_ROOT / "tools" / "multiaxle_check.py"
        lib_copy = REPO_ROOT / "svj-py" / "svj" / "multiaxle.py"
        assert tools_copy.read_text() == lib_copy.read_text(), "tools/multiaxle_check.py and svj/multiaxle.py differ"


MAN_TIPPER = EXAMPLES_DIR / "man_tgs_32_430_8x4_twin_steer_tipper.svj.json"


@pytest.mark.skipif(not MAN_TIPPER.exists(), reason="MAN example not found")
class TestRealMultiAxle:
    """First real-vehicle multi-axle example (v0.99.1: axle_groups, wheelbase_reference)."""

    def test_groups_and_weight_share(self):
        v = load(MAN_TIPPER, validate_on_load=False)
        assert [g["id"] for g in v.axle_groups] == ["front_axles", "rear_bogie"]
        # Published unladen: 6359 kg front axles / 9432 kg total
        assert v.weight_distribution_front == pytest.approx(6359 / 9432, rel=1e-3)
        assert v.plated_masses["gross_vehicle_mass_legal"] == 32000

    def test_validates_clean(self):
        with open(MAN_TIPPER) as f:
            data = json.load(f)
        assert validate(data, schema_path=SCHEMA) == []

    def test_cg_based_share_matches_groups(self):
        v = load(MAN_TIPPER, validate_on_load=False)
        groups = v.data.pop("axle_groups")
        try:
            assert v.weight_distribution_front == pytest.approx(6359 / 9432, abs=0.01)
        finally:
            v.data["axle_groups"] = groups


MAN_TRIDEM = EXAMPLES_DIR / "man_tgs_36_430_8x4_4_tridem_lift_tag.svj.json"


@pytest.mark.skipif(not MAN_TRIDEM.exists(), reason="MAN tridem example not found")
def test_man_tridem_lift_tag():
    v = load(MAN_TRIDEM, validate_on_load=False)
    assert v.axle("A4")["liftable"] and v.axle("A4")["steered"]
    assert v.wheel_count("A4L") == 1 and v.wheel_count("A2L") == 2
    assert v.weight_distribution_front == pytest.approx(4853 / 9858, rel=1e-3)
    with open(MAN_TRIDEM) as f:
        assert validate(json.load(f), schema_path=SCHEMA) == []


HEMTT = EXAMPLES_DIR / "oshkosh_hemtt_a4_m977a4_8x8.svj.json"


@pytest.mark.skipif(not HEMTT.exists(), reason="HEMTT example not found")
def test_hemtt_bogie_centre_wheelbase():
    v = load(HEMTT, validate_on_load=False)
    pos = {a["id"]: a["position_x"] for a in v.axles}
    assert (pos["A1"] + pos["A2"]) / 2 - (pos["A3"] + pos["A4"]) / 2 == pytest.approx(5.334, abs=1e-3)
    assert v.wheel_formula == "8x8/4" and v.tyre_count == 8
    with open(HEMTT) as f:
        assert validate(json.load(f), schema_path=SCHEMA) == []


TATRA = EXAMPLES_DIR / "tatra_t815_7_8x8_swing_axle.svj.json"


@pytest.mark.skipif(not TATRA.exists(), reason="Tatra example not found")
def test_tatra_swing_axles():
    v = load(TATRA, validate_on_load=False)
    assert set(v.topologies().values()) == {"swing_axle"}
    assert [a["position_x"] for a in v.axles] == pytest.approx([0.0, -1.95, -5.2, -6.65])
    with open(TATRA, encoding="utf-8") as f:
        # the old data gives no joint types for the swing half-axles: the migration reports the unconnected hubs
        assert [w for w in validate(json.load(f), schema_path=SCHEMA) if "not connected to the chassis" not in w] == []


DIFF_CONTROL = EXAMPLES_DIR / "skeleton_awd_ondemand_diff_control.svj.json"


def _diff_control_doc():
    with open(DIFF_CONTROL, encoding="utf-8") as f:
        return json.load(f)


class TestDifferentialControl:
    """v0.99.3: lock_control and transfer_case.coupling."""

    def test_checker_in_sync(self):
        tools_copy = REPO_ROOT / "tools" / "drivetrain_check.py"
        lib_copy = REPO_ROOT / "svj-py" / "svj" / "drivetrain.py"
        assert tools_copy.read_text() == lib_copy.read_text(), "tools/drivetrain_check.py and svj/drivetrain.py differ"

    def test_example_is_clean(self):
        from svj.drivetrain import check
        doc = _diff_control_doc()
        assert check(doc) == ([], [])
        assert validate(doc, schema_path=SCHEMA) == []

    def test_schema_rejects_bad_shapes(self):
        doc = _diff_control_doc()
        cc = doc["powertrain"]["transfer_case"]["center_diff"]["lock_control"]
        cc["stages"][0]["combine"] = "divide"
        cc["stages"][1]["input"] = "banana"
        doc["powertrain"]["transfer_case"]["coupling"].pop("max_torque")
        errs = validate(doc, schema_path=SCHEMA)
        assert errs  # at least one schema error is reported

    def test_unsorted_curve_and_min_max(self):
        from svj.drivetrain import check
        doc = _diff_control_doc()
        st = doc["powertrain"]["transfer_case"]["center_diff"]["lock_control"]["stages"]
        st[0]["curve"] = [[2, 1], [1, 2]]
        st[2]["min"], st[2]["max"] = 1.0, 0.0
        errors, _ = check(doc)
        assert any("strictly increasing" in e for e in errors)
        assert any("min" in e and "max" in e for e in errors)

    def test_chain_target_overlap(self):
        from svj.drivetrain import check
        doc = _diff_control_doc()
        rear = next(d for d in doc["powertrain"]["differentials"] if d["id"] == "diff_rear")
        rear["lock_control"][1]["target"] = "lock"
        errors, _ = check(doc)
        assert any("overlaps" in e for e in errors)
        rear["lock_control"][1]["target"] = "lock_power"
        errors, _ = check(doc)
        assert any("more than one chain" in e for e in errors)

    def test_lock_control_on_open_diff_warns(self):
        from svj.drivetrain import check
        doc = _diff_control_doc()
        next(d for d in doc["powertrain"]["differentials"] if d["id"] == "diff_rear")["type"] = "open"
        _, warnings = check(doc)
        assert any("no lock to modulate" in w for w in warnings)

    def test_coupling_rules(self):
        from svj.drivetrain import check
        doc = _diff_control_doc()
        tc = doc["powertrain"]["transfer_case"]
        tc["coupling"]["ramp_torque"] = 900.0
        errors, _ = check(doc)
        assert any("exceeds max_torque" in e for e in errors)
        tc["coupling"]["ramp_torque"] = 40.0
        tc["type"] = "full_time"
        _, warnings = check(doc)
        assert any("implies 'on_demand'" in w for w in warnings)
        tc["type"] = "on_demand"
        del tc["coupling"]
        _, warnings = check(doc)
        assert any("neither torque_split nor coupling" in w for w in warnings)


class TestMultibody:
    """Multibody topology cross-references and joint-type inference."""

    def _doc(self):
        with open(LEGACY_BMW, encoding="utf-8") as f:
            return json.load(f)

    def test_checker_in_sync(self):
        a = (REPO_ROOT / "tools" / "multibody_check.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "multibody.py").read_text()
        assert a == b, "tools/multibody_check.py and svj/multibody.py differ"

    def test_shipped_files_are_clean(self):
        from svj.multibody import check
        for p in list(EXAMPLES_DIR.glob("*.svj.json")) + [TEMPLATE]:
            assert check(json.loads(p.read_text(encoding="utf-8"))) == ([], []), p.name

    def test_dangling_body_ref_and_duplicate_claim(self):
        from svj.multibody import check
        d = self._doc()
        links = d["suspension"]["FL"]["topology"]["links"]
        links[0]["body_ref"] = "nope"
        links[1]["body_ref"] = links[2]["body_ref"]
        errors, _ = check(d)
        assert any("'nope' is not a chassis.mass_bodies id" in e for e in errors)
        assert any("already used by" in e for e in errors)

    def test_parent_unknown_and_cycle(self):
        from svj.multibody import check
        d = self._doc()
        mb = d["chassis"]["mass_bodies"]
        mb[0]["parent"] = "ghost"
        errors, _ = check(d)
        assert any("parent 'ghost'" in e for e in errors)
        mb[0]["parent"] = mb[1]["id"]
        mb[1]["parent"] = mb[0]["id"]
        errors, _ = check(d)
        assert any("cycle" in e for e in errors)

    def test_quaternion_norm(self):
        from svj.multibody import check
        d = self._doc()
        up = d["suspension"]["FL"]["topology"]["upright"]
        first = next(iter(up["hardpoints"]))
        up["hardpoints"][first] = {"position": up["hardpoints"][first], "orientation": [0, 0, 0, 2]}
        errors, _ = check(d)
        assert any("not a unit quaternion" in e for e in errors)
        up["hardpoints"][first]["orientation"] = [0, 0, 0, 1.004]
        errors, warnings = check(d)
        assert not errors and any("renormalise" in w for w in warnings)

    def test_outboard_ref_and_mass_mismatch(self):
        from svj.multibody import check
        d = self._doc()
        ln = d["suspension"]["FL"]["topology"]["links"][1]
        ln["outboard_ref"] = "hardpoints.does_not_exist"
        ln["mass"] = 99.0
        errors, warnings = check(d)
        assert any("not an upright hardpoint" in e for e in errors)
        assert any("differs from body" in w for w in warnings)

    def test_effective_joints_explicit_and_inferred(self):
        from svj.multibody import infer_joint_types
        assert infer_joint_types("macpherson", "strut") == ("translational", "spherical")
        assert infer_joint_types("double_wishbone", "arm") == ("spherical", "revolute")
        assert infer_joint_types("double_wishbone", "rod") == ("spherical", "spherical")
        assert infer_joint_types("trailing_arm", "arm") == ("revolute", "revolute")
        assert infer_joint_types("solid_axle", "arm") == (None, None)
        d = self._doc()
        links = d["suspension"]["FL"]["topology"]["links"]
        links[1].pop("joint_type"); links[1].pop("inboard_joint_type")
        from svj import loads
        v = loads(json.dumps(d), validate_on_load=False)
        j = next(x for x in v.joints() if x["station"] == "FL" and x["link"] == links[1]["name"])
        assert (j["outboard"], j["outboard_source"]) == ("spherical", "inferred")
        assert (j["inboard"], j["inboard_source"]) == ("revolute", "inferred")
        s = next(x for x in v.joints() if x["station"] == "FL" and x["link"] == "strut")
        assert s["outboard_source"] == "explicit"


class TestStrutAndDamperConventions:
    """v0.99.4: strut_lower, spring/damper key names, damper.reference."""

    def _doc(self):
        with open(LEGACY_BMW, encoding="utf-8") as f:
            return json.load(f)

    def test_shipped_struts_have_length(self):
        import math
        for name in ("bmw_e30_325i_semi_trailing", "corvette_c3_chapman_strut", "skeleton_ff_macpherson_torsion"):
            d = json.loads((EXAMPLES_DIR / f"{name}.svj.json").read_text(encoding="utf-8"))
            cons = {c["id"]: c for c in d["constraints"]}
            struts = [cid for cid in cons if cid.startswith("slide_strut_") and cid.endswith("_outboard")]
            assert struts, name
            for cid in struts:
                low = cons[cid]["frame_a"]["position"]                          # strut meets the upright at the lower clamp
                top = cons[cid.replace("slide_", "ball_").replace("_outboard", "_inboard")]["frame_a"]["position"]
                assert math.dist(top, low) > 0.1, (name, cid)

    def test_zero_length_strut_is_flagged(self):
        from svj.multibody import check
        d = self._doc()
        t = d["suspension"]["FL"]["topology"]
        strut = next(l for l in t["links"] if l.get("type") == "strut")
        strut["outboard_ref"] = "hardpoints.strut_top"
        errors, warnings = check(d)
        assert not errors
        assert any("zero-length" in w and "strut_lower" in w for w in warnings)

    def test_pivot_links_may_be_zero_length(self):
        from svj.multibody import check
        d = json.loads((EXAMPLES_DIR / "skeleton_4axle_modular_trailer_pendulum.svj.json").read_text(encoding="utf-8"))
        _, warnings = check(d)
        assert not any("zero-length" in w for w in warnings)

    def test_point_keys_flagged(self):
        from svj.multibody import check
        d = self._doc()
        d["suspension"]["FL"]["spring"]["inboard_point"] = [0, -0.5, -0.6]
        d["suspension"]["FL"]["damper"]["outboard_point"] = [0, -0.6, -0.2]
        _, warnings = check(d)
        assert any("spring: unknown key 'inboard_point'" in w and "inboard_mount" in w for w in warnings)
        assert any("damper: unknown key 'outboard_point'" in w and "outboard_mount" in w for w in warnings)

    def test_damper_reference(self):
        from svj.multibody import check
        d = self._doc()
        dm = d["suspension"]["FL"]["damper"]
        dm["reference"] = "wheel"
        assert check(d) == ([], [])
        assert [w for w in validate(d, schema_path=SCHEMA) if "deprecated" not in w] == []
        dm["motion_ratio"] = 0.9
        _, warnings = check(d)
        assert any("reference 'wheel' with motion_ratio" in w for w in warnings)
        dm["reference"] = "elsewhere"
        assert validate(d, schema_path=SCHEMA)  # schema rejects unknown reference


PANELS = EXAMPLES_DIR / "skeleton_ff_articulated_panels.svj.json"
TRACTOR = EXAMPLES_DIR / "skeleton_tractor_loader_hitch.svj.json"


def _doc(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestConstraints:
    """v0.99.5: constraints[], poses[], forward kinematics, per-pose CG / inertia, actuator reach."""

    def test_checker_in_sync(self):
        a = (REPO_ROOT / "tools" / "constraints_check.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "constraints.py").read_text()
        assert a == b, "tools/constraints_check.py and svj/constraints.py differ"

    def test_examples_validate_and_are_clean(self):
        from svj.constraints import check
        for path in (PANELS, TRACTOR):
            d = _doc(path)
            assert check(d) == ([], []), path.name
            assert validate(d, schema_path=SCHEMA) == [], path.name

    def test_panel_directions(self):
        from svj.constraints import apply, body_transforms
        d = _doc(PANELS)
        pos = {b["id"]: b["position"] for b in d["chassis"]["mass_bodies"]}
        moved = lambda body, pose: apply(body_transforms(d, pose)[body], pos[body])
        assert moved("door_fl", "door_fl_open")[1] < pos["door_fl"][1] - 0.3       # left door swings out (-Y)
        assert moved("door_fr", "doors_open")[1] > pos["door_fr"][1] + 0.3         # right door swings out (+Y)
        assert moved("hood", "hood_up")[2] < pos["hood"][2] - 0.3                  # hood rises (Z is down)
        assert moved("tailgate", "tailgate_up")[2] < pos["tailgate"][2] - 0.2               # hatch rises

    def test_rotation_keeps_distances(self):
        import math
        from svj.constraints import apply, body_transforms
        d = _doc(TRACTOR)
        X = body_transforms(d, "loader_dump")
        pivot = d["chassis"]["markers"]["loader_boom_hinge"]["position"]
        tip = [2.20, 0.0, -0.90]
        assert math.dist(pivot, tip) == pytest.approx(math.dist(pivot, apply(X["loader_boom"], tip)), abs=1e-9)
        assert apply(X["loader_boom"], pivot) == pytest.approx(pivot, abs=1e-9)    # the pivot itself does not move

    def test_welded_bodies_follow_parent_and_chain(self):
        from svj.constraints import apply, body_transforms
        d = _doc(TRACTOR)
        X = body_transforms(d, {"hinge_hitch_lower_link": 0.5})
        a, b = X["hitch_lower_link"], X["implement"]
        assert a[0] == b[0]
        p = d["chassis"]["markers"]["hitch_lower_link_hinge"]["position"]
        assert apply(a, p) == pytest.approx(p, abs=1e-9)
        end = [-4.35, 0.0, -0.60]
        assert apply(b, end) == pytest.approx(apply(a, end), abs=1e-9)

    def test_cg_and_inertia_per_pose(self):
        from svj.constraints import pose_cg, pose_inertia
        d = _doc(TRACTOR)
        ref = pose_cg(d)
        assert ref["delta"] == [0.0, 0.0, 0.0]
        assert ref["cg"] == pytest.approx(d["chassis"]["center_of_gravity"])
        up = pose_cg(d, "loader_dump")
        assert up["cg"][2] < ref["cg"][2]                                           # CG rises
        i0, i1 = pose_inertia(d), pose_inertia(d, "loader_dump")
        assert i0["Ixx"] == pytest.approx(d["chassis"]["inertia"]["Ixx"], rel=1e-6)
        assert i1 != i0 and all(i1[k] > 0 for k in ("Ixx", "Iyy", "Izz"))

    def test_inertia_matches_direct_rebuild(self):
        # swap the moved bodies' contributions by hand and compare with pose_inertia
        from svj.constraints import (_inertia_mat, _madd, _mm, _steiner, _sub, _tr, apply, body_transforms,
                                      pose_cg, pose_inertia)
        d = _doc(TRACTOR)
        pose = {"hinge_loader_boom": 0.6, "hinge_loader_bucket": 0.2}
        X = body_transforms(d, pose)
        cg0 = tuple(d["chassis"]["center_of_gravity"])
        acc = _inertia_mat(d["chassis"]["inertia"])
        for b in d["chassis"]["mass_bodies"]:
            if b["id"] in ("loader_boom", "loader_bucket"):
                ib = _inertia_mat(b["inertia"])
                acc = _madd(acc, _madd(ib, _steiner(b["mass"], _sub(tuple(b["position"]), cg0))), -1.0)
                R = X[b["id"]][0]
                acc = _madd(acc, _madd(_mm(_mm(R, ib), _tr(R)),
                                       _steiner(b["mass"], _sub(apply(X[b["id"]], tuple(b["position"])), cg0))))
        acc = _madd(acc, _steiner(d["chassis"]["mass_total"], tuple(pose_cg(d, pose)["delta"])), -1.0)
        got = pose_inertia(d, pose)
        assert got["Ixx"] == pytest.approx(acc[0][0]) and got["Izz"] == pytest.approx(acc[2][2])
        assert got["Ixz"] == pytest.approx(-acc[0][2])

    def test_actuator_reach_and_pose_stroke(self):
        from svj.constraints import check, element_lengths
        d = _doc(TRACTOR)
        length = element_lengths(d, "loader_dump")["loader_boom_cylinder"]
        c = next(x for x in d["constraints"] if x["id"] == "loader_boom_cylinder")
        assert c["retracted_length"] <= length <= c["retracted_length"] + c["stroke"]["max"]
        c["stroke"]["max"] = 0.2                                                    # too short for the dump pose
        errors, _ = check(d)
        assert any("loader_dump" in e and "loader_boom_cylinder" in e and "reach" in e for e in errors)

    def test_reference_and_range_rules(self):
        from svj.constraints import check
        d = _doc(PANELS)
        j = next(x for x in d["constraints"] if x["id"] == "hinge_hood")
        j["range"] = {"min": 0.2, "max": 1.0}
        errors, _ = check(d)
        assert any("reference pose (0) lies outside" in e for e in errors)
        j["range"] = {"min": 0.0, "max": 0.5}
        errors, _ = check(d)
        assert any("hood_up" in e and "outside its range" in e for e in errors)

    def test_frames_must_coincide_and_axes_align(self):
        from svj.constraints import check
        d = _doc(PANELS)
        next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "tailgate")["markers"]["hinge"]["position"][0] += 0.05
        errors, _ = check(d)
        assert any("must coincide" in e for e in errors)
        d = _doc(PANELS)
        next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "door_fl")["markers"]["hinge"]["orientation"] = [0.7071068, 0, 0, 0.7071068]
        errors, _ = check(d)
        assert any("Z axes" in e for e in errors)

    def test_graph_rules(self):
        from svj.constraints import check
        d = _doc(TRACTOR)
        d["constraints"].append({"id": "extra", "type": "joint", "joint_type": "revolute", "body_a": "loader_bucket",
                                 "frame_a": {"position": [2.65, 0, -0.78]}, "body_b": "implement",
                                 "frame_b": {"position": [2.65, 0, -0.78]}})
        _, warnings = check(d)
        assert any("child of 2 joints" in w for w in warnings)
        d = _doc(TRACTOR)
        d["constraints"][0]["body_a"] = "loader_bucket"                             # boom hangs from the bucket, bucket from the boom
        errors, _ = check(d)
        assert any("not connected to the chassis" in e for e in errors)
        d = _doc(TRACTOR)
        d["constraints"][0]["body_b"] = "nope"
        errors, _ = check(d)
        assert any("body_b 'nope'" in e for e in errors)

    def test_physical_completeness_warnings(self):
        from svj.constraints import check
        d = _doc(TRACTOR)
        del next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "loader_boom")["inertia"]
        next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "loader_bucket")["inertia"] = {"Ixx": 1.0, "Iyy": 1.0, "Izz": 5.0}
        act = next(c for c in d["constraints"] if c["id"] == "loader_boom_cylinder")
        del act["bore_diameter"], act["rod_diameter"], act["max_pressure"]
        _, warnings = check(d)
        assert any("loader_boom" in w and "no inertia" in w for w in warnings)
        assert any("loader_bucket" in w and "not physically possible" in w for w in warnings)
        assert any("loader_boom_cylinder" in w and "force capability" in w for w in warnings)

    def test_actuator_force_limits(self):
        import math
        from svj.constraints import actuator_force_limits
        push, pull = actuator_force_limits({"bore_diameter": 0.08, "rod_diameter": 0.045, "max_pressure": 18e6})
        assert push == pytest.approx(18e6 * math.pi / 4 * 0.08 ** 2)
        assert pull < push

    def test_schema_rejects_bad_constraints(self):
        d = _doc(PANELS)
        d["constraints"][0]["joint_type"] = "hinge"
        assert validate(d, schema_path=SCHEMA)
        d = _doc(PANELS)
        del d["constraints"][0]["marker_b"]
        assert validate(d, schema_path=SCHEMA)
        d = _doc(PANELS)
        del next(c for c in d["constraints"] if c["type"] == "spring")["rate"]
        assert validate(d, schema_path=SCHEMA)

    def test_vehicle_api(self):
        v = load(TRACTOR, validate_on_load=False)
        assert len([c for c in v.constraints if not c.get("x_derived")]) == 7 and {p["id"] for p in v.poses} >= {"transport", "loader_dump"}
        assert v.pose_cg("loader_dump")["cg"][2] < v.pose_cg()["cg"][2]
        assert {k for k in v.element_lengths("loader_dump") if k.endswith("_cylinder")} == {"loader_boom_cylinder", "loader_bucket_cylinder", "hitch_lower_link_cylinder"}
        assert v.pose_inertia("hitch_up")["Iyy"] > 0
        assert v.body_transforms()["implement"][1] == (0.0, 0.0, 0.0)

    def test_inertia_matrix_form_equals_object_form(self):
        from svj.constraints import check, pose_inertia
        d = _doc(TRACTOR)
        ref = pose_inertia(d, "loader_dump")
        for b in d["chassis"]["mass_bodies"]:
            if b["id"] in ("loader_boom", "loader_bucket"):
                i = b["inertia"]
                b["inertia"] = [[i["Ixx"], -i["Ixy"], -i["Ixz"]], [-i["Ixy"], i["Iyy"], -i["Iyz"]], [-i["Ixz"], -i["Iyz"], i["Izz"]]]
        assert check(d) == ([], [])
        assert validate(d, schema_path=SCHEMA) == []
        assert pose_inertia(d, "loader_dump") == pytest.approx(ref)
        m = pose_inertia(d, "loader_dump", form="matrix")
        assert m[0][0] == pytest.approx(ref["Ixx"]) and m[0][2] == pytest.approx(-ref["Ixz"]) and m[0][1] == m[1][0]

    def test_inertia_orientation_rotates_tensor(self):
        from svj.constraints import body_inertia, check, pose_inertia
        d = _doc(TRACTOR)
        boom = next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "loader_boom")
        boom["inertia"] = {"Ixx": 100.0, "Iyy": 200.0, "Izz": 250.0, "Ixy": 0.0, "Ixz": 0.0, "Iyz": 0.0}
        boom["inertia_orientation"] = [0, 0, 0.7071068, 0.7071068]                 # 90 degrees about Z swaps X and Y
        m = body_inertia(boom)
        assert m[0][0] == pytest.approx(200.0, rel=1e-6) and m[1][1] == pytest.approx(100.0, rel=1e-6) and m[2][2] == pytest.approx(250.0)
        assert check(d) == ([], [])
        assert validate(d, schema_path=SCHEMA) == []
        # the composite in the reference pose is untouched by a rotated frame; the pose result follows the vehicle-axes tensor
        boom2 = dict(boom)
        boom2["inertia"] = {"Ixx": 200.0, "Iyy": 100.0, "Izz": 250.0}
        del boom2["inertia_orientation"]
        d2 = _doc(TRACTOR)
        next(b for b in d2["chassis"]["mass_bodies"] if b["id"] == "loader_boom").update(boom2)
        d2["chassis"]["mass_bodies"] = [b if b["id"] != "loader_boom" else boom2 for b in d2["chassis"]["mass_bodies"]]
        a = pose_inertia(d, "loader_dump")
        b = pose_inertia(d2, "loader_dump")
        assert a["Ixx"] == pytest.approx(b["Ixx"], rel=1e-6) and a["Iyy"] == pytest.approx(b["Iyy"], rel=1e-6)

    def test_inertia_matrix_validation(self):
        from svj.constraints import check
        d = _doc(TRACTOR)
        boom = next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "loader_boom")
        boom["inertia"] = [[100.0, -3.0, 0.0], [-9.0, 200.0, 0.0], [0.0, 0.0, 250.0]]     # not symmetric
        errors, _ = check(d)
        assert any("loader_boom" in e and "not symmetric" in e for e in errors)
        boom["inertia"] = [[100.0, 0.0, 0.0], [0.0, 200.0, 0.0], [0.0, 0.0, 900.0]]       # violates the triangle inequality
        _, warnings = check(d)
        assert any("loader_boom" in w and "not physically possible" in w for w in warnings)
        boom["inertia"] = [[1.0, 2.0], [2.0, 1.0]]                                          # wrong shape: schema rejects
        assert validate(d, schema_path=SCHEMA)

    def test_body_inertia_api(self):
        v = load(TRACTOR, validate_on_load=False)
        m = v.body_inertia("loader_boom")
        assert len(m) == 3 and all(len(r) == 3 for r in m) and m[0][1] == m[1][0]
        assert v.body_inertia("nope") is None
        mm = v.pose_inertia("loader_dump", form="matrix")
        assert mm[1][1] == pytest.approx(v.pose_inertia("loader_dump")["Iyy"])


TRUCK = EXAMPLES_DIR / "skeleton_dump_truck_tipper_cab.svj.json"


class TestLatchCouplingDrive:
    """v0.99.6: latch, coupling, joint.drive."""

    def test_new_examples_are_clean(self):
        from svj.constraints import check
        for path in (PANELS, TRUCK):
            d = _doc(path)
            assert check(d) == ([], []), path.name
            assert validate(d, schema_path=SCHEMA) == [], path.name

    def test_coupling_derives_coordinates_both_ways(self):
        from svj.constraints import pose_values
        d = _doc(TRUCK)
        v = pose_values(d, {"hinge_tipper_body": 0.5})
        assert v["hinge_tailgate"] == pytest.approx([0.4])
        v = pose_values(d, {"hinge_tailgate": 0.4})
        assert v["hinge_tipper_body"] == pytest.approx([0.5])
        v = pose_values(d, {"hinge_cab": 0.2})
        assert "hinge_tailgate" not in v and "hinge_tipper_body" not in v

    def test_coupled_joint_moves_in_kinematics(self):
        from svj.constraints import apply, body_transforms
        d = _doc(TRUCK)
        tip = body_transforms(d, {"hinge_tipper_body": 0.9})
        # the tailgate rides on the tipped body and swings a further 0.72 rad about its own hinge
        both = body_transforms(d, {"hinge_tipper_body": 0.9, "hinge_tailgate": 0.72})
        gate_only = body_transforms(d, {"hinge_tipper_body": 0.9, "hinge_tailgate": 0.0})
        p = next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "tailgate")["position"]
        assert apply(tip["tailgate"], p) == pytest.approx(apply(both["tailgate"], p), abs=1e-9)
        assert apply(tip["tailgate"], p) != pytest.approx(apply(gate_only["tailgate"], p), abs=1e-6)

    def test_pose_cg_uses_the_coupled_tailgate(self):
        from svj.constraints import pose_cg
        d = _doc(TRUCK)
        a = pose_cg(d, {"hinge_tipper_body": 0.9})["cg"]
        b = pose_cg(d, {"hinge_tipper_body": 0.9, "hinge_tailgate": 0.0})["cg"]
        assert a != pytest.approx(b, abs=1e-9)

    def test_coupling_rules(self):
        from svj.constraints import check
        d = _doc(TRUCK)
        link = next(c for c in d["constraints"] if c["id"] == "tailgate_link")
        d["poses"].append({"id": "bad", "values": {"hinge_tipper_body": 0.5, "hinge_tailgate": 0.9}})
        errors, _ = check(d)
        assert any("violates coupling" in e for e in errors)
        d = _doc(TRUCK)
        next(c for c in d["constraints"] if c["id"] == "tailgate_link")["ratio"] = 2.0
        errors, warnings = check(d)
        assert any("tip_full" in e and "through a coupling" in e for e in errors)
        assert any("maps outside the range" in w for w in warnings)
        d = _doc(TRUCK)
        link = next(c for c in d["constraints"] if c["id"] == "tailgate_link")
        link["joint_b"] = "hinge_tipper_body"
        errors, _ = check(d)
        assert any("two different joint coordinates" in e for e in errors)
        link["joint_b"] = "ghost"
        errors, _ = check(d)
        assert any("'ghost' is not a joint id" in e for e in errors)
        link["joint_b"] = "hinge_tailgate"
        link["ratio"] = 0
        errors, _ = check(d)
        assert any("non-zero" in e for e in errors)

    def test_double_driven_coordinate_warns(self):
        from svj.constraints import check
        d = _doc(TRUCK)
        d["constraints"].append({"id": "second", "type": "coupling", "joint_a": "hinge_cab", "joint_b": "hinge_tailgate", "ratio": 0.1})
        _, warnings = check(d)
        assert any("driven by 2 couplings" in w for w in warnings)

    def test_latch_rules(self):
        from svj.constraints import check
        d = _doc(PANELS)
        latch = next(c for c in d["constraints"] if c["id"] == "hood_latch")
        latch["position"] = 0.3
        errors, _ = check(d)
        assert any("must engage at position 0" in e for e in errors)
        latch["position"] = 5.0
        errors, _ = check(d)
        assert any("outside the joint range" in e for e in errors)
        latch["position"] = 0.0
        latch["joint_ref"] = "nope"
        errors, _ = check(d)
        assert any("joint_ref 'nope'" in e for e in errors)
        latch["joint_ref"] = "hinge_hood"
        latch["coordinate"] = 1
        errors, _ = check(d)
        assert any("coordinate 1 does not exist" in e for e in errors)

    def test_detent_latch_may_be_released_anywhere_in_range(self):
        from svj.constraints import check
        d = _doc(PANELS)
        check_latch = next(c for c in d["constraints"] if c["id"] == "door_fl_check")
        assert check_latch["state"] == "released" and check_latch["position"] == 0.55
        assert check(d) == ([], [])

    def test_drive_rules(self):
        from svj.constraints import check
        d = _doc(PANELS)
        hatch = next(c for c in d["constraints"] if c["id"] == "hinge_tailgate")
        del hatch["drive"]["target"]
        errors, _ = check(d)
        assert any("needs a target" in e for e in errors)
        hatch["drive"]["target"] = 9.0
        errors, _ = check(d)
        assert any("outside the joint range" in e for e in errors)
        hatch["drive"].update({"target": 0.0})
        del hatch["drive"]["max_force"]
        _, warnings = check(d)
        assert any("without max_force" in w for w in warnings)
        d = _doc(PANELS)
        hatch = next(c for c in d["constraints"] if c["id"] == "hinge_tailgate")
        hatch["joint_type"] = "cylindrical"
        hatch["range"] = {"min": [0.0, 0.0], "max": [1.3, 0.1]}
        errors, _ = check(d)
        assert any("one-coordinate joints" in e for e in errors)

    def test_schema_for_new_types(self):
        d = _doc(TRUCK)
        link = next(c for c in d["constraints"] if c["id"] == "tailgate_link")
        del link["ratio"]
        assert validate(d, schema_path=SCHEMA)
        d = _doc(TRUCK)
        next(c for c in d["constraints"] if c["id"] == "cab_latch").pop("holding_force")
        assert validate(d, schema_path=SCHEMA)
        d = _doc(PANELS)
        next(c for c in d["constraints"] if c["id"] == "hinge_tailgate")["drive"]["mode"] = "turbo"
        assert validate(d, schema_path=SCHEMA)
        d = _doc(TRUCK)
        next(c for c in d["constraints"] if c["id"] == "cab_latch")["state"] = "maybe"
        assert validate(d, schema_path=SCHEMA)

    def test_truck_physics_sanity(self):
        from svj.constraints import check, element_lengths, pose_cg
        d = _doc(TRUCK)
        ref, full = pose_cg(d), pose_cg(d, "tip_full")
        assert full["cg"][0] < ref["cg"][0] and full["cg"][2] < ref["cg"][2]        # CG moves back and up when tipping
        assert pose_cg(d, "cab_tilted")["cg"][0] > ref["cg"][0]                     # cab tilts forward
        ram = next(c for c in d["constraints"] if c["id"] == "tipper_body_cylinder")
        length = element_lengths(d, "tip_full")["tipper_body_cylinder"]
        assert ram["retracted_length"] <= length <= ram["retracted_length"] + ram["stroke"]["max"]

    def test_partial_mass_decomposition(self):
        d = _doc(TRUCK)
        assert validate(d, schema_path=SCHEMA) == []                       # a partial list of bodies is fine
        d["chassis"]["mass_bodies_complete"] = True
        assert any("mass_bodies_complete is true" in w for w in validate(d, schema_path=SCHEMA))
        d["chassis"]["mass_bodies_complete"] = False
        d["chassis"]["mass_total"] = 5000.0                                # listed masses exceed the total
        assert any("exceeds mass_total" in w for w in validate(d, schema_path=SCHEMA))
        d["chassis"]["mass_bodies_complete"] = "yes"
        assert validate(d, schema_path=SCHEMA)                             # schema: boolean


class TestPartNaming:
    """v0.99.7: display `name`, canonical part vocabulary, alias advisories."""

    def test_canonical_part_id(self):
        from svj.constraints import canonical_part_id as c
        assert c("door_fl") == "door_fl"                      # already canonical
        assert c("bonnet") == "hood"
        assert c("Engine-Bonnet") == "hood"
        assert c("hatch") == "tailgate" and c("liftgate") == "tailgate"
        assert c("boot_lid") == "trunk"
        assert c("front_left_door") == "door_fl"              # side prefix moves to a suffix
        assert c("door_lf") == "door_fl" and c("door_rb") == "door_rr"
        assert c("left_side_mirror") == "mirror_l"
        assert c("side_mirror_left") == "mirror_l"
        assert c("tipper") == "tipper_body" and c("dump_box") == "tipper_body"
        assert c("front_loader_bucket") == "loader_bucket"
        assert c("lower_link") == "hitch_lower_link" and c("top_link") == "hitch_top_link"
        assert c("dipper") == "stick"
        assert c("upright_fl") == "upright_fl" and c("engine") is None and c("front_subframe") is None and c("lower_control_arm_fl") is None   # unlisted: no opinion
        assert c(None) is None and c(5) is None

    def test_alias_advisory_on_bodies(self):
        from svj.constraints import check
        d = _doc(PANELS)
        next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "tailgate")["id"] = "hatch"
        for cn in d["constraints"]:
            for k in ("body_a", "body_b"):
                if cn.get(k) == "tailgate":
                    cn[k] = "hatch"
        errors, warnings = check(d)
        assert not errors
        assert any("'hatch'" in w and "'tailgate'" in w and "canonical" in w for w in warnings)

    def test_unknown_names_are_not_flagged(self):
        from svj.constraints import check
        d = _doc(TRACTOR)
        for b in d["chassis"]["mass_bodies"]:
            if b["id"] == "implement":
                b["id"] = "my_custom_plough"
        for cn in d["constraints"]:
            for k in ("body_a", "body_b"):
                if cn.get(k) == "implement":
                    cn[k] = "my_custom_plough"
        for b in d["chassis"]["mass_bodies"]:
            if b.get("parent") == "implement":
                b["parent"] = "my_custom_plough"
        _, warnings = check(d)
        assert not any("canonical" in w for w in warnings)

    def test_actuator_suffix_advisory(self):
        from svj.constraints import check
        d = _doc(TRUCK)
        next(c for c in d["constraints"] if c["id"] == "tipper_body_cylinder")["id"] = "tipper_ram"
        _, warnings = check(d)
        assert any("tipper_ram" in w and "_cylinder" in w for w in warnings)

    def test_shipped_examples_follow_the_vocabulary(self):
        from svj.constraints import PART_ALIASES, PART_CANONICAL, canonical_part_id
        assert not (set(PART_ALIASES) & PART_CANONICAL)       # an alias is never also canonical
        assert set(PART_ALIASES.values()) <= PART_CANONICAL
        for path in (PANELS, TRACTOR, TRUCK):
            for b in _doc(path)["chassis"]["mass_bodies"]:
                canon = canonical_part_id(b["id"])
                assert canon in (None, b["id"]), (path.name, b["id"], canon)

    def test_name_field(self):
        d = _doc(PANELS)
        door = next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "door_fl")
        assert door["name"] == "Front-left door"
        assert validate(d, schema_path=SCHEMA) == []
        door["name"] = 5
        assert validate(d, schema_path=SCHEMA)
        d = _doc(PANELS)
        d["constraints"][0]["name"] = "Left door hinge"
        d["poses"][1]["name"] = "Left door open"
        assert validate(d, schema_path=SCHEMA) == []


BMW = LEGACY_BMW
TRUCK6X4 = LEGACY_TRUCK


class TestSuspensionView:
    """v0.99.8: the authored suspension expanded into the §24 body / joint model."""

    def test_view_in_sync(self):
        a = (REPO_ROOT / "tools" / "suspension_view.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "suspension_view.py").read_text()
        assert a == b, "tools/suspension_view.py and svj/suspension_view.py differ"

    def test_quaternion_rotates_z_onto_axis(self):
        import math
        from svj.constraints import apply, quat_to_mat
        from svj.suspension_view import quat_z_to
        for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, -1], [1, 2, 3], [-0.3, 0.2, -0.9]):
            n = math.sqrt(sum(c * c for c in axis))
            want = [c / n for c in axis]
            got = [sum(quat_to_mat(quat_z_to(axis))[i][j] * (0, 0, 1)[j] for j in range(3)) for i in range(3)]
            assert got == pytest.approx(want, abs=1e-6), axis

    def test_macpherson_corner_expansion(self):
        from svj.suspension_view import expand_suspension
        d = _doc(BMW)
        view = expand_suspension(d)
        ids = {c["id"]: c for c in view["constraints"]}
        # existing bodies are reused: only the four wheels are new
        assert {b["id"] for b in view["mass_bodies"]} == {"wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"}
        strut = ids["slide_strut_fl_outboard"]
        assert (strut["joint_type"], strut["body_a"], strut["body_b"]) == ("translational", "strut_fl", "upright_fl")
        assert ids["fixed_strut_fl_inboard"]["joint_type"] == "fixed"          # the legacy fixture states it explicitly: an explicit value wins
        assert ids["hinge_lower_control_arm_fl_inboard"]["joint_type"] == "revolute"
        assert ids["ball_lower_control_arm_fl_outboard"]["joint_type"] == "spherical"
        assert ids["ball_steering_tie_rod_fl_inboard"]["joint_type"] == "spherical"
        assert ids["hinge_wheel_fl"]["body_a"] == "upright_fl" and ids["hinge_wheel_fl"]["body_b"] == "wheel_fl"
        assert all(c["x_derived"] for c in view["constraints"])

    def test_joint_frames_coincide_and_axes_follow_the_geometry(self):
        import math
        from svj.constraints import quat_to_mat
        from svj.suspension_view import expand_suspension
        d = _doc(BMW)
        pts = {b["name"]: b for b in d["suspension"]["FL"]["topology"]["links"]}
        arm = pts["lower_control_arm"]["inboard_points"]
        ids = {c["id"]: c for c in expand_suspension(d)["constraints"]}
        hinge = ids["hinge_lower_control_arm_fl_inboard"]
        assert hinge["frame_a"] == hinge["frame_b"]
        z = [quat_to_mat(hinge["frame_a"]["orientation"])[i][2] for i in range(3)]
        axis = [arm[1][i] - arm[0][i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in axis))
        assert z == pytest.approx([c / n for c in axis], abs=1e-6)             # hinge axis through the two inboard points
        assert hinge["frame_a"]["position"] == pytest.approx(arm[0], abs=1e-6)
        # the strut slides along top -> lower clamp
        slide = ids["slide_strut_fl_outboard"]
        top = d["suspension"]["FL"]["topology"]["upright"]["hardpoints"]["strut_top"]
        low = d["suspension"]["FL"]["topology"]["upright"]["hardpoints"]["strut_lower"]
        dz = [quat_to_mat(slide["frame_a"]["orientation"])[i][2] for i in range(3)]
        sd = [low[i] - top[i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in sd))
        assert dz == pytest.approx([c / n for c in sd], abs=1e-6)

    def test_expanded_document_is_valid_and_checks_clean(self):
        from svj.constraints import check
        from svj.suspension_view import with_expanded_suspension
        for path in (BMW, LEGACY_MX5, TRUCK6X4):
            d = json.loads(path.read_text(encoding="utf-8"))
            v = with_expanded_suspension(d)
            errors, _ = check(v)
            assert errors == [], (path.name, errors[:2])
            # the only schema complaint allowed is a derived body whose mass the authored suspension does not give
            bad = [w for w in validate(v, schema_path=SCHEMA) if w.startswith("schema") and not (".mass:" in w and "minimum of 0" in w)]
            assert not bad, (path.name, bad[:2])

    def test_original_document_is_untouched(self):
        from svj.suspension_view import with_expanded_suspension
        d = _doc(BMW)
        before = json.dumps(d, sort_keys=True)
        with_expanded_suspension(d)
        assert json.dumps(d, sort_keys=True) == before

    def test_shared_axle_body_created_once(self):
        from svj.suspension_view import expand_suspension
        view = expand_suspension(_doc(TRUCK6X4))
        ids = [b["id"] for b in view["mass_bodies"]]
        assert ids.count("a2_housing") == 1 and ids.count("a1_beam") == 1
        assert any("joint type unknown" in n for n in view["notes"])             # leaf springs have no inferable joint

    def test_missing_mass_is_noted_not_invented(self):
        from svj.suspension_view import expand_suspension
        view = expand_suspension(_doc(TRUCK6X4))
        body = next(b for b in view["mass_bodies"] if b["id"].startswith("lower_torque_rod"))
        assert body["mass"] == 0.0 and body["x_derived"] is True

    def test_expansion_is_idempotent_in_ids(self):
        from svj.suspension_view import with_expanded_suspension
        v1 = with_expanded_suspension(_doc(BMW))
        v2 = with_expanded_suspension(v1)
        ids = [c["id"] for c in v2["constraints"]]
        assert len(ids) == len(set(ids))
        assert len(v2["chassis"]["mass_bodies"]) == len(v1["chassis"]["mass_bodies"])


class TestContactAndSuspensionNames:
    """v0.99.8: contact constraint, suspension part names."""

    def _panels(self):
        return _doc(PANELS)

    def test_panels_example_has_clean_contacts(self):
        from svj.constraints import check
        d = self._panels()
        contacts = [c for c in d["constraints"] if c["type"] == "contact"]
        assert {c["id"] for c in contacts} == {"hood_stop_l", "hood_stop_r", "tailgate_stop_l", "tailgate_stop_r"}
        assert check(d) == ([], [])
        assert validate(d, schema_path=SCHEMA) == []

    def test_contact_distance_reference_and_open_poses(self):
        from svj.constraints import contact_distance
        d = self._panels()
        stop = next(c for c in d["constraints"] if c["id"] == "hood_stop_l")
        assert contact_distance(d, stop) == pytest.approx(0.0, abs=1e-9)                # touching in the closed pose
        assert contact_distance(d, stop, "hood_up") > 0.5                                # the hood lifts away
        assert contact_distance(d, stop, "door_fl_open") == pytest.approx(0.0, abs=1e-9)  # unaffected by a door
        gate = next(c for c in d["constraints"] if c["id"] == "tailgate_stop_r")
        assert contact_distance(d, gate, "tailgate_up") > 0.5

    def _frame_doc(self, a_shape, b_shape, a_pos, b_pos, a_q=None, b_q=None):
        fa = {"position": a_pos, **({"orientation": a_q} if a_q else {})}
        fb = {"position": b_pos, **({"orientation": b_q} if b_q else {})}
        mb = [{"id": "part", "mass": 1.0, "position": b_pos, "inertia": {"Ixx": 1, "Iyy": 1, "Izz": 1}}]
        return {"chassis": {"mass_total": 100.0, "center_of_gravity": [0, 0, 0], "mass_bodies": mb},
                "constraints": [{"id": "c", "type": "contact", "body_a": "chassis", "frame_a": fa, "shape_a": a_shape,
                                 "body_b": "part", "frame_b": fb, "shape_b": b_shape, "law": {"stiffness": 1e4}}]}

    def test_shape_pair_distances(self):
        from svj.constraints import contact_distance
        # point above a plane (plane normal +Z of its frame)
        d = self._frame_doc({"type": "plane"}, {"type": "point"}, [0, 0, 0], [0.1, 0.2, 0.3])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.3)
        # sphere over a plane
        d = self._frame_doc({"type": "plane"}, {"type": "sphere", "radius": 0.05}, [0, 0, 0], [0, 0, 0.2])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.15)
        # two spheres (order of the arguments does not matter)
        d = self._frame_doc({"type": "sphere", "radius": 0.1}, {"type": "sphere", "radius": 0.2}, [0, 0, 0], [1.0, 0, 0])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.7)
        # point and box: 0.05 outside a 0.2-long box face
        d = self._frame_doc({"type": "box", "size": [0.2, 0.2, 0.2]}, {"type": "point"}, [0, 0, 0], [0.15, 0, 0])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.05)
        d = self._frame_doc({"type": "box", "size": [0.2, 0.2, 0.2]}, {"type": "point"}, [0, 0, 0], [0.0, 0, 0])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(-0.1)           # inside: negative
        # box lowest corner over a plane, box tilted 45 degrees about X
        d = self._frame_doc({"type": "plane"}, {"type": "box", "size": [0.2, 0.2, 0.2]}, [0, 0, 0], [0, 0, 0.5], None, [0.3826834, 0, 0, 0.9238795])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.5 - 0.1 * 2 ** 0.5, abs=1e-6)
        # cylinder lying on a plane: axis horizontal -> lowest point is the radius below the centre
        d = self._frame_doc({"type": "plane"}, {"type": "cylinder", "radius": 0.05, "length": 0.4}, [0, 0, 0], [0, 0, 0.3], None, [0.7071068, 0, 0, 0.7071068])
        assert contact_distance(d, d["constraints"][0]) == pytest.approx(0.25, abs=1e-6)

    def test_unsupported_and_invalid_shapes(self):
        from svj.constraints import check, contact_pair_supported
        assert contact_pair_supported("point", "plane") and contact_pair_supported("plane", "sphere") and contact_pair_supported("sphere", "sphere")
        assert not contact_pair_supported("plane", "plane") and not contact_pair_supported("point", "point") and not contact_pair_supported("box", "box")
        d = self._frame_doc({"type": "box", "size": [0.2, 0.2, 0.2]}, {"type": "box", "size": [0.1, 0.1, 0.1]}, [0, 0, 0], [0.5, 0, 0])
        errors, _ = check(d)
        assert any("not supported" in e for e in errors)
        d = self._frame_doc({"type": "sphere"}, {"type": "point"}, [0, 0, 0], [0.5, 0, 0])
        errors, _ = check(d)
        assert any("positive radius" in e for e in errors)

    def test_reference_gap_must_match_the_geometry(self):
        from svj.constraints import check
        d = self._panels()
        stop = next(c for c in d["constraints"] if c["id"] == "hood_stop_l")
        stop["law"]["gap"] = 0.005
        errors, _ = check(d)
        assert any("hood_stop_l" in e and "law.gap" in e for e in errors)
        stop["law"]["gap"] = 0.0
        next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "hood")["markers"]["hood_stop_l_pad"]["position"][2] += 0.02
        errors, _ = check(d)
        assert any("hood_stop_l" in e and "apart at the reference pose" in e for e in errors)

    def test_penetration_in_a_pose_is_reported(self):
        from svj.constraints import apply, body_transforms, check, contact_distance
        d = self._panels()
        gate = next(b for b in d["chassis"]["mass_bodies"] if b["id"] == "tailgate")
        probe = gate["position"]                                            # a point on the tailgate
        target = apply(body_transforms(d, "tailgate_up")["tailgate"], probe)  # where it ends up when the tailgate is open
        c = {"id": "tailgate_probe", "type": "contact", "body_a": "chassis", "frame_a": {"position": list(target)},
             "shape_a": {"type": "sphere", "radius": 0.012}, "body_b": "tailgate", "frame_b": {"position": list(probe)},
             "shape_b": {"type": "point"}, "law": {"stiffness": 1e4}}
        ref = contact_distance({**d, "constraints": d["constraints"] + [c]}, c)
        c["law"]["gap"] = ref                                              # consistent at the reference pose
        d["constraints"].append(c)
        errors, warnings = check(d)
        assert not errors
        assert any("tailgate_up" in w and "tailgate_probe" in w and "interpenetrates by 12.0 mm" in w for w in warnings)   # the point reaches the sphere centre

    def test_contact_between_jointed_bodies_is_allowed(self):
        from svj.constraints import check
        d = self._panels()
        _, warnings = check(d)
        assert not any("already connected" in w for w in warnings)               # the hood is hinged to the chassis and still rests on stops

    def test_schema_for_contact(self):
        d = self._panels()
        c = next(x for x in d["constraints"] if x["id"] == "hood_stop_l")
        del c["law"]
        assert validate(d, schema_path=SCHEMA)
        d = self._panels()
        del next(x for x in d["constraints"] if x["id"] == "hood_stop_l")["shape_a"]
        assert validate(d, schema_path=SCHEMA)
        d = self._panels()
        next(x for x in d["constraints"] if x["id"] == "hood_stop_l")["shape_b"]["type"] = "torus"
        assert validate(d, schema_path=SCHEMA)
        d = self._panels()
        next(x for x in d["constraints"] if x["id"] == "hood_stop_l")["law"]["restitution"] = 1.5
        assert validate(d, schema_path=SCHEMA)

    def test_suspension_part_names(self):
        from svj.constraints import canonical_part_id as c
        assert c("upright_fl") == "upright_fl" and c("knuckle_fr") == "upright_fr"
        assert c("lca_a2l") == "lower_wishbone_a2l" and c("upper_arm_fl") == "upper_wishbone_fl"
        assert c("track_rod_rl") == "tie_rod_rl" and c("sway_bar") == "arb" and c("shock_fl") == "damper_fl"
        assert c("steering_gear") == "rack" and c("handwheel") == "steering_wheel"
        assert c("lower_control_arm_fl") is None and c("engine") is None and c("transmission") is None   # not in the vocabulary
        assert c("upright_a3r") == "upright_a3r"                                                        # multi-axle station suffix

    def test_shipped_suspension_bodies_follow_the_vocabulary(self):
        from svj.constraints import canonical_part_id
        for path in list(EXAMPLES_DIR.glob("*.svj.json")) + [TEMPLATE]:
            for b in json.loads(path.read_text(encoding="utf-8")).get("chassis", {}).get("mass_bodies", []):
                canon = canonical_part_id(b["id"])
                assert canon in (None, b["id"]), (path.name, b["id"], canon)


def _migrated(path):
    from svj.migrate_suspension import migrate
    return migrate(json.loads(path.read_text(encoding="utf-8")))


class TestUnifiedSuspension:
    """v0.100: wheel stations as bodies, joints and elements; the migration from the corner section."""

    def test_migration_in_sync(self):
        a = (REPO_ROOT / "tools" / "migrate_suspension.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "migrate_suspension.py").read_text()
        assert a == b, "tools/migrate_suspension.py and svj/migrate_suspension.py differ"

    def test_legacy_files_still_validate_with_a_deprecation_warning(self):
        d = json.loads(LEGACY_BMW.read_text(encoding="utf-8"))
        warnings = validate(d, schema_path=SCHEMA)
        assert any("deprecated since 0.100" in w for w in warnings)
        assert not [w for w in warnings if w.startswith("schema")]

    def test_migrated_files_are_valid_and_checks_clean(self):
        from svj.constraints import check
        for path in (LEGACY_BMW, LEGACY_MX5, LEGACY_TRUCK):
            new, _ = _migrated(path)
            assert "suspension" not in new and new["_metadata"]["version"] == "0.100"
            errors, _ = check(new)
            assert errors == [], (path.name, errors[:2])
            assert [w for w in validate(new, schema_path=SCHEMA) if w.startswith("schema")] == [], path.name

    def test_original_document_is_not_modified(self):
        d = json.loads(LEGACY_MX5.read_text(encoding="utf-8"))
        before = json.dumps(d, sort_keys=True)
        from svj.migrate_suspension import migrate
        migrate(d)
        assert json.dumps(d, sort_keys=True) == before

    def test_migrating_a_unified_file_is_a_no_op(self):
        from svj.migrate_suspension import migrate
        d = _doc(TRACTOR)
        new, notes = migrate(d)
        assert json.dumps(new, sort_keys=True) == json.dumps(d, sort_keys=True) and "nothing to migrate" in notes[0]

    def test_bodies_keep_their_part_names_and_meaning(self):
        new, _ = _migrated(LEGACY_MX5)
        bodies = {b["id"]: b for b in new["chassis"]["mass_bodies"]}
        wheel, rack = bodies["wheel_fl"], bodies["rack"]
        assert wheel["name"] == "Wheel FL" and wheel["description"] == "Rim + tyre"
        assert rack["description"] == "Steering rack / gear housing"
        assert bodies["upright_fl"]["markers"]["wheel_center"]["position"]                      # hardpoints became markers
        assert all(b["x_derived"] for b in (wheel, rack))                                       # generated, so checked leniently

    def test_leaf_pack_keeps_its_name_and_gets_end_joints(self):
        new, _ = _migrated(LEGACY_TRUCK)
        assert "leaf_spring_a1l" in {b["id"] for b in new["chassis"]["mass_bodies"]}
        ids = {c["id"]: c for c in new["constraints"]}
        assert ids["hinge_leaf_spring_a1l_front_eye"]["joint_type"] == "revolute"
        assert ids["slide_leaf_spring_a1l_rear_end"]["joint_type"] == "translational"
        assert ids["fixed_leaf_spring_a1l_seat"]["body_a"] == "leaf_spring_a1l"

    def test_wheel_stations_carry_the_roles_an_analysis_needs(self):
        new, _ = _migrated(LEGACY_MX5)
        st = {s["id"]: s for s in new["wheel_stations"]}
        fl, rl = st["FL"], st["RL"]
        assert (fl["wheel_body"], fl["upright_body"], fl["axle"], fl["side"], fl["topology_hint"]) == ("wheel_fl", "upright_fl", "A1", "L", "double_wishbone")
        assert fl["steering_joint"] == "slide_rack" and "steering_joint" not in rl             # only the front is steered
        bodies = {b["id"]: b for b in new["chassis"]["mass_bodies"]}
        assert fl["wheel_center_marker"] in bodies[fl["upright_body"]]["markers"]
        assert fl["alignment"] and fl["wheel"]["rim_diameter"]
        joints = {c["id"]: c for c in new["constraints"] if c["type"] == "joint"}
        assert joints[fl["steering_joint"]]["joint_type"] == "translational"
        assert joints["hinge_wheel_fl"]["body_a"] == fl["upright_body"] and joints["hinge_wheel_fl"]["body_b"] == fl["wheel_body"]

    def test_tie_rods_hang_from_the_rack(self):
        new, _ = _migrated(LEGACY_BMW)
        joints = {c["id"]: c for c in new["constraints"]}
        assert joints["ball_steering_tie_rod_fl_inboard"]["body_a"] == "rack"
        assert joints["slide_rack"]["body_a"] == "chassis" and joints["slide_rack"]["joint_type"] == "translational"

    def test_spring_with_mounts_is_converted_by_the_motion_ratio(self):
        new, _ = _migrated(LEGACY_MX5)
        old = json.loads(LEGACY_MX5.read_text(encoding="utf-8"))["suspension"]["FL"]["spring"]
        sp = next(c for c in new["constraints"] if c["id"] == "spring_fl")
        mr = old["motion_ratio"]
        assert sp.get("reference") != "wheel"
        assert sp["rate"] == pytest.approx(old["rate"] / mr ** 2, rel=1e-4)                     # wheel rate -> element rate
        assert sp["x_converted_from_wheel_rate"] == {"motion_ratio": mr, "estimated": False}
        assert sp["preload"] == pytest.approx(old["preload"] / mr, rel=1e-4)
        assert sp["spring_type"] == "coilover"

    def test_damper_with_mounts_at_the_damper_keeps_its_curves(self):
        new, _ = _migrated(LEGACY_MX5)
        old = json.loads(LEGACY_MX5.read_text(encoding="utf-8"))["suspension"]["FL"]["damper"]
        dm = next(c for c in new["constraints"] if c["id"] == "damper_fl")
        assert dm["bump_curve"] == old["bump_curve"] and dm.get("reference") != "wheel"

    def test_spring_and_damper_without_mounts_become_wheel_level_elements(self):
        new, _ = _migrated(LEGACY_BMW)
        old = json.loads(LEGACY_BMW.read_text(encoding="utf-8"))["suspension"]["FL"]
        sp = next(c for c in new["constraints"] if c["id"] == "spring_fl")
        dm = next(c for c in new["constraints"] if c["id"] == "damper_fl")
        assert sp["reference"] == "wheel" and sp["rate"] == old["spring"]["rate"]               # kept as quoted
        assert dm["reference"] == "wheel" and dm["bump_curve"] == old["damper"]["bump_curve"]
        assert sp["body_b"] == "upright_fl"                                                     # at the wheel carrier

    def test_bump_and_rebound_stops_become_curved_springs(self):
        new, _ = _migrated(LEGACY_MX5)
        old = json.loads(LEGACY_MX5.read_text(encoding="utf-8"))["suspension"]["FL"]
        bump = next(c for c in new["constraints"] if c["id"] == "bump_stop_fl")
        rebound = next(c for c in new["constraints"] if c["id"] == "rebound_stop_fl")
        assert bump["reference"] == "wheel" and bump["free_length"] == pytest.approx(old["spring"]["free_length"] - old["bump_stop"]["gap"], abs=1e-6)
        xs = [p[0] for p in bump["rate_curve"]]
        assert xs == sorted(xs) and bump["rate_curve"][0][1] == 0.0 and bump["rate_curve"][-1][1] == old["bump_stop"]["rate_curve"][-1][1]
        assert rebound["rate_curve"][0][1] < 0.0 and rebound["rate_curve"][-1][1] == 0.0       # pulls only in extension

    def test_anti_roll_bars_move_to_axle_level_data(self):
        new, _ = _migrated(LEGACY_MX5)
        bars = {b["id"]: b for b in new["anti_roll_bars"]}
        front = bars["arb_front"]
        assert front["stations"] == ["FL", "FR"] and front["bar_rate"] == 600.0 and set(front["drop_link_mounts"]) == {"FL", "FR"}

    def test_coupling_reference_survives_for_stations_without_a_spring(self):
        new, _ = _migrated(LEGACY_TRUCK)
        st = {s["id"]: s for s in new["wheel_stations"]}
        assert st["A2L"]["coupling_ref"] and not st["A1L"].get("coupling_ref")
        from svj.multiaxle import check
        assert check(new)[0] == []

    def test_motion_ratio_estimate(self):
        from svj.migrate_suspension import estimate_motion_ratio
        # mount on the wheel carrier (strut, axle): MR = cosine between the element axis and vertical
        assert estimate_motion_ratio([0, 0, -0.4], [0, 0, 0], None, [0, 0.6, 0]) == pytest.approx(1.0)
        import math
        assert estimate_motion_ratio([0, 0, 0], [0.2, 0, 0.3464102], None, [0, 0.6, 0]) == pytest.approx(math.cos(math.radians(30)), abs=1e-3)
        # mount half-way along an arm hinged about the longitudinal axis at the chassis end: lever ratio 0.5
        assert estimate_motion_ratio([0, 0.3, -0.4], [0, 0.3, 0], ([0, 0, 0], [1, 0, 0]), [0, 0.6, 0]) == pytest.approx(0.5)
        assert estimate_motion_ratio([0, 0, 0], [0, 0, 0], None, [0, 0, 0]) is None             # no element
        assert estimate_motion_ratio([0, 0, -0.4], [0.4, 0, -0.4], None, [0, 0, 0]) is None      # horizontal: 0, outside 0.05-2

    def test_alias_axle_body_is_canonicalised_and_shared(self):
        new, _ = _migrated(LEGACY_TRUCK)
        ids = [b["id"] for b in new["chassis"]["mass_bodies"]]
        assert len(ids) == len(set(ids))
        st = {s["id"]: s for s in new["wheel_stations"]}
        assert st["A2L"]["upright_body"] == st["A2R"]["upright_body"]                           # one shared axle housing

    def test_vehicle_serves_the_unified_model(self):
        new, _ = _migrated(LEGACY_MX5)
        from svj import loads
        v = loads(json.dumps(new), validate_on_load=False)
        assert v.is_unified and v.stations == ["FL", "FR", "RL", "RR"] and v.topologies()["FL"] == "double_wishbone"
        assert v.spring("FL")["rate"] > 0 and v.damper("FL")["bump_curve"] and v.arb("FL")["bar_id"] == "arb_front"
        assert v.corner("A1L")["alignment"] and "upright.wheel_center" in v.hardpoints("FL")
        assert {j["joint_type"] for j in v.joints()} >= {"revolute", "spherical", "translational"}
        assert v.tyre_count == 4 and v.axle_count == 2

    def test_station_checks(self):
        from svj.constraints import check
        new, _ = _migrated(LEGACY_MX5)
        d = json.loads(json.dumps(new))
        d["wheel_stations"][0]["wheel_body"] = "ghost"
        d["wheel_stations"][1]["steering_joint"] = "nope"
        d["wheel_stations"][2]["wheel_center_marker"] = "missing_marker"
        d["wheel_stations"][3]["axle"] = "A7"
        d["anti_roll_bars"][0]["stations"] = ["FL", "ZZ"]
        errors, _ = check(d)
        assert any("wheel_body 'ghost'" in e for e in errors)
        assert any("steering_joint 'nope'" in e for e in errors)
        assert any("wheel_center_marker 'missing_marker'" in e for e in errors)
        assert any("does not match the station id" in e for e in errors)
        assert any("station 'ZZ' is not in wheel_stations" in e for e in errors)
        d2 = json.loads(json.dumps(new))
        d2["wheel_stations"].append(dict(d2["wheel_stations"][0]))
        assert any("duplicate station id" in e for e in check(d2)[0])

    def test_generated_items_are_checked_leniently_authored_ones_are_not(self):
        from svj.constraints import check
        new, _ = _migrated(LEGACY_BMW)
        body = next(b for b in new["chassis"]["mass_bodies"] if b["id"] == "wheel_fl")
        assert body["mass"] == 0.0 or body["x_derived"]
        errors, warnings = check(new)
        assert errors == []
        del body["x_derived"]
        for c in new["constraints"]:
            if c.get("body_b") == "wheel_fl":
                del c["x_derived"]
        body["mass"] = 0.0
        errors, _ = check(new)
        assert any("wheel_fl" in e and "positive mass" in e for e in errors)                    # an authored body must have mass

    def test_schema_mass_rule(self):
        new, _ = _migrated(LEGACY_BMW)
        assert [w for w in validate(new, schema_path=SCHEMA) if w.startswith("schema")] == []
        body = next(b for b in new["chassis"]["mass_bodies"] if b["id"] == "wheel_fl")
        body["mass"] = 0.0
        assert [w for w in validate(new, schema_path=SCHEMA) if w.startswith("schema")] == []   # generated: zero mass is allowed
        del body["x_derived"]
        assert any(".mass" in w for w in validate(new, schema_path=SCHEMA))                     # authored: it is not

    def test_torsional_spring_and_damper(self):
        from svj.constraints import check
        d = _doc(TRACTOR)
        frame = {"position": [0.0, 0.5, -0.5], "orientation": [-0.7071068, 0, 0, 0.7071068]}
        d["constraints"].append({"id": "bar_spring", "type": "spring", "kind": "torsional", "rate": 600.0, "body_a": "chassis", "frame_a": frame,
                                 "body_b": "loader_boom", "frame_b": dict(frame)})
        d["constraints"].append({"id": "bar_damper", "type": "damper", "kind": "torsional", "damping": 12.0, "body_a": "chassis", "frame_a": frame,
                                 "body_b": "loader_boom", "frame_b": dict(frame)})
        errors, warnings = check(d)
        assert errors == [] and not any("zero-length" in w for w in warnings)
        assert [w for w in validate(d, schema_path=SCHEMA) if w.startswith("schema")] == []
        d["constraints"][-2]["frame_b"] = {"position": [0.0, 0.5, -0.5], "orientation": [0, 0, 0, 1]}
        errors, _ = check(d)
        assert any("bar_spring" in e and "not parallel" in e for e in errors)

    def test_damper_element_rules(self):
        from svj.constraints import check, element_lengths
        new, _ = _migrated(LEGACY_MX5)
        dm = next(c for c in new["constraints"] if c["id"] == "damper_fl")
        assert element_lengths(new)["damper_fl"] > 0                                            # dampers have a length too
        dm["bump_curve"] = [[0.2, 10], [0.1, 20]]
        errors, _ = check(new)
        assert any("damper_fl" in e and "strictly increasing" in e for e in errors)
        dm["bump_curve"] = [[0.0, 0], [0.1, 20]]
        del dm["rebound_curve"]
        assert any("both bump_curve and rebound_curve" in e for e in check(new)[0])
        assert validate(new, schema_path=SCHEMA)                                                # the schema wants both curves or a damping


class TestLoopSolver:
    def test_solver_in_sync(self):
        a = (REPO_ROOT / "tools" / "loop_solver.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "loopsolver.py").read_text()
        assert a == b, "tools/loop_solver.py and svj/loopsolver.py differ"

    @staticmethod
    def _arm():
        """A control arm hinged to the chassis about a longitudinal axis (y rotation axis at x = 0), wheel centre 0.5 m out."""
        q_y = [0.7071067811865476, 0.0, 0.0, 0.7071067811865476]      # z axis -> +y ... rotation about x maps z to -y; the hinge turns about the car's x axis
        q_x = [0.0, 0.7071067811865476, 0.0, 0.7071067811865476]      # z axis -> +x
        return {
            "_metadata": {"version": "0.100"},
            "chassis": {"mass_bodies": [
                {"id": "upright_fl", "name": "Upright FL", "mass": 5.0, "position": [0, 0.5, 0.3],
                 "markers": {"wheel_center": {"position": [0, 0.5, 0.3]}}},
                {"id": "wheel_fl", "mass": 20.0, "position": [0, 0.5, 0.3]}]},
            "constraints": [
                {"id": "hinge_arm", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "upright_fl",
                 "frame_a": {"position": [0, 0, 0.3], "orientation": q_x}, "frame_b": {"position": [0, 0, 0.3], "orientation": q_x}},
                {"id": "hinge_wheel", "type": "joint", "joint_type": "revolute", "body_a": "upright_fl", "body_b": "wheel_fl",
                 "frame_a": {"position": [0, 0.5, 0.3], "orientation": q_y}, "frame_b": {"position": [0, 0.5, 0.3], "orientation": q_y}}],
            "wheel_stations": [{"id": "FL", "wheel_body": "wheel_fl", "upright_body": "upright_fl"}]}

    def test_single_arm_follows_the_circle(self):
        import math
        from svj.loopsolver import sweep
        rows = sweep(self._arm(), "FL", [0.0, 0.05, -0.05])
        assert all(r["converged"] for r in rows)
        # the wheel centre swings about the hinge at x = 0, z = 0.3 on a 0.5 m radius
        for r in rows:
            c = r["wheel_centre"]
            assert abs(math.hypot(c[1], c[2] - 0.3) - 0.5) < 1e-6
        assert abs(rows[1]["wheel_centre"][2] - 0.25) < 1e-6              # z points down: bump lowers z
        assert rows[1]["camber_deg"] != rows[0]["camber_deg"]            # the arm tilts the wheel as it swings

    def test_mx5_template_closes_and_bump_steer_is_small(self):
        v = Vehicle(json.loads(TEMPLATE.read_text(encoding="utf-8")))
        rows = v.wheel_sweep("FL", [-0.04, 0.0, 0.04])
        assert all(r["converged"] for r in rows)
        assert abs(rows[1]["camber_deg"] + 0.7) < 1e-3 and abs(rows[1]["toe_deg"]) < 1e-6          # the declared static camber
        assert abs(rows[2]["wheel_centre"][2] - rows[1]["wheel_centre"][2] + 0.04) < 1e-6      # z points down
        g = v.suspension_gains("FL")
        assert g is not None and abs(g["bump_steer_deg_per_m"]) < 5.0

    def test_steering_rack_turns_the_wheel(self):
        v = Vehicle(json.loads(TEMPLATE.read_text(encoding="utf-8")))
        r0, r1 = v.wheel_sweep("FL", [0.0], steer=0.0)[0], v.wheel_sweep("FL", [0.0], steer=0.01)[0]
        assert r1["converged"] and abs(r1["toe_deg"] - r0["toe_deg"]) > 1.0

    def test_kingpin_axis_from_the_steering_motion(self):
        import math
        v = Vehicle(json.loads(TEMPLATE.read_text(encoding="utf-8")))
        from svj.loopsolver import steering_axis
        ax = steering_axis(v.data, "FL")
        # the hardpoints are fitted to a front axle with about 7.9 deg caster, 14.4 deg kingpin inclination and 49 mm scrub
        assert abs(ax["caster_deg"] - 7.9) < 0.1
        assert abs(ax["kpi_deg"] - 14.4) < 0.1
        assert abs(ax["scrub_radius"] - 0.049) < 0.002

    def test_declared_alignment_is_compared_with_the_geometry(self):
        from svj.loopsolver import check_alignment
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        assert check_alignment(doc) == []                          # the template declares what its geometry gives
        doc["wheel_stations"][0]["alignment"]["kpi"] = 0.1
        doc["wheel_stations"][0]["alignment"]["scrub_radius"] = 0.15
        warnings = check_alignment(doc)
        assert any("FL: declared kpi" in w for w in warnings) and any("scrub_radius" in w for w in warnings)

    def test_roll_center_of_the_front_wishbones(self):
        from svj.loopsolver import roll_center
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        rc = roll_center(doc, "FL")
        assert rc is not None and 0.06 < rc["height"] < 0.11          # unequal, converging wishbones: a roll centre about 84 mm above the ground

    def test_rear_is_a_five_link_that_closes(self):
        from svj.loopsolver import sweep
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        rods = [c for c in doc["constraints"] if c["type"] == "joint" and c["body_b"] in ("upper_control_arm_rl", "lower_control_arm_rl", "toe_link_rl", "upper_lateral_link_rl", "lower_lateral_link_rl")]
        assert len(rods) == 5 and all(c["joint_type"] == "spherical" for c in rods)          # five rods, one degree of freedom
        rows = sweep(doc, "RL", [-0.05, 0.0, 0.05])
        assert all(r["converged"] for r in rows)
        assert rows[2]["camber_deg"] < rows[0]["camber_deg"]                                   # bump gives more negative camber

    def test_steering_wheel_coupled_to_the_rack(self):
        from svj.loopsolver import alignment, solve
        doc = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        doc["chassis"]["mass_bodies"].append({"id": "steering_wheel", "name": "Steering wheel", "category": "structural", "mass": 0.6,
                                              "position": [0.5, -0.4, -0.7], "parent": "chassis", "inertia": {"Ixx": 0.01, "Iyy": 0.01, "Izz": 0.02}})
        doc["constraints"] += [
            {"id": "hinge_steering_wheel", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "steering_wheel",
             "frame_a": {"position": [0.5, -0.4, -0.7]}, "frame_b": {"position": [0.5, -0.4, -0.7]}},
            {"id": "steering_ratio", "type": "coupling", "joint_a": "hinge_steering_wheel", "joint_b": "slide_rack", "ratio": 0.0063}]
        r = solve(doc, joint_values={"hinge_steering_wheel": 1.0})
        assert r["converged"] and abs(alignment(doc, "FL", r["transforms"])["toe_deg"]) > 3.0         # one radian of the wheel moves the rack 6.3 mm

    def test_unknown_station(self):
        from svj.loopsolver import SolveError, sweep
        with pytest.raises(SolveError):
            sweep(self._arm(), "XX", [0.0])


class TestAttachments:
    ATT = EXAMPLES_DIR / "attachments"

    def test_assembler_in_sync(self):
        a = (REPO_ROOT / "tools" / "assemble.py").read_text()
        b = (REPO_ROOT / "svj-py" / "svj" / "assemble.py").read_text()
        assert a == b, "tools/assemble.py and svj/assemble.py differ"

    def test_role_table_is_symmetric(self):
        from svj.assemble import ROLE_MATES
        for r, m in ROLE_MATES.items():
            assert ROLE_MATES.get(m) == r, (r, m)

    def _comb(self):
        from svj.assemble import combination_from_file
        return combination_from_file(str(self.ATT / "tractor_loader.svj-combination.json"))

    def test_composite_reproduces_the_single_file_tractor(self):
        from svj.assemble import assemble
        from svj.constraints import pose_cg, pose_inertia
        doc, notes = assemble(self._comb())
        orig = json.loads((EXAMPLES_DIR / "skeleton_tractor_loader_hitch.svj.json").read_text(encoding="utf-8"))
        assert doc["chassis"]["mass_total"] == pytest.approx(orig["chassis"]["mass_total"])
        assert doc["chassis"]["center_of_gravity"] == pytest.approx(orig["chassis"]["center_of_gravity"], abs=1e-5)
        for a, b in (("loader.loader_dump", "loader_dump"), ("loader.loader_dig", "loader_dig")):
            assert pose_cg(doc, a)["cg"] == pytest.approx(pose_cg(orig, b)["cg"], abs=1e-4)
        ia, ib = pose_inertia(doc, "loader.loader_dump"), pose_inertia(orig, "loader_dump")
        for k in ("Ixx", "Iyy", "Izz", "Ixz"):
            assert ia[k] == pytest.approx(ib[k], rel=1e-4, abs=0.01)
        assert "loader.loader_boom" in {b["id"] for b in doc["chassis"]["mass_bodies"]}
        assert any(c["id"] == "loader_mount" and c["joint_type"] == "fixed" for c in doc["constraints"])
        assert doc.get("x_assembled") is True

    def test_composite_has_no_constraint_errors(self):
        from svj.assemble import assemble
        from svj.constraints import check
        doc, _ = assemble(self._comb())
        errors, warnings = check(doc)
        assert errors == [] and warnings == []

    def test_shorthand_equals_combination_file(self):
        v = load(self.ATT / "tractor_with_loader.svj.json")
        from svj.assemble import assemble
        a = v.assemble().data
        b, _ = assemble(self._comb())
        assert a["chassis"]["center_of_gravity"] == pytest.approx(b["chassis"]["center_of_gravity"])
        assert {c["id"] for c in a["constraints"]} == {c["id"] for c in b["constraints"]}
        assert v.interfaces and v.attachments

    def test_unit_is_placed_so_interface_frames_coincide(self):
        from svj.assemble import assemble
        doc, _ = assemble(self._comb())
        boom = next(b for b in doc["chassis"]["mass_bodies"] if b["id"] == "loader.loader_boom")
        assert boom["position"] == pytest.approx([1.0, 0.0, -1.0], abs=1e-6)        # where the single-file tractor has it

    def test_mismatched_roles_and_sizes_are_errors(self):
        from svj.assemble import check_combination
        c = self._comb()
        c["units"][1]["doc"]["interfaces"][0]["role"] = "fifth_wheel"
        errors, _ = check_combination(c)
        assert any("does not mate" in e for e in errors)
        c = self._comb()
        c["units"][1]["doc"]["interfaces"][0]["size"]["pin_spacing"] = 0.5
        errors, _ = check_combination(c)
        assert any("pin_spacing" in e for e in errors)
        c = self._comb()
        c["units"][1]["doc"]["interfaces"][0]["gender"] = "socket"
        errors, _ = check_combination(c)
        assert any("both interfaces" in e for e in errors)

    def test_structure_errors(self):
        from svj.assemble import check_combination
        c = self._comb()
        c["connections"] = []
        assert any("not connected" in e for e in check_combination(c)[0])
        c = self._comb()
        c["connections"][0]["b"] = "loader.nothing"
        assert any("no interface" in e for e in check_combination(c)[0])
        c = self._comb()
        c["units"][1]["root"] = True
        assert any("exactly one root" in e for e in check_combination(c)[0])

    def test_interface_rules(self):
        from svj.assemble import check_interfaces
        doc = {"chassis": {"mass_total": 1, "center_of_gravity": [0, 0, 0], "markers": {}}, "interfaces": [
            {"id": "a.b", "role": "loader_mount"}, {"id": "x", "role": "mystery", "frame": {"position": [0, 0, 0]}},
            {"id": "x", "role": "loader_mount", "gender": "neuter", "marker": "gone"}]}
        errors, warnings = check_interfaces(doc)
        assert any("reserved" in e for e in errors) and any("duplicate" in e for e in errors)
        assert any("gender" in e for e in errors) and any("needs a `frame`" in e for e in errors)
        assert any("vocabulary" in w for w in warnings)

    def test_shipped_attachment_files_validate(self):
        for name in ("front_loader.svj.json", "tractor_host.svj.json", "tractor_with_loader.svj.json"):
            assert validate(json.loads((self.ATT / name).read_text(encoding="utf-8")), schema_path=SCHEMA) == [], name

    def test_tractor_and_semi_trailer_at_the_fifth_wheel(self):
        from svj.assemble import assemble, combination_from_file
        from svj.constraints import check, pose_cg
        doc, _ = assemble(combination_from_file(str(self.ATT / "tractor_semi_trailer.svj-combination.json")))
        assert doc["chassis"]["mass_total"] == pytest.approx(9800.0 + 34000.0)
        ids = {s["id"] for s in doc["wheel_stations"]}
        assert {"A1L", "trailer.A1L", "trailer.A3R"} <= ids              # the trailer's stations keep their names, qualified
        fw = next(c for c in doc["constraints"] if c["id"] == "fifth_wheel")
        assert fw["joint_type"] == "spherical" and fw["body_b"] == "trailer.chassis"
        assert check(doc)[0] == []
        straight, turning = pose_cg(doc)["cg"], pose_cg(doc, "turning_left")["cg"]
        assert abs(turning[1] - straight[1]) > 0.5                       # the trailer's mass swings sideways

    def test_chain_of_units(self):
        """A unit joined to another unit (not the root) is placed through the chain; a spherical joint is kept."""
        from svj.assemble import assemble
        c = self._comb()
        extra = json.loads(json.dumps(c["units"][1]["doc"]))
        extra["interfaces"] = [{"id": "tip", "role": "quick_coupler", "gender": "socket",
                                "frame": {"position": [0.5, 0.0, 0.0]}}]
        extra["constraints"], extra["poses"] = [], []
        extra["chassis"]["mass_bodies"] = []
        c["units"][1]["doc"]["interfaces"].append({"id": "bucket_tip", "role": "quick_coupler_pin", "gender": "plug",
                                                   "body": "loader_bucket", "frame": {"position": [3.0, 0.0, 0.0]}})
        c["units"].append({"id": "tool", "doc": extra})
        c["connections"].append({"id": "tool_mount", "a": "loader.bucket_tip", "b": "tool.tip", "joint": {"joint_type": "spherical"}})
        doc, _ = assemble(c)
        tool_mount = next(k for k in doc["constraints"] if k["id"] == "tool_mount")
        assert tool_mount["joint_type"] == "spherical" and tool_mount["body_a"] == "loader.loader_bucket" and tool_mount["body_b"] == "tool.chassis"


class TestAntiRollBarElements:
    def test_anti_roll_bar_as_bodies_joints_and_a_torsional_spring(self):
        from svj import constraints as cc
        z = {"inertia": {"Ixx": 0.01, "Iyy": 0.01, "Izz": 0.01}, "category": "structural", "mass": 1.0}
        doc = {"chassis": {"mass_bodies": [
            dict(z, id="bar_left", name="Bar left", position=[0, -0.4, 0], parent="chassis"),
            dict(z, id="bar_right", name="Bar right", position=[0, 0.4, 0], parent="chassis")]},
            "constraints": [
                {"id": "hinge_bar_left", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "bar_left",
                 "frame_a": {"position": [0, -0.4, 0]}, "frame_b": {"position": [0, -0.4, 0]}},
                {"id": "hinge_bar_right", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "bar_right",
                 "frame_a": {"position": [0, 0.4, 0]}, "frame_b": {"position": [0, 0.4, 0]}},
                {"id": "arb_torsion", "type": "spring", "kind": "torsional", "rate": 900.0, "body_a": "bar_left", "body_b": "bar_right",
                 "frame_a": {"position": [0, 0, 0]}, "frame_b": {"position": [0, 0, 0]}}]}
        ang = cc.element_angles(doc, {"hinge_bar_left": 0.1, "hinge_bar_right": -0.05})
        assert abs(abs(ang["arb_torsion"]) - 0.15) < 1e-6                      # the twist is the difference of the two halves
        assert abs(cc.element_angles(doc)["arb_torsion"]) < 1e-9

    def test_unified_template_loads_without_a_mass_warning(self):
        load(TEMPLATE)                                           # validate_on_load raises on a mass-sum mismatch

    def test_vertical_load_rating_warns_when_exceeded(self):
        from svj.assemble import check_combination, combination_from_file
        comb = combination_from_file(str((EXAMPLES_DIR / "attachments") / "tractor_loader.svj-combination.json"))
        _, w = check_combination(comb)
        assert not [x for x in w if "max_load" in x]
        for u in comb["units"]:
            for i in u["doc"]["interfaces"]:
                i["max_load"] = {"vertical_N": 1000.0}
        _, w = check_combination(comb)
        assert [x for x in w if "max_load.vertical_N" in x]


class TestLeafPack:
    P = dict(id="lp", axle="axle", x_front=-0.6, x_rear=0.6, seat_x=0.0, y=0.5, z=-0.2, leaves=6, width=0.07,
             thickness=0.008, mass=24.0, arch=0.08)

    def test_generator_in_sync(self):
        a = (REPO_ROOT / "tools" / "leaf_pack.py").read_text(encoding="utf-8").splitlines()
        b = (REPO_ROOT / "svj-py" / "svj" / "leafpack.py").read_text(encoding="utf-8").splitlines()
        assert a == b

    def test_chain_reproduces_the_cantilever_deflection_for_any_segment_count(self):
        from svj.leafpack import bending_stiffness, leaf_pack
        for m in (1, 2, 4, 9):
            p = dict(self.P, segments=m)
            r = leaf_pack(p)
            hinges = {c["id"][6:]: c for c in r["constraints"] if c["id"].startswith("hinge_")}
            ks = {c["id"][5:]: c["rate"] for c in r["constraints"] if c["id"].startswith("bend_")}
            tip, f = p["x_rear"], 1.0                         # unit tip force on the rear half
            defl = sum(((tip - hinges[i]["frame_a"]["position"][0]) ** 2) * f / ks[i] for i in ks if "_rear_" in i)
            exact = f * (tip - p["seat_x"]) ** 3 / (3 * bending_stiffness(p))
            assert defl == pytest.approx(exact, rel=1e-6), m

    def test_seat_rate_and_masses(self):
        from svj.leafpack import bending_stiffness, leaf_pack, seat_rate
        r = leaf_pack(self.P)
        assert r["rate"] == pytest.approx(48 * bending_stiffness(self.P) / 1.2 ** 3) == seat_rate(self.P)
        assert sum(b["mass"] for b in r["bodies"]) == pytest.approx(24.0)
        assert all(b.get("x_derived") for b in r["bodies"] + r["constraints"])

    def test_structure_ends_and_references(self):
        from svj.leafpack import leaf_pack
        r = leaf_pack(self.P)
        ids = {c["id"] for c in r["constraints"]}
        assert {"eye_lp_front", "slipper_lp_rear"} <= ids
        known = {"chassis", "axle"} | {b["id"] for b in r["bodies"]}
        assert all(c["body_a"] in known and c["body_b"] in known for c in r["constraints"])
        with pytest.raises(ValueError):
            leaf_pack(dict(self.P, end_rear="pin"))

    def test_pack_in_a_document_has_no_constraint_errors(self):
        from svj.constraints import check, element_angles
        from svj.leafpack import leaf_pack
        r = leaf_pack(self.P)
        z = {"inertia": {"Ixx": 1, "Iyy": 1, "Izz": 1}, "category": "suspension", "parent": "chassis"}
        doc = {"chassis": {"mass_bodies": [dict(z, id="axle", name="Axle", mass=60.0, position=[0, 0.5, -0.2])] + r["bodies"]},
               "constraints": r["constraints"]}
        errors, _ = check(doc)
        assert errors == []
        assert all(abs(a) < 1e-9 for a in element_angles(doc).values())


class TestTorsionBeam:
    P = dict(chassis="chassis", pivot_x=-1.9, pivot_z=-0.25, half_track_arms=0.40, half_track=0.75, wheel_x=-2.4, wheel_z=-0.25,
             plates=[(0.30, 0.003), (0.10, 0.003)])

    def _doc(self, **kw):
        from svj.torsionbeam import twist_beam
        r = twist_beam(dict(self.P, **kw))
        q = [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476]
        bodies = list(r["bodies"])
        cons = list(r["constraints"])
        stations = []
        for tag, side in (("l", "L"), ("r", "R")):
            arm = next(b for b in bodies if b["id"] == f"trailing_arm_r{tag}")
            wc = arm["markers"]["wheel_center"]["position"]
            bodies.append({"id": f"wheel_r{tag}", "name": "Wheel", "category": "wheel", "mass": 20.0, "position": wc, "parent": "chassis",
                           "inertia": {"Ixx": 0.5, "Iyy": 0.8, "Izz": 0.5}})
            fr = {"position": wc, "orientation": q}
            cons.append({"id": f"hinge_wheel_r{tag}", "type": "joint", "joint_type": "revolute", "body_a": f"trailing_arm_r{tag}",
                         "body_b": f"wheel_r{tag}", "frame_a": fr, "frame_b": fr})
            stations.append({"id": "R" + side, "wheel_body": f"wheel_r{tag}", "upright_body": f"trailing_arm_r{tag}"})
        return {"_metadata": {"version": "0.101"}, "chassis": {"mass_bodies": bodies}, "constraints": cons,
                "wheel_stations": stations}, r

    def test_generator_in_sync(self):
        a = (REPO_ROOT / "tools" / "torsion_beam.py").read_text(encoding="utf-8").splitlines()
        b = (REPO_ROOT / "svj-py" / "svj" / "torsionbeam.py").read_text(encoding="utf-8").splitlines()
        assert a == b

    def test_twist_rate_follows_the_section(self):
        from svj.torsionbeam import torsion_constant, twist_rate, roll_rate
        j = (0.30 + 0.10) * 0.003 ** 3 / 3
        assert torsion_constant(self.P) == pytest.approx(j)
        assert twist_rate(self.P) == pytest.approx(79.3e9 * j / 0.8)
        assert roll_rate(self.P) == pytest.approx(twist_rate(self.P) * (1.5 / 0.5) ** 2)

    def test_one_wheel_bump_twists_the_beam_and_leaves_the_other_side(self):
        from svj.loopsolver import _rotvec, solve
        doc, r = self._doc()
        res = solve(doc, travel={"RL": 0.05})
        assert res["converged"]
        assert res["wheel_centres"]["RL"][2] == pytest.approx(-0.25 - 0.05, abs=1e-3)
        assert res["wheel_centres"]["RR"][2] == pytest.approx(-0.25, abs=1e-6)
        ang = _rotvec(res["transforms"]["trailing_arm_rl"][0])[1]
        assert abs(abs(ang) - math.asin(0.05 / 0.5)) < 1e-5            # the arm swings about the lateral pivot
        assert _rotvec(res["transforms"]["trailing_arm_rr"][0]) == pytest.approx([0, 0, 0], abs=1e-7)

    def test_soft_threshold_only_frees_the_soft_directions(self):
        from svj.loopsolver import SOFT_RATE, _joint_residuals
        doc, r = self._doc()
        beam = next(c for c in doc["constraints"] if c["id"] == "twist_beam")
        from svj import constraints as cc
        X = {b["id"]: cc.IDENT for b in doc["chassis"]["mass_bodies"]}
        assert len(_joint_residuals(doc, beam, X)) == 5               # six minus the soft torsion
        assert beam["bushing"]["rate_ry"] < SOFT_RATE <= min(v for k, v in beam["bushing"].items() if k != "rate_ry")

    def test_document_has_no_constraint_errors(self):
        from svj.constraints import check
        doc, _ = self._doc()
        errors, _ = check(doc)
        assert errors == []


class TestCollisionProxies:
    @staticmethod
    def _doc():
        q = [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476]               # frame z -> +y: hinges about the lateral axis
        fr = {"position": [0.7, 0.0, 0.0], "orientation": q}
        z = {"inertia": {"Ixx": 1, "Iyy": 1, "Izz": 1}, "category": "structural", "mass": 2.0}
        return {"chassis": {"collision": [{"id": "cab", "type": "box", "size": [1.0, 1.0, 1.0], "position": [0, 0, 0]}],
                            "mass_bodies": [
            dict(z, id="arm", name="Arm", position=[0.7, 0, 0], parent="chassis"),
            dict(z, id="lid", name="Lid", position=[0.9, 0, 0], parent="arm",
                 collision=[{"id": "lid_box", "type": "box", "size": [0.4, 1.0, 0.1], "position": [0.9, 0, 0]}]),
            dict(z, id="knob", name="Knob", position=[5, 0, 0], parent="lid",
                 collision=[{"id": "knob_ball", "type": "sphere", "radius": 0.1, "position": [5, 0, 0]}])]},
                "constraints": [
            {"id": "hinge_arm", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "body_b": "arm", "frame_a": fr, "frame_b": fr},
            {"id": "hinge_lid", "type": "joint", "joint_type": "revolute", "body_a": "arm", "body_b": "lid", "frame_a": fr, "frame_b": fr}],
                "poses": [{"id": "folded", "values": {"hinge_arm": 3.141592653589793}}]}

    def test_checker_in_sync(self):
        a = (REPO_ROOT / "tools" / "collision_check.py").read_text(encoding="utf-8").splitlines()
        b = (REPO_ROOT / "svj-py" / "svj" / "collision.py").read_text(encoding="utf-8").splitlines()
        assert a == b

    def test_reference_pose_is_clear_and_a_folded_lid_overlaps(self):
        from svj.collision import clashes
        doc = self._doc()
        ref = clashes(doc, None, 1.0)
        lid = [k for k in ref if {k["a"], k["b"]} == {"cab", "lid_box"}]
        assert lid and lid[0]["separation"] == pytest.approx(0.2)           # 0.7 - 0.5 along x
        folded = [k for k in clashes(doc, "folded", 0.0) if {k["a"], k["b"]} == {"cab", "lid_box"}]
        assert folded and folded[0]["separation"] == pytest.approx(-0.2)         # centres 0.5 apart along x, half sizes 0.5 and 0.2

    def test_welded_and_directly_jointed_pairs_are_not_compared(self):
        from svj.collision import clashes, rigid_groups
        doc = self._doc()
        assert rigid_groups(doc)["lid"] == "lid" and rigid_groups(doc)["arm"] == "arm"
        doc["chassis"]["mass_bodies"][0]["collision"] = [{"id": "arm_box", "type": "box", "size": [5, 5, 5], "position": [0.7, 0, 0]}]
        assert not [k for k in clashes(doc, None, 10.0) if "arm_box" in (k["a"], k["b"]) and {k["body_a"], k["body_b"]} & {"chassis", "lid"}]      # chassis-arm and arm-lid are jointed
        doc["collision_ignore"] = [["chassis", "lid"]]
        assert not [k for k in clashes(doc, "folded", 0.0) if {k["body_a"], k["body_b"]} == {"chassis", "lid"}]

    def test_sphere_against_box_and_margins(self):
        from svj.collision import clashes
        doc = self._doc()
        ref = {frozenset((k["a"], k["b"])): k["separation"] for k in clashes(doc, None, 100.0)}
        assert ref[frozenset(("cab", "knob_ball"))] == pytest.approx(5.0 - 0.5 - 0.1)
        doc["chassis"]["collision"][0]["margin"] = 0.05
        ref = {frozenset((k["a"], k["b"])): k["separation"] for k in clashes(doc, None, 100.0)}
        assert ref[frozenset(("cab", "knob_ball"))] == pytest.approx(5.0 - 0.5 - 0.1 - 0.05)

    def test_check_reports_overlaps_and_bad_proxies(self):
        from svj.collision import check
        doc = self._doc()
        errors, warnings = check(doc)
        assert errors == [] and any("pose folded" in w for w in warnings)
        doc["chassis"]["mass_bodies"][1]["collision"][0]["size"] = [0.4, 0, 0.1]
        assert check(doc)[0]
        doc = self._doc()
        doc["chassis"]["collision"].append({"id": "x", "type": "capsule", "position": [0, 0, 0]})
        assert any("capsule" in m for m in check(doc)[0])
        doc = self._doc()
        doc["collision_ignore"] = [["chassis", "nothing"]]
        assert check(doc)[0]

    def test_composite_carries_the_units_proxies_placed_and_qualified(self):
        from svj.assemble import assemble, combination_from_file
        from svj.collision import check
        comb = combination_from_file(str((EXAMPLES_DIR / "attachments") / "tractor_loader.svj-combination.json"))
        for u in comb["units"]:
            u["doc"]["chassis"]["collision"] = [{"id": "hull", "type": "box", "size": [1.0, 1.0, 1.0], "position": list(u["doc"]["chassis"]["center_of_gravity"])}]
        doc, _ = assemble(comb)
        ids = [p["id"] for b in [doc["chassis"]] + doc["chassis"]["mass_bodies"] for p in b.get("collision", [])]
        assert "hull" in ids and any(i.endswith(".hull") for i in ids)
        assert check(doc)[0] == []


class TestAntiRollBarGenerator:
    P = dict(id="arb", x=-1.6, z=-0.25, y_mount=0.45, y_lever=0.35, lever_x=-0.2, diameter=0.02, arm_l="trailing_arm_rl", arm_r="trailing_arm_rr",
             link_l=[-2.0, -0.35, -0.10], link_r=[-2.0, 0.35, -0.10], stations=["RL", "RR"])

    def _doc(self):
        doc, _ = TestTorsionBeam()._doc()
        from svj.antirollbar import anti_roll_bar
        r = anti_roll_bar(self.P)
        doc["chassis"]["mass_bodies"] += r["bodies"]
        doc["constraints"] += r["constraints"]
        doc["anti_roll_bars"] = [r["anti_roll_bar"]]
        return doc, r

    def test_generator_in_sync(self):
        a = (REPO_ROOT / "tools" / "anti_roll_bar.py").read_text(encoding="utf-8").splitlines()
        b = (REPO_ROOT / "svj-py" / "svj" / "antirollbar.py").read_text(encoding="utf-8").splitlines()
        assert a == b

    def test_rates_follow_the_section_and_levers(self):
        from svj.antirollbar import bar_rate, drop_link_rate, polar_moment
        assert polar_moment(self.P) == pytest.approx(math.pi * 0.02 ** 4 / 32)
        assert bar_rate(self.P) == pytest.approx(79.3e9 * polar_moment(self.P) / 0.7)
        assert drop_link_rate(self.P) == pytest.approx(2 * bar_rate(self.P) / 0.2 ** 2)
        assert polar_moment(dict(self.P, inner_diameter=0.016)) < polar_moment(self.P)

    def test_document_has_no_constraint_errors(self):
        from svj.constraints import check
        doc, _ = self._doc()
        assert check(doc)[0] == []

    def test_opposite_bump_twists_the_bar_and_equal_bump_does_not(self):
        from svj.loopsolver import _rotvec, solve
        doc, _ = self._doc()

        def twist(res):
            t = res["transforms"]
            return _rotvec(t["arb_r"][0])[1] - _rotvec(t["arb_l"][0])[1]
        one = solve(doc, travel={"RL": 0.03})
        both = solve(doc, travel={"RL": 0.03, "RR": 0.03})
        assert one["converged"] and both["converged"]
        assert abs(twist(one)) > 0.01
        assert abs(twist(both)) < 1e-6

    def test_entry_is_an_anti_roll_bars_item(self):
        _, r = self._doc()
        assert r["anti_roll_bar"]["stations"] == ["RL", "RR"] and r["anti_roll_bar"]["bar_rate"] == pytest.approx(r["bar_rate"], rel=1e-6)


class TestInterfaceSupply:
    def test_demand_above_supply_warns(self):
        from svj.assemble import ROLE_MATES, check_combination, combination_from_file
        assert ROLE_MATES["hydraulic_coupler"] == "hydraulic_coupler"
        comb = combination_from_file(str((EXAMPLES_DIR / "attachments") / "tractor_loader.svj-combination.json"))
        host, loader = comb["units"][0]["doc"]["interfaces"], comb["units"][1]["doc"]["interfaces"]
        a, b = next(i for i in host if i["id"] == comb["connections"][0]["a"].split(".")[1]),             next(i for i in loader if i["id"] == comb["connections"][0]["b"].split(".")[1])
        a["supply"], b["demand"] = {"flow_lpm": 40.0}, {"flow_lpm": 60.0, "pressure_Pa": 1e7}
        _, w = check_combination(comb)
        assert [x for x in w if "flow_lpm 60" in x and "supplies 40" in x] and not [x for x in w if "pressure_Pa" in x]
        b["demand"]["flow_lpm"] = 30.0
        assert not [x for x in check_combination(comb)[1] if "flow_lpm" in x]


class TestLeafPackFrictionAndShackle:
    P = TestLeafPack.P

    def test_friction_follows_the_moment_and_gives_the_hysteresis_force(self):
        from svj.leafpack import leaf_pack
        r = leaf_pack(dict(self.P, segments=4, hysteresis_force=200.0))
        hinges = {c["id"]: c["friction"] for c in r["constraints"] if c["id"].startswith("hinge_") and "_rear_" in c["id"]}
        assert hinges["hinge_lp_rear_1"] == pytest.approx(100.0 * 0.6)              # F_h / 2 times the full half length
        assert hinges["hinge_lp_rear_4"] == pytest.approx(100.0 * 0.15)
        assert not [c for c in leaf_pack(self.P)["constraints"] if "friction" in c]

    def test_shackle_is_a_link_with_two_revolute_pins(self):
        from svj.constraints import check
        from svj.leafpack import leaf_pack
        r = leaf_pack(dict(self.P, end_rear="shackle", shackle_length=0.1))
        ids = {c["id"] for c in r["constraints"]}
        assert {"hanger_lp_rear", "shackle_pin_lp_rear"} <= ids and "shackle_lp_rear" in {b["id"] for b in r["bodies"]}
        z = {"inertia": {"Ixx": 1, "Iyy": 1, "Izz": 1}, "category": "suspension", "parent": "chassis"}
        doc = {"chassis": {"mass_bodies": [dict(z, id="axle", name="Axle", mass=60.0, position=[0, 0.5, -0.2])] + r["bodies"]},
               "constraints": r["constraints"]}
        assert check(doc)[0] == []
