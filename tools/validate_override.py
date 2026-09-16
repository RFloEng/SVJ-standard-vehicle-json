"""
SVJ Override File Validator
============================
Resolves an *.svj-override.json file (SVJ_Spec.md §3.4) against its `base`
SVJ file, applies the RFC 7396 JSON Merge Patch, and validates the RESULT
against the standard SVJ schema — because an override file's whole point
is that the resolved document must be a normal, valid SVJ file.

Usage:
    python tools/validate_override.py <file.svj-override.json> [--show-resolved]

Options:
    --show-resolved   Print the fully resolved (base + patch) document to stdout.
    -h, --help        Show this help text and exit.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


def merge_patch(target, patch):
    """RFC 7396 JSON Merge Patch."""
    if not isinstance(patch, dict):
        return patch
    if not isinstance(target, dict):
        target = {}
    result = dict(target)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            result[key] = merge_patch(result.get(key), value)
        else:
            result[key] = value
    return result


def validate_override_schema(doc, override_schema_path):
    with open(override_schema_path) as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)
    return [f"[{'.'.join(str(p) for p in e.absolute_path) or '<root>'}] {e.message}"
            for e in validator.iter_errors(doc)]


def validate_resolved_schema(doc, base_schema_path):
    with open(base_schema_path) as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for e in validator.iter_errors(doc):
        # Same unresolved-$ref tolerance as tools/validate.py
        if e.validator == "$ref" or "Unresolvable" in str(e.message):
            continue
        path_str = " → ".join(str(p) for p in e.absolute_path) if e.absolute_path else "<root>"
        errors.append(f"[{path_str}] {e.message}")
    return errors


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    show_resolved = "--show-resolved" in argv

    if not args or "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0

    override_path = Path(args[0])
    repo_root = Path(__file__).resolve().parent.parent
    override_schema_path = repo_root / "schema" / "svj-override.schema.json"
    base_schema_path = repo_root / "schema" / "svj.schema.json"

    print(f"\nValidating override: {override_path}")
    print("=" * 60)

    with open(override_path) as f:
        override_doc = json.load(f)

    struct_errors = validate_override_schema(override_doc, override_schema_path)
    if struct_errors:
        for e in struct_errors:
            print(f"  ERROR  {e}")
        print(f"  FAILED {len(struct_errors)} override-structure error(s)")
        return 1

    base_ref = override_doc["_metadata"]["base"]
    base_path = (override_path.parent / base_ref).resolve()
    if not base_path.exists():
        print(f"  ERROR  base file not found: {base_path}")
        return 1

    with open(base_path) as f:
        base_doc = json.load(f)

    resolved = merge_patch(base_doc, override_doc["patch"])

    if show_resolved:
        print(json.dumps(resolved, indent=2))

    resolved_errors = validate_resolved_schema(resolved, base_schema_path)
    if resolved_errors:
        for e in resolved_errors:
            print(f"  ERROR  {e}")
        print(f"  FAILED {len(resolved_errors)} schema error(s) in resolved document")
        return 1

    print(f"  OK     Override resolves to a valid SVJ document (base: {base_ref})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
