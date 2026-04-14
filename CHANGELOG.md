# Changelog

All notable changes to the SVJ specification.

## [0.94] — 2026-04-13

### Added
- **Multi-axle naming convention** (§21.1.1): formalized `A{n}{side}` corner naming
- FL/FR/RL/RR documented as aliases for A1L/A1R/A2L/A2R
- `axles[]` metadata array with `steered`, `driven`, `lift` flags, `position_x`
- Multi-axle steering linkage (§21.1.3) with per-axle ratio and phase
- Tyrrell P34 6-wheel example in spec
- Backward compatibility rules for multi-axle parsers

## [0.93] — 2026-04-11

### Added
- `alignment_convention` field: `relative_to_centerline` (negative camber = inward on both sides)
- Motion ratio vs hardpoint precedence rule (§9.3)
- Alignment vs hardpoint precedence rule (§9.6)
- Transaxle efficiency double-counting warning (§10.8)
- CG validation rule: X must be between 0 and −wheelbase

### Fixed
- **CG coordinates inverted** in ALL files — X was positive, corrected to negative per SAE J670 origin at front axle
- **Wheel/tire redundancy** — tire dimensions removed from corner `wheel`, now rim-only + `set_ref`

## [0.92] — 2026-04-13

### Added
- **Engine thermal model** (§10.3.1): heat capacity, warmup time, friction vs oil temperature, power derating vs coolant temperature
- **Gearbox thermal model** (§10.5.1): oil capacity, efficiency vs temperature
- **Differential thermal model**: same schema as gearbox
- **Brake thermal dynamics** (§9.9.4): disc→pad→caliper→ambient conductance network, speed-dependent air cooling
- **Environment conditions** (§15.2): ambient temperature, pressure, humidity, altitude, wind speed
- **Formalized heat sources** (§15.3.4): thermal resistance connecting components to cooling circuits
- `alignment_convention` field in _metadata: `relative_to_centerline` (negative camber = inward on both sides)
- Motion ratio vs hardpoint precedence rule (§9.3)
- Alignment vs hardpoint precedence rule (§9.6)
- Transaxle efficiency double-counting warning (§10.8)
- CG validation rule: X must be between 0 and -wheelbase (§7)

### Fixed
- **CG coordinates inverted** in ALL files — X was positive, should be negative per SAE J670 origin at front axle center
- **Wheel/tire redundancy** removed — tire dimensions eliminated from corner `wheel` object, now rim-only + `set_ref` to tire library

### Changed
- **Engine thermal model** (§10.3.1): heat capacity, warmup time, friction vs oil temperature, power derating vs coolant temperature
- **Gearbox thermal model** (§10.5.1): oil capacity, efficiency vs temperature
- **Differential thermal model**: same schema as gearbox
- **Brake thermal dynamics** (§9.9.4): disc→pad→caliper→ambient conductance network, speed-dependent air cooling, heat generation formula, fade model
- **Environment conditions** (§15.2): ambient temperature, pressure, humidity, altitude, wind speed
- **Formalized heat sources** (§15.3.4): thermal resistance and heat generation rates connecting components to cooling circuits

## [0.91] — 2026-04-09 — v1.0 Release Candidate

### Added
- Skeleton examples: FF hatchback (MacPherson + torsion beam), AWD BEV (dual motor), 4WD truck (solid axle + Panhard)
- Schema error-path validation (24 errors detected on deliberately broken file)

### Fixed
- Cross-reference audit: 0 broken §-references across 124 sections
- README rewritten for v0.9 content
- Roadmap section title updated

## [0.9.0] — 2026-04-09

### Added
- **TMeasy tire model** (§11.10): ~20 intuitive parameters (stiffness, peak force, sliding plateau, load/camber sensitivity, pneumatic trail)
- **Brush tire model** (§11.11): physics-first, ~10 parameters from contact patch geometry and tread stiffness
- **External model references** (§11.12): FTire (.fti), CDTire (.cdt), MF-Swift (.tir), PAC2002, RMOD-K file pointers with source lab, test conditions, version tracking
- Model fidelity guide (§11.12.1) comparing 6 tiers from brush to CDTire 50

## [0.8.3] — 2026-04-09

### Added
- CG `position` field on `upright`, `clutch`, `booster`, `master_cylinder`
- Global inertia reference convention: all tensors about component's own CG in vehicle frame axes
- Mass accounting clarification (no double counting between mass_bodies and component masses)

## [0.8.2] — 2026-04-09

### Added
- `Ixy` and `Iyz` cross-products to all inertia objects (full 6-component symmetric tensor)
- Matrix notation documented in §7.1

## [0.8.1] — 2026-04-09

### Added
- `upright.inertia` tensor, `link.mass`/`inertia`/`cg_position`/`mass_distribution`
- `spring.mass`, `damper.mass`, `arb.mass`, `disc.rotational_inertia`
- `steering.rack_mass`, `clutch.mass`
- Restored inertia tensors to all 14 mass_bodies in template

## [0.8.0] — 2026-04-08

### Added
- **3-tier compliance model** (§9.2.5): Tier 1 rigid, Tier 2 corner-level scalars, Tier 3 full 6-DOF bushing per joint
- **Chassis stiffness** (§7.3): torsional and bending stiffness
- **Static setup** (§9.12): ride height, corner weights, spring compression
- **Driver controls** (§16): throttle map, brake feel, traction control, launch control

## [0.7.0] — 2026-04-08

### Added
- **Electric/Hybrid** (§14): motors (P0-P4/in-wheel), battery (chemistry, capacity, thermal), inverters, regenerative braking
- **Cooling** (§15): thermal circuits with radiator, pump, thermostat
- Multi-axle/truck extension planned in roadmap (§21.1)

## [0.6.0] — 2026-04-07

### Changed
- **Drivetrain rewrite** (§10): `layout`, `clutch`, `gearbox` (replaces transmission), `transfer_case`, `driveshafts[]` with joint positions, `differentials[]` with `final_drive` moved here, `half_shafts` per corner with CV joints. `cv_joint_outer` hardpoint added to uprights.

## [0.5.3] — 2026-04-07

### Added
- Comprehensive suspension topology guide (§9.2.1): per-type documentation for all 10 system_types
- New types: `chapman_strut`, `torsion_beam`
- `axle_body` (§9.2.4) for shared rigid bodies, `lateral_location` for dependent types

## [0.5.2] — 2026-04-07

### Changed
- Brakes rewritten: `pedal`, `booster`, `master_cylinder` (bore_primary/secondary), `circuit_type`, ABS `ebd`/`brake_assist`, ESC `track_mode`. Complete force chain (§12.6).

## [0.5.1] — 2026-04-07

### Changed
- Template migrated to **Mazda MX-5 ND2 2024 Club 6MT** with factory data sourcing
- Steering: `max_steer_angle`, `lock_to_lock_turns`, `turning_circle`, `steering_wheel`

## [0.5.0] — 2026-04-06

### Added
- **Aerodynamics** (§13): coefficients, 7 sensitivity maps, component-based model, active systems (DRS, active ride height, active wing)

## [0.4.1] — 2026-04-06

### Added
- Tire set: `dimensions`, `rim` specs, `construction` (mass, stiffness, ratings, UTQG)

## [0.4.0] — 2026-04-06

### Added
- **Tires** (§11): Pacejka MF 5.2/6.2, thermal model, wear model, relaxation. Per-corner tire reference.
- **Brakes**: per-corner disc/caliper/pad. Top-level system (master cylinder, bias, ABS, ESC).

## [0.3.2] — 2026-04-06

### Added
- `mass_bodies` (§7.2): sprung mass decomposition into rigid bodies with 7 categories

## [0.3.1] — 2026-04-05

### Added
- Steering system (§8), wheel geometry per corner (§9.8), JSON Schema

## [0.3.0] — 2026-04-05

### Added
- Hybrid file structure (`$ref`), four-corner suspension, springs, dampers, ARB, alignment, bump stops, differential

## [0.2.0]

### Added
- Entity-based upright/link model, AC conversion, `x_` extensions

## [0.1.0]

### Added
- Initial draft: metadata, chassis, basic suspension topology, powertrain
