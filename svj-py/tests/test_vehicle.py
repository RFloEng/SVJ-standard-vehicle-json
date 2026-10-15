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
