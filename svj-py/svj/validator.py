"""
SVJ schema + consistency validation.

Wraps jsonschema Draft-07 validation and adds SVJ-specific cross-field checks.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def validate(
    data: dict[str, Any],
    schema_path: str | Path | None = None,
    schema: dict | None = None,
) -> list[str]:
    """Validate an SVJ document against the schema and consistency rules.

    Args:
        data: Parsed SVJ dict.
        schema_path: Path to svj.schema.json. If None, only consistency checks run.
        schema: Pre-loaded schema dict. Takes precedence over schema_path.

    Returns:
        List of error/warning strings. Empty list = valid.
    """
    errors = []

    # Schema validation
    if schema is None and schema_path is not None:
        schema_path = Path(schema_path)
        if schema_path.exists():
            with open(schema_path) as f:
                schema = json.load(f)

    if schema is not None:
        errors.extend(_schema_validate(data, schema))

    # Consistency checks
    errors.extend(_consistency_checks(data))

    return errors


def find_schema(near_path: Path | None = None) -> Path | None:
    """Try to locate svj.schema.json near a file or in common locations."""
    if near_path is None:
        return None

    candidates = [
        near_path.parent / "svj.schema.json",
        near_path.parent.parent / "schema" / "svj.schema.json",
        near_path.parent / "schema" / "svj.schema.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _schema_validate(data: dict, schema: dict) -> list[str]:
    """JSON Schema Draft-07 validation."""
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        return ["jsonschema not installed — run: pip install jsonschema"]

    validator = Draft7Validator(schema)
    errors = []
    for e in validator.iter_errors(data):
        path = ".".join(str(p) for p in e.absolute_path)
        errors.append(f"schema: {path}: {e.message}" if path else f"schema: {e.message}")
    return errors


def _consistency_checks(data: dict) -> list[str]:
    """Cross-field consistency checks beyond what the schema can express."""
    warnings = []

    chassis = data.get("chassis", {})

    # ── Mass consistency ──
    bodies = chassis.get("mass_bodies", [])
    unsprung = chassis.get("mass_unsprung_per_corner", {})
    if bodies and unsprung:
        body_sum = sum(b["mass"] for b in bodies if isinstance(b, dict) and "mass" in b)
        unsprung_sum = sum(v for k, v in unsprung.items() if isinstance(v, (int, float)))
        total_computed = body_sum + unsprung_sum
        total_stated = chassis.get("mass_total", 0)
        if total_stated and abs(total_computed - total_stated) > 1.0:
            warnings.append(
                f"consistency: mass_bodies({body_sum:.1f}) + unsprung({unsprung_sum:.1f}) "
                f"= {total_computed:.1f} ≠ mass_total({total_stated:.1f})"
            )

    # ── CG position ──
    cg = chassis.get("center_of_gravity", [])
    wheelbase = chassis.get("wheelbase", 0)
    if cg and len(cg) >= 1 and wheelbase > 0:
        cg_x = cg[0]
        if cg_x > 0:
            warnings.append(
                f"consistency: CG.x={cg_x} is positive — should be negative "
                f"(behind front axle) per SAE J670"
            )
        if cg_x < -wheelbase:
            warnings.append(
                f"consistency: CG.x={cg_x} is behind rear axle "
                f"(beyond -wheelbase={-wheelbase})"
            )

    # ── ARB consistency ──
    susp = data.get("suspension", {})
    arb_map: dict[str, float] = {}
    for corner in ("FL", "FR", "RL", "RR"):
        arb = susp.get(corner, {}).get("arb", {})
        if "bar_id" in arb and "bar_rate" in arb:
            bid = arb["bar_id"]
            rate = arb["bar_rate"]
            if bid in arb_map and arb_map[bid] != rate:
                warnings.append(
                    f"consistency: ARB '{bid}' rate mismatch: {arb_map[bid]} vs {rate}"
                )
            arb_map[bid] = rate

    # ── Tire set_ref validation ──
    tire_sets = set(data.get("tires", {}).get("sets", {}).keys())
    if tire_sets:
        for corner in ("FL", "FR", "RL", "RR"):
            tire = susp.get(corner, {}).get("tire", {})
            ref = tire.get("set_ref", "")
            if ref and ref not in tire_sets:
                warnings.append(
                    f"consistency: {corner}.tire.set_ref='{ref}' not in tires.sets"
                )

    # ── Steering derived fields ──
    steering = data.get("steering", {})
    if "lock_to_lock" in steering and "overall_ratio" in steering:
        l2l = steering["lock_to_lock"]
        ratio = steering["overall_ratio"]
        if ratio > 0:
            expected_max = (l2l / 2) / ratio
            actual_max = steering.get("max_steer_angle")
            if actual_max and abs(actual_max - expected_max) > 0.01:
                warnings.append(
                    f"consistency: max_steer_angle={actual_max:.4f} "
                    f"≠ derived {expected_max:.4f}"
                )

    return warnings
