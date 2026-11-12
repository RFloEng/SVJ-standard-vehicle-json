"""Tools give the same physical answers on a file in SAE J670 and on its ISO 8855 conversion (ISO migration, step 3)."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.frame import ISO, SAE, convert, flip_vector   # noqa: E402
from svj.loopsolver import alignment, check_alignment, roll_center, solve, steering_axis, sweep   # noqa: E402

NAMES = ["alfa_romeo_75_de_dion", "bmw_e30_325i_semi_trailing", "corvette_c3_chapman_strut",
         "skeleton_ff_macpherson_torsion", "citroen_2cv_trailing_arm"]


def pair(name):
    iso = json.loads((REPO_ROOT / "examples" / (name + ".svj.json")).read_text(encoding="utf-8"))     # shipped in ISO since 0.109
    return convert(iso, SAE)[0], iso


@pytest.mark.parametrize("name", NAMES)
def test_sweep_is_frame_independent(name):
    sae, iso = pair(name)
    a = sweep(sae, "FL", [-0.04, 0.0, 0.04])
    b = sweep(iso, "FL", [-0.04, 0.0, 0.04])
    for ra, rb in zip(a, b):
        assert ra["converged"] and rb["converged"]
        assert rb["camber_deg"] == pytest.approx(ra["camber_deg"], abs=1e-5)
        assert rb["toe_deg"] == pytest.approx(ra["toe_deg"], abs=1e-5)
        assert rb["wheel_centre"] == pytest.approx(flip_vector(ra["wheel_centre"]), abs=1e-6)
    # a bump raises the wheel in either frame
    assert (b[2]["wheel_centre"][2] - b[0]["wheel_centre"][2]) == pytest.approx(0.08, abs=1e-6)
    assert (a[2]["wheel_centre"][2] - a[0]["wheel_centre"][2]) == pytest.approx(-0.08, abs=1e-6)


@pytest.mark.parametrize("name", NAMES[:3])
def test_kingpin_and_roll_centre_are_frame_independent(name):
    sae, iso = pair(name)
    for key in ("caster_deg", "kpi_deg", "scrub_radius", "caster_trail"):
        va, vb = steering_axis(sae, "FL"), steering_axis(iso, "FL")
        if va is None:
            continue
        assert vb[key] == pytest.approx(va[key], abs=1e-4)      # finite-difference noise
    ra, rb = roll_center(sae, "FL"), roll_center(iso, "FL")
    if ra:
        assert rb["height"] == pytest.approx(ra["height"], abs=1e-6)


@pytest.mark.parametrize("name", NAMES)
def test_alignment_check_gives_the_same_findings(name):
    sae, iso = pair(name)
    assert check_alignment(iso) == check_alignment(sae)


def test_mesh_convention_rows_match_the_spec_tables():
    from mesh_check import convention
    # asset Y-up, -Z forward (Blender): spec 22.4 table
    assert convention("Y", "-Z", "right", "ISO_8855") == [[0, 0, -1], [-1, 0, 0], [0, 1, 0]]     # forward -> -Z, left -> -X, up -> +Y
    assert convention("Y", "-Z", "right", "SAE_J670") == [[0, 0, -1], [1, 0, 0], [0, -1, 0]]     # right -> +X, down -> -Y
    assert convention("Y", "-Z") == convention("Y", "-Z", "right", "SAE_J670")


def test_viewer_js_port_matches_the_python_conversion(tmp_path):
    """The viewer converts legacy SAE files on load with a JavaScript port of convert_frame; it must agree with it."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    html = (REPO_ROOT / "viewer" / "svj_viewer_v4.7.html").read_text(encoding="utf-8")
    port = html[html.index("const FRAME_VECTOR_KEYS"):html.index("const vec2three")]
    (tmp_path / "port.js").write_text(port + "\nmodule.exports={svjToISO};\n", encoding="utf-8")
    names = NAMES + ["skeleton_4wd_solid_axle", "man_tgs_36_430_8x4_4_tridem_lift_tag"]
    docs = {}
    for n in names:
        doc, iso = pair(n)
        docs[n] = {"in": doc, "out": iso}
    (tmp_path / "docs.json").write_text(json.dumps(docs), encoding="utf-8")
    (tmp_path / "run.js").write_text(
        "const {svjToISO}=require('./port.js');const d=JSON.parse(require('fs').readFileSync('docs.json','utf8'));"
        "const bad=Object.keys(d).filter(k=>JSON.stringify(svjToISO(d[k].in))!==JSON.stringify(d[k].out));"
        "console.log(JSON.stringify(bad));", encoding="utf-8")
    out = subprocess.run([node, "run.js"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == []
