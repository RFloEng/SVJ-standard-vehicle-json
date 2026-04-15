"""
SVJ file loader with $ref resolution.

Handles single-file (inline), multi-file (modular), and mixed modes.
Resolves $ref relative to the manifest file's location.
Rejects circular references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from svj.vehicle import Vehicle
from svj.validator import validate, find_schema


def load(path: str | Path, *, resolve_refs: bool = True, validate_on_load: bool = True) -> Vehicle:
    """Load an SVJ file from disk.

    Args:
        path: Path to the .svj.json file.
        resolve_refs: If True, resolve all $ref entries to inline data.
        validate_on_load: If True, run schema validation after loading.

    Returns:
        A Vehicle instance wrapping the parsed data.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        svj.errors.SVJValidationError: If validation fails (when validate_on_load=True).
        svj.errors.SVJRefError: If a $ref cannot be resolved or is circular.
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    if resolve_refs:
        data = _resolve_refs(data, base_dir=path.parent, seen=set())

    vehicle = Vehicle(data, source_path=path)

    if validate_on_load:
        schema_path = _find_schema_near(path)
        if schema_path:
            errors = validate(data, schema_path=schema_path)
            if errors:
                from svj.errors import SVJValidationError
                raise SVJValidationError(errors)

    return vehicle


def loads(text: str, *, validate_on_load: bool = False) -> Vehicle:
    """Load an SVJ vehicle from a JSON string.

    Note: $ref resolution is not possible without a base directory.

    Args:
        text: JSON string containing an SVJ document.
        validate_on_load: If True, run schema validation.

    Returns:
        A Vehicle instance.
    """
    data = json.loads(text)
    vehicle = Vehicle(data)

    if validate_on_load:
        errors = validate(data)
        if errors:
            from svj.errors import SVJValidationError
            raise SVJValidationError(errors)

    return vehicle


def _resolve_refs(
    obj: Any,
    base_dir: Path,
    seen: set[str],
) -> Any:
    """Recursively resolve $ref entries.

    Per spec §3.2:
    - $ref is resolved relative to the manifest file's location.
    - The $ref object is replaced entirely with the referenced content.
    - At least one level of nesting is supported.
    - Circular references are rejected.
    """
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            ref_path = (base_dir / obj["$ref"]).resolve()
            ref_key = str(ref_path)

            if ref_key in seen:
                from svj.errors import SVJRefError
                raise SVJRefError(f"Circular $ref detected: {ref_key}")

            if not ref_path.exists():
                from svj.errors import SVJRefError
                raise SVJRefError(f"$ref target not found: {ref_path}")

            seen_copy = seen | {ref_key}
            with open(ref_path) as f:
                ref_data = json.load(f)

            return _resolve_refs(ref_data, base_dir=ref_path.parent, seen=seen_copy)

        return {k: _resolve_refs(v, base_dir, seen) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_resolve_refs(item, base_dir, seen) for item in obj]

    return obj


def _find_schema_near(file_path: Path) -> Path | None:
    """Try to locate the SVJ schema relative to the loaded file."""
    candidates = [
        file_path.parent / "svj.schema.json",
        file_path.parent.parent / "schema" / "svj.schema.json",
        file_path.parent / "schema" / "svj.schema.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
