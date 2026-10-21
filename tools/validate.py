"""
SVJ Schema Validator
====================
Validates one or more SVJ files against the canonical JSON Schema.

Usage:
    python tools/validate.py <file.svj.json> [file2 ...] [--schema path/to/schema] [--strict]

Options:
    --schema PATH   Override the schema file path (default: schema/svj.schema.json)
    --strict        Exit non-zero even on warnings (currently: version < 0.99, multi-axle warnings)
    -h, --help      Show this help text and exit.

In addition to the JSON Schema, runs the multi-axle cross-reference rules in
tools/multiaxle_check.py (spec §23.7) and the differential-control rules in
tools/drivetrain_check.py (spec §10.6.1, §10.8.1) and the multibody
cross-references in tools/multibody_check.py (body_ref, parent, orientation, outboard_ref).
"""

import copy
import json
import sys
import warnings as _warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from multiaxle_check import check as multiaxle_check  # noqa: E402
from drivetrain_check import check as drivetrain_check  # noqa: E402
from multibody_check import check as multibody_check  # noqa: E402
from constraints_check import check as constraints_check  # noqa: E402
import assemble as _asm  # noqa: E402

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    print("Error: jsonschema is not installed.  Run:  pip install jsonschema")
    sys.exit(1)


# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_ref_error(err) -> bool:
    """True if this error (or its cause) is an unresolvable external $ref."""
    for candidate in (err, err.cause):
        if candidate is None:
            continue
        n = type(candidate).__name__
        if "RefResolution" in n or "Unresolvable" in n or "URLError" in n:
            return True
    return False


def validate_file(svj_path: str, schema: dict, strict: bool) -> bool:
    print(f"\nValidating: {svj_path}")
    print("=" * 60)

    try:
        doc = load_json(svj_path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ERROR  Cannot load file: {e}")
        return False

    # Strip $id so RefResolver doesn't try to fetch a urn: URI over the network.
    # All refs in the schema are internal (#/definitions/...) and resolve fine
    # against the in-memory schema object without an $id anchor.
    schema_local = copy.deepcopy(schema)
    schema_local.pop("$id", None)

    errors   = []
    warnings = []

    if (doc.get("_metadata") or {}).get("format") == "svj-combination":
        return _validate_combination(svj_path, doc, schema, schema_local, strict)

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        validator = Draft7Validator(schema_local)
        for err in validator.iter_errors(doc):
            if _is_ref_error(err):
                continue   # skip unresolvable external refs (e.g. tire sub-schemas)
            path_str = " → ".join(str(p) for p in err.absolute_path) if err.absolute_path else "<root>"
            errors.append(f"[{path_str}] {err.message}")

    # Multi-axle cross-reference rules (spec §23.7)
    ma_errors, ma_warnings = multiaxle_check(doc)
    errors.extend(ma_errors)
    warnings.extend(ma_warnings)

    # Differential control rules (spec §10.6.1, §10.8.1)
    dt_errors, dt_warnings = drivetrain_check(doc)
    errors.extend(dt_errors)
    warnings.extend(dt_warnings)

    # Multibody topology cross-references (proposals/svj_multibody_topology_proposal.md)
    mb_errors, mb_warnings = multibody_check(doc)
    errors.extend(mb_errors)
    warnings.extend(mb_warnings)

    # Movable parts: constraints, poses (spec §24)
    ct_errors, ct_warnings = constraints_check(doc)
    errors.extend(ct_errors)
    warnings.extend(ct_warnings)

    # Attachments: interfaces and fitted units (spec §27)
    if doc.get("interfaces"):
        i_errors, i_warnings = _asm.check_interfaces(doc)
        errors.extend(i_errors)
        warnings.extend(i_warnings)
    if doc.get("attachments") and not errors:
        try:
            comb = _asm.combination_from_vehicle(doc, str(Path(svj_path).resolve().parent))
            c_errors, c_warnings = _asm.check_combination(comb)
            errors.extend(c_errors)
            warnings.extend(c_warnings)
            if not c_errors:
                composite, _notes = _asm.assemble(comb)
                a_errors, a_warnings = constraints_check(composite)
                errors.extend(f"assembled: {e}" for e in a_errors)
                warnings.extend(f"assembled: {w}" for w in a_warnings)
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"attachments: cannot load a unit file: {e}")

    # Deprecation: the corner-based suspension section (spec §25)
    if isinstance(doc.get("suspension"), dict):
        warnings.append("suspension: the corner-based suspension section is deprecated since 0.100; "
                        "migrate it with tools/migrate_suspension.py (spec §25)")

    # Version advisory
    version = doc.get("_metadata", {}).get("version", "unknown")
    if version not in ("0.99", "0.99.1", "0.99.2", "0.99.3", "0.99.4", "0.99.5", "0.99.6", "0.99.7", "0.99.8", "0.100", "0.101"):
        warnings.append(
            f"_metadata.version is '{version}' — current spec is '0.101' "
            "(attachments)"
        )

    for w in warnings:
        print(f"  WARN   {w}")
    for e in errors:
        print(f"  ERROR  {e}")

    if not errors and not warnings:
        print(f"  OK     Valid SVJ {version}")
    elif not errors:
        print(f"  OK     Valid SVJ {version} — {len(warnings)} warning(s)")
    else:
        print(f"  FAILED {len(errors)} error(s)")

    return len(errors) == 0 and (not strict or len(warnings) == 0)


def _validate_combination(svj_path, doc, schema, schema_local, strict):
    """A *.svj-combination.json file (spec §27.3): schema, units and connections, then the assembled composite."""
    errors, warnings = [], []
    comb_schema_path = Path(__file__).resolve().parent.parent / "schema" / "svj-combination.schema.json"
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        if comb_schema_path.exists():
            cs = load_json(str(comb_schema_path))
            cs.pop("$id", None)
            for err in Draft7Validator(cs).iter_errors(doc):
                if _is_ref_error(err):
                    continue
                path_str = " > ".join(str(p) for p in err.absolute_path) if err.absolute_path else "<root>"
                errors.append(f"[{path_str}] {err.message}")
    n_units = 0
    if not errors:
        try:
            comb = _asm.combination_from_file(svj_path)
            n_units = len(comb["units"])
            c_errors, c_warnings = _asm.check_combination(comb)
            errors.extend(c_errors)
            warnings.extend(c_warnings)
            if not c_errors:
                composite, _notes = _asm.assemble(comb)
                a_errors, a_warnings = constraints_check(composite)
                errors.extend(f"assembled: {e}" for e in a_errors)
                warnings.extend(f"assembled: {w}" for w in a_warnings)
                with _warnings.catch_warnings():
                    _warnings.simplefilter("ignore")
                    for err in Draft7Validator(schema_local).iter_errors(composite):
                        if not _is_ref_error(err):
                            path_str = " > ".join(str(p) for p in err.absolute_path) if err.absolute_path else "<root>"
                            errors.append(f"assembled: [{path_str}] {err.message}")
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"cannot load a unit file: {e}")
    for w in warnings:
        print(f"  WARN   {w}")
    for e in errors:
        print(f"  ERROR  {e}")
    version = (doc.get("_metadata") or {}).get("version", "unknown")
    if not errors and not warnings:
        print(f"  OK     Valid SVJ combination {version} ({n_units} units)")
    elif not errors:
        print(f"  OK     Valid SVJ combination {version} - {len(warnings)} warning(s)")
    else:
        print(f"  FAILED {len(errors)} error(s)")
    return len(errors) == 0 and (not strict or len(warnings) == 0)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    for _stream in (sys.stdout, sys.stderr):                # a cp1252 console cannot print arrows or dashes
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    strict     = "--strict" in args
    schema_arg = None
    files      = []

    i = 0
    while i < len(args):
        if args[i] == "--schema":
            i += 1
            if i < len(args):
                schema_arg = args[i]
        elif not args[i].startswith("--"):
            files.append(args[i])
        i += 1

    if not files:
        print("Error: no input file(s) specified.")
        sys.exit(1)

    if schema_arg:
        schema_path = Path(schema_arg)
    else:
        script_dir  = Path(__file__).resolve().parent
        schema_path = script_dir.parent / "schema" / "svj.schema.json"

    if not schema_path.exists():
        print(f"Error: schema not found at {schema_path}")
        sys.exit(1)

    try:
        schema = load_json(str(schema_path))
    except Exception as e:
        print(f"Error: cannot load schema: {e}")
        sys.exit(1)

    all_passed = True
    for f in files:
        if not validate_file(f, schema, strict):
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
