"""Engine declaration for sound simulation (v0.107, spec §10.3.2-§10.3.3): schema, firing angles, formulas, checks."""

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.engine import check, engine_order, firing_angles, firing_frequency_hz, harmonic_hz   # noqa: E402
from svj.engine import motor_frequency_hz, supercharger_whine_hz, turbo_blade_pass_hz         # noqa: E402


def v8():
    return {"cycle": "four_stroke", "max_rpm": 7200, "torque_curve": [[1000, 180], [5500, 520], [7200, 430]],
            "configuration": "V8",
            "layout": {"cylinders": 8, "arrangement": "V", "bank_angle_deg": 90, "crank": "cross_plane",
                       "firing_order": [1, 8, 4, 3, 6, 5, 7, 2]},
            "aspiration": {"type": "turbo", "chargers": [{"id": "tc", "kind": "turbo", "blades": 11, "blow_off": True}]},
            "limiter": {"type": "hard_cut", "rpm": 7200}}


def doc_with(engine):
    return {"powertrain": {"engine": engine}}


def warnings_of(engine, **extra):
    d = doc_with(engine)
    d.update(extra)
    e, w = check(d)
    assert e == []
    return w


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "engine_check.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "engine.py").read_text()


def test_clean_declaration_has_no_findings():
    assert warnings_of(v8()) == []


def test_formulas():
    assert engine_order(8) == 4.0 and engine_order(3, "two_stroke") == 3.0
    assert firing_frequency_hz(6000, 8) == pytest.approx(400.0)                  # 100 rev/s * 4
    assert firing_frequency_hz(6000, 2, "two_stroke") == pytest.approx(200.0)
    assert harmonic_hz(6000, 2) == pytest.approx(200.0)
    assert turbo_blade_pass_hz(11, 120000) == pytest.approx(22000.0)
    assert supercharger_whine_hz(6000, 2.5, lobes=3) == pytest.approx(750.0)
    assert motor_frequency_hz(1000, 9.0, 4) == pytest.approx(600.0)


def test_firing_angles_are_derived_or_declared():
    assert firing_angles(v8()) == [0, 90, 180, 270, 360, 450, 540, 630]
    inline4 = {"layout": {"cylinders": 4, "arrangement": "I"}}
    assert firing_angles(inline4) == [0, 180, 360, 540]
    assert firing_angles({"cycle": "two_stroke", "layout": {"cylinders": 3, "arrangement": "I"}}) == [0, 120, 240]
    vtwin = {"layout": {"cylinders": 2, "arrangement": "V", "bank_angle_deg": 90, "crank": "single_plane"}}
    assert firing_angles(vtwin) == [0, 270]                                          # 270 / 450 degrees
    assert firing_angles({"layout": {"cylinders": 6, "arrangement": "V", "bank_angle_deg": 60}}) is None
    assert firing_angles({"layout": {"cylinders": 3, "arrangement": "I", "firing_angles_deg": [0, 240, 480]}}) == [0, 240, 480]
    assert firing_angles({"cycle": "wankel", "layout": {"cylinders": 2, "arrangement": "rotary"}}) is None


def test_underivable_pattern_asks_for_declared_angles():
    e = v8()
    e["layout"] = {"cylinders": 6, "arrangement": "V", "bank_angle_deg": 60}
    e["configuration"] = "V6"
    assert any("declare layout.firing_angles_deg" in w for w in warnings_of(e))
    e["layout"]["firing_angles_deg"] = [0, 120, 240, 360, 480, 600]
    assert warnings_of(e) == []


def test_layout_findings():
    e = v8()
    e["layout"]["firing_order"] = [1, 2, 3]
    assert any("not a permutation" in w for w in warnings_of(e))
    e = v8()
    e["layout"]["firing_angles_deg"] = [0, 90, 180]
    assert any("3 entries for 8 cylinders" in w for w in warnings_of(e))
    e["layout"]["firing_angles_deg"] = [0, 90, 180, 270, 360, 450, 540, 720]
    assert any("inside one cycle" in w for w in warnings_of(e))
    e["layout"]["firing_angles_deg"] = [90, 0, 180, 270, 360, 450, 540, 630]
    assert any("ascending" in w for w in warnings_of(e))
    e = v8()
    e["configuration"] = "V6"
    assert any("names 6 cylinders but layout.cylinders is 8" in w for w in warnings_of(e))


def test_aspiration_findings():
    e = v8()
    e["aspiration"] = {"type": "na", "chargers": [{"kind": "turbo"}]}
    assert any("naturally aspirated" in w for w in warnings_of(e))
    e["aspiration"] = {"type": "turbo"}
    assert any("lists no chargers" in w for w in warnings_of(e))
    e["aspiration"] = {"type": "supercharger", "chargers": [{"kind": "turbo"}]}
    assert any("not a roots" in w for w in warnings_of(e))
    e["aspiration"] = {"type": "twin_charged", "chargers": [{"kind": "turbo"}]}
    assert any("needs a turbo and a supercharger" in w for w in warnings_of(e))
    e["aspiration"] = {"type": "twin_charged", "chargers": [{"kind": "turbo", "blades": 9}, {"kind": "roots", "pulley_ratio": 2.0, "lobes": 3}]}
    assert warnings_of(e) == []
    e["aspiration"] = {"type": "turbo", "chargers": [{"id": "t", "kind": "turbo", "pulley_ratio": 2.0}]}
    assert any("has no pulley_ratio" in w for w in warnings_of(e))
    e["aspiration"] = {"type": "supercharger", "chargers": [{"id": "s", "kind": "roots", "blades": 9}]}
    assert any("not a blower" in w for w in warnings_of(e))


def test_limiter_curve_and_kind_findings():
    e = v8()
    e["limiter"]["rpm"] = 8000
    assert any("above max_rpm" in w for w in warnings_of(e))
    e = v8()
    e["torque_curve"].append([9000, 100])
    assert any("reaches 9000" in w for w in warnings_of(e))
    e = v8()
    e["kind"] = "electric"
    assert any("combustion fields" in w for w in warnings_of(e))
    assert any("'bev'" in w for w in warnings_of(v8(), electric={"hybrid_type": "bev"}))


def test_schema_accepts_the_declaration_and_rejects_bad_values():
    path = next(p for p in sorted(EXAMPLES_DIR.glob("*.svj.json")) if "engine" in (json.loads(p.read_text(encoding="utf-8")).get("powertrain") or {}))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_metadata"]["version"] = "0.107"
    decl = v8()
    decl.pop("torque_curve")
    data["powertrain"]["engine"].update(decl)
    data["powertrain"]["engine"].update({"kind": "ice", "fuel": "petrol", "exhaust": {"headers": "equal_length", "muffler": "chambered", "outlets": 4, "overrun": "burble"},
                                         "intake": {"type": "plenum"}})
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "schema" / "svj.schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    mine = lambda d: [e.message for e in v.iter_errors(d) if "engine" in list(map(str, e.absolute_path))]
    assert mine(data) == []
    bad = copy.deepcopy(data)
    bad["powertrain"]["engine"]["aspiration"]["type"] = "ram_air"
    bad["powertrain"]["engine"]["layout"]["cylinders"] = 0
    errs = mine(bad)
    assert any("ram_air" in x for x in errs) and any("minimum of 1" in x or "less than the minimum" in x for x in errs)
