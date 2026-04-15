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
            "version": "0.94",
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
        assert "SVJ v0.94" in repr(v)

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
                "version": "0.94",
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
            assert len(list(v.corners())) > 0, f"No corners in {f.name}"
