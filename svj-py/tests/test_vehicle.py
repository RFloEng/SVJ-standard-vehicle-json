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
