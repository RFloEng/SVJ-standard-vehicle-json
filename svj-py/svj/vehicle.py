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
    def is_unified(self) -> bool:
        """True for the unified suspension model (wheel_stations + constraints), False for the deprecated corner section."""
        return not self.suspension and bool(self.data.get("wheel_stations"))

    @property
    def wheel_stations(self) -> list[dict[str, Any]]:
        """The `wheel_stations` array of the unified model (may be empty)."""
        return self.data.get("wheel_stations", [])

    @property
    def stations(self) -> list[str]:
        """Wheel-station names present in the file, front to back, left to right.

        Legacy files return FL/FR/RL/RR; multi-axle files return A1L, A1R, A2L, ...
        """
        if self.is_unified:
            return sorted((s["id"] for s in self.wheel_stations if isinstance(s.get("id"), str) and is_station(s["id"])), key=_station_sort_key)
        return sorted((k for k in self.suspension if is_station(k)), key=_station_sort_key)

    def _station_view(self, sid: str) -> dict[str, Any]:
        """A corner-shaped view of a unified wheel station: topology hint, wheel, spring, damper, arb, alignment, ...

        Springs and dampers come from the station's elements (`spring_<station>`, `damper_<station>`); their `rate` and
        curves are element values unless `reference` is "wheel".
        """
        st = next((s for s in self.wheel_stations if s.get("id") == sid), None)
        if st is None:
            return {}
        view = {k: v for k, v in st.items() if k not in ("id", "name", "wheel_body", "upright_body", "topology_hint", "axle", "side")}
        view["topology"] = {"system_type": st.get("topology_hint", "")}
        sfx = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in sid.lower()).strip("_")
        for c in self.data.get("constraints", []) or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "spring" and c.get("id") == f"spring_{sfx}":
                view["spring"] = {k: v for k, v in c.items() if k not in ("id", "type", "body_a", "body_b", "frame_a", "frame_b", "x_derived")}
                view["spring"]["type"] = c.get("spring_type", "")
            if c.get("type") == "damper" and c.get("id") == f"damper_{sfx}":
                view["damper"] = {k: v for k, v in c.items() if k not in ("id", "type", "body_a", "body_b", "frame_a", "frame_b", "x_derived")}
        for bar in self.data.get("anti_roll_bars", []) or []:
            if sid in (bar.get("stations") or []):
                view["arb"] = {"bar_id": bar.get("id"), **{k: v for k, v in bar.items() if k not in ("id", "stations", "drop_link_mounts")}}
                if sid in (bar.get("drop_link_mounts") or {}):
                    view["arb"]["drop_link_mount"] = bar["drop_link_mounts"][sid]
        view.setdefault("spring", {})
        view.setdefault("damper", {})
        return view

    def corner(self, corner_id: str) -> dict[str, Any]:
        """Get full suspension data for a wheel station.

        Accepts legacy names (FL, FR, RL, RR) or A-notation (A1L, A3R, A2C).
        Aliases resolve both ways: corner("A1L") finds a legacy "FL" entry and
        corner("FL") finds an "A1L" entry.
        """
        if not is_station(corner_id):
            raise ValueError(f"Invalid wheel station: {corner_id}. Use FL/FR/RL/RR or A{{n}}{{L|R|C}}")
        if self.is_unified:
            target = canonical_station(corner_id)
            for s in self.wheel_stations:
                if isinstance(s.get("id"), str) and canonical_station(s["id"]) == target:
                    return self._station_view(s["id"])
            return {}
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
            yield c, (self._station_view(c) if self.is_unified else self.suspension[c])

    def topology(self, corner_id: str) -> str:
        """Get the suspension system_type for a wheel station."""
        return self.corner(corner_id).get("topology", {}).get("system_type", "")

    def joints(self) -> list[dict[str, Any]]:
        """Every suspension link with its effective joint types.

        Explicit `joint_type` / `inboard_joint_type` win; missing ones are inferred
        from `system_type` and the link type (see `svj.multibody.infer_joint_types`).
        Each item carries `outboard_source` / `inboard_source` = 'explicit',
        'inferred' or None (not inferable).
        """
        if self.is_unified:
            return [{"id": c.get("id"), "joint_type": c.get("joint_type"), "body_a": c.get("body_a"), "body_b": c.get("body_b"),
                     "derived": bool(c.get("x_derived"))}
                    for c in self.data.get("constraints", []) or [] if isinstance(c, dict) and c.get("type") == "joint"]
        from svj.multibody import effective_joints
        return effective_joints(self.data)

    # ── Movable parts (spec §24) ──────────────────────────────────────

    @property
    def constraints(self) -> list[dict[str, Any]]:
        """The `constraints` array: joints, springs and actuators between mass bodies."""
        return self.data.get("constraints", [])

    @property
    def poses(self) -> list[dict[str, Any]]:
        """The `poses` array: named joint-coordinate configurations."""
        return self.data.get("poses", [])

    def body_transforms(self, pose: Any = None) -> dict[str, tuple]:
        """Rigid transform `(R, t)` of every body from the reference pose to `pose` (a pose id or {joint_id: value})."""
        from svj.constraints import body_transforms
        return body_transforms(self.data, pose)

    def element_lengths(self, pose: Any = None) -> dict[str, float]:
        """Length (m) of every spring and actuator in `pose`."""
        from svj.constraints import element_lengths
        return element_lengths(self.data, pose)

    @property
    def interfaces(self) -> list[dict[str, Any]]:
        """The `interfaces` array: named frames where this unit can be joined to another (spec §27)."""
        return self.data.get("interfaces", [])

    @property
    def attachments(self) -> list[dict[str, Any]]:
        """The `attachments` array: units fitted to this vehicle (spec §27.4)."""
        return self.data.get("attachments", [])

    def clashes(self, pose=None, tolerance: float = 0.0) -> list[dict]:
        """Collision proxies of relatively movable bodies closer than `tolerance` (m) in `pose` (spec §28)."""
        from svj.collision import clashes
        return clashes(self.data, pose, tolerance)

    def assemble(self, base_dir: str | Path | None = None) -> "Vehicle":
        """The composite vehicle with every `attachments[]` unit fitted (qualified ids `unit.body`, spec §27).
        Unit files are resolved against `base_dir`, default the folder this file was loaded from."""
        from svj.assemble import assemble, check_combination, combination_from_vehicle
        base = Path(base_dir) if base_dir is not None else (self.source_path.parent if self.source_path else Path("."))
        comb = combination_from_vehicle(self.data, str(base))
        errors, _ = check_combination(comb)
        if errors:
            raise ValueError("invalid attachments: " + "; ".join(errors[:5]))
        doc, _notes = assemble(comb)
        return Vehicle(doc)

    def solve_pose(self, travel: dict | None = None, joint_values: dict | None = None) -> dict[str, Any]:
        """Solve the closed kinematic loops (spec §26): wheel centres raised by `travel` {station: m} with the
        joints in `joint_values` held. Returns transforms, residual, converged and wheel_centres."""
        from svj.loopsolver import solve
        return solve(self.data, travel, joint_values)

    def wheel_sweep(self, station: str, travels: list[float], steer: float | None = None) -> list[dict[str, Any]]:
        """Camber, toe, wheel-centre path and element lengths of a station at each wheel travel (m, bump positive)."""
        from svj.loopsolver import sweep
        return sweep(self.data, station, travels, steer=steer)

    def suspension_gains(self, station: str, delta: float = 0.01) -> dict[str, float] | None:
        """Camber gain and bump steer (deg per m of wheel travel) of a station around the reference pose."""
        from svj.loopsolver import gains
        return gains(self.data, station, delta)

    def pose_cg(self, pose: Any = None) -> dict[str, Any]:
        """Composite CG in `pose`: {'cg', 'delta', 'mass'} (spec §24.5)."""
        from svj.constraints import pose_cg
        return pose_cg(self.data, pose)

    def pose_inertia(self, pose: Any = None, form: str = "object") -> Any:
        """Composite inertia about the composite CG in `pose`: the spec §7.1 object, or a 3x3 matrix with
        `form="matrix"`; None without `chassis.inertia`."""
        from svj.constraints import pose_inertia
        return pose_inertia(self.data, pose, form)

    def body_inertia(self, body_id: str) -> list[list[float]] | None:
        """A mass body's inertia as a 3x3 matrix in the vehicle axes (accepts the object or matrix form and
        `inertia_orientation`), or None."""
        from svj.constraints import body_inertia
        body = next((b for b in self.chassis.get("mass_bodies", []) if b.get("id") == body_id), None)
        m = body_inertia(body) if body else None
        return [list(r) for r in m] if m else None

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
        if self.is_unified:
            st = next((s for s in self.wheel_stations if canonical_station(s.get("id", "")) == canonical_station(corner_id)), {})
            body = next((b for b in self.chassis.get("mass_bodies", []) if b.get("id") == st.get("upright_body")), {})
            return {f"upright.{k}": list(m["position"]) for k, m in (body.get("markers") or {}).items() if isinstance(m, dict) and "position" in m}
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
    def axle_groups(self) -> list[dict[str, Any]]:
        """The `axle_groups` array (v0.99.1), e.g. twin-steer front axles, rear bogie."""
        return self.data.get("axle_groups", [])

    @property
    def plated_masses(self) -> dict[str, Any]:
        return self.chassis.get("plated_masses", {})

    def _front_rear_groups(self) -> tuple[list[str], list[str]] | None:
        """Front and rear axle groups as used by spec §23.6 (needs axles[].position_x)."""
        pos = {a["id"]: a["position_x"] for a in self.axles if isinstance(a.get("position_x"), (int, float))}
        if len(pos) < 2:
            return None
        order = sorted(pos, key=lambda a: int(a[1:]))

        def group_of(aid: str) -> list[str]:
            g = next((g for g in self.axle_groups if aid in g.get("axle_refs", [])), None)
            if g:
                return [a for a in g["axle_refs"] if a in pos]
            xs = [pos[a] for a in order]
            gaps = [xs[i] - xs[i + 1] for i in range(len(xs) - 1)]
            cut = gaps.index(max(gaps)) + 1
            return order[:cut] if aid in order[:cut] else order[cut:]

        return group_of(order[0]), group_of(order[-1])

    @property
    def weight_distribution_front(self) -> float | None:
        """Share (0-1) of the unladen weight on the front axle group.

        Uses, in order: published `axle_groups[].kerb_load`; the CG between the
        front and rear group centres (multi-axle); 1 + CG.x / wheelbase (two axles).
        """
        groups = self.axle_groups
        loads = [g.get("kerb_load") for g in groups]
        fr = self._front_rear_groups()
        if groups and fr and all(isinstance(l, (int, float)) for l in loads):
            front = next((g for g in groups if fr[0][0] in g.get("axle_refs", [])), None)
            if front:
                return front["kerb_load"] / sum(loads)
        cg_x = self.cg[0] if self.cg else None
        if cg_x is None:
            return None
        if fr:
            pos = {a["id"]: a["position_x"] for a in self.axles}
            xf = sum(pos[a] for a in fr[0]) / len(fr[0])
            xr = sum(pos[a] for a in fr[1]) / len(fr[1])
            if xf != xr:
                return (cg_x - xr) / (xf - xr)
        wb = self.wheelbase
        if wb > 0:
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
