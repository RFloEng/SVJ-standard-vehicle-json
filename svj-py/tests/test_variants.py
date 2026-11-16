"""Variants: alternative engines, parts and geometries (spec 29.5)."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from svj.variants import apply_variant, check     # noqa: E402

MX5 = REPO_ROOT / "templates" / "mazda_mx5_nd2_2024.svj.json"


def load():
    return json.loads(MX5.read_text(encoding="utf-8"))


def errs(doc):
    return check(doc)[0]


def test_checker_in_sync():
    assert (REPO_ROOT / "tools" / "variant_check.py").read_text() == (REPO_ROOT / "svj-py" / "svj" / "variants.py").read_text()


def test_template_variants_are_clean():
    d = load()
    assert [v["id"] for v in d["variants"]] == ["turbo_kit", "high_front_roll_centre"]
    assert check(d) == ([], [])


def test_apply_gives_a_standalone_file():
    d = load()
    before = copy.deepcopy(d)
    out = apply_variant(d, "turbo_kit")
    assert d == before                                              # the input is untouched
    assert "variants" not in out and out["_metadata"]["variant"] == "turbo_kit"
    assert out["powertrain"]["engine"]["torque_curve"][3][1] == pytest.approx(d["powertrain"]["engine"]["torque_curve"][3][1] * 1.3, abs=0.1)
    assert out["chassis"] == d["chassis"]                           # everything else is the base


def test_geometry_variant_moves_the_hardpoints_and_still_closes():
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import loop_solver as ls
    d = load()
    out = apply_variant(d, "high_front_roll_centre")
    g = lambda doc: ls.sweep(doc, "FL", [0.05])[0]
    a, b = g(d), g(out)
    assert a["converged"] and b["converged"]
    assert abs(a["camber_deg"] - b["camber_deg"]) > 0.1              # a different camber gain


def test_unknown_variant():
    with pytest.raises(KeyError):
        apply_variant(load(), "nope")


def variant(**kw):
    d = load()
    d["variants"] = [{"id": "t", **kw}]
    return d


def test_replace_an_element_by_id_keeps_its_id():
    d = variant(replace={"constraints[spring_fl]": {"id": "spring_fl", "type": "spring"}})
    assert errs(d) == []
    d = variant(replace={"constraints[spring_fl]": {"id": "other", "type": "spring"}})
    assert any("must be an object with id 'spring_fl'" in e for e in errs(d))


def test_replace_may_add_a_key_but_set_may_not():
    assert errs(variant(replace={"powertrain.engine.x_new": 1})) == []
    assert any("does not resolve" in e or "x_new" in e for e in errs(variant(set={"powertrain.engine.x_new": 1})))


def test_remove_then_set_order():
    d = variant(remove=["setups"], set={"chassis.mass_total": 1000.0})
    assert errs(d) == []
    out = apply_variant(d, "t")
    assert "setups" not in out and out["chassis"]["mass_total"] == 1000.0
    d = variant(remove=["constraints[spring_fl]"])
    assert len(apply_variant(d, "t")["constraints"]) == len(load()["constraints"]) - 1


def test_structure_errors():
    d = load()
    d["variants"] = [{"id": "a"}, {"id": "a"}, {"set": {}}]
    e = errs(d)
    assert any("duplicate id" in x for x in e) and any("id is required" in x for x in e)
    assert any("edited more than once" in x for x in errs(variant(remove=["chassis.mass_total"], set={"chassis.mass_total": 1})))
    assert any("cannot be replaced" in x for x in errs(variant(replace={"_metadata": {}})))
    assert any("does not resolve" in x for x in errs(variant(set={"chassis.nothing": 1})))
    assert any("must be an object" in x for x in errs(variant(set=[1])))
    assert any("no `remove`" in w for w in check(variant())[1])


def test_validate_reports_a_variant_that_breaks_the_file(tmp_path):
    d = variant(set={"chassis.mass_total": "heavy"})
    f = tmp_path / "v.svj.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "validate.py"), str(f)], capture_output=True, text=True, encoding="utf-8")
    assert "variant 't'" in r.stdout and r.returncode != 0


def test_vehicle_api():
    from svj import Vehicle
    v = Vehicle(load())
    assert [x["id"] for x in v.variants] == ["turbo_kit", "high_front_roll_centre"]
    out = v.apply_variant("turbo_kit")
    assert out.variants == [] and out.data["_metadata"]["variant"] == "turbo_kit"


def test_schema_accepts_variants():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "schema" / "svj.schema.json").read_text(encoding="utf-8"))
    schema.pop("$id", None)
    jsonschema.Draft7Validator(schema).validate(load())
    d = load()
    d["variants"][0]["remove"] = "setups"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft7Validator(schema).validate(d)
