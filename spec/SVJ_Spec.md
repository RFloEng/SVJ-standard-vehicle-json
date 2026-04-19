# Standard Vehicle JSON (SVJ) Specification v0.95

## 1. Overview & Philosophy

SVJ is a **modular, entity-based exchange format** for vehicle dynamics data. Its purpose is to provide a single source of truth that can be consumed by:

- **Game-oriented simulators** (Assetto Corsa, BeamNG.drive, rFactor2)
- **Professional tools** (IPG CarMaker, VI-Grade, Adams Car, MATLAB/Simulink)
- **Custom applications** (telemetry analysis, setup tools, engineering calculators)

### Design Principles

1. **Explicit over implicit** — Every value is stated; no hidden defaults.
2. **Four-corner independence** — Each wheel station is fully defined. Symmetry is the user's choice, not the format's assumption.
3. **Hybrid file structure** — A single `.svj.json` can contain the full vehicle inline *or* reference external modules via `$ref`.
4. **Extensible** — Simulator-specific or proprietary data lives in `x_` prefixed keys and never pollutes the core schema.
5. **Human-readable** — JSON with meaningful key names. No binary blobs, no encoded arrays.
6. **Validatable** — A formal JSON Schema (`svj.schema.json`) exists for every release. Parsers SHOULD validate on load.

---

## 2. Physical Units & Reference Frame

| Quantity             | Unit           | Symbol |
|----------------------|----------------|--------|
| Length               | Meter          | m      |
| Mass                 | Kilogram       | kg     |
| Force                | Newton         | N      |
| Torque               | Newton-meter   | Nm     |
| Angle                | Radians        | rad    |
| Angular velocity     | Radians/second | rad/s  |
| Pressure             | Pascal         | Pa     |
| Time                 | Second         | s      |
| Temperature          | Celsius        | °C     |
| Velocity             | Meters/second  | m/s    |
| Stiffness (linear)   | N/m            |        |
| Stiffness (angular)  | Nm/rad         |        |

### 2.1 Coordinate System — SAE J670

**Origin:** Center of the front axle at ground level.

| Axis | Direction    | Positive Sense       |
|------|-------------|----------------------|
| X    | Longitudinal | Forward              |
| Y    | Lateral      | Right (driver POV)   |
| Z    | Vertical     | Down (toward ground) |

**Origin:** Midpoint of the front axle at ground level, projected onto the vehicle centerline.

> **Note:** All hardpoint coordinates are expressed in the **vehicle reference frame** (global body-fixed). Corner-specific data (FL, FR, RL, RR) uses the appropriate Y sign for each side: negative Y = left, positive Y = right.

---

## 3. File Structure

### 3.1 Single-File (Inline) Mode

The entire vehicle is contained in one `.svj.json` file. All sections are nested objects.

```
my_car.svj.json       ← everything inside
```

### 3.2 Multi-File (Modular) Mode

A root manifest references external module files using the `$ref` key. Each module is a standalone `.svj.json` fragment.

```
my_car/
├── manifest.svj.json          ← root file with $ref pointers
├── chassis.svj.json
├── steering.svj.json
├── suspension_front.svj.json
├── suspension_rear.svj.json
└── powertrain.svj.json
```

**Reference syntax:**
```json
{
  "suspension": {
    "FL": { "$ref": "./suspension_FL.svj.json" },
    "FR": { "$ref": "./suspension_FR.svj.json" },
    "RL": { "$ref": "./suspension_RL.svj.json" },
    "RR": { "$ref": "./suspension_RR.svj.json" }
  }
}
```

A conforming parser MUST:
- Resolve `$ref` relative to the manifest file's location.
- Replace the `$ref` object entirely with the referenced file's contents.
- Support at least one level of nesting (a module MAY contain further `$ref` entries).
- Reject circular references.

### 3.3 Mixed Mode

A single file MAY contain some sections inline and others as `$ref`. This is the expected workflow: start inline, split to modules as the project grows.

---

## 4. Top-Level Structure

```json
{
  "_metadata": { },
  "vehicle_info": { },
  "chassis": { },
  "steering": { },
  "suspension": { },
  "tires": { },
  "brakes": { },
  "powertrain": { },
  "aerodynamics": { },
  "x_<simulator>": { }
}
```

Every top-level key except `_metadata` is OPTIONAL. A file containing only `_metadata` and `suspension` is valid (useful for sharing a suspension setup independently).

---

## 5. `_metadata`

| Key                  | Type    | Required | Description                                 |
|----------------------|---------|----------|---------------------------------------------|
| `specification`      | string  | YES      | Always `"SVJ"`                              |
| `version`            | string  | YES      | Spec version, e.g. `"0.3.1"`               |
| `description`        | string  | no       | Human-readable file description              |
| `coordinate_system`  | string  | YES      | Always `"SAE_J670"`                         |
| `units`              | string  | YES      | Always `"SI"`                               |
| `created`            | string  | no       | ISO 8601 timestamp                          |
| `author`             | string  | no       | Author or tool name                         |
| `source_format`      | string  | no       | Origin format if converted (e.g. `"AC"`, `"BeamNG"`) |

---

## 6. `vehicle_info`

| Key          | Type    | Required | Description                                         |
|--------------|---------|----------|-----------------------------------------------------|
| `make`       | string  | no       | Manufacturer                                        |
| `model`      | string  | no       | Model name                                          |
| `year`       | integer | no       | Model year                                          |
| `variant`    | string  | no       | Trim/variant (e.g. `"GT3 RS"`)                     |
| `drive_type` | string  | no       | One of: `"FWD"`, `"RWD"`, `"AWD"`, `"4WD"`         |

---

## 7. `chassis`

| Key                        | Type       | Required | Description                                            |
|----------------------------|------------|----------|--------------------------------------------------------|
| `mass_total`               | number     | YES      | Total vehicle mass including fluids (kg)                |
| `mass_unsprung_per_corner` | object     | no       | `{"FL": n, "FR": n, "RL": n, "RR": n}` (kg)           |
| `wheelbase`                | number     | YES      | Front axle to rear axle distance (m)                    |
| `track_front`              | number     | YES      | Front track width, center-to-center contact patches (m) |
| `track_rear`               | number     | YES      | Rear track width (m)                                    |
| `center_of_gravity`        | [x, y, z]  | YES      | CG position in vehicle reference frame (m)              |
| `inertia`                  | object     | no       | See §7.1                                                |

### 7.1 `inertia`

Moments of inertia about the CG, in the principal axes.

| Key     | Type   | Unit  | Description                                |
|---------|--------|-------|--------------------------------------------|
| `Ixx`   | number | kg·m² | Roll inertia (about X axis)                |
| `Iyy`   | number | kg·m² | Pitch inertia (about Y axis)               |
| `Izz`   | number | kg·m² | Yaw inertia (about Z axis)                 |
| `Ixz`   | number | kg·m² | Product of inertia X-Z (couples roll/yaw)  |
| `Ixy`   | number | kg·m² | Product of inertia X-Y (0 if left-right symmetric) |
| `Iyz`   | number | kg·m² | Product of inertia Y-Z (0 if left-right symmetric) |

> **Reference point:** All inertia tensors are expressed **about the component's own CG**, in the **vehicle reference frame axes** (SAE J670). To compute the composite vehicle inertia, apply the parallel-axis (Steiner) theorem to translate each body's inertia to the vehicle CG.

> **Rotating components:** Some components (engine crankshaft, gearbox shafts, driveshafts, half-shafts, brake discs) carry a **scalar** rotational inertia about their spin axis, not a full 3D tensor. These values are used in drivetrain dynamics (acceleration, deceleration, shift transients) and are separate from the 3D spatial inertia used for vehicle-level dynamics. The scalar spin inertia does not need parallel-axis translation — it is used directly in the drivetrain torque equations.

> **Full tensor:** The symmetric inertia tensor in the vehicle frame is:
> ```
> | Ixx  -Ixy  -Ixz |
> |-Ixy   Iyy  -Iyz |
> |-Ixz  -Iyz   Izz |
> ```
> For a left-right symmetric vehicle, `Ixy ≈ 0` and `Iyz ≈ 0`. These may be omitted (default 0). For individual `mass_bodies` placed off the centerline, or for components whose principal axes are not aligned with the vehicle frame, `Ixy` and `Iyz` SHOULD be provided for accurate parallel-axis theorem summation.

> **Migration from v0.2:** `"roll"` → `"Ixx"`, `"pitch"` → `"Iyy"`, `"yaw"` → `"Izz"`.

### 7.2 `mass_bodies` — Sprung Mass Decomposition

The optional `mass_bodies` array breaks down the vehicle's sprung mass into individually positioned rigid bodies. This enables accurate composite inertia computation via the parallel-axis theorem and supports workflows where subsystems (engine, gearbox, fuel load, driver, ballast) are placed independently.

| Key           | Type    | Required | Description                                          |
|---------------|---------|----------|------------------------------------------------------|
| `id`          | string  | YES      | Unique identifier (e.g. `"engine"`, `"body_shell"`)  |
| `description` | string  | no       | Human-readable label                                 |
| `category`    | string  | no       | See §7.2.1 for recommended values                    |
| `mass`        | number  | YES      | Body mass (kg)                                       |
| `position`    | [x,y,z] | YES     | CG of this body in the vehicle reference frame (m)    |
| `inertia`     | object  | no       | Inertia tensor about this body's own CG (§7.1 format)|

#### 7.2.1 Recommended `category` Values

| Value          | Description                                                    |
|----------------|----------------------------------------------------------------|
| `"structural"` | BIW, monocoque, subframes, roll cage                           |
| `"powertrain"` | Engine, transmission, exhaust, driveshafts                     |
| `"fluid"`      | Fuel, coolant, oil (mass varies during operation)              |
| `"payload"`    | Driver, passenger, luggage                                     |
| `"ballast"`    | Added weight for balance tuning                                |
| `"electrical"` | Battery pack, motors, inverters (EV/hybrid)                    |
| `"other"`      | Anything that does not fit the above                           |

#### 7.2.2 Relationship to Composite Fields

When `mass_bodies` is present:

1. **`mass_total`** remains REQUIRED and represents the fully resolved vehicle mass. It MUST include both sprung and unsprung contributions. A conforming validator MAY check:
   ```
   mass_total ≈ Σ mass_bodies[i].mass + Σ mass_unsprung_per_corner[j]
   ```

2. **`center_of_gravity`** remains REQUIRED and represents the composite CG of the entire vehicle. A validator MAY check consistency with the mass-weighted centroid of all bodies and unsprung masses.

3. **`inertia`** remains OPTIONAL at the top level. When present alongside `mass_bodies`, it represents the pre-computed composite inertia (parallel-axis contributions already summed). A parser MAY recompute it from the bodies and compare.

> **Design rationale:** Keeping the composite fields required means that simple parsers that only need total mass and CG can ignore `mass_bodies` entirely. Advanced tools can use the decomposition for detailed dynamics or to reposition components.

> **Note on unsprung mass:** The bodies in `mass_bodies` represent the **sprung** portion. Unsprung masses are already captured per-corner in `mass_unsprung_per_corner` and include wheel assemblies, upright, and lower link mass. Do not double-count.

### 7.3 `chassis_stiffness` — Structural Flexibility

The vehicle body/frame is not infinitely rigid. Chassis torsional stiffness directly affects load transfer distribution, handling balance, and suspension effectiveness.

| Key                    | Type   | Required | Description                                              |
|------------------------|--------|----------|----------------------------------------------------------|
| `torsional_stiffness`  | number | no       | Torsional stiffness about the longitudinal axis (Nm/deg) |
| `bending_stiffness`    | number | no       | Bending stiffness about the lateral axis (N/mm at center) |
| `measurement_method`   | string | no       | `"calculated"`, `"measured"`, `"fem"`, `"estimated"`     |

> **Typical values:** Open-top roadster (MX-5, S2000): 4,000–10,000 Nm/deg. Modern coupe: 25,000–40,000 Nm/deg. Race car with cage: 15,000–30,000 Nm/deg. Full monocoque (F1, LMP): 40,000+ Nm/deg.

> **Why it matters:** A chassis with low torsional stiffness effectively has a "third spring" between front and rear axles. This changes the effective roll stiffness distribution, making anti-roll bar tuning less predictable. Most simple sims assume infinite stiffness; advanced tools (Adams Flex, rFactor2) model chassis flex explicitly.

---

## 8. `steering`

The steering system defines how driver input translates to wheel angle. Tie rod endpoints are already defined per-corner in `suspension.*.topology.upright.hardpoints.steering_tie_rod_end`; this section defines the rack and column that drives them.

### 8.1 Top-Level Properties

| Key                  | Type    | Required | Description                                                        |
|----------------------|---------|----------|--------------------------------------------------------------------|
| `type`               | string  | YES      | `"rack_and_pinion"`, `"recirculating_ball"`, `"worm_and_sector"`   |
| `rack_position`      | [x,y,z] | YES     | Center of the steering rack in vehicle reference frame (m)         |
| `rack_travel`        | number  | YES      | Total rack travel, end-to-end (m)                                  |
| `overall_ratio`      | number  | YES      | Steering wheel angle (rad) per wheel steer angle (rad) at center   |
| `lock_to_lock`       | number  | YES      | Total steering wheel rotation, stop to stop (rad)                  |
| `ackermann`          | number  | no       | Ackermann percentage: 0.0 = parallel, 1.0 = 100% Ackermann       |
| `rack_mass`          | number  | no       | Steering rack assembly mass (kg)                                   |
| `max_steer_angle`    | number  | no       | Maximum road wheel steer angle (rad). Derived: `(lock_to_lock/2) / overall_ratio` |
| `lock_to_lock_turns` | number  | no       | Total steering wheel rotation in turns (convenience field, = `lock_to_lock / (2π)`) |
| `turning_circle`     | number  | no       | Minimum turning circle diameter, curb-to-curb (m)                  |
| `steering_wheel`     | object  | no       | Physical steering wheel properties (§8.5)                          |
| `power_assist`       | object  | no       | See §8.2                                                           |
| `column`             | object  | no       | See §8.3                                                           |
| `tie_rod_inboard`    | object  | no       | See §8.4                                                           |

### 8.2 `power_assist`

| Key              | Type   | Required | Description                                              |
|------------------|--------|----------|----------------------------------------------------------|
| `type`           | string | YES      | `"none"`, `"hydraulic"`, `"electric"`, `"electro_hydraulic"` |
| `assist_curve`   | array  | no       | `[[vehicle_speed_m_s, assist_factor], ...]`               |
| `max_assist_torque` | number | no    | Maximum assist torque at the column (Nm)                  |

> **Convention:** `assist_factor` is a multiplier on driver torque. 1.0 = no assist, 3.0 = rack force is 3× the driver input. Speed-sensitive assist is modeled via the curve; at higher speeds, assist typically decreases.

### 8.3 `column`

| Key              | Type   | Required | Description                                    |
|------------------|--------|----------|------------------------------------------------|
| `inertia`        | number | no       | Rotational inertia of steering column (kg·m²)  |
| `damping`        | number | no       | Rotational damping (Nm·s/rad)                  |
| `friction`       | number | no       | Coulomb friction torque (Nm)                   |

### 8.4 `tie_rod_inboard`

Per-side inboard pickup points of the tie rods on the rack. These close the kinematic loop between the rack and the upright hardpoints.

| Key   | Type    | Required | Description                                     |
|-------|---------|----------|-------------------------------------------------|
| `left`  | [x,y,z] | YES   | Left tie rod → rack attachment point (m)        |
| `right` | [x,y,z] | YES   | Right tie rod → rack attachment point (m)       |

> **Note:** These points move laterally with rack displacement. At zero rack displacement (straight ahead), they are at the coordinates specified here.

### 8.5 `steering_wheel`

Physical properties of the steering wheel itself.

| Key        | Type   | Required | Description                                  |
|------------|--------|----------|----------------------------------------------|
| `diameter` | number | no       | Steering wheel rim diameter (m)              |
| `mass`     | number | no       | Steering wheel mass (kg)                     |

> **Derived fields:** `max_steer_angle` can be computed as `(lock_to_lock / 2) / overall_ratio`. `lock_to_lock_turns` = `lock_to_lock / (2 × π)`. These convenience fields avoid repeated calculations in parsers.

---

## 9. `suspension`

The suspension object contains exactly four corner entries:

```json
{
  "suspension": {
    "FL": { },
    "FR": { },
    "RL": { },
    "RR": { }
  }
}
```

Each corner is a **complete, independent definition**. There is no inheritance or mirroring between corners.

### 9.1 Corner Object

| Key           | Type   | Required | Description                |
|---------------|--------|----------|----------------------------|
| `topology`    | object | YES      | Kinematic structure        |
| `wheel`       | object | YES      | Wheel/rim geometry (§9.8)  |
| `spring`      | object | YES      | Spring parameters          |
| `damper`      | object | YES      | Damper parameters          |
| `arb`         | object | no       | Anti-roll bar connection    |
| `alignment`   | object | no       | Static alignment settings   |
| `brake`       | object | no       | Brake disc/caliper/pad (§9.9)  |
| `tire`        | object | no       | Tire assignment & overrides (§9.10) |
| `bump_stop`   | object | no       | Bump stop definition        |
| `rebound_stop`| object | no       | Rebound/droop stop          |
| `compliance_summary` | object | no | Simplified compliance (§9.11) — Tier 2 |
| `static_setup`| object | no       | Installed ride state (§9.12)             |

---

### 9.2 `topology`

| Key            | Type   | Required | Description                                                   |
|----------------|--------|----------|---------------------------------------------------------------|
| `system_type`  | string | YES      | See §9.2.1 for allowed values and topology guide              |
| `upright`      | object | YES      | Rigid sub-body at the wheel (§9.2.2)                          |
| `links`        | array  | YES      | Constraint elements connecting chassis to upright (§9.2.3)    |
| `axle_body`    | object | no       | Shared rigid body for dependent/semi-independent types (§9.2.4) |
| `lateral_location` | string | no   | Lateral constraint method for dependent types (§9.2.1)        |

#### 9.2.1 `system_type` Values & Topology Guide

Each `system_type` defines the kinematic arrangement of the suspension. The table below lists all supported types. The detailed topology guide below specifies the **minimum required** links, hardpoints, and special considerations for each.

| Value                 | Category         | Description                                           |
|-----------------------|------------------|-------------------------------------------------------|
| `"double_wishbone"`   | Independent      | Upper + lower A-arms (or wishbones)                   |
| `"macpherson"`        | Independent      | Strut + lower control arm                             |
| `"chapman_strut"`     | Independent      | MacPherson variant for driven rear axle               |
| `"multi_link"`        | Independent      | 3–5 independent links                                 |
| `"trailing_arm"`      | Independent      | Single arm pivoting about a lateral axis               |
| `"semi_trailing_arm"` | Independent      | Arm with angled pivot axis                             |
| `"torsion_beam"`      | Semi-independent | Twist beam connecting trailing arms (axle_body required) |
| `"solid_axle"`        | Dependent        | Live axle housing with integral differential (axle_body required) |
| `"de_dion"`           | Dependent        | Dead tube connecting wheels, diff on chassis (axle_body required) |
| `"custom"`            | —                | Non-standard; describe in `x_` extension               |

---

##### `double_wishbone` — Double Wishbone / SLA

Upper and lower A-arms (or wishbones) with ball joints at the upright. The most tuneable independent design; used on sports cars, race cars, and premium vehicles.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `upper_wishbone` | `arm` | 2 points (front + rear pivots) | `hardpoints.upper_ball_joint` | A-arm: 2 chassis pivots → 1 ball joint |
| `lower_wishbone` | `arm` | 2 points (front + rear pivots) | `hardpoints.lower_ball_joint` | A-arm: 2 chassis pivots → 1 ball joint |
| `steering_tie_rod` | `rod` | 1 point (rack end) | `hardpoints.steering_tie_rod_end` | Front axle only |

**Minimum hardpoints:** `upper_ball_joint`, `lower_ball_joint`, `wheel_center`, `damper_outboard`. Add `steering_tie_rod_end` on steered axles.

**Examples:** Mazda MX-5 (front), Ferrari, Aston Martin, Formula 1, LMP.

---

##### `macpherson` — MacPherson Strut

A telescopic strut (spring + damper integrated) replaces the upper arm. The strut body acts as both the damper and the upper locating element, with a lower control arm providing the second constraint.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `strut` | `strut` | 1 point (strut top mount / turret) | `hardpoints.strut_top` | The strut top is on the body/turret |
| `lower_control_arm` | `arm` | 2 points (front + rear pivots) | `hardpoints.lower_ball_joint` | Single A-arm or L-arm |
| `steering_tie_rod` | `rod` | 1 point (rack end) | `hardpoints.steering_tie_rod_end` | Front axle only |

**Minimum hardpoints:** `strut_top`, `lower_ball_joint`, `wheel_center`. Add `steering_tie_rod_end` on steered axles.

**Note:** Spring and damper `inboard_mount` / `outboard_mount` are typically the same as the strut link mounts. The `strut` link type signals to parsers that this link is telescopic (piston in cylinder), not a rigid body.

**Examples:** Most FWD front suspensions, VW Golf, Ford Focus (front), Toyota Corolla.

---

##### `chapman_strut` — Chapman Strut

Functionally identical to MacPherson but used on **driven rear axles**. The driveshaft passes through or alongside the strut. Topology is the same as `macpherson` minus the steering tie rod.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `strut` | `strut` | 1 point (strut top mount) | `hardpoints.strut_top` | |
| `lower_control_arm` | `arm` | 2 points | `hardpoints.lower_ball_joint` | |
| `toe_link` | `rod` | 1 point | `hardpoints.toe_link_end` | Optional, for rear toe control |

**Minimum hardpoints:** `strut_top`, `lower_ball_joint`, `wheel_center`.

**Examples:** Lotus Elan, Lotus Elise (some variants), Corvette C1–C3 rear.

---

##### `multi_link` — Multi-Link

Three to five independent links (rods or arms) locate the upright. The most general independent design; allows fine-tuning of camber, toe, and anti-dive/squat independently.

**Minimum links (3-link):**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `upper_control_arm` | `arm` | 2 points | `hardpoints.upper_ball_joint` | |
| `lower_control_arm` | `arm` | 2 points | `hardpoints.lower_ball_joint` | |
| `toe_link` | `rod` | 1 point | `hardpoints.toe_link_end` | Controls rear toe |

**Extended links (5-link):** Add `upper_lateral_link` and `lower_lateral_link` as `rod` type for full 5-link with separate lateral and longitudinal control.

**Minimum hardpoints:** `upper_ball_joint`, `lower_ball_joint`, `wheel_center`. Add `toe_link_end`, `upper_lateral_end`, `lower_lateral_end` as needed per link count.

**Examples:** Mazda MX-5 (rear, 5-link), BMW 3-series (rear), Mercedes W205 (rear), Audi A4 (rear).

---

##### `trailing_arm` — Trailing Arm

A single arm pivots about an axis that is **perpendicular to the vehicle centerline** (pure lateral axis). The wheel moves in an arc in the longitudinal plane. Zero camber change through travel; zero toe change. Simple but limited.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `trailing_arm` | `arm` | 2 points (left + right pivot bushings, same Y) | `hardpoints.wheel_center` | Pivot axis is pure lateral (both inboard points share the same X coordinate) |

**Minimum hardpoints:** `wheel_center`, `damper_outboard`.

**Lateral location:** The trailing arm provides longitudinal and vertical constraint only. Lateral location comes from the arm width or an additional link. For fully independent trailing arms, each side is a separate corner.

**Examples:** Citroën 2CV (front), VW Beetle (front — with torsion bar spring), some motorcycle rear ends.

---

##### `semi_trailing_arm` — Semi-Trailing Arm

Like a trailing arm but the pivot axis is **angled** relative to the vehicle centerline (neither pure lateral nor pure longitudinal). This causes coupled camber and toe changes through wheel travel.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `semi_trailing_arm` | `arm` | 2 points (front-inner + rear-inner, at different X and Y) | `hardpoints.wheel_center` | Pivot axis angle defines camber/toe coupling |

**Minimum hardpoints:** `wheel_center`, `damper_outboard`.

**Pivot axis angle:** Defined by the line between the two `inboard_points`. The angle to the Y-axis (when viewed from above) determines the ratio of camber-to-toe change. Typical values: 10°–25° from the lateral axis.

**Examples:** BMW E30/E36 (rear), Mercedes W123/W124 (rear), many 1970s–1990s RWD cars.

---

##### `torsion_beam` — Torsion Beam / Twist Beam (Semi-Independent)

Two trailing arms connected by a transverse torsion beam that resists relative twist between the two sides. The beam acts as a roll spring. This is a **semi-independent** system: both corners share an `axle_body` and must be defined as a left/right pair.

**`axle_body` REQUIRED:** The torsion beam itself is modeled as a rigid body with torsional compliance.

**Minimum links per side:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `trailing_arm` | `arm` | 2 points (front bushing, same side) | `hardpoints.wheel_center` | The trailing arm from bushing to wheel |

**`axle_body` properties:**

| Key | Type | Description |
|-----|------|-------------|
| `id` | string | Shared identifier (same for both corners) |
| `mass` | number | Total beam assembly mass (kg) |
| `torsional_stiffness` | number | Beam torsional stiffness (Nm/rad) — acts as roll spring |
| `beam_position` | [x,y,z] | Center of the beam cross-section (m) |
| `beam_type` | string | `"open_section"`, `"closed_section"`, `"tubular"` |

**Minimum hardpoints:** `wheel_center`, `damper_outboard`.

**Note:** Both corners sharing the same `axle_body.id` are mechanically coupled. A parser MUST model the torsional spring between them. The beam's torsional stiffness replaces or supplements a conventional ARB.

**`lateral_location`:** Not needed — trailing arms provide all constraints.

**Examples:** VW Golf (rear), Peugeot 308 (rear), Renault Mégane (rear), Honda Civic FK2 Type R (rear).

---

##### `solid_axle` — Live Axle / Solid Axle (Dependent)

A rigid axle housing containing the differential and half-shafts. Both wheels are rigidly connected — zero camber change, zero toe change. The axle must be located longitudinally and laterally by separate links.

**`axle_body` REQUIRED:** The axle housing is modeled as a rigid body shared between both corners.

**Minimum links per side:**

Depends on the lateral and longitudinal location method. Common arrangements:

**4-link (most common modern):**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `upper_link` | `rod` | 1 point (chassis) | `hardpoints.upper_link_end` | Upper trailing link |
| `lower_link` | `rod` | 1 point (chassis) | `hardpoints.lower_link_end` | Lower trailing link |

Plus one **lateral location** device per axle (shared, not per-corner):

| `lateral_location` value | Description | Additional link |
|--------------------------|-------------|----------------|
| `"panhard_rod"` | Diagonal rod, one end on axle, one on chassis | 1 `rod` link on one corner only |
| `"watts_link"` | Two rods + central pivot | 2 `rod` links + pivot point |
| `"track_bar"` | Same as Panhard rod (alternative name) | 1 `rod` link |

**3-link + Panhard:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `lower_trailing_link` | `rod` | 1 point | `hardpoints.lower_link_end` | Per side |
| `upper_a_arm` | `arm` | 2 points | `hardpoints.upper_link_end` | Single upper A-arm (provides lateral + longitudinal) |
| `panhard_rod` | `rod` | 1 point | `hardpoints.panhard_axle_end` | One side only |

**Hotchkiss drive (leaf-spring located):**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `leaf_spring` | `arm` | 2 points (front eye + rear shackle) | `hardpoints.spring_pad` | Leaf spring provides longitudinal + lateral location |

**`axle_body` properties:**

| Key | Type | Description |
|-----|------|-------------|
| `id` | string | Shared identifier (same for both corners) |
| `mass` | number | Axle housing + diff + half-shafts mass (kg) |
| `position` | [x,y,z] | Axle CG position (m) |
| `inertia` | object | Ixx/Iyy/Izz/Ixz about axle CG |

**Minimum hardpoints:** `wheel_center`, `damper_outboard`, plus link endpoints per arrangement above.

**`lateral_location`:** SHOULD be specified. One of: `"panhard_rod"`, `"watts_link"`, `"track_bar"`, `"leaf_located"`, `"a_arm"`.

**Examples:** Ford Mustang GT (rear, 3-link + Panhard pre-2015), Toyota Tacoma (rear, leaf), Jeep Wrangler (rear, 4-link), Land Rover Defender (front + rear).

---

##### `de_dion` — De Dion Tube (Dependent)

A rigid **dead tube** connects the two wheel hubs, keeping them parallel. The differential is **chassis-mounted** (sprung mass), and driveshafts with CV joints connect to the wheels. The tube locates the wheels laterally and maintains zero camber change, but the diff is not part of the unsprung mass.

**`axle_body` REQUIRED:** The De Dion tube is a rigid body shared between both corners.

**Minimum links per side:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `trailing_link` | `rod` | 1 point (chassis) | `hardpoints.trailing_link_end` | Longitudinal location |

Plus lateral location (same options as `solid_axle`): `panhard_rod`, `watts_link`, or `a_arm`.

**`axle_body` properties:** Same as `solid_axle` but `mass` is lower (no diff, no ring/pinion — just tube + hubs).

**Minimum hardpoints:** `wheel_center`, `damper_outboard`, `trailing_link_end`.

**Examples:** Alfa Romeo 75 (rear), Smart ForTwo (rear), Aston Martin DB4/DB5 (rear).

---

##### `custom`

For suspension systems that do not fit any standard type. All kinematics must be fully described via `links` and `hardpoints`. Use `x_` extensions to provide additional metadata about the custom design.

---

#### 9.2.2 `upright`

The upright (hub carrier / knuckle) is treated as a rigid body. All outboard attachment points are defined here.

| Key           | Type   | Required | Description                                    |
|---------------|--------|----------|------------------------------------------------|
| `id`          | string | YES      | Unique identifier (e.g. `"upright_FL"`)        |
| `mass`        | number | no       | Mass of upright assembly (kg)                  |
| `cg_position` | [x,y,z]| no      | CG of the upright assembly in vehicle frame (m)|
| `inertia`     | object | no       | Inertia tensor about the upright CG, in vehicle frame axes — same format as §7.1 |
| `hardpoints`  | object | YES      | Named points on the upright (§9.2.2.1)         |

##### 9.2.2.1 Standard Hardpoint Names

These names are RECOMMENDED for interoperability. Additional custom hardpoints MAY be added.

| Key                      | Description                                      |
|--------------------------|--------------------------------------------------|
| `upper_ball_joint`       | Upper arm → upright connection                   |
| `lower_ball_joint`       | Lower arm → upright connection                   |
| `steering_tie_rod_end`   | Steering link → upright connection               |
| `wheel_center`           | Geometric center of the wheel                    |
| `strut_top`              | MacPherson strut upper mount (on upright side)   |
| `damper_outboard`        | Damper → upright attachment (if direct)          |
| `arb_drop_link_outboard` | ARB drop link → upright/arm attachment           |
| `cv_joint_outer`         | Outboard CV joint center — must match `half_shafts.*.cv_outer.position` (driven corners only) |

Hardpoint values are `[x, y, z]` arrays in the **vehicle reference frame**.

#### 9.2.3 `links`

Each link is a rigid rod or arm connecting the chassis (inboard) to the upright (outboard).

| Key             | Type    | Required | Description                                            |
|-----------------|---------|----------|--------------------------------------------------------|
| `name`             | string  | YES      | Descriptive name (e.g. `"upper_wishbone"`, `"toe_link"`)|
| `type`             | string  | no       | `"arm"` (default), `"rod"`, `"strut"`                  |
| `inboard_points`   | array   | YES      | Array of `[x, y, z]` chassis-side pickup points        |
| `outboard_ref`     | string  | YES      | Dot-path to an upright hardpoint (see §9.2.3.1)       |
| `mass`             | number  | no       | Link total mass (kg)                                   |
| `inertia`          | number  | no       | Rotational inertia about the link's pivot axis (kg·m²). For an A-arm, this is the axis defined by the two `inboard_points`. |
| `cg_position`      | [x,y,z] | no      | Link CG in vehicle reference frame (m). If absent, parsers MAY estimate as the midpoint between mean(inboard_points) and the outboard hardpoint. |
| `mass_distribution` | object | no      | `{"sprung_fraction": 0.5}` — fraction of mass that is sprung. Default 0.5 if absent. |
| `bushings`         | array   | no       | Bushing at each inboard point — Tier 3 compliance (§9.2.5) |
| `outboard_bushing` | object  | no      | Bushing at the outboard joint (§9.2.5) — if not a rigid ball joint |

##### 9.2.3.1 `outboard_ref` Path Resolution

The path is resolved **within the same corner**, starting from `topology.upright`. Example:

```
"outboard_ref": "hardpoints.upper_ball_joint"
```

This resolves to: `suspension.<corner>.topology.upright.hardpoints.upper_ball_joint`

> **Migration from v0.2:** Old-style refs like `"upright_front.hardpoints.X"` are DEPRECATED. Use `"hardpoints.X"` instead.

#### 9.2.4 `axle_body` — Shared Rigid Body

Required for `torsion_beam`, `solid_axle`, and `de_dion` suspension types. Represents the rigid element that couples or connects both sides of the axle.

| Key                    | Type    | Required | Description                                              |
|------------------------|---------|----------|----------------------------------------------------------|
| `id`                   | string  | YES      | Shared identifier (same on both corners of the axle)     |
| `mass`                 | number  | no       | Total mass of the shared body (kg)                       |
| `position`             | [x,y,z] | no      | CG position of the shared body (m)                       |
| `inertia`              | object  | no       | Inertia tensor about CG (Ixx/Iyy/Izz/Ixz)              |
| `torsional_stiffness`  | number  | no       | Beam torsional stiffness (Nm/rad) — `torsion_beam` only  |
| `beam_type`            | string  | no       | `"open_section"`, `"closed_section"`, `"tubular"` — `torsion_beam` only |
| `beam_position`        | [x,y,z] | no      | Center of cross-beam (m) — `torsion_beam` only           |

> **Coupling rule:** Both corners sharing the same `axle_body.id` are mechanically coupled. A kinematic solver MUST constrain the two uprights accordingly: rigidly for `solid_axle`/`de_dion`, torsionally for `torsion_beam`. The `axle_body.mass` contributes to unsprung mass and should be included (split 50/50) in `mass_unsprung_per_corner`.

#### 9.2.5 `bushing` — Joint Compliance (Tier 3)

A bushing describes the elastic and damping properties of a rubber or hydro mount at a suspension joint. Each bushing has 6 degrees of freedom: 3 translational (radial X, radial Y, axial Z in the bushing's local frame) and 3 rotational (conical, torsional, cardanic).

**Three-tier compliance model:**
1. **Tier 1 — Rigid:** No compliance data. All joints are rigid. (Simple sims, AC basic)
2. **Tier 2 — Summary:** `compliance_summary` at corner level with scalar toe/camber stiffness. (AC extended, simple models)
3. **Tier 3 — Full:** `bushings` array on each link with per-joint 6-DOF stiffness. (Adams Car, rFactor2, CarMaker)

A parser SHOULD use the highest-fidelity data available. If Tier 3 is present, it takes precedence over Tier 2. If neither is present, assume rigid joints.

| Key               | Type   | Required | Description                                          |
|-------------------|--------|----------|------------------------------------------------------|
| `rate_x`          | number | no       | Radial stiffness, longitudinal axis (N/m)            |
| `rate_y`          | number | no       | Radial stiffness, lateral axis (N/m)                 |
| `rate_z`          | number | no       | Axial stiffness (N/m)                                |
| `rate_rx`         | number | no       | Conical stiffness about X (Nm/rad)                   |
| `rate_ry`         | number | no       | Conical stiffness about Y (Nm/rad)                   |
| `rate_rz`         | number | no       | Torsional stiffness about Z (Nm/rad)                 |
| `damping_x`       | number | no       | Radial damping, longitudinal (N·s/m)                 |
| `damping_y`       | number | no       | Radial damping, lateral (N·s/m)                      |
| `damping_z`       | number | no       | Axial damping (N·s/m)                                |
| `rate_x_curve`    | array  | no       | Non-linear: `[[displacement_m, force_N], ...]`       |
| `rate_y_curve`    | array  | no       | Non-linear: `[[displacement_m, force_N], ...]`       |
| `rate_z_curve`    | array  | no       | Non-linear: `[[displacement_m, force_N], ...]`       |
| `preload`         | [x,y,z]| no      | Preload force vector in bushing local frame (N)      |

> **Bushing orientation:** The bushing local frame is defined by the link's geometry. For a rod-type link, Z is along the rod axis, X and Y are radial. For an arm-type link, Z is along the pivot axis. If orientation matters for non-symmetric bushings, use the `x_` extension to specify a rotation matrix.

> **Typical values:** Rear trailing arm longitudinal: 10,000–30,000 N/m (soft for ride). Lateral control arm: 80,000–200,000 N/m (stiff for geometry). Subframe mount: 500–2,000 N/m (very soft for NVH isolation).

> **Array alignment:** `bushings[i]` corresponds to `inboard_points[i]`. If a link has 2 inboard points (A-arm), the `bushings` array has 2 entries, one per pivot.

---

### 9.11 `compliance_summary` — Tier 2 Corner Compliance

Simplified compliance model at the corner level. These scalar values capture the net effect of all bushings on toe and camber change under load, without requiring per-bushing detail.

| Key                 | Type   | Required | Description                                              |
|---------------------|--------|----------|----------------------------------------------------------|
| `toe_stiffness`     | number | no       | Lateral force → toe angle stiffness (N/rad)              |
| `camber_stiffness`  | number | no       | Lateral force → camber angle stiffness (N/rad)           |
| `caster_stiffness`  | number | no       | Longitudinal force → caster change stiffness (N/rad)     |
| `longitudinal_stiffness` | number | no  | Longitudinal force → fore-aft deflection (N/m)           |
| `lateral_stiffness` | number | no       | Lateral force → lateral deflection (N/m)                 |

> **Usage:** A sim that doesn't model per-bushing compliance (like Assetto Corsa) can read `toe_stiffness` and `camber_stiffness` directly. If both Tier 2 and Tier 3 data exist, Tier 3 is authoritative; a validator MAY check that the summary is consistent with the bushing data.

### 9.12 `static_setup` — Installed Ride State

The actual as-installed state at rest on a flat surface, including corner weights and ride heights.

| Key               | Type   | Required | Description                                         |
|-------------------|--------|----------|-----------------------------------------------------|
| `ride_height`     | number | no       | Distance from ground to chassis reference point (m) |
| `corner_weight`   | number | no       | Static vertical load at this corner (N)             |
| `spring_compression` | number | no    | Static compression of the spring at rest (m)        |
| `damper_position` | number | no       | Damper shaft position from full extension (m)       |

> **Ride height measurement:** Measured from the ground plane to a defined chassis reference point (typically the rocker panel or subframe rail). The measurement point should be documented in `x_` extensions if not obvious.

> **Corner weights:** The four corner weights SHOULD sum to `mass_total × g`. Cross-weight percentage = (FL + RR) / (mass_total × g) × 100%. A value of 50% indicates perfect diagonal balance.

---

### 9.3 `spring`

> **Motion ratio precedence:** If `inboard_mount` and `outboard_mount` are provided, a kinematic solver SHOULD compute the motion ratio from geometry. The scalar `motion_ratio` field then serves as a fallback (for point-mass sims) or validation check. If the computed and declared ratios disagree by more than 5%, the parser SHOULD warn. If only the scalar is provided, use it directly.

| Key              | Type    | Required | Description                                              |
|------------------|---------|----------|----------------------------------------------------------|
| `type`           | string  | YES      | `"coil"`, `"torsion_bar"`, `"leaf"`, `"air"`, `"coilover"` |
| `rate`           | number  | YES      | Wheel-rate stiffness (N/m) OR see `rate_curve`           |
| `mass`           | number  | no       | Spring mass (kg). Convention: ~50% sprung, ~50% unsprung |
| `rate_curve`     | array   | no       | Non-linear: `[[displacement_m, force_N], ...]`           |
| `free_length`    | number  | no       | Uncompressed spring length (m)                           |
| `preload`        | number  | no       | Installed preload force (N)                              |
| `motion_ratio`   | number  | no       | Spring displacement / wheel displacement (dimensionless) |
| `inboard_mount`  | [x,y,z] | no      | Chassis-side spring mount point                          |
| `outboard_mount` | [x,y,z] | no      | Suspension-side spring mount point                       |

> **Convention:** If `rate` is provided, it represents the **wheel rate** (force at the wheel per unit of wheel travel). If the spring rate at the coil is known instead, provide `motion_ratio` and the parser computes wheel rate as: `wheel_rate = coil_rate × motion_ratio²`.

> **Non-linear springs:** When `rate_curve` is present, it takes precedence over `rate`. The curve is an ordered array of `[displacement, force]` pairs. Displacement is measured from free length (compression positive in SAE Z-down).

---

### 9.4 `damper`

| Key                | Type    | Required | Description                                           |
|--------------------|---------|----------|-------------------------------------------------------|
| `type`             | string  | no       | `"monotube"`, `"twin_tube"`, `"adjustable"`, `"mrd"` (magneto-rheological) |
| `bump_curve`       | array   | YES      | `[[velocity_m_s, force_N], ...]` (compression)        |
| `rebound_curve`    | array   | YES      | `[[velocity_m_s, force_N], ...]` (extension)          |
| `motion_ratio`     | number  | no       | Damper velocity / wheel velocity (dimensionless)      |
| `mass`             | number  | no       | Damper mass (kg). Body ≈ sprung, rod+piston ≈ unsprung |
| `inboard_mount`    | [x,y,z] | no      | Chassis-side damper mount point                       |
| `outboard_mount`   | [x,y,z] | no      | Suspension-side damper mount point                    |

> **Convention:** Velocities are always positive in both curves. Force is positive (resisting motion). Bump = compression (wheel moving up in SAE Z-down = Z decreasing). Rebound = extension (wheel moving down = Z increasing).

> **Minimum data:** At least two points per curve. The first point SHOULD be `[0.0, 0.0]`. Interpolation between points is linear. Extrapolation beyond the last point is linear from the last two points.

---

### 9.5 `arb` (Anti-Roll Bar)

The ARB is defined **per corner** as that corner's connection to the bar. The bar itself is shared across an axle; both corners of the same axle reference the same logical bar.

| Key                | Type    | Required | Description                                        |
|--------------------|---------|----------|----------------------------------------------------|
| `bar_id`           | string  | YES      | Shared identifier (e.g. `"arb_front"`)             |
| `bar_rate`         | number  | YES      | Torsional stiffness of the bar (Nm/rad)            |
| `wheel_rate_equiv` | number  | no       | Equivalent wheel rate contribution (N/m)           |
| `motion_ratio`     | number  | no       | ARB arm displacement / wheel displacement          |
| `drop_link_mount`  | [x,y,z] | no      | Drop link attachment point on arm/upright side     |
| `mass`             | number  | no       | Full bar mass for this axle (kg) — same value on both corners |

> Two corners sharing the same `bar_id` are mechanically coupled. A parser MAY verify consistency: if FL.arb.bar_id == FR.arb.bar_id, both must share the same `bar_rate`.

---

### 9.6 `alignment`

> **Sign convention:** When `alignment_convention` is `"relative_to_centerline"` (default), alignment values use **vehicle-relative** signs, not absolute rotations:
> - **Camber:** Negative = top of wheel leans **inward** (toward vehicle centerline) on **both** left and right sides.
> - **Toe:** Positive = front of wheel points **inward** (toe-in) on **both** left and right sides.
>
> This means the same numeric values can be used for FL and FR on a symmetric setup. A parser using absolute SAE rotations must flip the sign for the right-side wheels.
>
> When `alignment_convention` is `"absolute"`, values are pure SAE J670 rotations about the vehicle-frame axes. In this case, FL and FR camber will have opposite signs for a symmetric setup.

Static alignment values at design ride height.

| Key             | Type   | Unit | Description                                                |
|-----------------|--------|------|------------------------------------------------------------|
| `camber`        | number | rad  | Negative = top of wheel leans inward                       |
| `toe`           | number | rad  | Positive = toe-in (front of wheel points toward centerline)|
| `caster`        | number | rad  | Positive = steering axis tilts rearward at top             |
| `caster_trail`  | number | m    | Mechanical trail at ground (optional, can be derived)      |
| `kpi`           | number | rad  | King pin inclination (steering axis lateral tilt)          |
| `scrub_radius`  | number | m    | Lateral offset at ground between steering axis and contact |

---

### 9.7 `bump_stop` / `rebound_stop`

| Key              | Type   | Required | Description                                        |
|------------------|--------|----------|----------------------------------------------------|
| `gap`            | number | YES      | Distance from design position to contact (m)       |
| `rate`           | number | no       | Linear rate once engaged (N/m)                     |
| `rate_curve`     | array  | no       | Non-linear: `[[penetration_m, force_N], ...]`      |
| `type`           | string | no       | `"rubber"`, `"hydraulic"`, `"progressive"`         |

---

### 9.8 `wheel`

> **Tire dimensions have been removed from the wheel object.** The per-corner `wheel` defines only the physical rim (diameter, width, offset, mass, rotational inertia) and a `set_ref` that points to a tire set in `tires.sets`. This eliminates the "double-definition" hazard where tire dimensions could contradict between the wheel and the tire library. The tire library is the **single authoritative source** for tire geometry.

Physical geometry of the wheel and fitted tire carcass at this corner. This section describes **dimensions only** — tire force models (Pacejka, brush, etc.) are defined separately in the `tires` section (§11).

| Key                 | Type   | Required | Description                                                       |
|---------------------|--------|----------|-------------------------------------------------------------------|
| `rim_diameter`      | number | YES      | Rim diameter (m) — e.g. 0.4826 for an 19" rim                    |
| `rim_width`         | number | YES      | Rim width (m) — e.g. 0.2413 for a 9.5" rim                      |
| `rim_offset`        | number | no       | ET / offset from wheel centerplane to mounting face (m)           |
| `tire_section_width`| number | YES      | Tire section width (m) — e.g. 0.255 for a 255-series tire        |
| `tire_aspect_ratio` | number | YES      | Sidewall height / section width (dimensionless, e.g. 0.35)       |
| `tire_outer_diameter`| number | no      | Overall tire OD (m). If absent, derived: `rim_diameter + 2 × tire_section_width × tire_aspect_ratio` |
| `loaded_radius`     | number | no       | Static loaded radius under vehicle weight (m)                     |
| `mass`              | number | no       | Total wheel + tire mass (kg). This is part of unsprung mass.      |
| `rotational_inertia`| number | no       | Spin inertia about the wheel axis (kg·m²)                        |

> **Tire size shorthand:** A tire labeled "255/35R19" maps to: `tire_section_width: 0.255`, `tire_aspect_ratio: 0.35`, `rim_diameter: 0.4826` (19 × 0.0254).

> **Note:** `loaded_radius` depends on load and inflation pressure. The value here represents the static condition at design ride height. Dynamic loaded radius is the responsibility of the tire model, not this section.

> **Relationship to tire sets (§11):** The `wheel` object describes the **installed assembly** — the specific rim and fitted tire at this corner, with its total mass and rotational inertia. The tire set referenced via `tire.set_ref` (§9.10) carries the tire's own dimensions, rim fitment specs, and structural properties independently. When both exist, `wheel` values are authoritative for the installed state (e.g. actual rim width, total assembly mass), while the tire set provides the force model, thermal model, and manufacturer's reference geometry.
---

### 9.9 `brake` — Per-Corner Brake Assembly

Physical description of the brake components at this corner. Each part carries its own mass and thermal properties, enabling per-corner brake balance analysis and thermal simulation.

| Key       | Type   | Required | Description              |
|-----------|--------|----------|--------------------------|
| `disc`    | object | YES      | Brake disc / rotor       |
| `caliper` | object | no       | Brake caliper            |
| `pad`     | object | no       | Friction pad             |

#### 9.9.1 `disc`

| Key                | Type   | Required | Description                                              |
|--------------------|--------|----------|----------------------------------------------------------|
| `type`             | string | YES      | `"solid"`, `"vented"`, `"drilled"`, `"carbon_ceramic"`   |
| `outer_diameter`   | number | YES      | Disc outer diameter (m)                                   |
| `inner_diameter`   | number | no       | Friction ring inner diameter (m)                          |
| `thickness`        | number | no       | Disc thickness (m)                                        |
| `effective_radius` | number | no       | Effective friction radius for torque calculation (m)      |
| `mass`             | number | no       | Disc mass (kg) — contributes to unsprung/rotational mass  |
| `material`         | string | no       | `"cast_iron"`, `"carbon_ceramic"`, `"carbon_carbon"`      |
| `specific_heat`    | number | no       | Specific heat capacity (J/(kg·°C))                        |
| `max_temperature`  | number | no       | Maximum operating temperature before fade (°C)            |
| `thermal_mass`     | number | no       | Effective thermal mass m·c (J/°C). If absent, derived from `mass × specific_heat` |
| `rotational_inertia` | number | no    | Spin inertia about wheel axis (kg·m²). Added to `wheel.rotational_inertia` for total spinning mass. Derived: `0.5 × mass × (r_outer² + r_inner²)` for a solid annular disc. |

#### 9.9.2 `caliper`

| Key                  | Type    | Required | Description                                       |
|----------------------|---------|----------|---------------------------------------------------|
| `type`               | string  | no       | `"floating"`, `"fixed"`, `"sliding"`               |
| `pistons`            | integer | no       | Total piston count (e.g. 4, 6)                     |
| `piston_area_total`  | number  | no       | Total piston area, drive side (m²)                 |
| `mass`               | number  | no       | Caliper mass including bracket (kg)                |
| `position`           | [x,y,z] | no      | Caliper CG position (m) — if absent, approximated near disc effective_radius |

#### 9.9.3 `pad`

| Key             | Type   | Required | Description                                                |
|-----------------|--------|----------|------------------------------------------------------------|
| `material`      | string | no       | `"organic"`, `"semi_metallic"`, `"ceramic"`, `"racing"`    |
| `area`          | number | no       | Pad friction area per side (m²)                            |
| `thickness`     | number | no       | New pad thickness (m)                                      |
| `mass`          | number | no       | Mass per pad (kg)                                          |
| `mu_cold`       | number | no       | Nominal friction coefficient at ambient temperature        |
| `mu_curve`      | array  | no       | Temperature-dependent μ: `[[temp_°C, mu], ...]`            |
| `specific_heat` | number | no       | Pad specific heat capacity (J/(kg·°C))                     |

> **Note on brake mass:** Disc and caliper masses are part of the unsprung mass at each corner. When `mass_unsprung_per_corner` is provided, these brake masses should be included in that total. The per-component masses here enable detailed thermal and rotational inertia calculations.

> **Brake torque:** Torque at the wheel = line_pressure × piston_area_total × 2 (both sides of disc) × mu × effective_radius. The `brakes` top-level section (§12) provides the hydraulic system that generates line pressure.

#### 9.9.4 Brake Thermal Dynamics

The per-corner thermal properties in disc and pad define the materials; this section describes the heat flow model that connects them.

| Key                          | Type   | Required | Description                                           |
|------------------------------|--------|----------|-------------------------------------------------------|
| `disc_to_pad_conductance`    | number | no       | Thermal conductance disc → pad (W/°C)                 |
| `disc_to_air_conductance`    | number | no       | Thermal conductance disc → ambient (W/°C) at rest     |
| `disc_to_air_speed_curve`    | array  | no       | `[[vehicle_speed_m_s, conductance_W_°C], ...]` — air cooling increases with speed |
| `pad_to_caliper_conductance` | number | no       | Thermal conductance pad → caliper (W/°C)              |
| `caliper_to_air_conductance` | number | no       | Thermal conductance caliper → ambient (W/°C)          |
| `initial_temperature`        | number | no       | Starting brake temperature (°C)                       |

> **Heat generation:** Instantaneous brake heat = `T_brake × ω_wheel` (brake torque × wheel angular velocity, in Watts). This heat is distributed between disc and pad according to their thermal contact properties. The disc receives the majority (~90-95%) due to its larger thermal mass and conductivity.

> **Fade model:** As disc temperature rises, the pad `mu_curve` (§9.9.3) determines the friction coefficient, which feeds back into brake torque. This creates a natural fade model: heavy braking → disc heats → μ drops → less braking force. Recovery occurs when the cooling path (disc → air, disc → pad → caliper → air) dissipates heat faster than it's generated.

---

### 9.10 `tire` — Per-Corner Tire Assignment

Links this corner to a tire set defined in the top-level `tires` library (§11) and allows per-corner overrides for setup-specific values.

| Key                     | Type   | Required | Description                                                |
|-------------------------|--------|----------|------------------------------------------------------------|
| `set_ref`               | string | YES      | Key into `tires.sets` (e.g. `"front_245_35r19"`)          |
| `pressure`              | number | no       | Inflation pressure at this corner (Pa). Overrides set default. |
| `temperature_initial`   | number | no       | Starting temperature (°C). Overrides set default.           |
| `wear_initial`          | number | no       | Initial wear state (0.0 = new, 1.0 = worn out)             |
| `camber_stiffness_mult` | number | no       | Corner-specific multiplier on camber stiffness (1.0 = nominal) |

> **Resolution rule:** When a field exists both in the tire set and the per-corner override, the per-corner value takes precedence. All other parameters are inherited from the referenced set.


## 10. `powertrain` — Drivetrain System

The powertrain section describes the complete torque path from engine (or motor) to the driven wheels, including all rotating components, their inertias, gear ratios, and the physical geometry that connects them to the suspension.

### 10.1 Top-Level Properties

| Key              | Type   | Required | Description                                    |
|------------------|--------|----------|------------------------------------------------|
| `layout`         | string | no       | Drivetrain layout (§10.2)                      |
| `engine`         | object | no       | Internal combustion engine (§10.3)             |
| `clutch`         | object | no       | Clutch / torque converter (§10.4)              |
| `gearbox`        | object | no       | Gearbox / transmission (§10.5)                 |
| `transfer_case`  | object | no       | Transfer case for AWD/4WD (§10.6)              |
| `driveshafts`    | array  | no       | Propshafts connecting gearbox to diffs (§10.7) |
| `differentials`  | array  | no       | One or more differentials (§10.8)              |
| `half_shafts`    | object | no       | Per-corner axle shafts with CV joints (§10.9)  |

### 10.2 `layout`

Defines how power flows from the engine/motor to the wheels.

| Value   | Description                                                        |
|---------|--------------------------------------------------------------------|
| `"FR"`  | Front engine, rear drive — propshaft + rear diff + rear half-shafts |
| `"FF"`  | Front engine, front drive — transaxle + front half-shafts           |
| `"MR"`  | Mid engine, rear drive — rear transaxle or short propshaft          |
| `"RR"`  | Rear engine, rear drive — rear transaxle                            |
| `"AWD"` | All-wheel drive — transfer case + front and rear diffs              |
| `"4WD"` | Part-time four-wheel drive — selectable transfer case               |

> **Convention:** `layout` is informational. The actual torque path is fully determined by the `driveshafts`, `differentials`, and `half_shafts` entries. A parser SHOULD validate that the topology matches the stated layout.

### 10.3 `engine`

| Key               | Type   | Required | Description                                     |
|-------------------|--------|----------|-------------------------------------------------|
| `idle_rpm`        | number | no       | Idle speed (rev/min)                            |
| `max_rpm`         | number | no       | Limiter / redline (rev/min)                     |
| `torque_curve`    | array  | YES      | `[[rpm, torque_Nm], ...]` ordered by RPM         |
| `inertia`         | number | no       | Rotational inertia of crankshaft + flywheel (kg·m²) |
| `displacement`    | number | no       | Engine displacement (L)                         |
| `configuration`   | string | no       | e.g. `"V8"`, `"I4"`, `"flat6"`, `"electric"`   |
| `compression_ratio`| number| no       | Compression ratio (e.g. 13.0)                   |
| `position`        | [x,y,z]| no      | Engine CG position in vehicle frame (m)         |
| `mass`            | number | no       | Engine assembly mass (kg)                       |
| `thermal`         | object | no       | Engine thermal model (§10.3.1)                  |

#### 10.3.1 Engine Thermal Model

Describes how engine temperature affects performance. The engine is treated as a lumped thermal mass with heat generation from combustion and friction, and heat rejection to the cooling circuit.

| Key                      | Type   | Required | Description                                              |
|--------------------------|--------|----------|----------------------------------------------------------|
| `heat_capacity`          | number | no       | Engine block thermal mass (J/°C)                         |
| `temperature_nominal`    | number | no       | Normal operating temperature (°C)                        |
| `temperature_cold_start` | number | no       | Cold start temperature (°C) — typically ambient           |
| `warmup_time`            | number | no       | Time to reach nominal temp under moderate load (s)       |
| `heat_generation_curve`  | array  | no       | `[[rpm, load_fraction, heat_W], ...]` — heat produced by combustion |
| `friction_vs_temperature`| array  | no       | `[[oil_temp_°C, friction_multiplier], ...]` — cold engine friction penalty |
| `power_derating_vs_temperature` | array | no | `[[coolant_temp_°C, power_multiplier], ...]` — ECU power cut at overtemp |
| `oil_temperature_offset` | number | no       | Typical offset between coolant and oil temperature (°C)  |

> **Cold start penalty:** At cold oil temperatures (below ~60°C), internal friction can increase engine losses by 15–30%. The `friction_vs_temperature` curve captures this. At nominal temperature (typically 90–100°C), the multiplier is 1.0.

> **Overheating derating:** Most modern ECUs reduce ignition timing or fuel injection when coolant temperature exceeds a threshold (typically 110–115°C). `power_derating_vs_temperature` models this protection.

### 10.4 `clutch`

The interface between engine and gearbox input shaft.

| Key               | Type   | Required | Description                                          |
|-------------------|--------|----------|------------------------------------------------------|
| `type`            | string | no       | `"single_plate"`, `"multi_plate"`, `"dual_clutch"`, `"torque_converter"` |
| `max_torque`      | number | no       | Maximum transmittable torque (Nm)                    |
| `inertia_driven`  | number | no       | Inertia of the driven side (pressure plate + disc) (kg·m²) |
| `engagement_point`| number | no       | Pedal travel fraction at bite point (0.0–1.0)        |
| `mass`            | number | no       | Clutch assembly mass (pressure plate + disc + bearing) (kg) |
| `position`        | [x,y,z]| no      | Clutch assembly CG position (m) — typically between engine and gearbox |

> **Dual-clutch:** For DCT gearboxes, two clutches are implicit. `max_torque` is the per-clutch value. Odd/even gear assignment is handled by the gearbox.

### 10.5 `gearbox`

| Key              | Type   | Required | Description                                            |
|------------------|--------|----------|--------------------------------------------------------|
| `type`           | string | no       | `"manual"`, `"sequential"`, `"dct"`, `"auto"`, `"cvt"` |
| `ratios`         | array  | YES      | Forward gear ratios `[1st, 2nd, ..., Nth]`             |
| `reverse_ratios` | array  | no       | Reverse gear ratio(s) `[R1, ...]` — usually one entry  |
| `inertia_input`  | number | no       | Input shaft inertia (kg·m²)                            |
| `inertia_output` | number | no       | Output shaft inertia (kg·m²)                           |
| `efficiency`     | number | no       | Mechanical efficiency per gear mesh (0.0–1.0, e.g. 0.97) |
| `shift_time`     | number | no       | Typical shift duration (s) — for sequential/DCT/auto   |
| `position`       | [x,y,z]| no      | Gearbox CG position (m)                                |
| `mass`           | number | no       | Gearbox assembly mass (kg)                             |
| `output_flange`  | [x,y,z]| no      | Gearbox output flange position (m) — propshaft front joint connects here |
| `thermal`        | object | no       | Gearbox thermal model (§10.5.1)                         |

#### 10.5.1 Gearbox Thermal Model

| Key                          | Type   | Required | Description                                       |
|------------------------------|--------|----------|---------------------------------------------------|
| `oil_capacity`               | number | no       | Gearbox oil volume (m³)                           |
| `heat_capacity`              | number | no       | Thermal mass of gearbox + oil (J/°C)              |
| `efficiency_vs_temperature`  | array  | no       | `[[oil_temp_°C, efficiency], ...]` — cold oil = lower efficiency |
| `temperature_nominal`        | number | no       | Normal operating oil temperature (°C)             |
| `heat_generation_rate`       | number | no       | Heat generated at nominal load (W) — derived from (1 - efficiency) × input power |

> **Transaxle:** For FF/MR/RR layouts where gearbox and final drive share a housing, the `final_drive` ratio is specified in the differential entry (§10.8), not here. The `output_flange` is then the differential output.

### 10.6 `transfer_case`

For AWD and 4WD layouts. Splits torque from the gearbox output to front and rear driveshafts.

| Key               | Type   | Required | Description                                         |
|-------------------|--------|----------|-----------------------------------------------------|
| `type`            | string | no       | `"full_time"`, `"part_time"`, `"on_demand"`         |
| `ratio_high`      | number | no       | High-range ratio (1.0 = direct, typical)            |
| `ratio_low`       | number | no       | Low-range ratio (e.g. 2.48 for off-road reduction)  |
| `torque_split`    | array  | no       | Default F/R torque split `[front, rear]` (e.g. [0.4, 0.6]) |
| `center_diff`     | object | no       | Center differential — same schema as §10.8 differential |
| `inertia`         | number | no       | Transfer case rotating inertia (kg·m²)              |
| `position`        | [x,y,z]| no      | Transfer case CG (m)                                |
| `mass`            | number | no       | Transfer case mass (kg)                             |
| `output_front`    | [x,y,z]| no      | Front output flange position (m)                    |
| `output_rear`     | [x,y,z]| no      | Rear output flange position (m)                     |

### 10.7 `driveshafts` — Propshafts

Array of propshafts connecting gearbox (or transfer case) to differentials. A typical RWD car has one propshaft; AWD has two (front + rear).

Each driveshaft entry:

| Key               | Type    | Required | Description                                         |
|-------------------|---------|----------|-----------------------------------------------------|
| `id`              | string  | YES      | Unique identifier (e.g. `"propshaft_rear"`)         |
| `from`            | string  | no       | Source component: `"gearbox"`, `"transfer_front"`, `"transfer_rear"` |
| `to`              | string  | no       | Destination diff id (e.g. `"diff_rear"`)            |
| `joint_front`     | object  | no       | Front joint — connects to gearbox/TC output (§10.7.1) |
| `joint_rear`      | object  | no       | Rear joint — connects to diff input (§10.7.1)       |
| `joint_center`    | object  | no       | Center support bearing/joint for 2-piece shafts     |
| `sections`        | integer | no       | Number of shaft sections (1 or 2)                   |
| `mass`            | number  | no       | Propshaft total mass (kg)                           |
| `cg_position`     | [x,y,z] | no      | Propshaft CG position (m) — midpoint of shaft if absent |
| `inertia`         | number  | no       | Rotational inertia about spin axis (kg·m²)          |

#### 10.7.1 Joint Object

Describes a universal joint (Cardan/Hooke) or CV joint on a propshaft.

| Key        | Type    | Required | Description                                     |
|------------|---------|----------|-------------------------------------------------|
| `type`     | string  | no       | `"universal"`, `"cv"`, `"flex_disc"`, `"guibo"` |
| `position` | [x,y,z] | no      | Joint center position (m)                        |
| `max_angle`| number  | no       | Maximum operating angle (rad)                    |

### 10.8 `differentials`

> **Transaxle vehicles (FF, MR, RR):** When the gearbox and differential share the same housing, both `gearbox.efficiency` and the differential's implicit efficiency are modeling the same mechanical event. For transaxle layouts, set `gearbox.efficiency` to account for the total meshing loss and omit a separate differential efficiency, OR set gearbox efficiency to 1.0 and put all losses in the differential. Do not apply both — this would double-count friction losses.

Array of differential units. Each entry describes one differential with its location, final drive ratio, physical properties, and connection geometry.

| Key              | Type    | Required | Description                                          |
|------------------|---------|----------|------------------------------------------------------|
| `id`             | string  | YES      | Unique identifier (e.g. `"diff_rear"`, `"diff_front"`, `"diff_center"`) |
| `location`       | string  | no       | `"rear"`, `"front"`, `"center"`                      |
| `type`           | string  | no       | `"open"`, `"locked"`, `"lsd_clutch"`, `"lsd_torsen"`, `"lsd_viscous"`, `"active"`, `"spool"` |
| `final_drive`    | number  | YES      | Ring-and-pinion ratio (e.g. 2.866)                   |
| `preload`        | number  | no       | LSD preload torque (Nm)                              |
| `lock_power`     | number  | no       | Locking ratio under power (0.0–1.0)                  |
| `lock_coast`     | number  | no       | Locking ratio on coast/overrun (0.0–1.0)             |
| `ramp_angle_power`| number | no       | LSD power ramp angle (deg) — for asymmetric LSDs     |
| `ramp_angle_coast`| number | no       | LSD coast ramp angle (deg)                           |
| `efficiency`     | number  | no       | Mechanical efficiency (0.0–1.0, e.g. 0.95)          |
| `inertia`        | number  | no       | Rotating inertia of diff internals (kg·m²)           |
| `mass`           | number  | no       | Diff assembly mass including housing (kg)            |
| `position`       | [x,y,z] | no      | Diff CG position (m)                                 |
| `input_flange`   | [x,y,z] | no      | Pinion flange position — propshaft rear joint connects here |
| `output_left`    | [x,y,z] | no      | Left output flange position — half-shaft inner CV     |
| `output_right`   | [x,y,z] | no      | Right output flange position — half-shaft inner CV    |
| `thermal`        | object  | no       | Differential thermal model                            |

The differential thermal model uses the same schema as §10.5.1 (`oil_capacity`, `heat_capacity`, `efficiency_vs_temperature`, `temperature_nominal`, `heat_generation_rate`).

> **`final_drive` moved here:** In v0.5.x, `final_drive` was in `transmission`. From v0.6.0 it belongs to the differential, because in AWD systems front and rear diffs may have different final drive ratios. For backward compatibility, parsers SHOULD also check `gearbox.final_drive` as a fallback.

> **Asymmetric LSD:** The 2024 MX-5 ND3 uses a conical clutch LSD with different ramp angles for power and coast. `ramp_angle_power` and `ramp_angle_coast` capture this asymmetry. Lower angle = more aggressive locking.

### 10.9 `half_shafts` — Per-Corner Axle Shafts

Connects differential output flanges to the driven wheels via constant-velocity (CV) joints. Defined per driven corner.

```json
{
  "half_shafts": {
    "FL": { ... },
    "FR": { ... },
    "RL": { ... },
    "RR": { ... }
  }
}
```

Only driven corners need entries. For a RWD car, only `RL` and `RR` are present.

| Key          | Type    | Required | Description                                           |
|--------------|---------|----------|-------------------------------------------------------|
| `diff_ref`   | string  | no       | `id` of the differential this shaft connects to       |
| `cv_inner`   | object  | no       | Inboard CV joint (at the diff side) — §10.91         |
| `cv_outer`   | object  | no       | Outboard CV joint (at the wheel side) — §10.91       |
| `length`     | number  | no       | Shaft length between joint centers (m)                |
| `mass`       | number  | no       | Shaft + joints total mass (kg)                        |
| `cg_position`| [x,y,z] | no      | Shaft CG position (m) — midpoint between CV joints if absent |
| `inertia`    | number  | no       | Rotational inertia about spin axis (kg·m²)            |

#### 10.91 CV Joint Object

| Key           | Type    | Required | Description                                    |
|---------------|---------|----------|------------------------------------------------|
| `type`        | string  | no       | `"rzeppa"`, `"tripod"`, `"double_offset"`, `"cross_groove"` |
| `position`    | [x,y,z] | no      | Joint center position (m)                       |
| `max_angle`   | number  | no       | Maximum plunge/articulation angle (rad)         |
| `max_plunge`  | number  | no       | Maximum axial plunge (m) — tripod and plunging types |

> **Geometric consistency:** The `cv_outer.position` SHOULD match the upright hardpoint `cv_joint_outer` in `suspension.*.topology.upright.hardpoints` (if defined). The `cv_inner.position` SHOULD match the `differential.output_left` or `output_right` position for the corresponding side. Parsers MAY validate this consistency with a tolerance of ±5 mm.

> **Inertia chain:** For accurate drivetrain dynamics, the total inertia reflected at the wheel is: `J_wheel = J_engine × (gear_ratio × final_drive)² + J_gearbox_out × final_drive² + J_diff + J_halfshaft + J_wheel_assembly`. Each component provides its own inertia value.

### 10.10 Drivetrain Topology Examples

**RWD (e.g. Mazda MX-5):**
```
engine → clutch → gearbox → propshaft_rear → diff_rear → RL half-shaft → RL wheel
                                                        → RR half-shaft → RR wheel
```

**FF (e.g. VW Golf):**
```
engine → clutch → gearbox/transaxle → diff_front → FL half-shaft → FL wheel
                                                  → FR half-shaft → FR wheel
```

**AWD with center diff (e.g. Subaru WRX):**
```
engine → clutch → gearbox → transfer_case (center_diff)
                              → propshaft_front → diff_front → FL/FR half-shafts
                              → propshaft_rear  → diff_rear  → RL/RR half-shafts
```

**Part-time 4WD (e.g. Jeep Wrangler):**
```
engine → clutch → gearbox → transfer_case (hi/lo range, no center diff)
                              → propshaft_front → diff_front → FL/FR half-shafts
                              → propshaft_rear  → diff_rear  → RL/RR half-shafts
```

---

## 11. `tires` — Tire Model Library

The top-level `tires` object contains named tire sets that can be referenced from each suspension corner via `tire.set_ref`. This avoids duplicating 50–100+ Pacejka coefficients when the same tire model is shared across an axle.

```json
{
  "tires": {
    "sets": {
      "front_245_35r19": { ... },
      "rear_275_35r19": { ... }
    }
  }
}
```

### 11.1 Tire Set Object

| Key             | Type   | Required | Description                                         |
|-----------------|--------|----------|-----------------------------------------------------|
| `description`   | string | no       | Human-readable name (e.g. `"Michelin PS4S 245/35R19"`) |
| `size_code`     | string | no       | Standard tire size notation (e.g. `"245/35R19"`)     |
| `source`        | string | no       | Origin of data: `"measured"`, `"fitted"`, `"estimated"`, `"manufacturer"` |
| `dimensions`    | object | no       | Tire carcass geometry (§11.2)                        |
| `rim`           | object | no       | Recommended rim specifications (§11.3)               |
| `construction`  | object | no       | Structural and physical properties (§11.4)           |
| `reference`     | object | no       | Reference conditions for coefficients (§11.5)        |
| `pacejka`       | object | no       | Magic Formula coefficients (§11.6)                   |
| `tmeasy`        | object | no       | TMeasy model parameters (§11.10)                     |
| `brush`         | object | no       | Brush tire model parameters (§11.11)                 |
| `external_models`| array | no       | External proprietary model files (§11.12)            |
| `relaxation`    | object | no       | Force build-up dynamics (§11.7)                      |
| `thermal`       | object | no       | Thermal model parameters (§11.8)                     |
| `wear`          | object | no       | Wear model parameters (§11.9)                        |
| `pressure`      | number | no       | Default inflation pressure (Pa)                      |
| `temperature_nominal` | number | no | Nominal operating temperature (°C)                   |

### 11.2 `dimensions`

Physical geometry of the tire carcass. These define the tire's envelope and are the values printed on the sidewall.

| Key                | Type    | Required | Description                                                     |
|--------------------|---------|----------|-----------------------------------------------------------------|
| `section_width`    | number  | no       | Nominal section width (m) — e.g. 0.245 for a 245-series tire   |
| `aspect_ratio`     | number  | no       | Sidewall height / section width (e.g. 0.35 for a /35 tire)     |
| `rim_diameter_code`| integer | no       | Nominal rim diameter in inches (e.g. 19). Convenience field — the metric value is in `rim.diameter`. |
| `overall_diameter` | number  | no       | Outer diameter of inflated, unloaded tire (m)                   |
| `section_height`   | number  | no       | Sidewall height (m). If absent: `section_width × aspect_ratio`  |
| `tread_width`      | number  | no       | Effective tread contact width (m) — typically narrower than section_width |

> **Size code parsing:** `"245/35R19"` → `section_width: 0.245`, `aspect_ratio: 0.35`, `rim_diameter_code: 19`. The `R` indicates radial construction. The `size_code` field is informational; `dimensions` fields are the authoritative values.

### 11.3 `rim`

Recommended rim specifications for this tire. Defines the wheel this tire is designed to be mounted on.

| Key             | Type   | Required | Description                                              |
|-----------------|--------|----------|----------------------------------------------------------|
| `diameter`      | number | no       | Rim diameter (m) — e.g. 0.4826 for 19"                  |
| `width_nominal` | number | no       | Recommended rim width (m) — e.g. 0.2286 for 9.0"        |
| `width_range`   | array  | no       | `[min_width, max_width]` in meters — approved mounting range |
| `offset_range`  | array  | no       | `[min_ET, max_ET]` recommended offset range (m)          |

> **Relationship to `suspension.*.wheel`:** The per-corner `wheel` object (§9.8) describes the **actual installed wheel** — its specific width, offset, mass, and inertia. The tire set `rim` describes the tire manufacturer's **recommended fitment**. They may differ (e.g. the tire is approved for 8.5"–10.0" rims but is mounted on a 9.5" wheel). The per-corner `wheel` values are authoritative for the installed configuration.

### 11.4 `construction`

Structural and physical properties of the tire itself (carcass, tread compound, ratings). These affect ride dynamics, rolling resistance, and are needed for accurate vertical force models.

| Key                    | Type   | Required | Description                                                  |
|------------------------|--------|----------|--------------------------------------------------------------|
| `mass`                 | number | no       | Tire mass only, without rim (kg)                             |
| `vertical_stiffness`   | number | no       | Radial spring rate at reference load and pressure (N/m)      |
| `vertical_damping`     | number | no       | Radial damping coefficient (N·s/m)                           |
| `lateral_stiffness`    | number | no       | Lateral structural stiffness of carcass (N/m)                |
| `rolling_radius`       | number | no       | Effective rolling radius at reference load (m)               |
| `tread_depth_new`      | number | no       | Tread depth when new (m) — e.g. 0.007 for 7 mm             |
| `ply_type`             | string | no       | `"radial"`, `"bias"`, `"bias_belted"`                        |
| `speed_rating`         | string | no       | Speed rating code (e.g. `"Y"` for 300 km/h)                 |
| `load_index`           | integer| no       | Load index per tire standard (e.g. 96 = 710 kg)             |
| `utqg`                 | object | no       | UTQG ratings: `{"treadwear": 300, "traction": "AA", "temperature": "A"}` |

> **Tire mass vs wheel mass:** `construction.mass` is the tire carcass alone. `suspension.*.wheel.mass` is the complete wheel+tire assembly (rim + tire + valve + balance weights). Use `construction.mass` for thermal calculations and `wheel.mass` for unsprung mass and rotational inertia.

### 11.5 `reference`

The conditions at which the Pacejka coefficients were identified. Scaling factors in the model adjust for deviations from these reference values.

| Key        | Type   | Required | Description                                  |
|------------|--------|----------|----------------------------------------------|
| `load`     | number | no       | Reference vertical load Fz0 (N)              |
| `pressure` | number | no       | Reference inflation pressure (Pa)            |
| `speed`    | number | no       | Reference forward velocity (m/s)             |
| `camber`   | number | no       | Reference camber angle (rad)                 |

### 11.6 `pacejka` — Magic Formula Coefficients

The Pacejka Magic Formula tire model is the industry standard for steady-state tire force and moment representation. SVJ supports both MF 5.2 and MF 6.2 structures.

| Key             | Type   | Required | Description                                  |
|-----------------|--------|----------|----------------------------------------------|
| `model`         | string | YES      | `"MF52"` or `"MF62"`                        |
| `lateral`       | object | YES      | Pure lateral force Fy coefficients           |
| `longitudinal`  | object | YES      | Pure longitudinal force Fx coefficients      |
| `aligning`      | object | no       | Self-aligning torque Mz coefficients         |
| `overturning`   | object | no       | Overturning moment Mx coefficients           |
| `rolling_resistance` | object | no  | Rolling resistance moment My coefficients    |
| `combined`      | object | no       | Combined slip weighting factors              |

#### 11.6.1 Coefficient Naming Convention

Coefficients follow the standard Pacejka naming convention used in `.tir` files:

- **`lateral`**: `pCy1`, `pDy1`–`pDy3`, `pEy1`–`pEy5`, `pKy1`–`pKy7`, `pHy1`–`pHy3`, `pVy1`–`pVy4`, `pPy1`–`pPy5`
- **`longitudinal`**: `pCx1`, `pDx1`–`pDx3`, `pEx1`–`pEx4`, `pKx1`–`pKx3`, `pHx1`–`pHx2`, `pVx1`–`pVx2`, `pPx1`–`pPx4`
- **`aligning`**: `qBz1`–`qBz10`, `qCz1`, `qDz1`–`qDz11`, `qEz1`–`qEz5`, `qHz1`–`qHz4`
- **`overturning`**: `qsx1`–`qsx14`
- **`rolling_resistance`**: `qsy1`–`qsy8`
- **`combined`**: `rBx1`–`rBx3`, `rCx1`, `rHx1`, `rBy1`–`rBy4`, `rCy1`, `rHy1`, `rVy1`–`rVy6`

Each group is stored as a flat JSON object: `{ "pCy1": 1.3, "pDy1": 1.0, ... }`.

> **Partial sets:** Not all coefficients need to be present. A parser SHOULD default missing coefficients to 0.0 (which typically disables that effect). At minimum, `lateral` and `longitudinal` should contain the shape (`pCy1`/`pCx1`), peak (`pDy1`/`pDx1`), and stiffness (`pKy1`/`pKx1`) factors.

> **Compatibility:** MF 5.2 files can be loaded into an MF 6.2 parser — the additional pressure-dependency coefficients (`pPy*`, `pPx*`) simply default to zero.

### 11.7 `relaxation`

Transient force build-up model. Relaxation lengths control how quickly the tire develops lateral and longitudinal forces after a slip input.

| Key            | Type   | Required | Description                                     |
|----------------|--------|----------|-------------------------------------------------|
| `lateral`      | number | no       | Lateral relaxation length σα (m)                |
| `longitudinal` | number | no       | Longitudinal relaxation length σκ (m)           |

> **Typical values:** 0.2–0.5 m lateral, 0.05–0.15 m longitudinal for passenger car tires.

### 11.8 `thermal`

Thermal model parameters for tire temperature simulation. Temperature affects grip (via μ scaling) and wear rate.

| Key                   | Type   | Required | Description                                          |
|-----------------------|--------|----------|------------------------------------------------------|
| `surface_heat_capacity` | number | no     | Thermal mass of tread surface (J/°C)                 |
| `carcass_heat_capacity` | number | no     | Thermal mass of carcass (J/°C)                       |
| `surface_to_carcass`    | number | no     | Thermal conductance surface → carcass (W/°C)        |
| `carcass_to_air`        | number | no     | Thermal conductance carcass → ambient (W/°C)        |
| `friction_heat_fraction`| number | no     | Fraction of friction energy going into tire (0–1)   |
| `mu_temperature_curve`  | array  | no     | μ multiplier vs temperature: `[[°C, factor], ...]`  |
| `optimal_temperature`   | number | no     | Temperature for peak grip (°C)                       |

### 11.9 `wear`

| Key              | Type   | Required | Description                                        |
|------------------|--------|----------|----------------------------------------------------|
| `rate_lateral`   | number | no       | Lateral wear rate coefficient (dimensionless)      |
| `rate_longitudinal` | number | no    | Longitudinal wear rate coefficient                 |
| `rate_thermal`   | number | no       | Temperature-accelerated wear coefficient           |
| `mu_wear_curve`  | array  | no       | μ multiplier vs wear state: `[[wear, factor], ...]`|
| `stiffness_wear_curve` | array | no  | Stiffness multiplier vs wear: `[[wear, factor], ...]` |

> **Wear state:** 0.0 = brand new, 1.0 = completely worn. Intermediate values scale grip and stiffness via the curves above.

### 11.10 `tmeasy` — TMeasy Tire Model

The TMeasy model (Rill, 2006) is a physically motivated, semi-empirical tire model that describes force generation using only ~20 intuitive parameters. It uses a piecewise description of the force-slip curve with three key points: the origin slope (stiffness), the peak (maximum force and corresponding slip), and the sliding plateau (force at large slip). This makes it significantly easier to parameterize than Pacejka while remaining physically meaningful.

TMeasy is widely used in educational contexts, lightweight real-time simulations, and as a starting point when full Pacejka data is unavailable.

#### 11.10.1 Lateral Force Parameters

| Key              | Type   | Required | Description                                               |
|------------------|--------|----------|-----------------------------------------------------------|
| `dFy0`           | number | no       | Cornering stiffness at zero slip (N/rad) — initial slope  |
| `Fy_max`         | number | no       | Peak lateral force (N)                                    |
| `alpha_max`      | number | no       | Slip angle at peak lateral force (rad)                    |
| `Fy_slide`       | number | no       | Sliding (plateau) lateral force at large slip (N)         |
| `alpha_slide`    | number | no       | Slip angle at which sliding plateau begins (rad)          |

#### 11.10.2 Longitudinal Force Parameters

| Key              | Type   | Required | Description                                               |
|------------------|--------|----------|-----------------------------------------------------------|
| `dFx0`           | number | no       | Longitudinal stiffness at zero slip (N/unit) — initial slope |
| `Fx_max`         | number | no       | Peak longitudinal force (N)                               |
| `kappa_max`      | number | no       | Slip ratio at peak longitudinal force                     |
| `Fx_slide`       | number | no       | Sliding longitudinal force at large slip (N)              |
| `kappa_slide`    | number | no       | Slip ratio at which sliding plateau begins                |

#### 11.10.3 Load and Camber Dependency

| Key              | Type   | Required | Description                                               |
|------------------|--------|----------|-----------------------------------------------------------|
| `Fz0`            | number | no       | Reference vertical load (N) — parameters valid at this load |
| `dFy0_dFz`       | number | no       | Cornering stiffness sensitivity to load (N/rad per N)     |
| `Fy_max_dFz`     | number | no       | Peak Fy sensitivity to load (per N)                       |
| `camber_stiffness`| number| no       | Camber thrust coefficient (N/rad)                         |
| `Fz_dependency`  | string | no       | `"linear"`, `"degressive"` — how parameters scale with load |

#### 11.10.4 Self-Aligning Torque

| Key              | Type   | Required | Description                                               |
|------------------|--------|----------|-----------------------------------------------------------|
| `pneumatic_trail_max` | number | no  | Maximum pneumatic trail at zero slip (m)                  |
| `pneumatic_trail_slide` | number | no | Pneumatic trail at sliding (m) — typically near zero     |

> **TMeasy curve shape:** The force-slip curve is constructed as: rising (initial slope `dF0`) → peak (`F_max` at `slip_max`) → declining → plateau (`F_slide` at `slip_slide`). The transition regions use smooth interpolation. This gives a realistic shape with only 5 parameters per force direction.

> **When to use TMeasy vs Pacejka:** TMeasy is preferred when: (a) full Pacejka test data is unavailable, (b) physical intuition of parameters matters (stiffness, peak force, and saturation are directly meaningful), (c) computational cost must be minimal, or (d) the model is for educational or prototyping purposes. Pacejka is preferred when high-fidelity measured data exists and precise combined-slip behavior is critical.

---

### 11.11 `brush` — Brush Tire Model

The brush model is the simplest physically-based tire force model. It treats the contact patch as an array of elastic bristles that deform under slip. Forces are derived from first principles: contact patch geometry, tread rubber stiffness, and friction coefficient. No curve fitting required — the characteristic shape emerges naturally.

| Key                  | Type   | Required | Description                                           |
|----------------------|--------|----------|-------------------------------------------------------|
| `contact_length`     | number | no       | Contact patch length (m) — typically 0.10–0.20 m      |
| `contact_width`      | number | no       | Contact patch width (m) — approximately tread width    |
| `tread_stiffness_lat`| number | no       | Lateral tread rubber stiffness per unit area (N/m³)   |
| `tread_stiffness_lon`| number | no       | Longitudinal tread rubber stiffness per unit area (N/m³) |
| `mu_static`          | number | no       | Static friction coefficient                            |
| `mu_kinetic`         | number | no       | Kinetic (sliding) friction coefficient                 |
| `pressure_distribution`| string| no      | Contact pressure shape: `"uniform"`, `"parabolic"`, `"trapezoidal"` |
| `bristle_rows`       | integer| no       | Number of bristle rows for discretized models          |
| `carcass_stiffness`  | number | no       | Lateral carcass stiffness (N/m) — adds compliance between rim and contact |

> **Derived quantities:** From the brush model parameters, a solver computes cornering stiffness as: `Cα = (c_lat × a² × w) / 3` where `c_lat` is tread lateral stiffness, `a` is half the contact length, and `w` is contact width. Peak force = `μ × Fz`. No empirical curve fitting is needed — the force-slip shape is a direct consequence of the physics.

> **When to use brush model:** When the goal is a physics-first model with transparent parameters that can be derived from material properties and geometry. The brush model is the foundation that Pacejka and TMeasy fit curves to. Some modern racing simulators (Live For Speed) use enhanced brush models internally for their transparent physical behavior, especially under combined slip.

---

### 11.12 `external_models` — Proprietary Tire Model Files

High-fidelity tire models (FTire, CDTire, MF-Swift) use proprietary parameter file formats generated by specialized fitting software from test rig measurements. These files contain hundreds of structural parameters that cannot be meaningfully inlined into JSON. SVJ references them by path.

Each entry in the `external_models` array:

| Key          | Type   | Required | Description                                              |
|--------------|--------|----------|----------------------------------------------------------|
| `type`       | string | YES      | Model type identifier (see below)                        |
| `version`    | string | no       | Model/software version used for fitting                  |
| `file`       | string | no       | Relative path to the parameter file (from SVJ root)      |
| `uri`        | string | no       | Absolute URI or URL to the parameter file                |
| `description`| string | no       | Human-readable notes (fitting source, test rig, date)    |
| `source_lab` | string | no       | Measurement laboratory (e.g. `"Calspan"`, `"MTS"`, `"TMPT"`) |
| `conditions` | object | no       | Test conditions: `{"load": N, "pressure": Pa, "speed": m/s, "surface": "..."}` |

#### Recognized `type` Values

| Value          | Format    | Description                                              |
|----------------|-----------|----------------------------------------------------------|
| `"ftire"`      | `.fti`    | FTire (cosin scientific) — flexible ring, 0–200 Hz       |
| `"cdtire"`     | `.cdt`    | CDTire (Fraunhofer ITWM) — scalable family 20/30/40/50   |
| `"mfswift"`    | `.tir`    | MF-Swift (TNO/Siemens) — MF 6.2 + rigid ring dynamics    |
| `"mftyre"`     | `.tir`    | MF-Tyre standalone .tir file (Pacejka)                    |
| `"pac2002"`    | `.tir`    | PAC2002 .tir file (TNO legacy format)                     |
| `"rmod_k"`     | varies    | RMOD-K tire model                                         |
| `"custom"`     | varies    | Any other format — describe in `description`              |

> **Relationship to inline models:** A tire set MAY contain both inline model data (`pacejka`, `tmeasy`, `brush`) AND external file references. The inline data serves as a fallback for tools that cannot read the proprietary format. A parser SHOULD prefer the external model when its type is supported, and fall back to inline data otherwise.

> **TYDEX raw data:** The `source_lab` and `conditions` fields enable traceability back to the original measurement. The industry-standard interchange format for raw tire test data is TYDEX (Tire Data Exchange). SVJ does not inline raw measurement data but acknowledges this pipeline: test rig → TYDEX → fitting tool → .fti/.cdt/.tir → referenced in SVJ.

#### 11.12.1 Model Fidelity Guide

| Model | Fidelity | Frequency | Parameters | Real-time | Best for |
|-------|----------|-----------|-----------|-----------|----------|
| Brush | Low | 0–8 Hz | ~10 | Yes | Physics-first, education, prototyping |
| TMeasy | Low-Mid | 0–8 Hz | ~20 | Yes | Lightweight sims, early design, intuitive tuning |
| Pacejka MF 5.2/6.2 | Mid | 0–8 Hz | 50–100 | Yes | Handling, racing sims, standard interchange |
| MF-Swift | Mid-High | 0–60 Hz | 100+ | Marginal | Ride, obstacle, belt dynamics |
| FTire | High | 0–200 Hz | 200+ | 10–20× RT | Comfort, durability, ABS/ESC development |
| CDTire 40/50 | High | 0–500 Hz | 300+ | No | NVH, durability, tire/soil interaction |

---

## 12. `brakes` — System-Level Braking

The top-level `brakes` object describes the complete braking system: pedal, booster, master cylinder, hydraulic circuits, bias, and electronic control. Per-corner brake assemblies (disc, caliper, pad) are in `suspension.*.brake` (§9.9).

| Key               | Type   | Required | Description                                  |
|-------------------|--------|----------|----------------------------------------------|
| `pedal`           | object | no       | Brake pedal geometry (§12.1)                 |
| `booster`         | object | no       | Brake booster / servo (§12.2)                |
| `master_cylinder` | object | no       | Tandem master cylinder (§12.3)               |
| `circuit_type`    | string | no       | `"dual_diagonal"`, `"front_rear_split"`      |
| `bias`            | number | no       | Front brake bias (0.0–1.0). 0.62 = 62% front |
| `bias_type`       | string | no       | `"fixed"`, `"adjustable"`, `"electronic"`    |
| `line_pressure_max`| number| no       | Maximum hydraulic line pressure (Pa)         |
| `abs`             | object | no       | Anti-lock braking system (§12.4)             |
| `esc`             | object | no       | Electronic stability control (§12.5)         |

### 12.1 `pedal`

| Key              | Type   | Required | Description                                     |
|------------------|--------|----------|-------------------------------------------------|
| `ratio`          | number | no       | Mechanical pedal ratio (lever advantage)        |
| `travel`         | number | no       | Maximum pedal travel (m)                        |
| `pad_area`       | number | no       | Pedal pad contact area (m²)                     |

### 12.2 `booster`

The brake booster (servo) multiplies the driver's pedal force before it reaches the master cylinder. Most road cars use vacuum or electric boosters; race cars often have none.

| Key              | Type   | Required | Description                                             |
|------------------|--------|----------|---------------------------------------------------------|
| `type`           | string | no       | `"none"`, `"vacuum"`, `"electric"`, `"hydraulic"`       |
| `boost_ratio`    | number | no       | Force multiplication factor (e.g. 3.5 = output is 3.5× input) |
| `diameter`       | number | no       | Booster diaphragm diameter (m) — for vacuum type        |
| `max_force`      | number | no       | Maximum output force before saturation (N)              |
| `mass`           | number | no       | Booster assembly mass (kg)                              |

> **No booster:** Race cars and some lightweight sports cars omit the booster. Set `type: "none"` and `boost_ratio: 1.0`.

### 12.3 `master_cylinder`

Tandem master cylinder with two separate pressure circuits. May have equal or unequal bore sizes for front/rear circuits.

| Key              | Type   | Required | Description                                            |
|------------------|--------|----------|--------------------------------------------------------|
| `bore_primary`   | number | no       | Primary circuit bore diameter (m) — typically front     |
| `bore_secondary` | number | no       | Secondary circuit bore diameter (m) — typically rear. If absent, same as primary. |
| `bore`           | number | no       | Single bore diameter (m) — shorthand when both are equal |
| `stroke`         | number | no       | Maximum piston stroke (m)                              |
| `reservoir_volume`| number| no       | Brake fluid reservoir volume (m³)                      |
| `mass`           | number | no       | Master cylinder assembly mass (kg)                     |
| `position`       | [x,y,z]| no      | Master cylinder CG position (m)                        |

> **Bore resolution:** If `bore_primary` and `bore_secondary` are present, they take precedence over `bore`. If only `bore` is present, both circuits use the same bore.

### 12.4 `abs`

| Key           | Type    | Required | Description                                    |
|---------------|---------|----------|------------------------------------------------|
| `enabled`     | boolean | no       | Whether ABS is present and active              |
| `type`        | string  | no       | `"2_channel"`, `"3_channel"`, `"4_channel"`    |
| `cycle_rate`  | number  | no       | ABS modulator cycling rate (Hz)                |
| `slip_target` | array   | no       | `[min_slip_ratio, max_slip_ratio]` target window |
| `ebd`         | boolean | no       | Electronic Brake-force Distribution present    |
| `brake_assist`| boolean | no       | Emergency Brake Assist present                 |

### 12.5 `esc`

| Key                  | Type    | Required | Description                                 |
|----------------------|---------|----------|---------------------------------------------|
| `enabled`            | boolean | no       | Whether ESC is present and active           |
| `yaw_rate_threshold` | number  | no       | Yaw rate error threshold for intervention (rad/s) |
| `sideslip_threshold` | number  | no       | Body sideslip angle threshold (rad)         |
| `torque_vectoring`   | boolean | no       | Whether ESC can apply differential braking for yaw control |
| `track_mode`         | boolean | no       | Whether a reduced-intervention track mode exists |

### 12.6 Force Chain — Pedal to Wheel

The complete braking force chain, from driver foot to brake torque at the wheel:

```
F_foot                          Driver pedal force (N)
  × pedal.ratio                 Mechanical leverage
  × booster.boost_ratio         Servo multiplication (1.0 if none)
  = F_mc                        Force on master cylinder piston (N)

P_line = F_mc / A_mc            Line pressure (Pa)
  where A_mc = π × (bore/2)²   Master cylinder piston area

F_clamp = P_line × A_caliper    Clamping force per caliper (N)
  where A_caliper = caliper.piston_area_total

F_friction = F_clamp × 2 × μ   Friction force (both disc faces)
  where μ = pad.mu (temperature-dependent)

T_brake = F_friction × R_eff    Brake torque at wheel (Nm)
  where R_eff = disc.effective_radius
```

> **Hydraulic ratio** per corner = `caliper.piston_area_total / A_mc`. This is the hydraulic force multiplication between master cylinder and caliper. A typical value is 2–5×.

> **Total system ratio** from pedal force to clamping force = `pedal.ratio × boost_ratio × hydraulic_ratio`. For a road car: ~4.5 × 3.5 × 3.0 ≈ 47×.

> **Bias distribution:** Line pressure is split between front and rear circuits by the `bias` ratio. Each front corner receives `P_line × bias / 2`, each rear receives `P_line × (1 − bias) / 2`.

---

## 13. `aerodynamics`

Aerodynamic forces and moments acting on the vehicle body. The model supports three levels of fidelity:

1. **Basic** — Scalar coefficients (Cd, Cl) with frontal area. Sufficient for simple drag/lift.
2. **Mapped** — Coefficients as functions of ride height, pitch, yaw, and roll. For detailed handling sims.
3. **Component-based** — Individual aero devices (wings, splitters, diffusers) with their own contributions, masses, and adjustable settings.

### 13.1 Top-Level Properties

| Key            | Type   | Required | Description                                     |
|----------------|--------|----------|-------------------------------------------------|
| `reference`    | object | YES      | Reference conditions and areas (§13.2)          |
| `coefficients` | object | no       | Static aerodynamic coefficients (§13.3)         |
| `maps`         | object | no       | Coefficient sensitivity maps (§13.4)            |
| `center_of_pressure` | [x,y,z] | no | Aero force application point (m)            |
| `components`   | array  | no       | Individual aero devices (§13.5)                 |
| `active_systems`| object| no       | DRS, active wing, etc. (§13.6)                  |

### 13.2 `reference`

| Key            | Type   | Required | Description                                               |
|----------------|--------|----------|-----------------------------------------------------------|
| `frontal_area` | number | YES      | Projected frontal area (m²) — measured or from CAD        |
| `planform_area`| number | no       | Top-view planform area (m²) — used for lift coefficients in some models |
| `reference_length` | number | no   | Reference length for moment coefficients (m) — typically wheelbase |
| `air_density`  | number | no       | Reference air density (kg/m³). Default: 1.225 (ISA sea level) |

### 13.3 `coefficients`

Static aerodynamic coefficients at zero yaw, reference ride height, and reference speed. All coefficients follow **SAE J1594 / wind-tunnel convention**:

| Key       | Type   | Required | Description                                                   |
|-----------|--------|----------|---------------------------------------------------------------|
| `Cd`      | number | no       | Drag coefficient (positive = rearward force)                  |
| `Cl`      | number | no       | Lift coefficient: positive = lift (upward), negative = downforce |
| `Cl_front`| number | no       | Lift coefficient attributed to front axle                     |
| `Cl_rear` | number | no       | Lift coefficient attributed to rear axle                      |
| `Cs`      | number | no       | Side force coefficient (at zero yaw, usually 0)               |
| `Cpm`     | number | no       | Pitch moment coefficient (positive = nose up)                 |
| `Cym`     | number | no       | Yaw moment coefficient (positive = nose right)                |
| `Crm`     | number | no       | Roll moment coefficient                                       |

> **Sign convention:** Aerodynamic forces are computed as `F = 0.5 × ρ × V² × C × A_frontal`. Positive `Cl` produces lift (upward, opposing SAE Z-down gravity). A car with net downforce has negative `Cl`. Drag always acts rearward regardless of `Cd` sign (convention: `Cd` is positive, applied in −X).

> **Front/rear split:** `Cl_front + Cl_rear` SHOULD equal `Cl`. If only `Cl` is given, parsers MAY assume 50/50 distribution. Aero balance is `Cl_front / Cl` (fraction of total lift/downforce on front axle).

### 13.4 `maps` — Sensitivity Functions

Aerodynamic coefficients vary with vehicle attitude and speed. Each map is an array of `[input_value, coefficient_value]` pairs.

| Key                   | Type   | Required | Description                                            |
|-----------------------|--------|----------|--------------------------------------------------------|
| `Cd_vs_yaw`          | array  | no       | `[[yaw_rad, Cd], ...]` — drag vs yaw angle            |
| `Cl_front_vs_ride_height` | array | no  | `[[ride_height_m, Cl_front], ...]` at front axle       |
| `Cl_rear_vs_ride_height`  | array | no  | `[[ride_height_m, Cl_rear], ...]` at rear axle         |
| `Cl_vs_pitch`        | array  | no       | `[[pitch_rad, Cl_multiplier], ...]` — pitch effect on total Cl |
| `Cs_vs_yaw`          | array  | no       | `[[yaw_rad, Cs], ...]` — side force vs yaw            |
| `Cym_vs_yaw`         | array  | no       | `[[yaw_rad, Cym], ...]` — yaw moment vs yaw           |
| `Cd_vs_ride_height`  | array  | no       | `[[ride_height_m, Cd], ...]` — drag vs front ride height |

> **Ride height** is measured from the aerodynamic reference plane (typically floor/splitter leading edge) to the ground. Lower ride height generally increases downforce until flow stalls.

> **Map resolution:** Maps override the corresponding scalar in `coefficients` via interpolation. For operating points outside the map range, extrapolation from the two nearest points applies (same convention as damper curves).

### 13.5 `components` — Aero Devices

Each entry represents a distinct aerodynamic device. Components allow granular control: add/remove a wing, adjust a splitter angle, calculate per-device forces.

| Key                | Type    | Required | Description                                          |
|--------------------|---------|----------|------------------------------------------------------|
| `id`               | string  | YES      | Unique identifier (e.g. `"rear_wing"`, `"front_splitter"`) |
| `type`             | string  | no       | `"wing"`, `"splitter"`, `"diffuser"`, `"spoiler"`, `"canard"`, `"flat_floor"`, `"vortex_generator"`, `"other"` |
| `description`      | string  | no       | Human-readable label                                 |
| `position`         | [x,y,z] | no      | Position of the device's aerodynamic center (m)      |
| `mass`             | number  | no       | Device mass (kg) — for weight tracking               |
| `area`             | number  | no       | Device reference area (m²) — wing planform, splitter area, etc. |
| `Cd_contribution`  | number  | no       | Drag coefficient contribution of this device         |
| `Cl_contribution`  | number  | no       | Lift coefficient contribution (negative = downforce) |
| `adjustable`       | boolean | no       | Whether angle/position can change                    |
| `settings`         | array   | no       | Discrete settings for adjustable devices (§13.5.1)   |
| `inertia`          | object  | no       | Rotational inertia if the device is a spinning element (rare) |

#### 13.5.1 Adjustable Settings

For devices with discrete positions (e.g. wing angle presets, Gurney flap on/off):

| Key    | Type   | Required | Description                                  |
|--------|--------|----------|----------------------------------------------|
| `name` | string | YES      | Setting label (e.g. `"low_drag"`, `"qualifying"`) |
| `angle`| number | no       | Device angle/incidence (rad)                  |
| `Cd`   | number | no       | Drag coefficient at this setting              |
| `Cl`   | number | no       | Lift coefficient at this setting              |

> **Summation rule:** Total vehicle Cd = base body Cd + Σ component Cd_contribution (or the active setting's Cd if adjustable). Same for Cl. The `coefficients` section (§13.3) represents the **total** including all installed components at their default settings.

> **Component mass:** Unlike brake or suspension masses that affect unsprung mass, aero device masses are sprung mass. They MAY also appear in `chassis.mass_bodies` for detailed CG/inertia tracking. If present in both, `mass_bodies` is authoritative.

### 13.6 `active_systems`

Electronic or pneumatic systems that modify aerodynamic devices in real-time.

| Key       | Type   | Required | Description                              |
|-----------|--------|----------|------------------------------------------|
| `drs`     | object | no       | Drag Reduction System (§13.6.1)          |
| `active_ride_height` | object | no | Aero-driven ride height control (§13.6.2) |
| `active_wing` | object | no    | Continuously variable wing (§13.6.3)      |

#### 13.6.1 `drs`

| Key                 | Type    | Required | Description                                    |
|---------------------|---------|----------|------------------------------------------------|
| `enabled`           | boolean | no       | Whether DRS is present                         |
| `component_ref`     | string  | no       | `id` of the affected component in `components` |
| `setting_ref`       | string  | no       | `name` of the setting when DRS is open         |
| `activation_speed`  | number  | no       | Minimum speed for activation (m/s)             |
| `transition_time`   | number  | no       | Time to deploy/retract (s)                     |

#### 13.6.2 `active_ride_height`

| Key              | Type   | Required | Description                                     |
|------------------|--------|----------|-------------------------------------------------|
| `enabled`        | boolean| no       | Whether the system is present                   |
| `min_height`     | number | no       | Minimum ride height at speed (m)                |
| `max_height`     | number | no       | Raised ride height at low speed (m)             |
| `transition_speed`| number| no       | Speed at which lowering begins (m/s)            |

#### 13.6.3 `active_wing`

| Key              | Type   | Required | Description                                     |
|------------------|--------|----------|-------------------------------------------------|
| `enabled`        | boolean| no       | Whether the system is present                   |
| `component_ref`  | string | no       | `id` of the affected component                  |
| `angle_range`    | array  | no       | `[min_angle_rad, max_angle_rad]`                |
| `Cl_range`       | array  | no       | `[Cl_at_min_angle, Cl_at_max_angle]`            |
| `Cd_range`       | array  | no       | `[Cd_at_min_angle, Cd_at_max_angle]`            |
| `response_time`  | number | no       | Actuator response time constant (s)             |

---

## 14. `electric` — Electric & Hybrid Powertrain

For battery-electric (BEV) and hybrid vehicles (HEV, PHEV). Pure ICE vehicles may omit this section entirely. The electric powertrain works alongside or replaces the ICE powertrain in §10.

### 14.1 Top-Level Properties

| Key         | Type   | Required | Description                                  |
|-------------|--------|----------|----------------------------------------------|
| `hybrid_type`| string| no       | `"none"`, `"mild"` (P0/P1), `"parallel"` (P2/P3), `"series"`, `"power_split"`, `"bev"` |
| `motors`    | array  | no       | Electric motor(s) (§14.2)                    |
| `battery`   | object | no       | Traction battery pack (§14.3)                |
| `inverters` | array  | no       | Power electronics (§14.4)                    |
| `regen`     | object | no       | Regenerative braking parameters (§14.5)      |

### 14.2 `motors` — Electric Motor Array

Each entry describes one electric motor/generator unit.

| Key               | Type    | Required | Description                                          |
|-------------------|---------|----------|------------------------------------------------------|
| `id`              | string  | YES      | Unique identifier (e.g. `"front_motor"`, `"p2_msg"`) |
| `placement`       | string  | no       | `"P0"` (belt), `"P1"` (flywheel), `"P2"` (post-clutch), `"P3"` (gearbox output), `"P4"` (axle-mounted), `"in_wheel"` |
| `type`            | string  | no       | `"pmsm"` (permanent magnet), `"im"` (induction), `"srm"` (switched reluctance), `"axial_flux"` |
| `max_power`       | number  | no       | Peak electrical power (W)                            |
| `max_torque`      | number  | no       | Peak torque (Nm)                                     |
| `max_rpm`         | number  | no       | Maximum motor speed (rev/min)                        |
| `continuous_power` | number | no       | Continuous rated power (W)                           |
| `torque_curve`    | array   | no       | `[[rpm, torque_Nm], ...]` — peak torque vs speed     |
| `efficiency_map`  | array   | no       | `[[rpm, torque_Nm, efficiency], ...]` — 3D map       |
| `inertia`         | number  | no       | Rotor inertia (kg·m²)                                |
| `mass`            | number  | no       | Motor + housing mass (kg)                            |
| `position`        | [x,y,z] | no      | Motor CG position (m)                                |
| `gear_ratio`      | number  | no       | Reduction gear ratio (if integrated, e.g. 9.0:1)    |
| `gear_efficiency` | number  | no       | Reduction gear efficiency (0.0–1.0)                  |
| `driven_axle`     | string  | no       | `"front"`, `"rear"`, `"left_front"`, `"right_rear"`, etc. |
| `cooling`         | string  | no       | `"air"`, `"liquid"`, `"oil"`                         |

> **Motor placement convention (P0–P4):**
> - **P0**: Belt-driven, crankshaft accessory position (mild hybrid BSG)
> - **P1**: Directly on crankshaft/flywheel, between engine and clutch
> - **P2**: Between clutch and gearbox input — can drive without engine
> - **P3**: At gearbox output — post-transmission
> - **P4**: At axle, independent of ICE drivetrain — decoupled axle drive
> - **in_wheel**: Hub motor integrated into the wheel assembly

### 14.3 `battery` — Traction Battery Pack

| Key                    | Type    | Required | Description                                      |
|------------------------|---------|----------|--------------------------------------------------|
| `chemistry`            | string  | no       | `"NMC"`, `"NCA"`, `"LFP"`, `"NMC811"`, `"solid_state"`, `"NiMH"` |
| `capacity_kwh`         | number  | no       | Gross energy capacity (kWh)                      |
| `capacity_usable_kwh`  | number  | no       | Usable energy capacity (kWh)                     |
| `voltage_nominal`      | number  | no       | Nominal pack voltage (V)                         |
| `voltage_max`          | number  | no       | Maximum pack voltage at full charge (V)          |
| `voltage_min`          | number  | no       | Minimum voltage at cutoff (V)                    |
| `cells_series`         | integer | no       | Number of cells in series (defines voltage)      |
| `cells_parallel`       | integer | no       | Number of cells in parallel (defines capacity)   |
| `internal_resistance`  | number  | no       | Pack internal resistance at nominal temp (Ω)     |
| `max_discharge_power`  | number  | no       | Maximum continuous discharge power (W)           |
| `max_charge_power`     | number  | no       | Maximum charge power (W)                         |
| `soc_initial`          | number  | no       | Initial state of charge (0.0–1.0)                |
| `mass`                 | number  | no       | Pack mass including housing and BMS (kg)         |
| `position`             | [x,y,z] | no      | Pack CG position (m)                             |
| `inertia`              | object  | no       | Pack inertia (Ixx/Iyy/Izz/Ixz) — significant for heavy packs |
| `thermal`              | object  | no       | Battery thermal properties (§14.3.1)             |

#### 14.3.1 Battery Thermal

| Key                       | Type   | Required | Description                                   |
|---------------------------|--------|----------|-----------------------------------------------|
| `heat_capacity`           | number | no       | Total pack thermal mass (J/°C)                |
| `optimal_temperature`     | number | no       | Optimal operating temperature (°C)            |
| `min_temperature`         | number | no       | Minimum safe operating temperature (°C)       |
| `max_temperature`         | number | no       | Maximum safe operating temperature (°C)       |
| `cooling_type`            | string | no       | `"air"`, `"liquid"`, `"refrigerant"`          |
| `cooling_power`           | number | no       | Maximum heat rejection rate (W)               |
| `resistance_vs_temp`      | array  | no       | `[[temp_°C, resistance_Ω], ...]`              |

### 14.4 `inverters`

| Key             | Type    | Required | Description                                    |
|-----------------|---------|----------|------------------------------------------------|
| `id`            | string  | YES      | Unique identifier                              |
| `motor_ref`     | string  | no       | `id` of the motor this inverter drives         |
| `max_power`     | number  | no       | Peak inverter power (W)                        |
| `efficiency`    | number  | no       | Typical conversion efficiency (0.0–1.0)        |
| `mass`          | number  | no       | Inverter mass (kg)                             |
| `position`      | [x,y,z] | no      | Inverter position (m)                          |

### 14.5 `regen` — Regenerative Braking

| Key                    | Type    | Required | Description                                     |
|------------------------|---------|----------|-------------------------------------------------|
| `max_torque`           | number  | no       | Maximum regen braking torque (Nm)               |
| `max_power`            | number  | no       | Maximum regen power (W)                         |
| `blend_with_hydraulic` | boolean | no       | Whether regen blends with friction brakes       |
| `front_rear_split`     | number  | no       | Fraction of regen on front axle (0.0–1.0) — for AWD EVs |
| `min_speed`            | number  | no       | Minimum speed for regen activation (m/s)        |
| `coast_regen`          | number  | no       | Regen torque applied on throttle lift (Nm) — for one-pedal driving |

---

## 15. `cooling` — Thermal Management

System-level thermal model. Component-level thermal properties (disc specific_heat, tire thermal model, battery thermal, engine thermal) are defined within their respective sections. This section describes: the ambient environment, the cooling infrastructure that connects components, and the thermal resistance network.

### 15.1 Top-Level Properties

| Key           | Type   | Required | Description                           |
|---------------|--------|----------|---------------------------------------|
| `environment` | object | no       | Ambient conditions (§15.3)            |
| `circuits`    | array  | no       | Array of cooling circuits (§15.3)     |

### 15.2 `environment` — Ambient Conditions

| Key                   | Type   | Required | Description                                     |
|-----------------------|--------|----------|-------------------------------------------------|
| `temperature_ambient` | number | no       | Ambient air temperature (°C). Default: 25       |
| `pressure_ambient`    | number | no       | Atmospheric pressure (Pa). Default: 101325      |
| `humidity`            | number | no       | Relative humidity (0.0–1.0)                     |
| `altitude`            | number | no       | Altitude above sea level (m) — affects air density and cooling |
| `wind_speed`          | number | no       | External wind speed (m/s) — affects stationary cooling |

> **Effect on systems:** Ambient temperature is the heat sink for all cooling circuits (radiator outlet approaches ambient at high airflow), tire temperature (cold start), brake temperature (initial), and engine cold-start behavior. Air density (from altitude and temperature) affects both aerodynamic forces and cooling efficiency.

### 15.3 Cooling Circuit

Each circuit represents an independent coolant loop.

| Key                   | Type    | Required | Description                                         |
|-----------------------|---------|----------|-----------------------------------------------------|
| `id`                  | string  | YES      | Unique identifier (e.g. `"engine_coolant"`, `"battery_cooling"`, `"oil"`) |
| `type`                | string  | no       | `"liquid"`, `"air"`, `"oil"`, `"refrigerant"`       |
| `coolant`             | string  | no       | Coolant type: `"water_glycol"`, `"oil"`, `"dielectric"`, `"r134a"`, `"r1234yf"` |
| `volume`              | number  | no       | Total fluid volume in circuit (m³)                  |
| `flow_rate`           | number  | no       | Nominal flow rate (m³/s)                            |
| `heat_sources`        | array   | no       | Heat source connections (§15.3.4)                       |
| `radiator`            | object  | no       | Heat exchanger (§15.3.1)                            |
| `pump`                | object  | no       | Coolant pump (§15.3.2)                              |
| `thermostat`          | object  | no       | Temperature regulation (§15.3.3)                    |

#### 15.3.1 `radiator`

| Key                   | Type   | Required | Description                                  |
|-----------------------|--------|----------|----------------------------------------------|
| `heat_rejection`      | number | no       | Maximum heat rejection at rated airflow (W)  |
| `area`                | number | no       | Frontal area of the radiator core (m²)       |
| `mass`                | number | no       | Radiator + fluid mass (kg)                   |
| `position`            | [x,y,z]| no      | Radiator position (m)                        |
| `air_flow_dependence` | array  | no       | `[[vehicle_speed_m_s, heat_rejection_W], ...]` |

#### 15.3.2 `pump`

| Key          | Type   | Required | Description                               |
|--------------|--------|----------|-------------------------------------------|
| `type`       | string | no       | `"mechanical"`, `"electric"`              |
| `flow_rate`  | number | no       | Maximum flow rate (m³/s)                  |
| `power`      | number | no       | Power consumption (W) — for electric pump |

#### 15.3.3 `thermostat`

| Key              | Type   | Required | Description                                |
|------------------|--------|----------|--------------------------------------------|
| `open_temperature` | number | no     | Temperature at which thermostat opens (°C) |
| `full_open_temperature` | number | no | Temperature at full opening (°C)          |

#### 15.3.4 `heat_sources` — Component Thermal Connections

Each entry in the `heat_sources` array connects a heat-generating component to this cooling circuit with its thermal resistance.

| Key                   | Type   | Required | Description                                         |
|-----------------------|--------|----------|-----------------------------------------------------|
| `component_ref`       | string | YES      | Id of the heat source (e.g. `"engine"`, `"rear_motor"`, `"battery"`) |
| `thermal_resistance`  | number | no       | Thermal resistance component → coolant (°C/W)       |
| `heat_generation_nominal` | number | no   | Nominal heat generation at steady-state (W)         |
| `heat_generation_max` | number | no       | Peak heat generation (W)                            |

> **Thermal network:** The complete thermal model forms a resistance network: component → coolant (via `thermal_resistance`) → radiator → ambient. A simulator computes steady-state temperatures as: `T_component = T_ambient + Q_total × (R_comp_to_coolant + R_coolant_to_ambient)`. Transient behavior uses the thermal masses (heat capacities) of each node.

---

## 16. `driver_controls` — Electronic Aids & Input Mapping

Parameters defining how driver inputs map to vehicle actuators, and the electronic driving aids that modify those inputs.

### 16.1 Top-Level Properties

| Key               | Type   | Required | Description                              |
|-------------------|--------|----------|------------------------------------------|
| `throttle`        | object | no       | Throttle pedal mapping (§16.2)           |
| `brake_feel`      | object | no       | Brake pedal feel characteristics (§16.3) |
| `traction_control`| object | no       | Traction control system (§16.4)          |
| `launch_control`  | object | no       | Launch control parameters (§16.5)        |

### 16.2 `throttle`

| Key               | Type   | Required | Description                                         |
|-------------------|--------|----------|-----------------------------------------------------|
| `map`             | array  | no       | `[[pedal_position_0_1, throttle_opening_0_1], ...]`  |
| `response_time`   | number | no       | Throttle actuator time constant (s)                 |
| `drive_by_wire`   | boolean| no       | Whether throttle is electronic (true) or cable (false) |

### 16.3 `brake_feel`

| Key                | Type   | Required | Description                                    |
|--------------------|--------|----------|------------------------------------------------|
| `dead_zone`        | number | no       | Pedal travel before brakes engage (m)          |
| `pedal_stiffness`  | number | no       | Pedal resistance (N/m)                         |
| `modulation_curve` | array  | no       | `[[pedal_force_N, line_pressure_Pa], ...]`     |

### 16.4 `traction_control`

| Key                  | Type    | Required | Description                                 |
|----------------------|---------|----------|---------------------------------------------|
| `enabled`            | boolean | no       | Whether TC is present and active            |
| `slip_threshold`     | number  | no       | Wheel slip ratio at which TC intervenes     |
| `intervention_mode`  | string  | no       | `"throttle_cut"`, `"brake_apply"`, `"both"` |
| `response_time`      | number  | no       | Time to full intervention (s)               |

### 16.5 `launch_control`

| Key                | Type    | Required | Description                                  |
|--------------------|---------|----------|----------------------------------------------|
| `enabled`          | boolean | no       | Whether launch control is available          |
| `target_rpm`       | number  | no       | Engine RPM hold point for launch (rev/min)   |
| `slip_target`      | number  | no       | Target wheel slip during launch              |

---

## 17. Extension Mechanism

Any key prefixed with `x_` is reserved for simulator-specific or proprietary data.

```json
{
  "x_beamng": {
    "jbeam_template": "coupe",
    "node_weight": 25
  },
  "x_ac": {
    "ks_version": "1.16",
    "data_folder": "content/cars/my_car"
  }
}
```

Extension keys MAY appear at any level of the hierarchy. Parsers MUST ignore unrecognized `x_` keys without error.

---

## 18. Conversion Reference

### 18.1 Assetto Corsa → SVJ

AC `suspensions.ini` uses a different axis convention:

| AC Axis          | AC Direction | SVJ Mapping |
|------------------|-------------|-------------|
| X (lateral)      | Right+      | Y           |
| Y (vertical)     | Up+         | −Z          |
| Z (longitudinal) | Forward+    | X           |

**Transform:**
```
svj_x =  ac_z
svj_y =  ac_x
svj_z = -ac_y
```

### 18.2 BeamNG.drive → SVJ

BeamNG JBeam uses a Y-up, Z-forward system:

| JBeam Axis | Direction  | SVJ Mapping |
|------------|-----------|-------------|
| X          | Right+    | Y           |
| Y          | Up+       | −Z          |
| Z          | Forward+  | X           |

**Transform:** Same as AC (§18.1).

---

## 19. Validation

Every SVJ release includes a **JSON Schema** file (`svj.schema.json`) that validates:
- Required fields are present.
- Types are correct (number, string, array).
- Enum values match allowed sets.
- Array items have the right shape (e.g. `[x, y, z]` = array of 3 numbers).
- `outboard_ref` strings match the pattern `hardpoints.<name>`.

### 19.1 Usage

```bash
# Python (jsonschema)
python -m jsonschema -i my_car.svj.json svj.schema.json

# Node.js (ajv)
npx ajv validate -s svj.schema.json -d my_car.svj.json
```

### 19.2 Limitations

The JSON Schema does NOT validate:
- `$ref` resolution (must be done by the parser before validation).
- Cross-corner consistency (e.g. matching `bar_id` and `bar_rate` on ARBs).
- Physical plausibility (e.g. CG within wheelbase, positive masses).

These checks are the responsibility of higher-level tools or linters built on top of the schema.

---

## 20. Versioning & Compatibility

- **Major version (1.x):** Breaking changes. Parsers for v0.x are NOT required to read v1.x.
- **Minor version (x.3):** Additive changes only. A v0.3 parser MUST accept v0.2 files (missing fields default to `null`/absent). A v0.2 parser SHOULD accept v0.3 files by ignoring unknown keys.
- **Patch version (x.x.1):** Clarifications, schema fixes, doc edits. No new required fields.

### Changelog

| Version | Changes                                                                                    |
|---------|--------------------------------------------------------------------------------------------|
| 0.1     | Initial draft. Metadata, chassis, basic suspension topology, powertrain.                   |
| 0.2     | Entity-based upright/link model. AC conversion logic. Extension prefix `x_`.               |
| 0.3     | Hybrid file structure (`$ref`). Four-corner suspension. Springs, dampers, ARB, alignment, bump stops. Inertia renamed to ISO convention. Differential added. `outboard_ref` simplified. |
| 0.3.1   | Steering system (§8). Wheel geometry per corner (§9.8). JSON Schema (§19). Tie rod inboard points close kinematic loop. Patch-level versioning introduced. |
| 0.3.2   | Sprung mass decomposition (`mass_bodies` in §7.2). Chassis mass can be broken into individually positioned rigid bodies with own CG and inertia. Composite fields unchanged and required for backward compatibility. |
| 0.4.0   | **Tires**: Top-level tire library (`tires.sets`) with Pacejka MF 5.2/6.2 coefficients, thermal model, wear model, relaxation lengths. Per-corner `tire` reference with pressure/temperature overrides. **Brakes**: Per-corner `brake` assembly (disc with mass/thermal, caliper, pad with μ curve). Top-level `brakes` system (master cylinder, bias, ABS, ESC). All new components carry physical mass and thermal properties. |
| 0.4.1   | Tire set expanded: dimensions, rim specs, construction properties (mass, stiffness, ratings). Wheel vs tire_set relationship documented. |
| 0.94   | **Multi-axle naming convention** (§21.1): formalized `A{n}{side}` corner naming (A1L, A2R, ...). FL/FR/RL/RR are aliases for A1L/A1R/A2L/A2R. Axle metadata array with `steered`, `driven`, `lift` flags. Multi-axle steering linkage with per-axle ratio and phase. Tyrrell P34 example. Backward compatibility rules. |
| 0.95   | **Aerodynamics extension**: 1D/2D lookup maps with interpolation/extrapolation, component-level modeling with cross-influences, wake/dirty air model, ground effect (underbody maps, tire squirt, sealing strips), enhanced active systems (DRS with activation conditions, PID-controlled active wings). **Data provenance**: `data_origin` field in metadata (type, detail, confidence). F1 aero reference example. |
| 0.93   | **Coordinate & consistency fixes** (corrections by external audit): CG coordinates corrected to negative-X (SAE J670 origin at front axle). Tire dimensions removed from corner `wheel` (single source: tire library via `set_ref`). `alignment_convention` added (`relative_to_centerline`). Motion ratio and alignment vs hardpoint precedence documented. Transaxle efficiency warning. |
| 0.92   | **Unified thermal model** + **Coordinate & consistency fixes**: Engine thermal (§10.3.1), gearbox/diff thermal (§10.5.1), brake thermal dynamics (§9.9.4), environment (§15.2), formalized heat sources (§15.3.4). **Fixes:** CG coordinates corrected to negative-X (SAE J670 origin at front axle). Tire dimensions removed from corner `wheel` (single source: tire library via `set_ref`). `alignment_convention` added (`relative_to_centerline` = negative camber always means inward). Motion ratio vs hardpoint precedence documented. Alignment vs hardpoint precedence documented. Transaxle efficiency double-counting warning added. | **Unified thermal model**: Engine thermal (§10.3.1) — heat capacity, warmup, friction vs oil temp, power derating vs coolant temp. Gearbox thermal (§10.5.1) — oil capacity, efficiency vs temp. Differential thermal (same schema). Brake thermal dynamics (§9.9.4) — disc/pad/caliper conductance network, speed-dependent cooling, heat generation formula, fade model description. Cooling expanded: `environment` (§15.2) with ambient temperature/pressure/humidity/altitude/wind. Heat sources formalized (§15.3.4) with `thermal_resistance` and heat generation rates connecting components to circuits. Complete thermal resistance network documented. |
| 0.91   | **v1.0 Release Candidate.** Cross-reference audit (0 broken). README rewritten. Skeleton examples for FF/AWD-EV/4WD topologies. Schema error-path validated. Spec freeze for parser development. |
| 0.9.0   | **Multi-model tire support**: `tmeasy` (§11.10) — semi-empirical model with ~20 intuitive parameters (stiffness, peak force, sliding plateau, load/camber sensitivity, pneumatic trail). `brush` (§11.11) — physics-first model from contact patch geometry and tread stiffness. `external_models[]` (§11.12) — references to proprietary parameter files (FTire .fti, CDTire .cdt, MF-Swift .tir, PAC2002, RMOD-K) with source lab, test conditions, version tracking. Model fidelity guide (§11.12.1) comparing all 6 tiers from brush to CDTire 50. |
| 0.8.3   | **Position/CG audit**: added `cg_position` to upright, driveshaft, half_shaft. Added `position` to clutch, booster, master_cylinder, brake caliper. Clarified inertia conventions: all tensors are about component's own CG in vehicle frame axes. Scalar rotational inertias documented as spin-axis values for drivetrain dynamics. Parallel-axis theorem reference added. |
| 0.8.2   | **Inertia tensor completion**: added `Ixy` and `Iyz` cross-products to all inertia objects (chassis, mass_bodies, upright, axle_body, aero_component, battery). Full 6-component symmetric tensor documented with matrix notation. Default 0 if absent (symmetric vehicle assumption). |
| 0.8.1   | **Mass/inertia audit patch**: added missing fields across spec — `upright.inertia` tensor, `link.mass`/`inertia`/`cg_position`/`mass_distribution`, `spring.mass`, `damper.mass`, `arb.mass`, `disc.rotational_inertia`, `steering.rack_mass`, `clutch.mass`. Restored inertia tensors to all 14 mass_bodies in template. Link mass_distribution.sprung_fraction documents sprung/unsprung split. |
| 0.8.0   | **Compliance** (§9.2.5): three-tier model — Tier 1 rigid, Tier 2 corner-level scalars (toe/camber/caster/lateral/longitudinal stiffness), Tier 3 full 6-DOF bushing per joint (rate_x/y/z, rate_rx/ry/rz, damping, non-linear curves, preload). Bushings array on link inboard points + outboard. **Chassis stiffness** (§7.3): torsional and bending stiffness with typical values. **Static setup** (§9.12): ride height, corner weights, spring compression. **Driver controls** (§16): throttle map, brake feel, traction control, launch control. |
| 0.7.0   | **Electric/Hybrid** (§14): `hybrid_type`, `motors[]` with P0–P4/in-wheel placement, torque curves, efficiency maps, gear reduction. `battery` with chemistry, capacity, voltage, cell config, internal resistance, SOC, thermal management. `inverters`. `regen` (max torque/power, blend with hydraulic, coast regen for one-pedal). **Cooling** (§15): thermal circuit model with `circuits[]` — coolant loops with radiator (heat rejection, area, speed-dependent), pump, thermostat. Updated roadmap with multi-axle/truck extension planned. |
| 0.6.0   | **Drivetrain rewrite** (§10): `layout` (FR/FF/MR/RR/AWD/4WD), `engine` expanded (position, mass, compression_ratio), new `clutch` (type, torque, inertia), `gearbox` replaces transmission (input/output inertia, efficiency, shift_time, output_flange position), `transfer_case` (hi/lo ratio, torque split, center diff), `driveshafts` array (propshafts with joint positions and types), `differentials` array with `final_drive` moved here (+ ramp angles, efficiency, input/output flange positions), `half_shafts` per driven corner (CV joint inner/outer positions and types, plunge, mass, inertia). Geometry consistency between CV joints and upright hardpoints documented. `cv_joint_outer` added to recommended hardpoint names. Drivetrain topology examples for RWD/FF/AWD/4WD. Inertia chain formula. |
| 0.5.3   | **Suspension topology guide** (§9.2.1): comprehensive per-type documentation with minimum required links, hardpoints, and notes for all 10 system_types. New types: `chapman_strut`, `torsion_beam`. New topology fields: `axle_body` (§9.2.4) for shared rigid bodies (solid_axle, de_dion, torsion_beam) with mass, position, inertia, torsional stiffness. `lateral_location` field for dependent types. |
| 0.5.2   | Brakes rewritten: `pedal` (ratio, travel), `booster` (type, boost_ratio, diameter, max_force, mass), `master_cylinder` expanded (bore_primary/bore_secondary for tandem, stroke), `circuit_type` (dual_diagonal/front_rear_split), ABS gains `ebd` and `brake_assist`, ESC gains `track_mode`. Complete force chain documented from pedal to wheel (§12.6). Hydraulic ratio and system ratio formulas. |
| 0.5.1   | Steering expanded: `max_steer_angle`, `lock_to_lock_turns`, `turning_circle`, `steering_wheel` (diameter, mass). Template migrated to Mazda MX-5 ND2 2024 — factory specs where available, engineering estimates marked with `_est`. Added `x_data_sources` to metadata. |
| 0.5.0   | **Aerodynamics** (§13): Reference conditions (frontal/planform area, air density). Static coefficients (Cd, Cl, Cl_front/rear, Cs, moment coefficients). Sensitivity maps (yaw, ride height, pitch). Component-based model (wing, splitter, diffuser — each with position, mass, Cd/Cl contributions, adjustable settings). Active systems (DRS, active ride height, active wing with angle/Cl/Cd ranges). |

---

## 21. Roadmap

| Section           | Version  | Status                                             |
|-------------------|---------|----------------------------------------------------|
| Metadata, chassis, CG, inertia | v0.1–0.3 | ✅ Done                               |
| Steering          | v0.3.1   | ✅ Done — rack, EPAS, steering wheel               |
| Mass decomposition| v0.3.2   | ✅ Done — mass_bodies with 7 categories             |
| Suspension topology| v0.5.3  | ✅ Done — 10 system_types with full guide           |
| Tires             | v0.4     | ✅ Done — Pacejka MF5.2/6.2, thermal, wear          |
| Brakes            | v0.5.2   | ✅ Done — per-corner + full force chain              |
| Aerodynamics      | v0.5     | ✅ Done — coefficients, maps, components, active     |
| Drivetrain        | v0.6     | ✅ Done — layout, clutch, gearbox, TC, propshafts, diffs, half-shafts, CV joints |
| Electric/Hybrid   | v0.7     | ✅ Done — motors (P0–P4), battery, inverters, regen  |
| Cooling           | v0.7     | ✅ Done — thermal circuits, radiator, pump, thermostat |
| **Multi-axle / Trucks** | **v1.x / Addendum** | **Planned** — see §20.1 |

### 21.1 Multi-Axle & Commercial Vehicle Extension

The current SVJ specification assumes a **4-corner vehicle** (FL, FR, RL, RR). This covers the vast majority of passenger cars, sports cars, and light vehicles. However, trucks, buses, trailers, and special vehicles require support for:

- **N axles** with M wheels per axle (e.g. 6×4, 8×8, tandem rear)
- **Steered rear axles** (all-wheel steering, trailer steering)
- **Multi-steered-axle vehicles** (Tyrrell P34: two steered front axles)
- **Lift axles** (raiseable non-driven axles)
- **Articulated vehicles** (tractor + trailer with fifth wheel coupling)
- **Multiple drive units** (tandem differentials, inter-axle diffs)

This will be addressed as an **addendum to v1.x** (not a separate standard), extending the `suspension` and `powertrain` structures to use named axles and arbitrary corner counts while maintaining full backward compatibility with the 4-corner model.

#### 21.1.1 Corner Naming Convention

**Canonical form:** `A{axle_number}{side}`

| Token | Meaning | Values |
|-------|---------|--------|
| `A`   | Literal prefix | Always `A` |
| `{axle_number}` | Axle index, front to rear | `1`, `2`, `3`, ... |
| `{side}` | Vehicle side | `L` (left/driver-side LHD), `R` (right/passenger-side LHD) |

**Standard 2-axle aliases:** For standard 4-corner vehicles, `FL`/`FR`/`RL`/`RR` remain valid as aliases for `A1L`/`A1R`/`A2L`/`A2R`. A parser MUST accept both forms. When `axles[]` is absent, `FL`/`FR`/`RL`/`RR` is assumed.

| Vehicle | Axle count | Corner names |
|---------|-----------|--------------|
| Standard car | 2 | A1L, A1R, A2L, A2R (or FL, FR, RL, RR) |
| Tyrrell P34 (6-wheel F1) | 3 | A1L, A1R, A2L, A2R, A3L, A3R |
| 6×4 truck | 3 | A1L, A1R, A2L, A2R, A3L, A3R |
| 8×8 military | 4 | A1L, A1R, A2L, A2R, A3L, A3R, A4L, A4R |
| Tractor + semi-trailer | Separate SVJ files, coupled via fifth-wheel reference |

#### 21.1.2 `axles` Array

The `axles` array is optional metadata that declares the axle topology. Each entry:

| Key        | Type    | Required | Description                                              |
|------------|---------|----------|----------------------------------------------------------|
| `id`       | string  | YES      | Canonical axle name: `A1`, `A2`, `A3`, ...               |
| `steered`  | boolean | no       | Whether this axle has steering input                     |
| `driven`   | boolean | no       | Whether this axle receives drive torque                  |
| `lift`     | boolean | no       | Whether this axle can be raised (tag axle)               |
| `corners`  | array   | YES      | Corner keys: `["A1L", "A1R"]`                            |
| `position_x` | number | no     | Axle center X position in vehicle frame (m)              |

Example — Tyrrell P34:

```json
{
  "suspension": {
    "axles": [
      { "id": "A1", "steered": true,  "driven": false, "corners": ["A1L", "A1R"], "position_x": 0.0 },
      { "id": "A2", "steered": true,  "driven": false, "corners": ["A2L", "A2R"], "position_x": -0.60 },
      { "id": "A3", "steered": false, "driven": true,  "corners": ["A3L", "A3R"], "position_x": -2.70 }
    ],
    "A1L": { "topology": { "system_type": "double_wishbone" }, "wheel": { "rim_diameter": 0.254, "set_ref": "front_10inch" } },
    "A1R": { "..." : "mirror of A1L" },
    "A2L": { "topology": { "system_type": "double_wishbone" }, "wheel": { "rim_diameter": 0.254, "set_ref": "front_10inch" } },
    "A2R": { "..." : "mirror of A2L" },
    "A3L": { "topology": { "system_type": "double_wishbone" }, "wheel": { "rim_diameter": 0.330, "set_ref": "rear_standard" } },
    "A3R": { "..." : "mirror of A3L" }
  }
}
```

#### 21.1.3 Multi-Axle Steering

When multiple axles are steered, the steering section extends to map rack input to each axle:

```json
{
  "steering": {
    "type": "rack_and_pinion",
    "axle_steering": [
      { "axle_ref": "A1", "ratio": 12.0, "phase": 1.0 },
      { "axle_ref": "A2", "ratio": 14.0, "phase": 1.0 },
      { "axle_ref": "A3", "ratio": 18.0, "phase": -1.0 }
    ]
  }
}
```

Where `phase` = 1.0 means same direction as driver input (front-steer), `phase` = -1.0 means counter-steer (rear-steer for tight turning). Each steered axle can have a different ratio.

#### 21.1.4 Backward Compatibility

A parser reading a multi-axle file SHOULD fall back gracefully:
- If `axles` is absent and only `FL`/`FR`/`RL`/`RR` keys exist, treat as standard 2-axle.
- If `axles` is present, use it to discover the topology and corner names.
- A 2-axle file with `axles` present is redundant but valid — the `axles` array simply confirms the FL/FR/RL/RR layout.
- A parser that does not support multi-axle SHOULD warn and process only corners it recognizes (FL/FR/RL/RR), ignoring the rest.
