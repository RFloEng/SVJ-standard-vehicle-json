"""SVJ <-> Project Chrono::Vehicle JSON converter (spec Appendix A).

The fixtures in tests/fixtures/chrono_synth are synthetic Chrono-format files (Apache-2.0, numbers chosen for the tests).
PyChrono is not installed, so nothing here runs a Chrono simulation: the checks are conversions, round trips, the loop
solver against hand geometry, static equilibrium and the tyre sign oracle against an independent port of Chrono's
pure-lateral Pac02 formulas (ChPac02Tire.cpp).
"""

import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj import chronoconvert as cc            # noqa: E402
from svj import loopsolver as ls               # noqa: E402
from svj.tiremodel import forces, params      # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "chrono_synth"
VEHICLE = FIX / "synth" / "vehicle" / "Synth_Vehicle.json"
G = 9.81


def convert(tire="synth/tire/Synth_FialaTire.json", camber="physical"):
    rep = cc.Report("chrono->svj")
    doc, rep = cc.chrono_to_svj(str(VEHICLE), str(FIX), tire, rep=rep, camber=camber, origin="synthetic")
    cc.finish_steering(doc, rep)
    return doc, rep


@pytest.fixture(scope="module")
def synth():
    return convert()


def validate(path):
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "validate.py"), str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def test_converter_in_sync():
    assert (REPO_ROOT / "tools" / "chrono_convert.py").read_bytes() == (REPO_ROOT / "svj-py" / "svj" / "chronoconvert.py").read_bytes()


# ---- Chrono -> SVJ -----------------------------------------------------------------------------------------------------

def test_synthetic_vehicle_validates_without_warnings(synth, tmp_path):
    doc, _ = synth
    p = tmp_path / "synth.svj.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    out = validate(p)
    assert "Valid SVJ" in out and "WARN" not in out and "ERROR" not in out, out
    assert doc["_metadata"]["coordinate_system"] == "ISO_8855"


def test_static_wheel_loads_follow_the_centre_of_gravity(synth):
    """Total mass and CG of the SVJ file equal the Chrono bodies' sum, so the axle loads from statics match."""
    doc, _ = synth
    chassis = json.loads((FIX / "synth" / "chassis" / "Synth_Chassis.json").read_text())["Components"][0]
    susp = json.loads((FIX / "synth" / "suspension" / "Synth_DoubleWishbone.json").read_text())
    wheel_m = json.loads((FIX / "synth" / "wheel" / "Synth_Wheel.json").read_text())["Mass"]
    tire_m = json.loads((FIX / "synth" / "tire" / "Synth_FialaTire.json").read_text())["Mass"]
    steer_m = json.loads((FIX / "synth" / "steering" / "Synth_RackPinion.json").read_text())["Steering Link"]["Mass"]
    # Chrono-side sums, independent of the converter: every body at its Chrono x
    parts = [(chassis["Mass"], 0.1)]
    for ax in (1.35, -1.35):
        for _ in "LR":
            for key, x in (("Spindle", susp["Spindle"]["COM"][0]), ("Upright", susp["Upright"]["COM"][0]),
                           ("Upper Control Arm", susp["Upper Control Arm"]["COM"][0]), ("Lower Control Arm", susp["Lower Control Arm"]["COM"][0])):
                parts.append((susp[key]["Mass"], ax + x))
            parts.append((wheel_m + tire_m, ax + susp["Spindle"]["COM"][0]))
    parts.append((steer_m, 1.23))
    M = sum(m for m, _ in parts)
    x_cg = sum(m * x for m, x in parts) / M
    assert doc["chassis"]["mass_total"] == pytest.approx(M, abs=1e-3)
    front = (x_cg + 1.35 + 0.0) / 2.7                     # fraction on the front axle from moments about the rear axle
    svj_front = (doc["chassis"]["center_of_gravity"][0] + doc["chassis"]["wheelbase"]) / doc["chassis"]["wheelbase"]
    assert svj_front == pytest.approx(front, abs=1e-3)
    # the loop solver's wheel stations carry the same total: sum of unsprung masses + sprung chassis remainder = total
    un = sum(doc["chassis"]["mass_unsprung_per_corner"].values())
    assert 0 < un < doc["chassis"]["mass_total"]


@pytest.mark.parametrize("station", ["FL", "FR"])
def test_kingpin_scrub_and_roll_centre_match_the_hand_geometry(synth, station):
    doc, _ = synth
    susp = json.loads((FIX / "synth" / "suspension" / "Synth_DoubleWishbone.json").read_text())
    ub, lb = susp["Upper Control Arm"]["Location Upright"], susp["Lower Control Arm"]["Location Upright"]
    kpi = math.degrees(math.atan2(abs(lb[1] - ub[1]), ub[2] - lb[2]))
    sa = ls.steering_axis(doc, station)
    assert sa["kpi_deg"] == pytest.approx(kpi, abs=0.01)
    assert sa["caster_deg"] == pytest.approx(0.0, abs=0.01)
    # scrub radius: wheel centre y minus the axis y at the ground plane (ground below the wheel centre by the loaded radius)
    zg = -next(w for w in doc["wheel_stations"] if w["id"] == station)["wheel"]["loaded_radius"]        # ground, wheel centre at z = 0
    y_axis = lb[1] + (ub[1] - lb[1]) * (zg - lb[2]) / (ub[2] - lb[2])
    assert sa["scrub_radius"] == pytest.approx(susp["Spindle"]["COM"][1] - y_axis, abs=2e-3)
    # roll centre: intersection of the two arm lines (front view), line through the contact patch, meets the centreline
    uc, lc = susp["Upper Control Arm"]["Location Chassis Front"], susp["Lower Control Arm"]["Location Chassis Front"]
    su, sl = (ub[2] - uc[2]) / (ub[1] - uc[1]), (lb[2] - lc[2]) / (lb[1] - lc[1])
    y_ic = (lc[2] - uc[2] + su * uc[1] - sl * lc[1]) / (su - sl)
    z_ic = uc[2] + su * (y_ic - uc[1])
    cy = susp["Spindle"]["COM"][1]
    h_hand = (z_ic - zg) * cy / (cy - y_ic)
    rc = ls.roll_center(doc, station)
    assert rc["height"] == pytest.approx(h_hand, abs=0.005)


def test_both_sides_are_mirror_images(synth):
    doc, _ = synth
    a, b = ls.steering_axis(doc, "FL"), ls.steering_axis(doc, "FR")
    for k in ("kpi_deg", "scrub_radius", "caster_deg"):
        assert a[k] == pytest.approx(b[k], abs=1e-4)
    ra, rb = ls.roll_center(doc, "FL"), ls.roll_center(doc, "FR")
    assert ra["height"] == pytest.approx(rb["height"], abs=1e-4)


def test_steering_direction_is_recorded_and_both_wheels_agree(synth):
    """Positive Chrono steering input is a LEFT turn (ChSteering.h); the solver tells which gear coordinate that is.

    NOT verified against a Chrono run (PyChrono is not installed): this checks the SVJ side only."""
    doc, rep = synth
    x = doc["x_chrono"]["steering"]
    r = x["solver_check"]["right_steer_rad"]
    assert r["FL"] * r["FR"] > 0 and abs(r["FL"] - r["FR"]) < 0.1 * abs(r["FL"])
    sign = x["gear_coordinate_sign_for_left_turn"]
    res = ls.solve(doc, joint_values={x["gear_joint"]: [sign * 0.002]})
    from svj import steeringcheck as sc
    assert sc._right_steer(doc, "FL", res["transforms"]) < 0 and sc._right_steer(doc, "FR", res["transforms"]) < 0     # left turn
    assert any("steering" in c for c in rep.checks)


def test_report_marks_what_is_not_carried(synth):
    _, rep = synth
    areas = {(s, a) for s, a, _ in rep.items}
    assert ("lost", "tyre") in areas and ("lost", "powertrain") in areas
    assert any(s == "assumed" and a == "steering" for s, a, _ in rep.items)


# ---- SVJ -> Chrono, round trips --------------------------------------------------------------------------------------------

def joints_in_chrono_frame(doc):
    """(type, position in the Chrono chassis frame) of every joint; ids may change on the way (tie rod joints are renamed)."""
    shift = doc["x_chrono"]["frame"]["shift_to_svj_origin"]
    return sorted((c["joint_type"], tuple(round(p + s, 5) for p, s in zip(c["frame_a"]["position"], shift)))
                  for c in doc["constraints"] if c["type"] == "joint")


def round_trip(doc, tmp_path, name, tire):
    rep = cc.Report("svj->chrono")
    vf = cc.svj_to_chrono(doc, str(tmp_path), name, rep)
    back, rep2 = cc.chrono_to_svj(vf, str(tmp_path), tire.format(name=name), origin="synthetic")
    cc.finish_steering(back, rep2)
    return back, rep, rep2


def test_round_trip_svj_chrono_svj_on_the_synthetic_sample(synth, tmp_path):
    doc, _ = synth
    back, rep, _ = round_trip(doc, tmp_path, "rt", "{name}/tire/{name}_tmeasy.json")
    assert back["chassis"]["mass_total"] == pytest.approx(doc["chassis"]["mass_total"], abs=1e-3)
    for a, b in zip(doc["chassis"]["center_of_gravity"][:2], back["chassis"]["center_of_gravity"][:2]):
        assert a == pytest.approx(b, abs=1e-4)
    ja, jb = joints_in_chrono_frame(doc), joints_in_chrono_frame(back)
    assert len(ja) == len(jb)
    for (ta, pa), (tb, pb) in zip(ja, jb):
        assert ta == tb and math.dist(pa, pb) < 1e-4
    # springs and dampers keep their rates
    ra = sorted(c["rate"] for c in doc["constraints"] if c["type"] == "spring" and c.get("rate"))
    rb = sorted(c["rate"] for c in back["constraints"] if c["type"] == "spring" and c.get("rate"))
    assert ra == rb
    da = sorted(c["damping"] for c in doc["constraints"] if c["type"] == "damper")
    db = sorted(c["damping"] for c in back["constraints"] if c["type"] == "damper")
    assert da == db
    # kingpin geometry survives
    for st in ("FL", "FR"):
        assert ls.steering_axis(back, st)["kpi_deg"] == pytest.approx(ls.steering_axis(doc, st)["kpi_deg"], abs=1e-3)
    assert back["steering"]["overall_ratio"] == pytest.approx(doc["steering"]["overall_ratio"], rel=1e-3)
    # what was dropped on the way is reported
    assert any(a == "tyre" for s, a, _ in rep.items if s in ("lost", "assumed"))


def test_round_trip_chrono_svj_chrono_keeps_the_numbers(synth, tmp_path):
    doc, _ = synth
    cc.svj_to_chrono(doc, str(tmp_path), "rt", cc.Report("svj->chrono"))
    orig = json.loads((FIX / "synth" / "suspension" / "Synth_DoubleWishbone.json").read_text())
    out = json.loads((tmp_path / "rt" / "suspension" / "rt_axle1.json").read_text())
    by = {b["Name"]: b for b in out["Bodies"]}
    assert by["upright"]["Mass"] == orig["Upright"]["Mass"]
    assert by["upright"]["Position"][1] == pytest.approx(orig["Upright"]["COM"][1], abs=1e-5)
    assert by["lower_wishbone"]["Mass"] == orig["Lower Control Arm"]["Mass"]
    tr = out["Distance Constraints"][0]
    assert tr["Point2"][1] == pytest.approx(orig["Tierod"]["Location Upright"][1], abs=1e-5)
    spring = next(t for t in out["TSDAs"] if "Spring Coefficient" in t)
    assert spring["Spring Coefficient"] == orig["Spring"]["Spring Coefficient"]
    assert spring["Free Length"] == pytest.approx(orig["Spring"]["Free Length"], abs=1e-6)
    shock = next(t for t in out["TSDAs"] if "Damping Coefficient" in t)
    assert shock["Damping Coefficient"] == orig["Shock"]["Damping Coefficient"]
    veh = json.loads((tmp_path / "rt" / "vehicle" / "rt_Vehicle.json").read_text())
    assert [a.get("Steering Index") for a in veh["Axles"]] == [0, None]
    rack = json.loads((tmp_path / "rt" / "steering" / "rt_rackpinion.json").read_text())
    assert rack["Pinion"]["Radius"] == pytest.approx(0.04, rel=1e-3)
    assert rack["Pinion"]["Maximum Angle (deg)"] == pytest.approx(180.0, rel=1e-3)


def test_shipped_hmmwv_round_trip_writes_the_pitman_arm_back(tmp_path):
    doc = json.loads((REPO_ROOT / "examples" / "chrono_hmmwv_17_bodies.svj.json").read_text(encoding="utf-8"))
    rep = cc.Report("svj->chrono")
    cc.svj_to_chrono(doc, str(tmp_path), "hm", rep)
    assert not [t for s, a, t in rep.items if s == "lost" and a == "steering"]
    veh = json.loads((tmp_path / "hm" / "vehicle" / "hm_Vehicle.json").read_text())
    assert veh["Steering Subsystems"][0]["Input File"].endswith("pitman.json") and veh["Axles"][0]["Steering Index"] == 0
    back, rep2 = cc.chrono_to_svj(str(tmp_path / "hm" / "vehicle" / "hm_Vehicle.json"), str(tmp_path), "hm/tire/hm_tmeasy.json", origin="synthetic")
    cc.finish_steering(back, rep2)
    assert back["chassis"]["mass_total"] == pytest.approx(doc["chassis"]["mass_total"], abs=1e-3)
    assert back["steering"]["overall_ratio"] == pytest.approx(doc["steering"]["overall_ratio"], rel=1e-4)
    assert len(joints_in_chrono_frame(back)) == len(joints_in_chrono_frame(doc))


def test_edited_pitman_linkage_is_reported_as_lost(tmp_path):
    doc = json.loads((REPO_ROOT / "examples" / "chrono_hmmwv_17_bodies.svj.json").read_text(encoding="utf-8"))
    for m in doc["chassis"]["mass_bodies"]:
        if m["id"] == "center_link":
            m["position"][0] += 0.05
    rep = cc.Report("svj->chrono")
    cc.svj_to_chrono(doc, str(tmp_path), "hm", rep)
    assert any(s == "lost" and a == "steering" for s, a, _ in rep.items)


def test_unified_suspension_is_required():
    with pytest.raises(cc.ConversionError):
        cc.svj_to_chrono({"chassis": {}}, "unused", "x")


# ---- tyres ----------------------------------------------------------------------------------------------------------------

TIR = cc.parse_tir((FIX / "synth" / "tire" / "Synth_Pac02.tir").read_text())


def chrono_fy0(Fz, alpha, gamma):
    """Pure lateral slip of ChPac02Tire.cpp (SAE signs, dpi = 0, all scaling factors 1), written from the C++."""
    c = {**TIR["LATERAL_COEFFICIENTS"], **TIR["SCALING_COEFFICIENTS"], **TIR["VERTICAL"]}
    fz0p = c["LFZO"] * c["FNOMIN"]
    dfz = (Fz - fz0p) / fz0p
    Cy = c["PCY1"] * c["LCY"]
    Ky0 = c["PKY1"] * c["FNOMIN"] * math.sin(2.0 * math.atan(Fz / (c["PKY2"] * fz0p))) * c["LFZO"] * c["LMUY"]
    Ky = Ky0 * (1.0 - c["PKY3"] * abs(gamma))
    Shy = (c["PHY1"] + c["PHY2"] * dfz) * c["LHY"] + c["PHY3"] * gamma * c["LKYG"]
    ay = alpha + Shy
    Svy = Fz * ((c["PVY1"] + c["PVY2"] * dfz) * c["LVY"] + (c["PVY3"] + c["PVY4"] * dfz) * gamma * c["LKYG"]) * c["LMUY"]
    sg = (ay > 0) - (ay < 0)
    Ey = min(1.0, (c["PEY1"] + c["PEY2"] * dfz) * (1.0 - (c["PEY3"] + c["PEY4"] * gamma) * sg) * c["LEY"])
    mu = abs((c["PDY1"] + c["PDY2"] * dfz) * (1.0 + c["PDY3"] * gamma ** 2) * c["LMUY"])
    Dy = mu * Fz
    By = Ky / (Cy * Dy + 0.1)
    Y1 = max(-math.pi / 2 + 0.01, min(math.pi / 2 - 0.01, By * ay))
    return Dy * math.sin(Cy * math.atan(Y1 - Ey * (Y1 - math.atan(Y1)))) + Svy


@pytest.fixture(scope="module")
def pac():
    doc, _ = convert("synth/tire/Synth_Pac02Tire.json", "physical")
    return params(doc["tires"]["sets"]["tire"]), doc


@pytest.mark.parametrize("Fz", [2000.0, 4000.0, 6000.0])
@pytest.mark.parametrize("alpha", [-0.15, -0.05, 0.02, 0.05, 0.12])
def test_pure_lateral_force_matches_chrono_formulas_with_iso_sign(pac, Fz, alpha):
    p, _ = pac
    svj = forces(p, Fz, 0.0, alpha, 0.0, None, 20.0)["Fy"]
    assert svj == pytest.approx(-chrono_fy0(Fz, alpha, 0.0), rel=2e-3, abs=2.0)      # ISO Fy = - Chrono's SAE-sign Fy


@pytest.mark.parametrize("gamma", [-0.06, 0.03, 0.06])
def test_physical_camber_is_chrono_with_the_inclination_sign_flipped(pac, gamma):
    p, _ = pac
    svj = forces(p, 4000.0, 0.0, 0.05, gamma, None, 20.0)["Fy"]
    assert svj == pytest.approx(-chrono_fy0(4000.0, 0.05, -gamma), rel=2e-3, abs=2.0)


def test_converted_tyre_passes_the_physical_sign_oracle(pac):
    p, _ = pac
    fy = lambda a, g: forces(p, 4000.0, 0.0, a, g, None, 20.0)["Fy"]
    assert fy(0.05, 0.0) > 0                                    # slip right -> force to the left (+Y)
    assert fy(0.0, 0.05) - fy(0.0, 0.0) < 0                     # lean right -> thrust to the right (-Y)
    assert forces(p, 4000.0, 0.05, 0.0, 0.0, None, 20.0)["Fx"] > 0
    f = forces(p, 4000.0, 0.0, 0.03, 0.0, None, 20.0)
    assert f["Fy"] * f["Mz"] < 0


def test_faithful_mode_keeps_chrono_literal_camber_and_fails_the_oracle():
    doc, rep = convert("synth/tire/Synth_Pac02Tire.json", "faithful")
    p = params(doc["tires"]["sets"]["tire"])
    fy = lambda a, g: forces(p, 4000.0, 0.0, a, g, None, 20.0)["Fy"]
    assert fy(0.0, 0.05) - fy(0.0, 0.0) > 0                     # the literal ISO-gamma-in-SAE-formula result: wrong direction
    assert fy(0.05, 0.0) > 0                                    # slip sign is the same in both modes
    assert any("literal sign" in t for _, _, t in rep.items)


# ---- shipped samples, notice, CLI -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["chrono_hmmwv_17_bodies", "chrono_hmmwv_4wd", "chrono_suv_patrol",
                                  "chrono_generic_double_wishbones", "chrono_synthetic_rack_pinion"])
def test_shipped_samples_validate_and_carry_provenance(name):
    p = REPO_ROOT / "examples" / f"{name}.svj.json"
    out = validate(p)
    assert "Valid SVJ" in out and "ERROR" not in out, out
    meta = json.loads(p.read_text(encoding="utf-8"))["_metadata"]
    assert meta["source_format"] == "Chrono::Vehicle" and meta["license"] and meta["attribution"]
    notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
    assert name in notice or f"{name}.svj.json" in notice
    if "synthetic" not in name:
        assert meta["license"] == "BSD-3-Clause"
    if name == "chrono_hmmwv_17_bodies":
        assert meta["license"] == "BSD-3-Clause" and "Project Chrono Development Team" in meta["copyright"]
        assert "Project Chrono Development Team" in notice and "hmmwv/vehicle/HMMWV_Vehicle.json" in meta["source_files"]


def test_cli_both_directions_and_report(tmp_path, capsys):
    out_svj = tmp_path / "o.svj.json"
    rep_json = tmp_path / "r.json"
    assert cc.main(["--to", "svj", str(VEHICLE), str(out_svj), "--data-root", str(FIX), "--tire", "synth/tire/Synth_FialaTire.json",
                    "--synthetic", "--report", str(rep_json)]) == 0
    assert "Conversion report" in capsys.readouterr().out
    assert json.loads(rep_json.read_text())["direction"] == "chrono->svj"
    assert cc.main(["--to", "chrono", str(out_svj), str(tmp_path / "chrono"), "--name", "cli", "--report", str(rep_json)]) == 0
    assert (tmp_path / "chrono" / "cli" / "vehicle" / "cli_Vehicle.json").exists()
    assert json.loads(rep_json.read_text())["direction"] == "svj->chrono"
    assert cc.main(["--to", "svj", str(tmp_path / "missing.json"), str(out_svj)]) == 2


def test_unsupported_chrono_input_is_an_error_not_a_silent_drop(tmp_path):
    bad = json.loads(VEHICLE.read_text())
    bad["Template"] = "TrackedVehicle"
    p = tmp_path / "v.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(cc.ConversionError):
        cc.chrono_to_svj(str(p), str(FIX))


# ---- meshes: Chrono OBJ <-> SVJ GLB ------------------------------------------------------------------------------------------

def _pos_set(prims, nd=5):
    return sorted(tuple(round(c, nd) for c in p) for pr in prims for p in pr["pos"])


@pytest.fixture(scope="module")
def mesh_trip(tmp_path_factory):
    t = tmp_path_factory.mktemp("meshtrip")
    svj = t / "o.svj.json"
    assert cc.main(["--to", "svj", str(VEHICLE), str(svj), "--data-root", str(FIX), "--tire", "synth/tire/Synth_FialaTire.json",
                    "--synthetic"]) == 0
    assert cc.main(["--to", "chrono", str(svj), str(t / "back"), "--name", "rt"]) == 0
    return t, svj, json.loads(svj.read_text(encoding="utf-8"))


def test_meshes_become_one_glb_with_visual_binding(mesh_trip):
    t, svj, doc = mesh_trip
    glb = t / doc["assets"]["meshes"][0]["uri"]
    assert glb.exists() and glb.read_bytes()[:4] == b"glTF"
    assert doc["chassis"]["visual"]["node"] == "SVJ::body::chassis"
    assert doc["_metadata"]["physics_frame"] == "ISO_8855"
    assert doc["_metadata"]["coordinate_system"]["up"] == "Y"
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "integrity_check.py"), str(svj), "--meshes"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "visual binding(s) passed" in r.stdout, r.stdout
    assert "ERROR" not in validate(svj)


def _iso(n):
    g = n["world_gl"][0]
    return [-g[2], -g[0], g[1]]                     # glTF (x, y, z) = (-Y, Z, -X) of ISO 8855


def test_glb_vertices_equal_the_obj_after_node_transform(mesh_trip):
    t, svj, doc = mesh_trip
    _, nodes = cc.read_glb((t / doc["assets"]["meshes"][0]["uri"]).read_bytes())
    names = [n["name"] for n in nodes]
    assert "SVJ::body::chassis" in names
    assert sum(1 for n in names if n.endswith("_rim")) == 4 and sum(1 for n in names if n.endswith("_tire")) == 4
    ch = next(n for n in nodes if n["name"] == "SVJ::body::chassis")
    src = cc.read_obj(str(FIX / "synth" / "meshes" / "synth_chassis.obj"))["prims"]
    assert len(_pos_set(ch["prims"])) == len(_pos_set(src))
    shift = doc["x_chrono"]["frame"]["shift_to_svj_origin"]       # p_svj = p_chrono - shift; the chassis frame sits at -shift
    assert _iso(ch) == pytest.approx([-s for s in shift], abs=1e-5)


def test_wheel_nodes_left_unrotated_right_half_turn(mesh_trip):
    t, svj, doc = mesh_trip
    _, nodes = cc.read_glb((t / doc["assets"]["meshes"][0]["uri"]).read_bytes())
    wheels = [n for n in nodes if n["name"].endswith("_rim")]
    left = [n for n in wheels if _iso(n)[1] > 0]
    right = [n for n in wheels if _iso(n)[1] < 0]
    assert len(left) == len(right) == 2
    for n in left:
        assert n["world_gl"][1][0][0] == pytest.approx(1.0) and n["world_gl"][1][2][2] == pytest.approx(1.0)
    for n in right:                                   # rot_z(pi): x and z axes reversed
        assert n["world_gl"][1][0][0] == pytest.approx(-1.0) and n["world_gl"][1][2][2] == pytest.approx(-1.0)
    assert {n["extras"]["chrono_role"] for n in nodes if n["name"].endswith("_tire")} == {"tire"}


def test_obj_round_trip_restores_vertices(mesh_trip):
    t, svj, doc = mesh_trip
    out = t / "back" / "rt"
    chassis_json = json.loads((out / "chassis" / "rt_chassis.json").read_text())
    mesh = json.dumps(chassis_json)
    assert "meshes/synth_chassis.obj" in mesh
    got = cc.read_obj(str(out / "meshes" / "synth_chassis.obj"))
    src = cc.read_obj(str(FIX / "synth" / "meshes" / "synth_chassis.obj"))
    assert _pos_set(got["prims"], 4) == _pos_set(src["prims"], 4)
    rim = cc.read_obj(str(out / "meshes" / "synth_rim.obj"))
    src_rim = cc.read_obj(str(FIX / "synth" / "meshes" / "synth_rim.obj"))
    assert _pos_set(rim["prims"], 4) == _pos_set(src_rim["prims"], 4)
    assert "synth_rim.obj" in (out / "wheel" / "rt_wheel1.json").read_text()
    assert "synth_tire_right.obj" in (out / "tire" / "rt_tmeasy.json").read_text()


def test_no_meshes_flag_and_missing_mesh_dir(tmp_path):
    svj = tmp_path / "n.svj.json"
    assert cc.main(["--to", "svj", str(VEHICLE), str(svj), "--data-root", str(FIX), "--tire", "synth/tire/Synth_FialaTire.json",
                    "--synthetic", "--no-meshes"]) == 0
    d = json.loads(svj.read_text(encoding="utf-8"))
    assert "assets" not in d and not (tmp_path / "meshes").exists()
