"""
Vehicle — the core SVJ data model.

Wraps the parsed JSON dict and provides typed accessors for every section.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

# Legacy two-axle corner identifiers (aliases of A1L/A1R/A2L/A2R since SVJ v0.99)
CORNERS = ("FL", "FR", "RL", "RR")
FRONT_CORNERS = ("FL", "FR")
REAR_CORNERS = ("RL", "RR")
LEGACY_ALIASES = {"FL": "A1L", "FR": "A1R", "RL": "A2L", "RR": "A2R"}
STATION_RE = re.compile(r"^(FL|FR|RL|RR|A([1-9][0-9]?)(L|R|C))$")
_SIDE_ORDER = {"L": 0, "C": 1, "R": 2}


def is_station(key: str) -> bool:
    """True if key is a valid wheel-station name (FL/FR/RL/RR or A{n}{L|R|C})."""
    return bool(STATION_RE.match(key))


def canonical_station(key: str) -> str:
    """Map a station name to A-notation: FL -> A1L, A3R -> A3R."""
    return LEGACY_ALIASES.get(key, key)


def station_axle(key: str) -> int:
    """1-based axle index of a station name (FL -> 1, RR -> 2, A3L -> 3)."""
    m = re.match(r"^A(\d+)", canonical_station(key))
    if not m:
        raise ValueError(f"Invalid wheel station: {key}")
    return int(m.group(1))


def _station_sort_key(key: str) -> tuple[int, int]:
    c = canonical_station(key)
    return int(c[1:-1]), _SIDE_ORDER[c[-1]]


class Vehicle:
    """An SVJ vehicle loaded into memory.

    Attributes:
        data: The raw parsed dict — full read/write access.
        source_path: The file this was loaded from (None if parsed from string).
    """

    def __init__(self, data: dict[str, Any], source_path: Path | None = None):
        self.data = data
        self.source_path = source_path

    # ── Metadata ──────────────────────────────────────────────────────

    @property
    def metadata(self) -> dict[str, Any]:
        return self.data.get("_metadata", {})

    @property
    def version(self) -> str:
        return self.metadata.get("version", "")

    @property
    def spec(self) -> str:
        return self.metadata.get("specification", "")

    # ── Vehicle info ──────────────────────────────────────────────────

    @property
    def vehicle_info(self) -> dict[str, Any]:
        return self.data.get("vehicle_info", {})

    @property
    def make(self) -> str:
        return self.vehicle_info.get("make", "")

    @property
    def model(self) -> str:
        return self.vehicle_info.get("model", "")

    @property
    def year(self) -> int | None:
        return self.vehicle_info.get("year")

    @property
    def drive_type(self) -> str:
        return self.vehicle_info.get("drive_type", "")

    @property
    def vehicle_class(self) -> str:
        return self.vehicle_info.get("vehicle_class", "")

    @property
    def name(self) -> str:
        """Human-readable vehicle name."""
        parts = [self.make, self.model]
        if self.year:
            parts.append(str(self.year))
        return " ".join(p for p in parts if p)

    # ── Chassis ───────────────────────────────────────────────────────

    @property
    def chassis(self) -> dict[str, Any]:
        return self.data.get("chassis", {})

    @property
    def mass_total(self) -> float:
        return self.chassis.get("mass_total", 0.0)

    @property
    def wheelbase(self) -> float:
        return self.chassis.get("wheelbase", 0.0)

    @property
    def track_front(self) -> float:
        return self.chassis.get("track_front", 0.0)

    @property
    def track_rear(self) -> float:
        return self.chassis.get("track_rear", 0.0)

    @property
    def cg(self) -> list[float]:
        """Center of gravity [x, y, z] in SAE J670 coordinates."""
        return self.chassis.get("center_of_gravity", [0.0, 0.0, 0.0])

    @property
    def mass_bodies(self) -> list[dict[str, Any]]:
        return self.chassis.get("mass_bodies", [])

    @property
    def mass_unsprung(self) -> dict[str, float]:
        return self.chassis.get("mass_unsprung_per_corner", {})

    @property
    def inertia(self) -> dict[str, float]:
        return self.chassis.get("inertia", {})

    # ── Suspension ────────────────────────────────────────────────────

    @property
    def suspension(self) -> dict[str, Any]:
        return self.data.get("suspension", {})

    @property
    def stations(self) -> list[str]:
        """Wheel-station names present in the file, front to back, left to right.

        Legacy files return FL/FR/RL/RR; multi-axle files return A1L, A1R, A2L, ...
        """
        return sorted((k for k in self.suspension if is_station(k)), key=_station_sort_key)

    def corner(self, corner_id: str) -> dict[str, Any]:
        """Get full suspension data for a wheel station.

        Accepts legacy names (FL, FR, RL, RR) or A-notation (A1L, A3R, A2C).
        Aliases resolve both ways: corner("A1L") finds a legacy "FL" entry and
        corner("FL") finds an "A1L" entry.
        """
        if not is_station(corner_id):
            raise ValueError(f"Invalid wheel station: {corner_id}. Use FL/FR/RL/RR or A{{n}}{{L|R|C}}")
        if corner_id in self.suspension:
            return self.suspension[corner_id]
        target = canonical_station(corner_id)
        for key in self.suspension:
            if is_station(key) and canonical_station(key) == target:
                return self.suspension[key]
        return {}

    def corners(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Iterate over all wheel stations as (id, data) pairs, front to back."""
        for c in self.stations:
            yield c, self.suspension[c]

    def topology(self, corner_id: str) -> str:
        """Get the suspension system_type for a wheel station."""
        return self.corner(corner_id).get("topology", {}).get("system_type", "")

    def topologies(self) -> dict[str, str]:
        """Get all suspension types as {station: system_type}."""
        return {c: self.topology(c) for c in self.stations}

    # ── Multi-axle (SVJ v0.99) ────────────────────────────────────────

    @property
    def axles(self) -> list[dict[str, Any]]:
        """The `axles` metadata array (may be empty)."""
        return self.data.get("axles", [])

    @property
    def axle_count(self) -> int:
        """Number of axles, from the wheel stations (falls back to `axles`)."""
        if self.stations:
            return len({station_axle(k) for k in self.stations})
        return len(self.axles)

    @property
    def is_multi_axle(self) -> bool:
        return self.axle_count > 2

    def axle(self, axle_id: str | int) -> dict[str, Any]:
        """Get `axles` metadata by id ("A2") or index (2)."""
        aid = axle_id if isinstance(axle_id, str) else f"A{axle_id}"
        return next((a for a in self.axles if a.get("id") == aid), {})

    def stations_on_axle(self, axle: int) -> list[str]:
        return [k for k in self.stations if station_axle(k) == axle]

    @property
    def suspension_couplings(self) -> list[dict[str, Any]]:
        return self.data.get("suspension_couplings", [])

    def wheel_count(self, corner_id: str) -> int:
        """Wheels mounted at a station (2 for duals)."""
        return int(self.corner(corner_id).get("wheel", {}).get("multiplicity", 1))

    @property
    def tyre_count(self) -> int:
        """Total tyres on the vehicle, counting dual wheels."""
        return sum(self.wheel_count(k) for k in self.stations)

    @property
    def wheel_formula(self) -> str:
        """vehicle_info.wheel_formula, or derived '<stations>x<driven>' from axles."""
        wf = self.vehicle_info.get("wheel_formula")
        if wf:
            return wf
        if not self.axles or not self.stations:
            return ""
        driven = sum(len(self.stations_on_axle(int(a["id"][1:]))) for a in self.axles if a.get("driven"))
        return f"{len(self.stations)}x{driven}"

    def hardpoints(self, corner_id: str) -> dict[str, list[float]]:
        """Get all hardpoints for a suspension corner.

        Returns dict of {point_name: [x, y, z]} from topology.upright
        and topology.links.
        """
        topo = self.corner(corner_id).get("topology", {})
        points = {}

        # Upright hardpoints
        upright = topo.get("upright", {})
        for key, val in upright.items():
            if isinstance(val, list) and len(val) == 3:
                points[f"upright.{key}"] = val

        # Link hardpoints
        for link in topo.get("links", []):
            link_name = link.get("name", "unknown")
            for endpoint in ("chassis_point", "upright_point"):
                if endpoint in link and isinstance(link[endpoint], list):
                    points[f"{link_name}.{endpoint}"] = link[endpoint]

        return points

    def spring(self, corner_id: str) -> dict[str, Any]:
        return self.corner(corner_id).get("spring", {})

    def damper(self, corner_id: str) -> dict[str, Any]:
        return self.corner(corner_id).get("damper", {})

    def arb(self, corner_id: str) -> dict[str, Any]:
        return self.corner(corner_id).get("arb", {})

    def alignment(self, corner_id: str) -> dict[str, Any]:
        return self.corner(corner_id).get("alignment", {})

    # ── Steering ──────────────────────────────────────────────────────

    @property
    def steering(self) -> dict[str, Any]:
        return self.data.get("steering", {})

    @property
    def steering_ratio(self) -> float:
        return self.steering.get("overall_ratio", 0.0)

    # ── Tires ─────────────────────────────────────────────────────────

    @property
    def tires(self) -> dict[str, Any]:
        return self.data.get("tires", {})

    @property
    def tire_sets(self) -> dict[str, Any]:
        return self.tires.get("sets", {})

    def tire_set(self, name: str) -> dict[str, Any]:
        return self.tire_sets.get(name, {})

    # ── Brakes ────────────────────────────────────────────────────────

    @property
    def brakes(self) -> dict[str, Any]:
        return self.data.get("brakes", {})

    # ── Powertrain ────────────────────────────────────────────────────

    @property
    def powertrain(self) -> dict[str, Any]:
        return self.data.get("powertrain", {})

    @property
    def engine(self) -> dict[str, Any]:
        return self.powertrain.get("engine", {})

    @property
    def gearbox(self) -> dict[str, Any]:
        return self.powertrain.get("gearbox", {})

    @property
    def gear_ratios(self) -> list[float]:
        return self.gearbox.get("ratios", [])

    @property
    def differentials(self) -> list[dict[str, Any]]:
        return self.powertrain.get("differentials", [])

    # ── Aerodynamics ──────────────────────────────────────────────────

    @property
    def aerodynamics(self) -> dict[str, Any]:
        return self.data.get("aerodynamics", {})

    # ── Electric / Hybrid ─────────────────────────────────────────────

    @property
    def electric(self) -> dict[str, Any]:
        return self.data.get("electric", {})

    # ── Cooling ───────────────────────────────────────────────────────

    @property
    def cooling(self) -> dict[str, Any]:
        return self.data.get("cooling", {})

    # ── Driver controls ───────────────────────────────────────────────

    @property
    def driver_controls(self) -> dict[str, Any]:
        return self.data.get("driver_controls", {})

    # ── Sections ──────────────────────────────────────────────────────

    @property
    def sections(self) -> list[str]:
        """List all top-level sections present (excluding _metadata and x_ extensions)."""
        return [k for k in self.data if not k.startswith("_") and not k.startswith("x_")]

    @property
    def extensions(self) -> dict[str, Any]:
        """All x_ extension keys and their data."""
        return {k: v for k, v in self.data.items() if k.startswith("x_")}

    # ── Query helpers ─────────────────────────────────────────────────

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Access nested data using dot notation.

        Example:
            vehicle.get("chassis.mass_total")
            vehicle.get("suspension.FL.topology.system_type")
            vehicle.get("powertrain.gearbox.ratios")
        """
        keys = dotpath.split(".")
        current = self.data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
        return current

    def has(self, dotpath: str) -> bool:
        """Check if a nested path exists."""
        return self.get(dotpath) is not None

    # ── Computed properties ───────────────────────────────────────────

    @property
    def weight_distribution_front(self) -> float | None:
        """Front weight distribution (0-1) estimated from CG position."""
        cg_x = self.cg[0] if self.cg else None
        wb = self.wheelbase
        if cg_x is not None and wb > 0:
            # CG.x is negative (behind front axle) in SAE J670.
            # Multi-axle: share on A1 vs. the rest, using wheelbase A1 -> last axle.
            return 1.0 + (cg_x / wb)
        return None

    @property
    def sprung_mass(self) -> float:
        """Total sprung mass (sum of mass_bodies)."""
        return sum(b.get("mass", 0) for b in self.mass_bodies if isinstance(b, dict))

    @property
    def unsprung_mass_total(self) -> float:
        """Total unsprung mass (sum of all corners)."""
        return sum(v for v in self.mass_unsprung.values() if isinstance(v, (int, float)))

    # ── Export ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return the raw data dict (for serialization)."""
        return self.data

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=indent, ensure_ascii=False)

    def save(self, path: str | Path, indent: int = 2) -> None:
        """Write the vehicle to a .svj.json file."""
        path = Path(path)
        with open(path, "w") as f:
            json.dump(self.data, f, indent=indent, ensure_ascii=False)
            f.write("\n")

    # ── Dunder ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        name = self.name or "Unknown"
        return f"<Vehicle: {name} (SVJ v{self.version})>"

    def __str__(self) -> str:
        return self.name or "Unknown Vehicle"

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __getitem__(self, key: str) -> Any:
        return self.data[key]
