"""
Vehicle — the core SVJ data model.

Wraps the parsed JSON dict and provides typed accessors for every section.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

# Corner identifiers
CORNERS = ("FL", "FR", "RL", "RR")
FRONT_CORNERS = ("FL", "FR")
REAR_CORNERS = ("RL", "RR")


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

    def corner(self, corner_id: str) -> dict[str, Any]:
        """Get full suspension data for a corner (FL, FR, RL, RR)."""
        if corner_id not in CORNERS:
            raise ValueError(f"Invalid corner: {corner_id}. Must be one of {CORNERS}")
        return self.suspension.get(corner_id, {})

    def corners(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Iterate over all available corners as (id, data) pairs."""
        for c in CORNERS:
            if c in self.suspension:
                yield c, self.suspension[c]

    def topology(self, corner_id: str) -> str:
        """Get the suspension system_type for a corner."""
        return self.corner(corner_id).get("topology", {}).get("system_type", "")

    def topologies(self) -> dict[str, str]:
        """Get all suspension types as {corner: system_type}."""
        return {c: self.topology(c) for c in CORNERS if c in self.suspension}

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
            # CG.x is negative (behind front axle) in SAE J670
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
