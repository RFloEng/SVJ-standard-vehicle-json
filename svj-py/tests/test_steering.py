"""Steering wheel placement, the wheel -> gear chain and the steering consistency checks (spec 8.5, 8.7, 25.4)."""
import copy
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.steeringcheck import check, axis_of_rake, rake_of_axis, _right_steer   # noqa: E402
from svj.loopsolver import solve                                              # noqa: E402
from svj.frame import convert, SAE                                            # noqa: E402

FILES = {
    "mx5": REPO_ROOT / "templates" / "mazda_mx5_nd2_2024.svj.json",
    "rack": REPO_ROOT / "examples" / "skeleton_ff_macpherson_torsion.svj.json",
    "box": REPO_ROOT / "examples" / "skeleton_ff_recirculating_ball.svj.json",
}


def load(key):
    return json.loads(FILES[key].read_text(encoding="utf-8"))


def steer_deg(doc, wheel_angle):
    r = solve(doc, joint_values={"hinge_steering_wheel": [wheel_angle]})
    assert r["converged"], r["residual"]
    return [math.degrees(_right_steer(doc, s, r["transforms"])) for s in ("FL", "FR")]


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "steering_check.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "steeringcheck.py").read_text()


@pytest.mark.parametrize("key", sorted(FILES))
def test_shipped_files_are_consistent(key):
    assert check(load(key)) == ([], [])


@pytest.mark.parametrize("key", sorted(FILES))
def test_positive_wheel_angle_steers_right(key):
    left, right = steer_deg(load(key), 1.0)
    assert left > 1 and right > 1
    left, right = steer_deg(load(key), -1.0)
    assert left < -1 and right < -1


@pytest.mark.parametrize("key", sorted(FILES))
def test_steering_wheel_reaches_lock_to_lock(key):
    """The solver compares a revolute angle modulo 2*pi, so the wheel can be turned past a half revolution."""
    d = load(key)
    half = d["steering"]["lock_to_lock"] / 2
    assert half > math.pi
    if key == "mx5":
        pytest.skip("the estimated tie rod hardpoints of the template do not reach full lock")
    left, right = steer_deg(d, half)
    assert min(left, right) > 25


def test_steering_wheel_frame_follows_the_placement():
    for key in FILES:
        d = load(key)
        sw = d["steering"]["steering_wheel"]
        assert math.isclose(math.degrees(rake_of_axis(sw["column_axis"], 1.0)), math.degrees(sw["column_rake"]), abs_tol=1e-3)
        hinge = next(c for c in d["constraints"] if c["id"] == "hinge_steering_wheel")
        assert hinge["frame_a"]["position"] == sw["position"]
        assert axis_of_rake(sw["column_rake"], 1.0)[0] > 0


def test_sae_file_gives_the_same_findings_and_steering():
    d = load("box")
    sae, _ = convert(d, SAE)
    assert check(sae) == ([], [])
    assert steer_deg(sae, 1.0) == pytest.approx(steer_deg(d, 1.0), abs=1e-6)


def test_recirculating_ball_layout():
    d = load("box")
    assert d["steering"]["type"] == "recirculating_ball"
    cons = {c["id"]: c for c in d["constraints"]}
    sj = {s["steering_joint"] for s in d["wheel_stations"] if s.get("steering_joint")}
    assert sj == {"hinge_sector_shaft"} and cons["hinge_sector_shaft"]["joint_type"] == "revolute"
    assert cons["hinge_sector_shaft"]["body_b"] == "pitman_arm"
    assert cons["couple_steering"]["joint_b"] == "hinge_sector_shaft"
    box_ratio = 1 / abs(cons["couple_steering"]["ratio"])
    assert 10 < box_ratio < 40                                 # rad of steering wheel per rad of sector shaft


# ── findings ──────────────────────────────────────────────────────────────────
def warn_about(doc, text):
    errors, warnings = check(doc)
    assert any(text in w for w in warnings + errors), (errors, warnings)


def test_axis_toward_the_driver_is_flagged():
    d = load("rack")
    d["steering"]["steering_wheel"]["column_axis"] = [-c for c in d["steering"]["steering_wheel"]["column_axis"]]
    d["steering"]["steering_wheel"].pop("column_rake")
    warn_about(d, "away from the driver")


def test_axis_and_rake_must_agree():
    d = load("rack")
    d["steering"]["steering_wheel"]["column_rake"] += math.radians(5)
    errors, _ = check(d)
    assert any("column_rake" in e for e in errors)


def test_zero_axis_is_an_error():
    d = load("rack")
    d["steering"]["steering_wheel"]["column_axis"] = [0, 0, 0]
    errors, _ = check(d)
    assert any("axis" in e for e in errors)


def test_rake_alone_gives_the_axis():
    d = load("rack")
    d["steering"]["steering_wheel"].pop("column_axis")
    assert check(d) == ([], [])


def test_joint_displaced_from_the_placement():
    d = load("rack")
    d["steering"]["steering_wheel"]["position"][0] += 0.05
    warn_about(d, "from steering_wheel.position")


def test_joint_axis_reversed():
    d = load("rack")
    sw = d["steering"]["steering_wheel"]
    sw["column_axis"] = [-c for c in sw["column_axis"]]
    sw.pop("column_rake")
    errors, warnings = check(d)
    assert any("away from the driver" in w for w in warnings)


def test_opposite_ratio_steers_left():
    d = load("rack")
    for c in d["constraints"]:
        if c["id"] == "couple_steering":
            c["ratio"] = -c["ratio"]
    warn_about(d, "steers the road wheels to the left")


def test_ratio_that_disagrees_with_the_geometry():
    d = load("rack")
    for c in d["constraints"]:
        if c["id"] == "couple_steering":
            c["ratio"] *= 1.5
    warn_about(d, "overall_ratio is")


def test_rack_travel_against_the_coupling():
    d = load("rack")
    d["steering"]["rack_travel"] = 0.2
    warn_about(d, "rack_travel is 200 mm")


def test_derived_fields():
    d = load("mx5")
    d["steering"]["max_steer_angle"] = 0.9
    d["steering"]["lock_to_lock_turns"] = 3.5
    errors, warnings = check(d)
    assert any("max_steer_angle" in w for w in warnings) and any("lock_to_lock_turns" in w for w in warnings)


def test_file_without_a_steering_chain_is_checked_for_ratios_only():
    d = load("rack")
    d["constraints"] = [c for c in d["constraints"] if c["id"] not in ("hinge_steering_wheel", "couple_steering")]
    d["steering"]["steering_wheel"]["position"] = [0, 0, 0]
    assert check(d) == ([], [])
