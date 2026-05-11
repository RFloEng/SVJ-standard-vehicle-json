"""
SVJ glTF Visual Binding Integrity Checker
==========================================
Validates that all visual bindings in an SVJ file are internally consistent:

  1. Every visual.node follows the SVJ::<category>::<name> pattern.
  2. For body/lod nodes, the <name> suffix matches the parent SVJ body id.
  3. Every visual.mesh_ref references a declared entry in assets.meshes.
  4. No two bodies share the same visual.node (uniqueness).

Usage:
    python tools/integrity_check.py <path-to-file.svj.json> [--strict]

Options:
    --strict    Treat warnings as errors (non-zero exit on any issue).
"""

import json
import re
import sys
from pathlib import Path

NODE_PATTERN = re.compile(r"^SVJ::(body|helper|lod)::[a-z0-9_]+$")
BINDING_CATEGORIES = {"body", "lod"}   # categories where id-suffix matching is required


def load_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_mesh_ids(data: dict) -> set:
    """Return the set of declared mesh IDs from assets.meshes."""
    meshes = data.get("assets", {}).get("meshes", [])
    return {m["id"] for m in meshes if "id" in m}


def collect_bindings(data: dict) -> list[dict]:
    """
    Walk the SVJ document and collect every visual binding found.
    Returns a list of dicts: {body_id, node, mesh_ref, location}
    """
    bindings = []

    def _add(body_id: str, visual: dict, location: str):
        if isinstance(visual, dict) and "node" in visual:
            bindings.append({
                "body_id":  body_id,
                "node":     visual.get("node", ""),
                "mesh_ref": visual.get("mesh_ref"),
                "location": location,
            })

    # Top-level chassis
    chassis = data.get("chassis", {})
    if "visual" in chassis:
        _add("chassis", chassis["visual"], "chassis")

    # Decomposed mass bodies (engine, gearbox, driver, ...)
    for body in chassis.get("mass_decomposition", []):
        bid = body.get("id", "<unknown>")
        if "visual" in body:
            _add(bid, body["visual"], f"chassis.mass_decomposition[{bid}]")

    # Suspension corners (upright visual)
    suspension = data.get("suspension", {})
    for corner_key in ("FL", "FR", "RL", "RR"):
        corner = suspension.get(corner_key, {})
        if "visual" in corner:
            upright_id = corner.get("upright_id", f"upright_{corner_key.lower()}")
            _add(upright_id, corner["visual"], f"suspension.{corner_key}")

    return bindings


def check(path: str, strict: bool = False) -> bool:
    print(f"\nChecking: {path}")
    print("=" * 60)

    try:
        data = load_file(path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ERROR  Could not load file: {e}")
        return False

    mesh_ids = collect_mesh_ids(data)
    bindings = collect_bindings(data)

    if not bindings:
        print("  INFO   No visual bindings found — nothing to check.")
        return True

    errors   = []
    warnings = []
    seen_nodes = {}

    for b in bindings:
        loc      = b["location"]
        body_id  = b["body_id"]
        node     = b["node"]
        mesh_ref = b["mesh_ref"]

        # Rule 1: node pattern
        m = NODE_PATTERN.match(node)
        if not m:
            errors.append(f"[{loc}] node '{node}' does not match SVJ::<category>::<name> pattern")
            continue

        category = m.group(1)
        suffix   = node.split("::")[-1]

        # Rule 2: id-suffix match (body and lod only)
        if category in BINDING_CATEGORIES and body_id != suffix:
            errors.append(
                f"[{loc}] Binding mismatch — body id '{body_id}' != node suffix '{suffix}' "
                f"(node: '{node}'). Fix: rename the body id OR the glTF node so they match."
            )

        # Rule 3: mesh_ref validity
        if mesh_ref is not None and mesh_ids and mesh_ref not in mesh_ids:
            errors.append(
                f"[{loc}] mesh_ref '{mesh_ref}' not found in assets.meshes "
                f"(declared: {sorted(mesh_ids)})"
            )
        if mesh_ref is None and len(mesh_ids) > 1:
            warnings.append(
                f"[{loc}] mesh_ref is absent but {len(mesh_ids)} mesh files are declared. "
                f"Add mesh_ref to avoid ambiguity."
            )

        # Rule 4: uniqueness
        if node in seen_nodes:
            errors.append(
                f"[{loc}] Duplicate node '{node}' — already used by '{seen_nodes[node]}'"
            )
        else:
            seen_nodes[node] = loc

    # Report
    for w in warnings:
        print(f"  WARN   {w}")
    for e in errors:
        print(f"  ERROR  {e}")

    if not errors and not warnings:
        print(f"  OK     All {len(bindings)} visual binding(s) passed.")
    elif not errors:
        print(f"  OK     {len(bindings)} binding(s) checked — {len(warnings)} warning(s), 0 errors.")
    else:
        print(f"\n  FAILED {len(errors)} error(s), {len(warnings)} warning(s) in {len(bindings)} binding(s).")

    passed = len(errors) == 0 and (not strict or len(warnings) == 0)
    return passed


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    strict = "--strict" in args
    files  = [a for a in args if not a.startswith("--")]

    if not files:
        print("Error: no input file specified.")
        sys.exit(1)

    all_passed = True
    for path in files:
        if not check(path, strict=strict):
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
