"""Tyre sign oracle (ISO migration, v0.109).

Physical cases that must hold in any axis system; the shipped sets are in ISO 8855 tyre axes (X forward, Y left, Z up)
and a legacy set declared `axis_system: SAE_J670` must give the same physical results through the evaluator.

Physical statements:
  1. Slip right (velocity points to the right of the heading): the lateral force on the tyre points LEFT.
  2. Driving slip (kappa > 0): the longitudinal force points FORWARD.
  3. Aligning moment restores: Mz has the opposite sign to the lateral force.
  4. Rolling resistance opposes rolling: My is negative for a wheel rolling forward (ISO: forward rolling is +Y).
  5. Camber: lean to the right (gamma > 0) pushes the tyre RIGHT (negative Y).
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.tiremodel import forces, params   # noqa: E402

# name: (file, set); both sets are ISO 8855 since v0.109
CASES = {
    "mf62_example": ("examples/tire_mf62_245_40r18.svj.json", "sport_245_40r18_mf62"),
    "mx5_template": ("templates/mazda_mx5_nd2_2024.svj.json", "front_205_45r17"),
}
FZ, VX = 4000.0, 20.0


def tyre_set(name):
    path, set_name = CASES[name]
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))["tires"]["sets"][set_name]


def evaluator(name):
    return params(tyre_set(name)), "left"          # the file's +Y axis points left (ISO 8855)


def direction(y_points, fy):
    """Physical direction of a lateral force given the sign of Fy in the file's own axes."""
    positive = y_points
    negative = "left" if y_points == "right" else "right"
    return positive if fy > 0 else negative


@pytest.mark.parametrize("name", CASES)
def test_1_slip_right_gives_a_force_to_the_left(name):
    p, y_points = evaluator(name)
    f = forces(p, FZ, 0.0, 0.05, 0.0, None, VX)          # alpha > 0 means velocity to the right
    assert direction(y_points, f["Fy"]) == "left"


@pytest.mark.parametrize("name", CASES)
def test_2_driving_slip_gives_a_forward_force(name):
    p, _ = evaluator(name)
    assert forces(p, FZ, 0.05, 0.0, 0.0, None, VX)["Fx"] > 0


@pytest.mark.parametrize("name", CASES)
def test_3_aligning_moment_has_the_opposite_sign_to_the_lateral_force(name):
    p, _ = evaluator(name)
    f = forces(p, FZ, 0.0, 0.03, 0.0, None, VX)
    assert f["Fy"] * f["Mz"] < 0


def test_4_rolling_resistance_opposes_rolling():
    p, _ = evaluator("mf62_example")                       # the only shipped set with rolling-resistance coefficients
    assert forces(p, FZ, 0.0, 0.0, 0.0, None, VX)["My"] < 0


@pytest.mark.parametrize("name", CASES)
def test_5_camber_lean_right_pushes_the_tyre_right(name):
    p, y_points = evaluator(name)
    fy = lambda a, g: forces(p, FZ, 0.0, a, g, None, VX)["Fy"]
    thrust = fy(0.0, 0.05) - fy(0.0, 0.0)                  # the change from camber (ply steer and conicity give an offset at zero)
    assert direction(y_points, thrust) == "right"
    assert direction(y_points, fy(0.0, -0.05) - fy(0.0, 0.0)) == "left"
    assert thrust * (fy(0.05, 0.0) - fy(0.0, 0.0)) < 0     # opposite to the slip force of a positive slip angle


@pytest.mark.parametrize("name", CASES)
def test_legacy_sae_set_gives_the_same_physical_results(name):
    """The same set written with SAE/Pacejka signs and declared SAE_J670 must evaluate to the ISO results."""
    import copy
    from svj.tiremodel import to_iso_set
    iso = tyre_set(name)
    sae = copy.deepcopy(iso)
    sae["pacejka"] = to_iso_set(iso["pacejka"])
    assert sae["pacejka"]["axis_system"] == "SAE_J670" and sae["pacejka"]["lateral"]["pKy1"] * iso["pacejka"]["lateral"]["pKy1"] < 0
    pa, pi = params(sae), params(iso)
    for kappa, alpha, gamma in ((0.0, 0.05, 0.0), (0.05, 0.0, 0.0), (0.0, 0.0, 0.05), (0.08, -0.12, 0.03), (-0.2, 0.2, -0.04)):
        a = forces(pa, FZ, kappa, alpha, gamma, None, VX)
        b = forces(pi, FZ, kappa, alpha, gamma, None, VX)
        for k in a:
            assert a[k] == pytest.approx(b[k], rel=1e-9, abs=1e-9), (k, kappa, alpha, gamma)
    from svj.tiremodel import mirror_camber
    m = mirror_camber(iso["pacejka"])
    mirrored = copy.deepcopy(iso)
    mirrored["pacejka"] = m
    pm = params(mirrored)
    for gamma in (0.02, 0.06):
        assert forces(pm, FZ, 0.0, 0.03, gamma, None, VX)["Fy"] == pytest.approx(forces(pi, FZ, 0.0, 0.03, -gamma, None, VX)["Fy"], rel=1e-9)


def test_axis_system_is_validated():
    s = tyre_set("mf62_example")
    s["pacejka"]["axis_system"] = "NED"
    with pytest.raises(ValueError):
        params(s)
