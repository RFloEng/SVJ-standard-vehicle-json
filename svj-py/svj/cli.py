"""
SVJ command-line interface.

Usage:
    svj validate <file.svj.json>
    svj info <file.svj.json>
    svj query <file.svj.json> <dotpath>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="svj",
        description="SVJ — Standard Vehicle JSON toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── validate ──
    p_val = sub.add_parser("validate", help="Validate an SVJ file")
    p_val.add_argument("file", help="Path to .svj.json file")
    p_val.add_argument("--schema", default=None, help="Path to svj.schema.json")

    # ── info ──
    p_info = sub.add_parser("info", help="Print vehicle summary")
    p_info.add_argument("file", help="Path to .svj.json file")

    # ── query ──
    p_query = sub.add_parser("query", help="Query a value by dot path")
    p_query.add_argument("file", help="Path to .svj.json file")
    p_query.add_argument("path", help="Dot-separated path (e.g. chassis.mass_total)")

    args = parser.parse_args(argv)

    if args.command == "validate":
        _cmd_validate(args)
    elif args.command == "info":
        _cmd_info(args)
    elif args.command == "query":
        _cmd_query(args)


def _cmd_validate(args: argparse.Namespace) -> None:
    from svj.loader import load
    from svj.validator import validate, find_schema

    try:
        vehicle = load(args.file, validate_on_load=False)
    except Exception as e:
        print(f"Error loading {args.file}: {e}", file=sys.stderr)
        sys.exit(1)

    schema_path = args.schema or find_schema(Path(args.file))
    errors = validate(vehicle.data, schema_path=schema_path)

    print(f"SVJ file: {args.file}")
    print(f"Version:  {vehicle.version}")
    print(f"Vehicle:  {vehicle.name}")

    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\nAll checks passed.")


def _cmd_info(args: argparse.Namespace) -> None:
    from svj.loader import load

    try:
        vehicle = load(args.file, validate_on_load=False)
    except Exception as e:
        print(f"Error loading {args.file}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Vehicle:      {vehicle.name}")
    print(f"SVJ version:  {vehicle.version}")
    print(f"Drive type:   {vehicle.drive_type or '?'}")
    print(f"Mass:         {vehicle.mass_total} kg")
    print(f"Wheelbase:    {vehicle.wheelbase} m")
    print(f"Track F/R:    {vehicle.track_front} / {vehicle.track_rear} m")

    wd = vehicle.weight_distribution_front
    if wd is not None:
        print(f"Weight dist:  {wd*100:.1f}% front / {(1-wd)*100:.1f}% rear")

    topos = vehicle.topologies()
    if topos:
        print(f"Suspension:")
        for c, t in topos.items():
            print(f"  {c}: {t}")

    if vehicle.gear_ratios:
        print(f"Gear ratios:  {vehicle.gear_ratios}")

    print(f"Sections:     {', '.join(vehicle.sections)}")

    exts = vehicle.extensions
    if exts:
        print(f"Extensions:   {', '.join(exts.keys())}")


def _cmd_query(args: argparse.Namespace) -> None:
    from svj.loader import load

    try:
        vehicle = load(args.file, validate_on_load=False)
    except Exception as e:
        print(f"Error loading {args.file}: {e}", file=sys.stderr)
        sys.exit(1)

    result = vehicle.get(args.path)
    if result is None:
        print(f"Path '{args.path}' not found", file=sys.stderr)
        sys.exit(1)

    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result)


if __name__ == "__main__":
    main()
