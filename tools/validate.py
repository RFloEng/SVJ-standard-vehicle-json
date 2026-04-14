#!/usr/bin/env python3
"""
SVJ Validator — validates .svj.json files against the SVJ schema
and performs cross-field consistency checks.

Usage:
    python validate.py <file.svj.json> [--schema path/to/schema.json]
"""

import argparse
import json
import math
import sys
from pathlib import Path

def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def schema_validate(data: dict, schema: dict) -> list[str]:
    """JSON Schema validation. Returns list of error strings."""
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        return ["jsonschema not installed — run: pip install jsonschema"]
    
    validator = Draft7Validator(schema)
    errors = []
    for e in validator.iter_errors(data):
        path = ".".join(str(p) for p in e.absolute_path)
        errors.append(f"  {path}: {e.message}")
    return errors

def consistency_checks(data: dict) -> list[str]:
    """Cross-field consistency checks beyond schema validation."""
    warnings = []
    
    chassis = data.get("chassis", {})
    
    # Mass consistency
    bodies = chassis.get("mass_bodies", [])
    unsprung = chassis.get("mass_unsprung_per_corner", {})
    if bodies and unsprung:
        body_sum = sum(b["mass"] for b in bodies if isinstance(b, dict) and "mass" in b)
        unsprung_sum = sum(v for k, v in unsprung.items() if isinstance(v, (int, float)))
        total_computed = body_sum + unsprung_sum
        total_stated = chassis.get("mass_total", 0)
        if total_stated and abs(total_computed - total_stated) > 1.0:
            warnings.append(f"  mass_bodies({body_sum:.1f}) + unsprung({unsprung_sum:.1f}) = {total_computed:.1f} ≠ mass_total({total_stated:.1f})")
    
    # ARB consistency (same bar_id should have same bar_rate)
    susp = data.get("suspension", {})
    arb_map = {}
    for corner in ["FL", "FR", "RL", "RR"]:
        arb = susp.get(corner, {}).get("arb", {})
        if "bar_id" in arb and "bar_rate" in arb:
            bid = arb["bar_id"]
            rate = arb["bar_rate"]
            if bid in arb_map and arb_map[bid] != rate:
                warnings.append(f"  ARB '{bid}': rate mismatch {arb_map[bid]} vs {rate}")
            arb_map[bid] = rate
    
    # Tire set_ref validation
    tire_sets = set(data.get("tires", {}).get("sets", {}).keys())
    if tire_sets:
        for corner in ["FL", "FR", "RL", "RR"]:
            tire = susp.get(corner, {}).get("tire", {})
            ref = tire.get("set_ref", "")
            if ref and ref not in tire_sets:
                warnings.append(f"  {corner}.tire.set_ref='{ref}' not found in tires.sets")
    
    # Steering derived fields
    steering = data.get("steering", {})
    if "lock_to_lock" in steering and "overall_ratio" in steering:
        l2l = steering["lock_to_lock"]
        ratio = steering["overall_ratio"]
        expected_max = (l2l / 2) / ratio
        actual_max = steering.get("max_steer_angle")
        if actual_max and abs(actual_max - expected_max) > 0.01:
            warnings.append(f"  max_steer_angle={actual_max:.4f} ≠ derived {expected_max:.4f}")
    
    return warnings

def main():
    parser = argparse.ArgumentParser(description="Validate SVJ vehicle files")
    parser.add_argument("file", help="Path to .svj.json file")
    parser.add_argument("--schema", default=None, help="Path to svj.schema.json (auto-detected if omitted)")
    args = parser.parse_args()
    
    # Load file
    try:
        data = load_json(args.file)
    except Exception as e:
        print(f"❌ Cannot load {args.file}: {e}")
        sys.exit(1)
    
    version = data.get("_metadata", {}).get("version", "unknown")
    print(f"SVJ file: {args.file}")
    print(f"Version:  {version}")
    
    # Find schema
    schema_path = args.schema
    if not schema_path:
        candidates = [
            Path(args.file).parent / "svj.schema.json",
            Path(__file__).parent.parent / "schema" / "svj.schema.json",
            Path("schema/svj.schema.json"),
        ]
        for c in candidates:
            if c.exists():
                schema_path = str(c)
                break
    
    if schema_path:
        schema = load_json(schema_path)
        errors = schema_validate(data, schema)
        if errors:
            print(f"\n❌ Schema validation: {len(errors)} errors")
            for e in errors:
                print(e)
        else:
            print(f"\n✅ Schema validation: PASS")
    else:
        print(f"\n⚠️  Schema not found — skipping schema validation")
    
    # Consistency checks
    warnings = consistency_checks(data)
    if warnings:
        print(f"\n⚠️  Consistency checks: {len(warnings)} warnings")
        for w in warnings:
            print(w)
    else:
        print(f"✅ Consistency checks: PASS")
    
    # Summary
    susp = data.get("suspension", {})
    corners = [c for c in ["FL", "FR", "RL", "RR"] if c in susp]
    types = set(susp.get(c, {}).get("topology", {}).get("system_type", "?") for c in corners)
    mass = data.get("chassis", {}).get("mass_total", "?")
    n_bodies = len(data.get("chassis", {}).get("mass_bodies", []))
    n_tiresets = len(data.get("tires", {}).get("sets", {}))
    
    print(f"\n📊 Summary:")
    print(f"   Vehicle:    {data.get('vehicle_info', {}).get('make', '?')} {data.get('vehicle_info', {}).get('model', '?')} {data.get('vehicle_info', {}).get('year', '?')}")
    print(f"   Mass:       {mass} kg")
    print(f"   Bodies:     {n_bodies}")
    print(f"   Suspension: {', '.join(types)}")
    print(f"   Tire sets:  {n_tiresets}")
    print(f"   Sections:   {', '.join(k for k in data if not k.startswith('_'))}")

if __name__ == "__main__":
    main()
