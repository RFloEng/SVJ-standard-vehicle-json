"""Reference pose, spring law, chassis remainder, brakes, bushings and aero (spec 7.2.3, 7.4, 12.6, 13.3, 24.4, 24.5)."""
import copy
import glob
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.referencecheck import check, _eigs, _stations     # noqa: E402

MX5 = REPO_ROOT / "templates" / "mazda_mx5_nd2_2024.svj.json"
FF = REPO_ROOT / "examples" / "skeleton_ff_macpherson_torsion.svj.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def findings(doc):
    e, w = check(doc)
    return e + w


def has(doc, text):
    return any(text in f for f in findings(doc))


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "reference_check.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "referencecheck.py").read_text()


def test_eigenvalues():
    assert _eigs(((2, 0, 0), (0, 1, 0), (0, 0, 3))) == pytest.approx([1, 2, 3])
    assert _eigs(((2, 1, 0), (1, 2, 0), (0, 0, 5))) == pytest.approx([1, 3, 5])
    assert _eigs(((-1, 0, 0), (0, 4, 0), (0, 0, 4))) == pytest.approx([-1, 4, 4])


def test_shipped_examples_have_no_findings():
    files = sorted(glob.glob(str(REPO_ROOT / "examples" / "*.svj.json")))
    assert files
    for f in files:
        d = load(f)
        if "tire" in Path(f).name or "wheel_stations" not in d and "chassis" not in d:
            continue
        assert findings(d) == [], (Path(f).name, findings(d))


def test_mx5_template_carries_the_findings_of_the_simulator_team():
    d = load(MX5)
    for text in ("remaining", "not positive definite", "brake share", "bushing rate", "Cpm", "do not balance the load"):
        assert has(d, text), text


# ── springs and the reference pose ────────────────────────────────────────────
def test_negative_preload_of_a_compression_spring():
    d = load(MX5)
    next(c for c in d["constraints"] if c["type"] == "spring" and c.get("rate") and c.get("preload") is not None)["preload"] = -100.0
    assert has(d, "negative preload")


def test_springs_that_do_not_carry_the_car():
    d = load(MX5)
    assert has(d, "do not balance the load")


def test_springs_that_carry_the_car():
    d = load(MX5)
    for c in d["constraints"]:
        if c["type"] == "spring" and isinstance(c.get("preload"), (int, float)):
            c["preload"] *= 7.0
    assert not has(d, "do not balance the load")


def test_unloaded_reference_pose_is_not_asked_to_balance():
    d = load(MX5)
    d["reference_pose"] = {"condition": "unloaded"}
    assert not has(d, "do not balance the load")


# ── mass ──────────────────────────────────────────────────────────────────────
def test_inertia_required_from_v0_111():
    d = load(FF)
    d["_metadata"]["version"] = "0.111"
    errors, _ = check(d)
    assert any("have no inertia" in e for e in errors)
    d["_metadata"]["version"] = "0.110"
    errors, _ = check(d)
    assert errors == []


def test_remainder_inside_the_vehicle_is_accepted():
    assert not any("remaining" in f for f in findings(load(FF)))


def test_remainder_outside_the_vehicle():
    d = load(FF)
    d["chassis"]["center_of_gravity"] = [30.0, 0.0, 0.5]
    assert has(d, "outside the vehicle")


def test_non_physical_remainder_inertia():
    d = load(FF)
    d["chassis"]["inertia"] = {"Ixx": 1.0, "Iyy": 1.0, "Izz": 1.0, "Ixy": 0.0, "Ixz": 0.0, "Iyz": 0.0}
    assert has(d, "not positive definite")


def test_complete_decomposition_must_add_up():
    d = load(FF)
    d["chassis"]["mass_bodies_complete"] = True
    assert has(d, "mass_bodies_complete")


def test_unsprung_per_corner_follows_the_bodies():
    d = load(FF)
    d["chassis"]["mass_unsprung_per_corner"] = {"FL": 1.0}
    assert has(d, "mass_unsprung_per_corner.FL")


# ── brakes ────────────────────────────────────────────────────────────────────
def test_bias_that_the_hardware_does_not_give():
    d = load(MX5)
    assert has(d, "brake share")
    d["brakes"]["bias"] = 0.581
    assert not has(d, "brake share")


def test_proportioning_changes_the_share():
    d = load(MX5)
    d["brakes"]["bias"] = 0.581
    d["brakes"]["proportioning"] = {"type": "fixed_ratio", "ratio": 0.5}
    assert has(d, "brake share")


# ── bushings, wheel hinge ─────────────────────────────────────────────────────
def test_soft_bushing_is_flagged_and_stiff_is_not():
    d = load(MX5)
    assert has(d, "bushing rate")
    for c in d["constraints"]:
        b = c.get("bushing")
        if isinstance(b, dict):
            for k in ("rate_x", "rate_y", "rate_z"):
                if k in b:
                    b[k] *= 100
    assert not has(d, "bushing rate")


def test_wheel_hinge_sense_from_v0_111():
    d = load(MX5)
    assert not has(d, "rolls the wheel backwards")          # earlier files are not asked
    d["_metadata"]["version"] = "0.111"
    assert has(d, "rolls the wheel backwards")


# ── aero ──────────────────────────────────────────────────────────────────────
def test_cpm_against_the_lift_split():
    d = load(MX5)
    assert has(d, "Cpm")
    d["aerodynamics"]["coefficients"]["Cpm"] = 0.0
    assert not has(d, "Cpm")
    d["aerodynamics"]["coefficients"]["Cl_front"] = 0.10
    d["aerodynamics"]["coefficients"]["Cl_rear"] = 0.02
    assert has(d, "Cpm")


# ── schema ────────────────────────────────────────────────────────────────────
def test_schema_accepts_the_new_fields():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "schema" / "svj.schema.json").read_text(encoding="utf-8"))
    d = load(FF)
    d["_metadata"]["version"] = "0.111"
    d["reference_pose"] = {"condition": "static_equilibrium", "load_case": "kerb"}
    d["brakes"] = {"proportioning": {"type": "knee", "knee_pressure": 3e6, "ratio": 0.4}}
    jsonschema.Draft7Validator(schema).validate(d)
    d["reference_pose"]["condition"] = "floating"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft7Validator(schema).validate(d)
