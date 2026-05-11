"""
SVJ Schema Validator
====================
Validates one or more SVJ files against the canonical JSON Schema.

Usage:
    python tools/validate.py <file.svj.json> [file2 ...] [--schema path/to/schema] [--strict]

Options:
    --schema PATH   Override the schema file path (default: schema/svj.schema.json)
    --strict        Exit non-zero even on warnings (currently: version < 0.97)
    -h, --help      Show this help text and exit.
"""

import copy
import json
import sys
import warnings as _warnings
from pathlib import Path

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

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        validator = Draft7Validator(schema_local)
        for err in validator.iter_errors(doc):
            if _is_ref_error(err):
                continue   # skip unresolvable external refs (e.g. tire sub-schemas)
            path_str = " → ".join(str(p) for p in err.absolute_path) if err.absolute_path else "<root>"
            errors.append(f"[{path_str}] {err.message}")

    # Version advisory
    version = doc.get("_metadata", {}).get("version", "unknown")
    if version not in ("0.97",):
        warnings.append(
            f"_metadata.version is '{version}' — consider upgrading to '0.97' "
            "for visual binding support"
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
        print(f"  FAILED {len(errors)} schema error(s)")

    return len(errors) == 0 and (not strict or len(warnings) == 0)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
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
