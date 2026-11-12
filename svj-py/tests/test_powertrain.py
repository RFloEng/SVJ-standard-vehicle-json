"""Part-load engine torque, engine braking, shift points and torque converter (v0.108, spec §10.3.6, §10.4.1, §10.5.2)."""

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.powertrain import check, converter, engine_torque, interp, shift_points_at   # noqa: E402


def engine():
    return {"idle_rpm": 800, "max_rpm": 7000,
            "torque_curve": [[1000, 200], [4000, 400], [7000, 300]],
            "torque_curve_closed": [[1000, -20], [4000, -35], [7000, -50]]}


def converter_data():
    return {"capacity_factor": [[0.0, 50.0], [0.5, 55.0], [0.9, 60.0]],
            "torque_ratio": [[0.0, 2.0], [0.5, 1.4], [0.9, 1.0]],
            "lockup": {"min_gear": 2, "engage_speed_ratio": 0.85}}


def warnings_of(**sections):
    e, w = check({"powertrain": sections})
    assert e == []
    return w


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "powertrain_check.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "powertrain.py").read_text()


def test_clean_declaration_has_no_findings():
    gb = {"ratios": [3.5, 2.0, 1.4, 1.0], "shift_points": [[6000, 0], [6000, 3000], [6000, 3200], [0, 3300]]}
    assert warnings_of(engine=engine(), gearbox=gb, clutch={"type": "torque_converter", "torque_converter": converter_data()}) == []


def test_interp_and_engine_torque():
    assert interp([[0, 0], [10, 100]], 5) == 50 and interp([[0, 0], [10, 100]], -3) == 0 and interp([[0, 0], [10, 100]], 99) == 100
    e = engine()
    assert engine_torque(e, 4000, 1.0) == pytest.approx(400)
    assert engine_torque(e, 4000, 0.0) == pytest.approx(-35)
    assert engine_torque(e, 4000, 0.5) == pytest.approx((400 - 35) / 2)           # linear in throttle between the two curves
    assert engine_torque(e, 2500, 1.0) == pytest.approx(300)                      # linear in rpm
    assert engine_torque(e, 4000, 2.0) == pytest.approx(400) and engine_torque(e, 4000, -1) == pytest.approx(-35)


def test_part_throttle_curves_are_used_and_closed_is_optional():
    e = engine()
    e["part_throttle"] = [{"throttle": 0.5, "curve": [[1000, 60], [4000, 120], [7000, 100]]}]
    assert engine_torque(e, 4000, 0.5) == pytest.approx(120)
    assert engine_torque(e, 4000, 0.25) == pytest.approx((-35 + 120) / 2)         # between closed and the 0.5 curve
    assert engine_torque(e, 4000, 0.75) == pytest.approx((120 + 400) / 2)
    del e["torque_curve_closed"]
    assert engine_torque(e, 4000, 0.0) is None                                    # no engine braking declared
    assert engine_torque(e, 4000, 0.5) == pytest.approx(120)                      # the lowest declared curve still answers
    assert engine_torque({"torque_curve": [[0, 100], [1, 100]]}, 500, 0.3) is None


def test_engine_findings():
    e = engine()
    e["torque_curve_closed"] = [[1000, 20], [4000, -35], [7000, -50]]
    assert any("is positive at 1000 rpm" in w for w in warnings_of(engine=e))
    e["torque_curve_closed"] = [[500, 20], [900, -5], [4000, -35], [7000, -50]]             # 500 rpm is below idle: a positive value there is fine
    assert not any("is positive" in w for w in warnings_of(engine=e))
    e = engine()
    e["torque_curve_closed"] = [[1000, 500], [4000, 500], [7000, 500]]
    assert any("above the full-throttle torque_curve" in w for w in warnings_of(engine=e))
    e = engine()
    e["torque_curve_closed"] = [[4000, -35], [1000, -20]]
    assert any("ascending in rpm" in w for w in warnings_of(engine=e))
    e = engine()
    e["part_throttle"] = [{"throttle": 0.6, "curve": [[1000, 50], [7000, 100]]}, {"throttle": 0.3, "curve": [[1000, 30], [7000, 60]]}]
    assert any("strictly ascending" in w for w in warnings_of(engine=e))
    e["part_throttle"] = [{"throttle": 0.5, "curve": [[1000, 900], [7000, 900]]}]
    assert any("at throttle 0.5 is above the one at throttle 1" in w for w in warnings_of(engine=e))


def test_converter_formulas():
    tc = converter_data()
    r = converter(tc, 2000.0, 0.0)                                                # stall: sr 0
    assert r["K"] == 50 and r["TR"] == 2.0 and r["T_in"] == pytest.approx((2000 / 50) ** 2) and r["T_out"] == pytest.approx(2.0 * 1600)
    assert r["efficiency"] == 0.0
    r = converter(tc, 2000.0, 1000.0)                                             # sr 0.5
    assert r["K"] == 55 and r["efficiency"] == pytest.approx(1.4 * 0.5)
    r = converter(tc, 2000.0, 1800.0)                                             # coupling point
    assert r["TR"] == pytest.approx(1.0) and r["efficiency"] == pytest.approx(0.9)
    assert converter(tc, 0.0, 100.0)["T_out"] == 0.0


def test_converter_findings():
    cl = {"type": "torque_converter", "torque_converter": converter_data()}
    assert warnings_of(clutch=cl) == []
    cl = {"type": "single_plate", "torque_converter": converter_data()}
    assert any("clutch.type is 'single_plate'" in w for w in warnings_of(clutch=cl))
    tc = converter_data()
    tc["capacity_factor"] = [[0.1, 50.0], [0.9, -2.0]]
    ws = warnings_of(clutch={"type": "torque_converter", "torque_converter": tc})
    assert any("must start at speed ratio 0" in w for w in ws) and any("must be positive" in w for w in ws)
    tc = converter_data()
    tc["torque_ratio"] = [[0.0, 0.8], [0.9, 0.8]]
    del tc["lockup"]
    ws = warnings_of(clutch={"type": "torque_converter", "torque_converter": tc})
    assert any("below 1 at stall" in w for w in ws) and any("no lockup" in w for w in ws)
    assert any("is missing" in w for w in warnings_of(clutch={"type": "torque_converter", "torque_converter": {"torque_ratio": [[0, 2]]}}))


def test_shift_points():
    gb = {"ratios": [3.5, 2.0, 1.0], "shift_points": [[6000, 0], [6000, 3000], [0, 3200]]}
    assert shift_points_at(gb, 0.5) == [[6000, 0], [6000, 3000], [0, 3200]]
    assert shift_points_at({"ratios": [1.0]}) is None
    gb["shift_points_vs_throttle"] = [{"throttle": 0.2, "points": [[3000, 0], [3000, 1500], [0, 1600]]},
                                      {"throttle": 1.0, "points": [[6000, 0], [6000, 3000], [0, 3200]]}]
    assert shift_points_at(gb, 0.6) == [[4500, 0], [4500, 2250], [0, 2400]]       # linear between the two tables
    assert shift_points_at(gb, 0.0)[0] == [3000, 0] and shift_points_at(gb, 1.0)[0] == [6000, 0]


def test_shift_point_findings():
    gb = {"ratios": [3.5, 2.0, 1.0], "shift_points": [[6000, 0], [6000, 3000]]}
    assert any("2 pairs for 3 forward gears" in w for w in warnings_of(gearbox=gb))
    gb = {"ratios": [3.5, 2.0, 1.0], "shift_points": [[3000, 0], [6000, 6500], [0, 3200]]}
    ws = warnings_of(gearbox=gb)
    assert any("not above down_rpm" in w for w in ws)
    gb = {"ratios": [3.5, 2.0, 1.0], "shift_points": [[6000, 0], [6000, 3000], [0, 2800]]}   # 6000 * 2.0 / 3.5 = 3428 > 3000 and 6000 * 1 / 2 = 3000 > 2800: ok
    assert warnings_of(gearbox=gb) == []
    gb["shift_points"][1][1] = 3600                                                 # down-shift of gear 2 above the post-shift speed
    assert any("would hunt" in w for w in warnings_of(gearbox=gb))
    gb = {"ratios": [3.5, 2.0], "shift_points_vs_throttle": [{"throttle": 0.8, "points": [[6000, 0], [0, 3000]]},
                                                            {"throttle": 0.4, "points": [[5000, 0], [0, 3000]]}]}
    assert any("strictly ascending" in w for w in warnings_of(gearbox=gb))


def test_schema_accepts_the_data_and_rejects_bad_values():
    jsonschema = pytest.importorskip("jsonschema")
    path = next(p for p in sorted(EXAMPLES_DIR.glob("*.svj.json")) if "engine" in (json.loads(p.read_text(encoding="utf-8")).get("powertrain") or {}))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_metadata"]["version"] = "0.108"
    pt = data["powertrain"]
    pt["engine"].update({"torque_curve_closed": [[1000, -20], [6000, -40]], "inertia_block": 0.4,
                         "part_throttle": [{"throttle": 0.5, "curve": [[1000, 50], [6000, 100]]}]})
    pt.setdefault("gearbox", {"ratios": [3.0, 2.0]}).update({"shift_latency": 0.2, "shift_points": [[6000, 0], [0, 3000]]})
    pt.setdefault("clutch", {}).update({"type": "torque_converter", "torque_converter": converter_data()})
    schema = json.loads((REPO_ROOT / "schema" / "svj.schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    mine = lambda d: [e.message for e in v.iter_errors(d) if {"engine", "gearbox", "clutch"} & set(map(str, e.absolute_path))]
    assert mine(data) == []
    bad = copy.deepcopy(data)
    bad["powertrain"]["engine"]["part_throttle"][0]["throttle"] = 1.5
    bad["powertrain"]["gearbox"]["shift_points"] = [[6000]]
    bad["powertrain"]["clutch"]["torque_converter"]["lockup"]["engage_speed_ratio"] = 2
    assert len(mine(bad)) >= 3
