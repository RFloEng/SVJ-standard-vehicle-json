"""Tests for the Vehicle class and loader."""

import json
import pytest
from pathlib import Path

from svj import Vehicle, load, loads, validate


# Path to the template file (relative to repo root)
REPO_ROOT = Path(__file__).parent.parent.parent
TEMPLATE = REPO_ROOT / "templates" / "mazda_mx5_nd2_2024.svj.json"
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
    with open(TATRA) as f:
        assert validate(json.load(f), schema_path=SCHEMA) == []


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
        with open(EXAMPLES_DIR / "bmw_e30_325i_semi_trailing.svj.json", encoding="utf-8") as f:
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
        assert infer_joint_types("macpherson", "strut") == ("translational", "fixed")
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
        with open(EXAMPLES_DIR / "bmw_e30_325i_semi_trailing.svj.json", encoding="utf-8") as f:
            return json.load(f)

    def test_shipped_struts_have_length(self):
        import math
        for name in ("bmw_e30_325i_semi_trailing", "corvette_c3_chapman_strut", "skeleton_ff_macpherson_torsion"):
            d = json.loads((EXAMPLES_DIR / f"{name}.svj.json").read_text(encoding="utf-8"))
            for st, c in d["suspension"].items():
                t = c.get("topology") if isinstance(c, dict) else None
                if not t or t.get("system_type") not in ("macpherson", "chapman_strut"):
                    continue
                link = next(l for l in t["links"] if l.get("type") == "strut")
                assert link["outboard_ref"] == "hardpoints.strut_lower"
                low = t["upright"]["hardpoints"]["strut_lower"]
                assert math.dist(link["inboard_points"][0], low) > 0.1, (name, st)

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
        assert validate(d, schema_path=SCHEMA) == []
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
        assert len(v.constraints) == 7 and {p["id"] for p in v.poses} >= {"transport", "loader_dump"}
        assert v.pose_cg("loader_dump")["cg"][2] < v.pose_cg()["cg"][2]
        assert set(v.element_lengths("loader_dump")) == {"loader_boom_cylinder", "loader_bucket_cylinder", "hitch_lower_link_cylinder"}
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
        assert c("upright_fl") is None and c("engine") is None and c("front_subframe") is None   # not in the vocabulary: no opinion
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
