# Standard Vehicle JSON (SVJ) Specification v0.102

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

> **Note:** All hardpoint coordinates are expressed in the **vehicle reference frame** (global body-fixed). Station-specific data (FL, FR, RL, RR, or `A{n}L`/`A{n}R`/`A{n}C`, §23.1) uses the appropriate Y sign for each side: negative Y = left, positive Y = right, Y ≈ 0 for a centreline station.

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

### 3.4 Override Files *(v0.98)*

`$ref` (§3.2) replaces a key with an **entire** external file — useful for splitting a vehicle into modules, but not for describing a small variant of an existing vehicle (a DOE parameter sweep, a supplier hand-off that should only disclose a subset of changed values, a "stiffer front spring" setup sheet). Duplicating the whole file for a one-field change is error-prone and makes diffs unreadable.

An **override file** (`*.svj-override.json`) is a separate file type that names a `base` SVJ file and a `patch` object applied on top of it using **JSON Merge Patch** semantics ([RFC 7396](https://www.rfc-editor.org/rfc/rfc7396)).

```json
{
  "_metadata": {
    "specification": "SVJ-OVERRIDE",
    "version": "0.98",
    "base": "./mazda_mx5_nd2_2024.svj.json",
    "description": "Stiffer front spring, DOE variant 3"
  },
  "patch": {
    "suspension": {
      "FL": { "spring": { "rate": 32000 } },
      "FR": { "spring": { "rate": 32000 } }
    }
  }
}
```

**Resolution rules:**

1. `base` is resolved relative to the override file's own location, using the same relative-path rule as `$ref` (§3.2).
2. The resolved base document (with its own `$ref` entries already expanded) is the starting document.
3. `patch` is applied as an RFC 7396 JSON Merge Patch: any key present in `patch` replaces the corresponding key in the base; `null` deletes a key; objects are merged recursively; arrays are replaced wholesale (merge patch does not diff array elements).
4. The result is a complete, standalone SVJ document and MUST validate against `svj.schema.json` like any other SVJ file.

**Why merge patch and not a custom diff format:** RFC 7396 is a formal, minimal standard with existing library support in every language, consistent with SVJ's "validatable" design principle (§1) — no bespoke patch semantics to document or get wrong.

**On IP protection:** SVJ is plain, human-readable JSON by design (§1, Design Principles) and does not define an encryption scheme. An override file provides a practical, low-friction alternative for supplier collaboration: a supplier can ship only the `patch` for the subsystem they were asked to tune, without ever receiving (or disclosing) the full vehicle. Encrypting the base or patch file itself, if required, is a transport/storage concern outside this spec.

---

## 4. Top-Level Structure

```json
{
  "_metadata": { },
  "vehicle_info": { },
  "chassis": { },
  "steering": { },
  "suspension": { },
  "axles": [ ],
  "suspension_couplings": [ ],
  "tires": { },
  "brakes": { },
  "powertrain": { },
  "aerodynamics": { },
  "validation": { },
  "benchmarks": [ ],
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
| `drive_type` | string  | no       | One of: `"FWD"`, `"RWD"`, `"AWD"`, `"4WD"`, `"none"` (trailers) |
| `wheel_formula` | string | no     | Stations × driven[/steered], e.g. `"6x4"`, `"8x8/4"` — counts hubs, not tyres (§23.6) |
| `vehicle_class` | string | no     | `"passenger_car"`, `"race_car"`, `"light_truck"`, `"heavy_truck"`, `"tractor_unit"`, `"trailer"`, `"semi_trailer"`, `"modular_trailer"`, `"bus"`, `"off_highway"`, `"military"`, `"special"` |

---

## 7. `chassis`

| Key                        | Type       | Required | Description                                            |
|----------------------------|------------|----------|--------------------------------------------------------|
| `mass_total`               | number     | YES      | Total vehicle mass including fluids (kg)                |
| `mass_unsprung_per_corner` | object     | no       | Per station, same keys as `suspension`: `{"FL": n, ...}` or `{"A1L": n, ...}` (kg) |
| `wheelbase`                | number     | YES      | Front axle to rear axle distance (m). Multi-axle: `A1` to last axle (§23.6) |
| `wheelbase_reference`      | string     | no       | How `wheelbase` is measured: `"last_axle"` (default), `"bogie_centre"`, `"bogie_centres"`, `"first_rear_axle"`, `"theoretical"`, `"explicit"` (§23.6) |
| `wheelbase_from` / `wheelbase_to` | string | no     | Axle id or `axle_groups` id bounding the wheelbase when `wheelbase_reference` is `"explicit"` (§23.6) |
| `plated_masses`            | object     | no       | Plated masses in kg: `gross_vehicle_mass_design`, `gross_vehicle_mass_legal`, `gross_combination_mass_design`, `gross_combination_mass_legal`, `payload`, `jurisdiction` *(v0.99.1)* |
| `track_front`              | number     | YES      | Front track width, center-to-center contact patches (m) — track at `A1` |
| `track_rear`               | number     | YES      | Rear track width (m) — track at the last axle; `0` for a single centreline wheel |
| `center_of_gravity`        | [x, y, z]  | YES      | CG position in vehicle reference frame (m)              |
| `inertia`                  | object     | no       | See §7.1                                                |
| `mass_bodies_complete`     | boolean    | no       | `true`: `mass_bodies` is an exhaustive decomposition (Σ bodies + Σ unsprung = `mass_total`); default `false`: a partial list (§7.2.2) *(v0.99.6)* |
| `markers`                  | object     | no       | Named frames fixed to the chassis (hinge points, cylinder bases, hitch pins); the chassis side of a constraint (§24.2) *(v0.99.5)* |

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
| `name`        | string  | no       | Short display label (e.g. `"Front-left door"`); `id` stays the stable key *(v0.99.7, §24.2)* |
| `description` | string  | no       | Human-readable label                                 |
| `category`    | string  | no       | See §7.2.1 for recommended values                    |
| `mass`        | number  | YES      | Body mass (kg); must be > 0 unless the body is generated (`x_derived: true`, §25.8), where 0 means the source data gave none |
| `position`    | [x,y,z] | YES     | CG of this body in the vehicle reference frame (m)    |
| `inertia`     | object \| 3×3 | no  | Inertia tensor about this body's own CG: the §7.1 object, or the full symmetric matrix *(v0.99.5, §24.2)* |
| `inertia_orientation` | [qx,qy,qz,qw] | no | Frame in which `inertia` is expressed (e.g. principal axes), relative to the vehicle axes; default identity *(v0.99.5)* |
| `parent`      | string  | no       | Parent body id; `chassis` (default), `ground` or another body. A body no constraint mentions is welded to it (§24.2) |
| `markers`     | object  | no       | Named frames `{position, orientation}` fixed to this body (§24.2) |

#### 7.2.1 Recommended `category` Values

| Value          | Description                                                    |
|----------------|----------------------------------------------------------------|
| `"structural"` | BIW, monocoque, subframes, roll cage                           |
| `"powertrain"` | Engine, transmission, exhaust, driveshafts                     |
| `"fluid"`      | Fuel, coolant, oil (mass varies during operation)              |
| `"payload"`    | Driver, passenger, luggage                                     |
| `"ballast"`    | Added weight for balance tuning                                |
| `"electrical"` | Battery pack, motors, inverters (EV/hybrid)                    |
| `"attachment"` | Loader, implement, body or other equipment that is not part of the base vehicle *(v0.99.5)* |
| `"other"`      | Anything that does not fit the above                           |

#### 7.2.2 Relationship to Composite Fields

When `mass_bodies` is present:

1. **`mass_total`** remains REQUIRED and represents the fully resolved vehicle mass. It MUST include both sprung and unsprung contributions, **and every body listed**. The list may be **partial** (the movable parts and attachments of §24, say) — the rest of the vehicle is then everything not listed, as an implicit body welded to the chassis. A conforming validator MAY check:
   ```
   Σ mass_bodies[i].mass + Σ mass_unsprung_per_corner[j]  ≤  mass_total      (the unsprung term only without wheel_stations[])
   ```
   and, only when the file states `chassis.mass_bodies_complete: true`, that the two sides are equal (an exhaustive decomposition).

2. **`center_of_gravity`** remains REQUIRED and represents the composite CG of the entire vehicle. A validator MAY check consistency with the mass-weighted centroid of all bodies and unsprung masses.

3. **`inertia`** remains OPTIONAL at the top level. When present alongside `mass_bodies`, it represents the pre-computed composite inertia (parallel-axis contributions already summed). A parser MAY recompute it from the bodies and compare.

> **Design rationale:** Keeping the composite fields required means that simple parsers that only need total mass and CG can ignore `mass_bodies` entirely. Advanced tools can use the decomposition for detailed dynamics or to reposition components.

> **Note on unsprung mass:** In a file with the corner-based `suspension` section the bodies in `mass_bodies` represent the **sprung** portion; unsprung masses are captured per-corner in `mass_unsprung_per_corner` (wheel assemblies, upright, lower link). Do not double-count. In a unified file (`wheel_stations[]`, §25) the uprights, arms and wheels are themselves bodies of `mass_bodies`, so the sum above is taken over the bodies alone and `mass_unsprung_per_corner` is only a per-corner summary of the same masses.

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
| `axle_ref`           | string  | no       | Axle driven by the primary steering gear. Default `"A1"` (§8.6)    |
| `additional_axles`   | array   | no       | Further steered axles (§8.6)                                       |

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

### 8.6 `additional_axles` — Multi-Axle Steering *(v0.99)*

The rack/box in §8.1 steers `steering.axle_ref` (default `A1`). Every other steered axle is listed here. Each must also be `steered: true` in `axles` (§23.2).

| Key                   | Type    | Required | Description                                                          |
|-----------------------|---------|----------|----------------------------------------------------------------------|
| `axle_ref`            | string  | YES      | `"A2"`, `"A3"`, …                                                    |
| `type`                | string  | YES      | See below                                                            |
| `ratio`               | number  | no       | Road-wheel angle of this axle per road-wheel angle of the primary axle (dimensionless, positive magnitude) |
| `phase`               | string  | no       | `"same"` (turns the same way as the primary axle) or `"opposed"` (counter-steer) |
| `max_steer_angle`     | number  | no       | Maximum road-wheel angle on this axle (rad)                          |
| `speed_lockout`       | number  | no       | Axle is locked straight above this speed (m/s)                       |
| `lock_in_reverse`     | boolean | no       | Axle is locked straight in reverse (typical of self-steer axles)     |
| `caster`              | number  | no       | `self_steer`: caster angle producing the self-steering moment (rad)  |
| `centering_stiffness` | number  | no       | `self_steer`: return-to-centre stiffness (Nm/rad)                    |
| `linkage_points`      | array   | no       | `[x,y,z]` points of the drag links / relay arms, if known            |

| `type`             | Meaning                                                                         | Examples |
|--------------------|---------------------------------------------------------------------------------|----------|
| `mechanical_link`  | Driven from the primary gear by drag links and relay levers; `ratio` is fixed  | Twin-steer 8×4 trucks, Tatra 8×8, Tyrrell P34 |
| `self_steer`       | Passive: follows the path through caster; no link to the steering wheel; `ratio` is nominal | Steerable lift axles, trailer self-tracking axles |
| `command_steer`    | Linked to trailer articulation angle or a separate mechanism                   | Command-steer semi-trailers |
| `hydraulic`        | Hydraulic master/slave cylinders                                               | Modular trailers, cranes |
| `active`           | Electronically controlled; `ratio` and `phase` describe the nominal map        | Rear-wheel steering, rear-steer axles |

---

## 9. `suspension` *(deprecated since v0.100)*

> **Deprecated.** From v0.100 a suspension is described by bodies, joints and elements plus `wheel_stations[]` (§25). This section is still accepted for one more release (validators warn) and is removed after it; `tools/migrate_suspension.py` converts a file. It stays documented here for readers of older files.

The suspension object contains one entry per wheel station. A two-axle vehicle uses the four legacy names:

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

Vehicles with any number of axles use `A{n}{L|R|C}` names (`A1L`, `A1R`, `A2L`, … `A3R`); `FL/FR/RL/RR` are aliases of `A1L/A1R/A2L/A2R`. The two forms must not be mixed. See §23.1.

Each corner is a **complete, independent definition**. There is no inheritance or mirroring between corners. Load sharing between axles (walking beams, rockers, air/hydraulic circuits) is described in `suspension_couplings` (§23.5), not by merging corners.

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
| `"swing_axle"`        | Independent      | Half-axle pivoting near the vehicle centreline *(v0.99)* |
| `"parallelogram"`     | Dependent        | Beam axle located by parallel upper/lower beams (lift axles) — axle_body required *(v0.99)* |
| `"pendulum_axle"`     | Dependent        | Beam axle oscillating about a longitudinal pivot — axle_body required *(v0.99)* |
| `"custom"`            | —                | Non-standard; describe in `x_` extension               |

> **Trailing arms locating a beam axle.** `trailing_arm` may be combined with an `axle_body` when both arms clamp one rigid axle (typical air-sprung trailer and tag axles). The arms then locate the axle longitudinally and vertically; the axle body makes the two sides dependent.

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
| `strut` | `strut` | 1 point (strut top mount / turret, on the body) | `hardpoints.strut_lower` | The link runs from the body-side top mount down to the strut's **lower clamp on the upright** (`strut_lower`). Its outboard end is *not* the top (v0.99.4) |
| `lower_control_arm` | `arm` | 2 points (front + rear pivots) | `hardpoints.lower_ball_joint` | Single A-arm or L-arm |
| `steering_tie_rod` | `rod` | 1 point (rack end) | `hardpoints.steering_tie_rod_end` | Front axle only |

**Minimum hardpoints:** `strut_top`, `strut_lower`, `lower_ball_joint`, `wheel_center`. Add `steering_tie_rod_end` on steered axles.

**Note:** Spring and damper `inboard_mount` / `outboard_mount` are typically the same as the strut's ends: `inboard_mount` = `strut_top`, `outboard_mount` = `strut_lower`. The `strut` link type signals to parsers that this link is telescopic (piston in cylinder), not a rigid body.

> **Strut end points (v0.99.4):** before v0.99.4 this table gave `strut_top` as both ends of the strut link, which collapses it to zero length and leaves a solver unable to locate the corner. The outboard end is the lower clamp on the knuckle, `strut_lower`. `tools/multibody_check.py` warns about any link whose inboard point coincides with its outboard hardpoint. Files that still reference `strut_top` as `outboard_ref` stay schema-valid; add `strut_lower` and repoint the link.

**Examples:** Most FWD front suspensions, VW Golf, Ford Focus (front), Toyota Corolla.

---

##### `chapman_strut` — Chapman Strut

Functionally identical to MacPherson but used on **driven rear axles**. The driveshaft passes through or alongside the strut. Topology is the same as `macpherson` minus the steering tie rod.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `strut` | `strut` | 1 point (strut top mount, on the body) | `hardpoints.strut_lower` | Lower clamp on the upright, as for `macpherson` *(v0.99.4)* |
| `lower_control_arm` | `arm` | 2 points | `hardpoints.lower_ball_joint` | |
| `toe_link` | `rod` | 1 point | `hardpoints.toe_link_end` | Optional, for rear toe control |

**Minimum hardpoints:** `strut_top`, `strut_lower`, `lower_ball_joint`, `wheel_center`.

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

##### `swing_axle` — Swing Axle / Swing Half-Axle *(v0.99)*

Each wheel is carried on a rigid half-axle (or arm) that pivots about an axis close to the vehicle centreline, usually at or near the differential. The wheel moves on an arc about that pivot, so camber changes strongly with travel and the roll centre is high. A low pivot reduces jacking.

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `swing_arm` | `arm` | 1 point (single pivot) or 2 points (pivot axis) | `hardpoints.wheel_center` | Pivot near centreline; for 2 points the axis is usually longitudinal |

**Minimum hardpoints:** `wheel_center`, `damper_outboard`.

**Driveline:** the half-shaft has a single inboard joint at (or close to) the pivot and no outer CV joint; `half_shafts.<corner>.cv_inner.position` SHOULD coincide with the swing pivot.

**Examples:** Tatra 815 (all axles, half-axles on a central backbone tube), VW Beetle (rear, early), Triumph Herald/Spitfire (rear), Mercedes-Benz low-pivot swing axle.

---

##### `parallelogram` — Parallelogram Beam Axle *(v0.99)*

A beam axle located by an upper and a lower longitudinal beam on each side, of (nearly) equal length and parallel, forming a four-bar linkage. The axle translates vertically without changing pitch, so caster stays constant — essential for steerable lift axles.

**`axle_body` REQUIRED.**

**Minimum links per side:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `upper_beam` | `arm` or `rod` | 1–2 points (frame hanger) | `hardpoints.upper_beam_end` | |
| `lower_beam` | `arm` or `rod` | 1–2 points (frame hanger) | `hardpoints.lower_beam_end` | Parallel to `upper_beam` |

**Minimum hardpoints:** `upper_beam_end`, `lower_beam_end`, `wheel_center`.

**Lift:** lift and load air springs are described with `axles[].liftable` / `axles[].lift` (§23.2); the corner `spring` is the load spring.

**Examples:** Hendrickson COMPOSILITE / TOUGHLIFT and Link lift axles (pusher and tag).

---

##### `pendulum_axle` — Pendulum / Oscillating Axle *(v0.99)*

A rigid beam axle that rotates about a single longitudinal pivot at its centre. Relative to its carrier it has only a roll degree of freedom. It may be unsprung (loaders, articulated haulers) or supported by a hydraulic cylinder (modular trailer axle lines).

**`axle_body` REQUIRED**, with `pendulum_pivot` (and optionally `pendulum_axis`, `roll_limit`).

**Minimum links:**

| Link name | type | inboard_points | outboard_ref | Notes |
|-----------|------|---------------|--------------|-------|
| `pendulum_pin` | `pivot` | 2 points defining the pivot axis (carrier side) | `hardpoints.pendulum_pivot` | Revolute joint; may appear on one corner only |

**Minimum hardpoints:** `wheel_center`, `pendulum_pivot`.

**Springing:** unsprung → `spring.type: "none"`, `damper.type: "none"`; hydraulically supported → `spring.type: "hydraulic"` plus a `hydraulic_circuit` coupling (§23.5). `lateral_location: "pendulum_pin"`.

**Examples:** Hydraulic modular trailers and SPMT axle lines, articulated dump truck front axle, wheel loader rear axle.

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
| `body_ref`    | string | no       | `chassis.mass_bodies[].id` of this upright as a rigid body *(v0.96, §9.2.3.3)* |

##### 9.2.2.1 Standard Hardpoint Names

These names are RECOMMENDED for interoperability. Additional custom hardpoints MAY be added.

| Key                      | Description                                      |
|--------------------------|--------------------------------------------------|
| `upper_ball_joint`       | Upper arm → upright connection                   |
| `lower_ball_joint`       | Lower arm → upright connection                   |
| `steering_tie_rod_end`   | Steering link → upright connection               |
| `wheel_center`           | Geometric center of the wheel                    |
| `strut_top`              | MacPherson / Chapman strut upper mount, **on the body** (strut link inboard point; spring/damper `inboard_mount`) |
| `strut_lower`            | Strut lower clamp **on the upright**: the strut link's `outboard_ref` and the spring/damper `outboard_mount` *(v0.99.4)* |
| `damper_outboard`        | Damper → upright attachment (if direct)          |
| `arb_drop_link_outboard` | ARB drop link → upright/arm attachment           |
| `cv_joint_outer`         | Outboard CV joint center — must match `half_shafts.*.cv_outer.position` (driven corners only) |

Hardpoint values are `[x, y, z]` arrays in the **vehicle reference frame**, or marker objects `{position, orientation}` (§9.2.3.3).

#### 9.2.3 `links`

Each link is a rigid rod or arm connecting the chassis (inboard) to the upright (outboard).

| Key             | Type    | Required | Description                                            |
|-----------------|---------|----------|--------------------------------------------------------|
| `name`             | string  | YES      | Descriptive name (e.g. `"upper_wishbone"`, `"toe_link"`)|
| `type`             | string  | no       | `"arm"` (default), `"rod"`, `"strut"`, `"torque_rod"` (reacts drive/brake torque on a beam axle), `"pivot"` (zero-length revolute, e.g. `pendulum_pin`) |
| `inboard_points`   | array   | YES      | Array of `[x, y, z]` chassis-side pickup points        |
| `outboard_ref`     | string  | YES      | Dot-path to an upright hardpoint (see §9.2.3.1)       |
| `mass`             | number  | no       | Link total mass (kg)                                   |
| `inertia`          | number  | no       | Rotational inertia about the link's pivot axis (kg·m²). For an A-arm, this is the axis defined by the two `inboard_points`. |
| `cg_position`      | [x,y,z] | no      | Link CG in vehicle reference frame (m). If absent, parsers MAY estimate as the midpoint between mean(inboard_points) and the outboard hardpoint. |
| `mass_distribution` | object | no      | `{"sprung_fraction": 0.5}` — fraction of mass that is sprung. Default 0.5 if absent. |
| `bushings`         | array   | no       | Bushing at each inboard point — Tier 3 compliance (§9.2.5) |
| `outboard_bushing` | object  | no      | Bushing at the outboard joint (§9.2.5) — if not a rigid ball joint |
| `joint_type`       | string  | no       | Outboard joint: `spherical`, `revolute`, `cylindrical`, `translational`, `universal`, `fixed`, `planar`, `convel`, `hooke`; inferred when absent (§9.2.3.2) |
| `inboard_joint_type` | string | no      | Inboard joint: `revolute`, `spherical`, `cylindrical`, `fixed`, `bushing`; inferred when absent (§9.2.3.2) |
| `body_ref`         | string  | no       | `chassis.mass_bodies[].id` of this link as a rigid body (§9.2.3.3) |

##### 9.2.3.1 `outboard_ref` Path Resolution

The path is resolved **within the same corner**, starting from `topology.upright`. Example:

```
"outboard_ref": "hardpoints.upper_ball_joint"
```

This resolves to: `suspension.<corner>.topology.upright.hardpoints.upper_ball_joint`

> **Migration from v0.2:** Old-style refs like `"upright_front.hardpoints.X"` are DEPRECATED. Use `"hardpoints.X"` instead.

##### 9.2.3.2 Joint types and inference *(v0.96 fields; inference rules normative from v0.99.3)*

`joint_type` is the joint at the **outboard** connection (link ↔ upright); `inboard_joint_type` is the joint at the **inboard** (link ↔ chassis) connection(s). When a link omits one, converters MUST resolve it with the table below (`tools/multibody_check.py::infer_joint_types`, `svj.multibody.infer_joint_types` and `Vehicle.joints()` implement it identically). An explicit value always wins. A dash means *not inferable*: the file must state the joint explicitly for a multibody export.

| Link `type` | `system_type` | Outboard | Inboard |
|---|---|---|---|
| `arm` | `double_wishbone`, `macpherson`, `chapman_strut`, `multi_link`, `custom` | `spherical` | `revolute` |
| `arm` | `trailing_arm`, `semi_trailing_arm`, `torsion_beam`, `parallelogram` | `revolute` | `revolute` |
| `rod`, `torque_rod` | any | `spherical` | `spherical` |
| `strut` | `macpherson`, `chapman_strut` | `translational` | `fixed` |
| `pivot` | `pendulum_axle` | `revolute` | — |
| anything else (`arm` on `solid_axle`, `de_dion`, `swing_axle`, leaf springs, …) | | — | — |

> Several shipped files state `fixed` for the outboard joint of a trailing or torsion arm whose upright is rigid with the arm; the explicit value overrides the inferred `revolute`.

##### 9.2.3.3 Body references and orientation frames *(v0.96)*

- `body_ref` (on `upright` and on a link) names a `chassis.mass_bodies[].id` that represents the part as a rigid body. Each body can be claimed by at most one part. `mass_body.parent` is `"chassis"`, `"ground"` or another body id and must not form a cycle.
- Where both exist, the part's `mass` / `cg_position` should agree with the body's `mass` / `position` (checker tolerance 1 % and 5 mm).
- A hardpoint, or a spring/damper mount, is either `[x, y, z]` or `{ "position": [x, y, z], "orientation": [qx, qy, qz, qw] }`. The quaternion is a unit quaternion in the vehicle frame; the checker errors when its norm deviates from 1 by more than 0.01 and warns above 0.001. `bushings[].orientation` and `mass_body.markers.*.orientation` follow the same rule.
- `tools/multibody_check.py` (run by `tools/validate.py`; mirrored as `svj-py/svj/multibody.py`) enforces: unique mass-body ids, `parent` resolves and is acyclic, `body_ref` resolves and is unique, `outboard_ref` names an upright hardpoint, `bushings` count matches `inboard_points`, unit quaternions, and warns on mass / CG mismatches and on an `arm` with two inboard points and a `spherical` inboard joint.

#### 9.2.4 `axle_body` — Shared Rigid Body

Required for `torsion_beam`, `solid_axle`, `de_dion`, `parallelogram` and `pendulum_axle`; optional for `trailing_arm` locating a beam axle. Represents the rigid element that couples or connects both sides of **one** axle.

| Key                    | Type    | Required | Description                                              |
|------------------------|---------|----------|----------------------------------------------------------|
| `id`                   | string  | YES      | Shared identifier (same on both corners of the axle)     |
| `mass`                 | number  | no       | Total mass of the shared body (kg)                       |
| `position`             | [x,y,z] | no      | CG position of the shared body (m)                       |
| `inertia`              | object  | no       | Inertia tensor about CG (Ixx/Iyy/Izz/Ixz)              |
| `torsional_stiffness`  | number  | no       | Beam torsional stiffness (Nm/rad) — `torsion_beam` only  |
| `beam_type`            | string  | no       | `"open_section"`, `"closed_section"`, `"tubular"` — `torsion_beam` only |
| `beam_position`        | [x,y,z] | no      | Center of cross-beam (m) — `torsion_beam` only           |
| `portal_drop`          | number  | no      | Portal axle: wheel centre below axle tube centreline (m, positive = lower) *(v0.99)* |
| `hub_reduction_ratio`  | number  | no      | Hub or portal gear reduction (input speed / wheel speed) *(v0.99)* |
| `pendulum_pivot`       | [x,y,z] | no      | `pendulum_axle`: point on the oscillation axis (m) *(v0.99)* |
| `pendulum_axis`        | [x,y,z] | no      | `pendulum_axle`: unit axis direction, default `[1,0,0]` *(v0.99)* |
| `roll_limit`           | number  | no      | `pendulum_axle`: maximum oscillation each way (rad) *(v0.99)* |

> **Coupling rule:** Both corners sharing the same `axle_body.id` are mechanically coupled. A kinematic solver MUST constrain the two uprights accordingly: rigidly for `solid_axle`/`de_dion`, torsionally for `torsion_beam`. The `axle_body.mass` contributes to unsprung mass and should be included (split 50/50) in `mass_unsprung_per_corner`. An `axle_body.id` MUST NOT be shared by corners of different axles — inter-axle links are `suspension_couplings` (§23.5).

> **Portal axles:** with `portal_drop > 0` the wheel centre (`hardpoints.wheel_center`) is below the axle tube; ground clearance under the axle increases by `portal_drop`. `hub_reduction_ratio` multiplies the differential `final_drive` for the torque at the wheel and SHOULD be included in the inertia chain (§10.9).

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

> **Corner weights:** The corner weights of all stations SHOULD sum to `mass_total × g` (for trailers, minus the load carried at the king-pin or drawbar). For two-axle vehicles, cross-weight percentage = (FL + RR) / (mass_total × g) × 100%; 50% indicates perfect diagonal balance.

---

### 9.3 `spring`

> **Motion ratio precedence:** If `inboard_mount` and `outboard_mount` are provided, a kinematic solver SHOULD compute the motion ratio from geometry. The scalar `motion_ratio` field then serves as a fallback (for point-mass sims) or validation check. If the computed and declared ratios disagree by more than 5%, the parser SHOULD warn. If only the scalar is provided, use it directly.

| Key              | Type    | Required | Description                                              |
|------------------|---------|----------|----------------------------------------------------------|
| `type`           | string  | YES      | `"coil"`, `"torsion_bar"`, `"leaf"`, `"air"`, `"coilover"`, `"rubber_torsion"`, `"rubber_block"`, `"hydropneumatic"`, `"hydraulic"`, `"none"` |
| `rate`           | number  | YES*     | Wheel-rate stiffness (N/m) OR see `rate_curve`. *Not required for `none`, `hydraulic`, `hydropneumatic` |
| `coupling_ref`   | string  | no       | id of the `suspension_couplings` entry that springs this station (§23.5) |
| `end_type_front` | string  | no       | Leaf: `"eye"`, `"slipper"`, `"shackle"`, `"fixed"`       |
| `end_type_rear`  | string  | no       | Leaf: `"eye"`, `"slipper"`, `"shackle"`, `"fixed"`       |
| `end_friction`   | number  | no       | Coulomb friction coefficient at sliding (slipper) ends   |
| `hysteresis_force` | number | no      | Equivalent friction/hysteresis force at the wheel (N) — inter-leaf friction, rubber hysteresis |
| `leaf_count`     | integer | no       | Number of leaves                                         |
| `effective_area` | number  | no       | Air spring / cylinder effective area (m²)                |
| `nominal_pressure` | number | no      | Air spring pressure at design ride height (Pa)           |
| `torsional_rate` | number  | no       | `rubber_torsion` / `torsion_bar` rate at the pivot (Nm/rad) |
| `arm_length`     | number  | no       | `rubber_torsion`: pivot to wheel centre (m)              |
| `arm_start_angle`| number  | no       | `rubber_torsion`: arm angle below horizontal at zero load (rad) |
| `hydropneumatic` | object  | no       | Gas-over-oil strut data (below)                          |
| `mass`           | number  | no       | Spring mass (kg). Convention: ~50% sprung, ~50% unsprung |
| `rate_curve`     | array   | no       | Non-linear: `[[displacement_m, force_N], ...]`           |
| `free_length`    | number  | no       | Uncompressed spring length (m)                           |
| `preload`        | number  | no       | Installed preload force (N)                              |
| `motion_ratio`   | number  | no       | Spring displacement / wheel displacement (dimensionless) |
| `inboard_mount`  | [x,y,z] | no      | Chassis-side spring mount point                          |
| `outboard_mount` | [x,y,z] | no      | Suspension-side spring mount point                       |

> **Convention:** If `rate` is provided, it represents the **wheel rate** (force at the wheel per unit of wheel travel). If the spring rate at the coil is known instead, provide `motion_ratio` and the parser computes wheel rate as: `wheel_rate = coil_rate × motion_ratio²`.

> **Non-linear springs:** When `rate_curve` is present, it takes precedence over `rate`. The curve is an ordered array of `[displacement, force]` pairs. Displacement is measured from free length (compression positive in SAE Z-down).

**Spring types added in v0.99:**

| Type             | Description | Notes |
|------------------|-------------|-------|
| `rubber_torsion` | Rubber cords compressed in a square tube, loaded in torsion by a short trailing arm (Torflex-type trailer axles) | Give `torsional_rate`, `arm_length`, `arm_start_angle`; `rate` is the equivalent wheel rate |
| `rubber_block`   | Solid elastomer bolster / shear springs (walking-beam and vocational suspensions) | Strongly progressive — prefer `rate_curve` |
| `hydropneumatic` | Gas-over-oil strut; stiffness from gas compression | Use the `hydropneumatic` object; `rate` optional (linearised) |
| `hydraulic`      | Fluid column in a cylinder; compliance and load sharing come from the circuit | Pair with a `hydraulic_circuit` coupling |
| `none`           | No spring at this station: unsprung (e.g. oscillating axle) or sprung through a coupling | Set `coupling_ref` when a coupling carries the load |

`hydropneumatic` object:

| Key                     | Type   | Description                                  |
|-------------------------|--------|----------------------------------------------|
| `gas_precharge_pressure`| number | Pa                                           |
| `gas_volume`            | number | Gas volume at precharge (m³)                 |
| `polytropic_index`      | number | 1.0 (isothermal) … 1.4 (adiabatic)           |
| `piston_area`           | number | m²                                           |
| `rod_area`              | number | m² (annulus side)                            |
| `static_pressure`       | number | Pa at design ride height                     |

> **Leaf springs in bogies:** measured load equalisation of leaf-spring tandems depends heavily on friction at the spring ends. Fill `end_type_front`, `end_type_rear` and `end_friction` when the spring sits on a rocker or trunnion (§23.5).

---

### 9.4 `damper`

| Key                | Type    | Required | Description                                           |
|--------------------|---------|----------|-------------------------------------------------------|
| `type`             | string  | no       | `"monotube"`, `"twin_tube"`, `"adjustable"`, `"mrd"` (magneto-rheological), `"hydraulic_strut"` (damping inside a hydraulic/hydropneumatic spring), `"none"` |
| `bump_curve`       | array   | YES*     | `[[velocity_m_s, force_N], ...]` (compression). *Not required for `none` / `hydraulic_strut` |
| `rebound_curve`    | array   | YES*     | `[[velocity_m_s, force_N], ...]` (extension). *Not required for `none` / `hydraulic_strut` |
| `motion_ratio`     | number  | no       | Damper velocity / wheel velocity (dimensionless)      |
| `reference`        | string  | no       | `"damper"` (default) or `"wheel"` — where the curves are defined *(v0.99.4)* |
| `mass`             | number  | no       | Damper mass (kg). Body ≈ sprung, rod+piston ≈ unsprung |
| `inboard_mount`    | [x,y,z] | no      | Chassis-side damper mount point                       |
| `outboard_mount`   | [x,y,z] | no      | Suspension-side damper mount point                    |

> **Reference of the curves (v0.99.4):** with `reference: "damper"` (default) `bump_curve` / `rebound_curve` are force and velocity **at the damper**, related to the wheel by `motion_ratio` (damper velocity ÷ wheel velocity); a solver SHOULD derive the ratio from the mounts when they are given (§9.3). With `reference: "wheel"` they are force **at the wheel** against **wheel** velocity — the form simulators that work at the wheel provide. `motion_ratio` MUST then be absent or `1`, and any mounts are geometry only. A reader that needs damper values converts with `v_damper = v_wheel × MR` and `F_damper = F_wheel ÷ MR`; one that needs wheel values from a damper-referenced file does the inverse. Writing wheel-referenced values with a real strut geometry and no `reference` makes a geometry-solving reader scale the wheel force by about MR² (a ratio of 0.9 under-damps the wheel by 19 %), so converters without damper geometry should say `"wheel"` instead of inventing a vertical damper. (Springs need no flag: `rate` is the wheel rate, §9.3.)

> **Mount key names:** the keys are `inboard_mount` / `outboard_mount` (spring and damper). The look-alikes `inboard_point` / `outboard_point` (used by link `inboard_points`) are not part of the schema and are ignored by readers; `tools/validate.py` warns when it sees them.

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
| `multiplicity`      | integer| no       | Wheels on this hub (2 = duals). Default 1 (§23.4) *(v0.99)*       |
| `dual_spacing`      | number | no       | Centre-to-centre spacing of multiple wheels (m) (§23.4)           |
| `positions`         | array  | no       | Per-wheel offset and tire assignment (§23.4)                      |

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
| `"multi_axle"` | Three or more axles; use `vehicle_info.wheel_formula` and §23.6 *(v0.99)* |

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
| `coupling`        | object | no       | Torque-limited centre coupling for on-demand AWD *(v0.99.3, §10.6.1)* |
| `inertia`         | number | no       | Transfer case rotating inertia (kg·m²)              |
| `position`        | [x,y,z]| no      | Transfer case CG (m)                                |
| `mass`            | number | no       | Transfer case mass (kg)                             |
| `output_front`    | [x,y,z]| no      | Front output flange position (m)                    |
| `output_rear`     | [x,y,z]| no      | Rear output flange position (m)                     |

#### 10.6.1 `coupling` — Torque-Limited Centre Coupling *(v0.99.3)*

For AWD systems with no fixed split, where the centre transmits torque up to a limit (Haldex-style and other on-demand couplings). Use it together with `transfer_case.type: "on_demand"`; that field stays the single place that says what kind of transfer case this is. `torque_split` remains the nominal split and MAY be omitted when `coupling` is present.

| Key           | Type   | Required | Description                                                         |
|---------------|--------|----------|---------------------------------------------------------------------|
| `max_torque`  | number | YES      | Maximum torque the coupling transmits (Nm, > 0)                     |
| `ramp_torque` | number | no       | Torque at which the coupling starts to engage (Nm); MUST NOT exceed `max_torque` |
| `mechanism`   | string | no       | `"viscous"`, `"clutch_pack"`, `"electronic"`; omit when unknown      |

```json
"transfer_case": {
  "type": "on_demand",
  "coupling": { "mechanism": "clutch_pack", "ramp_torque": 40.9, "max_torque": 816.6 }
}
```

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
| `location`       | string  | no       | `"rear"`, `"front"`, `"center"`, `"inter_axle"` (between tandem drive axles) |
| `axle_ref`       | string  | no       | Axle driven by this differential (`"A2"`, …) *(v0.99)* |
| `through_drive`  | boolean | no       | Carrier passes drive through to the next axle (tandem through-drive) *(v0.99)* |
| `type`           | string  | no       | `"open"`, `"locked"`, `"lsd_clutch"`, `"lsd_torsen"`, `"lsd_viscous"`, `"active"`, `"spool"` |
| `final_drive`    | number  | YES      | Ring-and-pinion ratio (e.g. 2.866)                   |
| `preload`        | number  | no       | LSD preload torque (Nm)                              |
| `lock_power`     | number  | no       | Locking ratio under power (0.0–1.0)                  |
| `lock_coast`     | number  | no       | Locking ratio on coast/overrun (0.0–1.0)             |
| `lock_control`   | object \| array | no | Dynamic lock modulation *(v0.99.3, §10.8.1)*      |
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

#### 10.8.1 `lock_control` — Dynamic Differential Lock *(v0.99.3)*

Optional on every differential entry and on `transfer_case.center_diff`. It describes a lock that is *modulated* by the driving state (gear, brake, axle speed ratio, …) instead of being constant. Without it the constant `lock_power` / `lock_coast` / `preload` apply. It is meaningful for `type` `lsd_clutch`, `lsd_torsen`, `lsd_viscous` and `active`.

`lock_control` is either one **chain** or an **array of chains** with distinct targets (for example one chain for `lock_power` and one for `lock_coast`).

| Key      | Type  | Required | Description |
|----------|-------|----------|-------------|
| `target` | string | YES | `"lock"` (the same chain drives both `lock_power` and `lock_coast`), `"lock_power"`, `"lock_coast"`, `"preload"` |
| `stages` | array  | YES | At least one stage, applied in order. The running value starts at the static value of the target (0 if absent) |

Each stage:

| Key                    | Type      | Required | Description |
|------------------------|-----------|----------|-------------|
| `input`                | string    | YES      | Controller input (table below), or a custom name starting with `x_` |
| `combine`              | string    | YES      | `"multiply"` (`v = v · y`) or `"add"` (`v = v + y`) |
| `curve`                | `curve2d` | YES      | Input value → stage output `y`; linear interpolation, clamped at both ends; x strictly increasing |
| `filter_time_constant` | number    | no       | First-order low-pass time constant on `y` (s); 0 or absent = none |
| `min`, `max`           | number    | no       | Clamp of the running value after the stage, in the unit of the target; `min` ≤ `max` |

| `input`                               | Unit  | Meaning |
|---------------------------------------|-------|---------|
| `gear`                                | index | Engaged gear, 1-based; reverse `-1`, neutral `0` |
| `brake`, `throttle`                   | 0–1   | Pedal position |
| `speed`                               | m/s   | Vehicle speed |
| `rear_speed_ratio`                    | –     | Rear axle speed ÷ front axle speed |
| `oversteer_factor`                    | –     | Simulator-defined oversteer indicator |
| `slip_angle_front`, `slip_angle_rear` | rad   | Axle-average slip angle |

**Units and clamping.** `lock_power` / `lock_coast` are dimensionless fractions 0–1 and `preload` is in Nm. The running value may leave that range between stages (a gear multiplier of 12.8 is legal); the **final** value is clamped to the target's valid range (0–1 for the locks, ≥ 0 for the preload) before use.

```json
"center_diff": {
  "type": "lsd_clutch", "lock_power": 0.4, "lock_coast": 0.2,
  "lock_control": { "target": "lock", "stages": [
    { "input": "gear",  "combine": "multiply", "curve": [[1,1.0],[2,0.8],[3,0.6]] },
    { "input": "brake", "combine": "multiply", "curve": [[0,1],[1,0]], "filter_time_constant": 0.1 }
  ] }
}
```

Cross-field rules (curve ordering, target overlap in an array, `min` ≤ `max`, `ramp_torque` ≤ `max_torque`, lock control on `open`/`locked`/`spool` differentials, `on_demand` without `torque_split` or `coupling`) are checked by `tools/drivetrain_check.py`, which `tools/validate.py` runs automatically.

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

Only driven corners need entries. For a RWD car, only `RL` and `RR` are present. Multi-axle vehicles use the same station names as `suspension` (`A2L`, `A3R`, …, §23.1).

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

These checks are the responsibility of higher-level tools or linters built on top of the schema. `tools/validate.py` runs `tools/multiaxle_check.py` after the schema for the multi-axle cross-reference rules (§23.7).

---

## 20a. `validation` — Model Correlation Status *(v0.98)*

This section is **optional**. It has no bearing on kinematics, dynamics, or any solved quantity — it is a provenance record answering "has this assembled model been checked against a real car, and how well?"

Field-level provenance already exists (`_est: true`, `_source` strings, per PROJECT_BRIEF conventions) but says nothing about the **assembled vehicle's** correlation status. Two SVJ files with identical topology are otherwise indistinguishable in trustworthiness — one may be a first guess, the other correlated against instrumented test data.

| Key                   | Type   | Required | Description                                                        |
|-----------------------|--------|----------|----------------------------------------------------------------------|
| `status`              | string | no       | `"unvalidated"`, `"simulation_only"`, `"correlated"`, `"partially_correlated"` |
| `method`              | string | no       | `"physical_test"`, `"peer_reference"`, `"fem"`, `"other"`            |
| `test_reference`      | string | no       | Free-text pointer to the test/report this was correlated against    |
| `correlated_channels` | array  | no       | Array of strings naming the channels checked (e.g. `"lateral_accel"`, `"yaw_rate"`) |
| `correlation_quality` | string | no       | Free-text or `"good"` / `"fair"` / `"poor"`                          |
| `date`                | string | no       | ISO 8601 date of the correlation exercise                            |
| `notes`               | string | no       | Free-text caveats (e.g. operating range where correlation is valid)  |

```json
"validation": {
  "status": "correlated",
  "method": "physical_test",
  "test_reference": "Skidpad 2026-03, run log SK-0417",
  "correlated_channels": ["lateral_accel", "yaw_rate", "roll_angle"],
  "correlation_quality": "good",
  "date": "2026-03-12",
  "notes": "Correlated at 0.85g steady-state; not validated for transient >0.9g"
}
```

> **Not a computation.** Nothing in this block is checked by a solver — it's metadata for humans and pipelines deciding whether a model is trustworthy enough for a given use (e.g. gating "virtual sign-off" on `status: "correlated"`).

---

## 20b. `benchmarks` — Performance KPI Targets *(v0.98)*

This section is **optional**. It provides a standard place to record performance KPIs — targets, factory-spec measurements, or simulation results — alongside the model that's supposed to reproduce them, instead of a side-channel spreadsheet.

`benchmarks` is an array of entries:

| Key      | Type   | Required | Description                                                    |
|----------|--------|----------|------------------------------------------------------------------|
| `id`     | string | YES      | Free-form KPI identifier (e.g. `"skidpad_lateral_g"`, `"accel_0_100kph"`) |
| `value`  | number | YES      | The KPI value                                                    |
| `unit`   | string | YES      | Unit of the value (e.g. `"g"`, `"s"`, `"km/h"`)                  |
| `type`   | string | YES      | `"target"`, `"measured"`, or `"simulated"`                       |
| `source` | string | no       | Where the value came from (test report, spec sheet, sim run id) |

```json
"benchmarks": [
  { "id": "skidpad_lateral_g", "value": 0.95, "unit": "g", "type": "target" },
  { "id": "accel_0_100kph", "value": 6.2, "unit": "s", "type": "measured", "source": "factory spec sheet" }
]
```

> `id` is deliberately free-form rather than an enum, consistent with the `x_` extension philosophy (§17) of not over-constraining what teams choose to track.

---

## 20. Versioning & Compatibility

- **Major version (1.x):** Breaking changes. Parsers for v0.x are NOT required to read v1.x.
- **Minor version (x.3):** Additive changes only. A v0.3 parser MUST accept v0.2 files (missing fields default to `null`/absent). A v0.2 parser SHOULD accept v0.3 files by ignoring unknown keys.
- **Patch version (x.x.1):** Clarifications, schema fixes, doc edits. No new required fields.

### Changelog

| Version | Changes                                                                                    |
|---------|--------------------------------------------------------------------------------------------|
| 0.102   | **Collision proxies** (§28). Additive. `collision[]` on `chassis` and on any `mass_bodies` entry (sphere, box, cylinder in vehicle coordinates, optional `margin`, `source_node`) and a top-level `collision_ignore`; pairs of relatively movable bodies are compared in the reference pose and every pose (`tools/collision_check.py`, `svj.collision`); the validator warns about overlaps and errors on malformed proxies. `_metadata.version` gains `0.102` |
| 0.101   | **Attachments and combinations** (§27; `proposals/svj_articulated_parts_proposal.md`, phase 4). Additive. Top-level **`interfaces[]`** (named frames with a role from a mating table, a gender and sizes), **`attachments[]`** (units fitted to a vehicle) and the **`*.svj-combination.json`** file (`schema/svj-combination.schema.json`): units joined by connections that carry a joint object. Units are ordinary SVJ files; `vehicle_info.vehicle_class: "attachment"` for units only ever fitted (chassis needs only `mass_total` and `center_of_gravity`). Assembly (`tools/assemble.py`) places units so interface frames coincide, qualifies ids `unit.id`, and builds one composite (mass, CG, inertia, poses) that all §24 / §26 machinery works on. `_metadata.version` gains `0.101` |
| 0.100   | **Unified suspension** (§25; `proposals/svj_unified_suspension_proposal.md`) — *breaking*, with one release of transition. A wheel station is bodies, joints and elements, not a typed corner: `wheel_stations[]` (wheel and carrier bodies, wheel-centre marker, steering joint, coupling reference, tyre / brake / reference alignment, optional `topology_hint`), `anti_roll_bars[]`, new `damper` constraint, `spring` / `damper` gain `kind` (`linear` / `torsional`) and `reference` (`element` / `wheel`), spring and bump / rebound stops as elements, rack as a body on a slide, leaf pack as a body with eye / slipper / seat joints. The corner-based `suspension` section is **deprecated** (accepted, validators warn) and `tools/migrate_suspension.py` converts it, marking generated items `x_derived` (zero mass allowed only there). `mass_bodies` keeps holding every body. Body ids of known suspension parts keep their canonical names. `placement: link_between_points` works on link bodies. All 28 shipped examples and the template are migrated |
| 0.99.8  | **Contact** (§24.6.3): `contact` constraints between any two bodies with primitive shapes (point, plane, sphere, box, cylinder) on markers and a penalty law (`gap`, `stiffness`, `damping`, `friction`, `restitution`); the checker computes the signed distance between the shapes at the reference pose and in every pose. The part-name vocabulary now also covers the suspension, steering and brake parts (upright, wishbones, tie rod, rack, …) with the same alias advisory and the multi-axle station suffix (`_a2l`). New tool `tools/suspension_view.py` expands an authored suspension into the body / joint model (transition tool toward `proposals/svj_unified_suspension_proposal.md`). Panels example gains rubber stops |
| 0.99.7  | **Part names** (§24.2, `docs/naming_convention.md`): optional display `name` on `mass_bodies`, `constraints` and `poses`; a recommended vocabulary for movable parts and attachments (doors, hood, trunk, tailgate, flaps, mirrors, cab, tipper body, loader, excavator, three-point hitch parts, implements) with aliases and side suffixes, patterns for joint, cylinder, strut, latch, coupling and pose ids, and marker names; `tools/constraints_check.py` flags an alias of a listed part and `_ram` / `_piston` actuator names. The three movable-part examples follow the vocabulary and carry display names |
| 0.99.6  | **Constraint set completed** (§24.6.1, §24.6.2, §24.4, §7.2.2): `latch` (engage position, holding force, state), `coupling` (`q_b = ratio · q_a`, coordinates a pose does not name are derived), rotary / linear `joint.drive`; `constraints` entries no longer all need bodies and frames (latch and coupling refer to joints); `mass_bodies` may be a **partial** decomposition (the sum may not exceed `mass_total`; equality only when `chassis.mass_bodies_complete` is true). Example `skeleton_dump_truck_tipper_cab` (tilting cab, tipper, linked tailgate, latches, rams); the panels example gains latches, door checks and a powered hatch |
| 0.99.5  | **Movable parts and attachments** (§24): top-level `constraints[]` — `joint` (revolute, translational, cylindrical, spherical, universal, planar, fixed, with vector coordinates, ranges, end stops, friction, damping, bushing), `spring`, `actuator` (stroke, bore/pressure force limits) — between `mass_bodies`, `chassis`/`ground`, joined by markers; `poses[]`; `chassis.markers`; `mass_body.inertia` may be a full 3×3 matrix and gets `inertia_orientation`; `category: "attachment"`. Forward kinematics, per-pose CG, composite inertia and actuator-reach checks in the new `tools/constraints_check.py` (mirrored in `svj-py`). Additive: every earlier file stays valid. Origin: `proposals/svj_articulated_parts_proposal.md` |
| 0.99.4  | **Strut and damper conventions** (from converter feedback): the MacPherson/Chapman strut link now ends at the new `strut_lower` hardpoint (lower clamp on the upright) instead of `strut_top`, which had made every strut link zero-length (§9.2.1, §9.2.2.1); `damper.reference` `"damper"` (default) or `"wheel"` for dampers specified at the wheel (§9.4); `inboard_point` / `outboard_point` flagged as misspellings of `inboard_mount` / `outboard_mount`. Additive: older files stay valid, the checker warns about zero-length links. Five shipped examples corrected |
| 0.99.3  | **Differential control** (§10.6.1, §10.8.1): optional `lock_control` on differentials and `transfer_case.center_diff` (ordered stages — input → curve → multiply/add — with a time-constant filter and clamps; one chain or an array of chains for separate power/coast), and optional `transfer_case.coupling` (`max_torque`, `ramp_torque`, `mechanism`) for torque-limited on-demand AWD. Additive: every v0.96–v0.99.2 file stays valid. New `tools/drivetrain_check.py` (mirrored in `svj-py`). Origin: `proposals/svj_differential_control_proposal.md` |
| 0.99.2  | **Visual binding layer, part 2** (§22): one category set shared by schema, spec and `docs/naming_convention.md` (`body`, `suspension`, `steering`, `wheel`, `brake`, `powertrain`, `aero`, `helper`, `lod`); `visual` defined on suspension links, uprights, axle bodies, wheels and dual-wheel positions, springs, dampers, ARBs, brake discs and calipers, steering rack/column/wheel, powertrain units, driveshafts and aero components; new `placement` (`rigid` \| `link_between_points`) with `mesh_axis`, `from_point` and `scale_to_length` for parts defined by hardpoints; `x_`/`_` keys allowed inside `visual`; `tools/integrity_check.py` rewritten (id resolution for every carrier, placement and category rules). Additive — every v0.96–v0.99.1 file, including all v0.97 bindings, remains valid. |
| 0.99.1  | **Real-vehicle data patch** (from `proposals/multi_axle_real_vehicle_examples_research.md`): `axle_groups` with design/legal/kerb loads per group (§23.2.1); `chassis.plated_masses`; `wheelbase_reference` gains `bogie_centres`, `first_rear_axle`, `theoretical`, `explicit` (+ `wheelbase_from`/`wheelbase_to`) with a definition table (§23.6); checker rules for both. First real-vehicle multi-axle example: MAN TGS 32.430 8x4 BB twin-steer tipper. Additive — all 0.99 files remain valid. |
| 0.99    | **Multi-axle vehicles** (§23): `A{n}{L\|R\|C}` station naming with `FL/FR/RL/RR` as aliases; `axles` metadata (position, track, steered, driven, lift); multi-axle steering `steering.additional_axles` (§8.6); multiple wheels per station (`wheel.multiplicity`, `positions`); `suspension_couplings` (equalizer rocker, walking beam, trunnion spring, pneumatic and hydraulic circuits). New `system_type`s `swing_axle`, `parallelogram`, `pendulum_axle`; new spring types `rubber_torsion`, `rubber_block`, `hydropneumatic`, `hydraulic`, `none` with leaf end type/friction and hydropneumatic data; damper types `hydraulic_strut`, `none`; portal axle and pendulum fields on `axle_body`; `torque_rod` and `pivot` link types; `vehicle_info.wheel_formula`/`vehicle_class`; `inter_axle` differentials. `tools/multiaxle_check.py` cross-reference rules. Ten multi-axle skeleton examples. `svj-py` 0.2.0 and viewer v4.0 are multi-axle aware. Schema fixes from the audit: truck tyre `size_code`s, `_` metadata keys in pacejka groups. Existing files remain valid. |
| 0.98    | **Override files** (§3.4): `*.svj-override.json` — `base` + RFC 7396 JSON Merge Patch `patch`, for DOE variants and partial-disclosure supplier hand-offs, validated with `tools/validate_override.py`. **`validation`** (§20a): vehicle-level correlation status against physical test data. **`benchmarks`** (§20b): array of target/measured/simulated KPI entries. All additions optional — full backward compatibility. |
| 0.1     | Initial draft. Metadata, chassis, basic suspension topology, powertrain.                   |
| 0.2     | Entity-based upright/link model. AC conversion logic. Extension prefix `x_`.               |
| 0.3     | Hybrid file structure (`$ref`). Four-corner suspension. Springs, dampers, ARB, alignment, bump stops. Inertia renamed to ISO convention. Differential added. `outboard_ref` simplified. |
| 0.3.1   | Steering system (§8). Wheel geometry per corner (§9.8). JSON Schema (§19). Tie rod inboard points close kinematic loop. Patch-level versioning introduced. |
| 0.3.2   | Sprung mass decomposition (`mass_bodies` in §7.2). Chassis mass can be broken into individually positioned rigid bodies with own CG and inertia. Composite fields unchanged and required for backward compatibility. |
| 0.4.0   | **Tires**: Top-level tire library (`tires.sets`) with Pacejka MF 5.2/6.2 coefficients, thermal model, wear model, relaxation lengths. Per-corner `tire` reference with pressure/temperature overrides. **Brakes**: Per-corner `brake` assembly (disc with mass/thermal, caliper, pad with μ curve). Top-level `brakes` system (master cylinder, bias, ABS, ESC). All new components carry physical mass and thermal properties. |
| 0.4.1   | Tire set expanded: dimensions, rim specs, construction properties (mass, stiffness, ratings). Wheel vs tire_set relationship documented. |
| 0.94   | *(Planned, never landed in the spec file — superseded by §23 in v0.99.)* **Multi-axle naming convention** (§21.1): formalized `A{n}{side}` corner naming (A1L, A2R, ...). FL/FR/RL/RR are aliases for A1L/A1R/A2L/A2R. Axle metadata array with `steered`, `driven`, `lift` flags. Multi-axle steering linkage with per-axle ratio and phase. Tyrrell P34 example. Backward compatibility rules. |
| 0.97   | **glTF Visual Binding Layer** (§22): optional `assets.meshes` manifest, `visual` field on any body (`mesh_ref` + `node`), flexible `coordinate_system` object for Y-up/Z-forward glTF assets, SAE J670 ↔ Blender transform table. `SVJ::category::id` naming convention for glTF nodes (see `docs/naming_convention.md`). `tools/integrity_check.py` validates 4 binding rules. `tools/validate.py` validates any SVJ file against the JSON Schema. All additions optional — full backward compatibility. |
| 0.96   | **Multibody topology extension**: Explicit joint types on links (`joint_type`, `inboard_joint_type`), body references (`body_ref`) linking suspension parts to chassis mass bodies, `orientation` quaternion definition, extended hardpoints accepting marker objects (position + orientation), oriented bushings with preload, mass body parent/markers hierarchy, oriented spring/damper mounts. All additions optional — full backward compatibility. |
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

## 22. glTF Visual Binding Layer *(v0.97, extended in v0.99.2)*

This section is **optional**. A file that omits all `visual` fields and the `assets` block is fully valid SVJ. Parsers that do not handle visual bindings MUST ignore these fields.

### 22.1 Purpose

SVJ physics bodies are pure data — mass, hardpoints, stiffness. The glTF Visual Binding Layer attaches each body to its 3D representation in a `.glb` or `.gltf` asset, enabling a single SVJ file to drive both the dynamics simulation and the visual renderer.

### 22.2 Asset Manifest

Declare the glTF files used by the vehicle in the top-level `assets` object:

```json
"assets": {
  "meshes": [
    { "id": "chassis_body", "uri": "meshes/car_body.glb" },
    { "id": "wheel_set",    "uri": "meshes/wheels.glb" }
  ]
}
```

| Field | Type   | Required | Description |
|-------|--------|----------|-------------|
| `id`  | string | YES      | Short identifier referenced by `mesh_ref` in `visual` blocks |
| `uri` | string | YES      | Relative path from the SVJ file to the glTF asset |

The `uri` MUST be a relative path. Absolute paths and remote URLs are not permitted.

### 22.3 Visual Binding

Any part described in the file MAY carry an optional `visual` field. As of **v0.99.2** the schema defines `visual` at every site in this table; all of them are optional and additive.

| Where | Part | Typical category |
|-------|------|------------------|
| `chassis.visual` | Sprung body | `body` |
| `chassis.mass_bodies[].visual` | Decomposed mass body (engine block, fuel tank, driver…) | `body`, `powertrain` |
| `suspension.<station>.topology.upright.visual` | Upright / knuckle | `suspension` |
| `suspension.<station>.visual` | Upright / knuckle (v0.97 corner-level form, still valid) | `body`, `suspension` |
| `suspension.<station>.topology.links[].visual` | Wishbone, trailing arm, tie rod, toe link, pushrod, torque rod | `suspension` |
| `suspension.<station>.topology.axle_body.visual` | Axle beam or housing | `suspension`, `body` |
| `suspension.<station>.wheel.visual` | Rim / wheel | `wheel` |
| `suspension.<station>.wheel.positions[].visual` | One wheel of a dual/triple set (§23.4) | `wheel` |
| `suspension.<station>.spring.visual` | Coil, leaf, air spring | `suspension` |
| `suspension.<station>.damper.visual` | Damper body | `suspension` |
| `suspension.<station>.arb.visual` | Anti-roll bar | `suspension` |
| `suspension.<station>.brake.disc.visual` / `.caliper.visual` | Brake disc, caliper | `brake` |
| `steering.visual` | Rack / steering gear housing | `steering` |
| `steering.column.visual` | Column | `steering` |
| `steering.steering_wheel.visual` | Steering wheel | `steering` |
| `powertrain.engine/gearbox/clutch/transfer_case.visual` | Driveline units | `powertrain` |
| `powertrain.differentials[].visual`, `powertrain.driveshafts[].visual` | Diff housing, propshaft | `powertrain` |
| `aerodynamics.components[].visual` | Wing, splitter, diffuser | `aero` |

```json
"chassis": {
  "mass_total": 1077,
  "visual": {
    "mesh_ref": "chassis_body",
    "node": "SVJ::body::chassis"
  }
}
```

| Field             | Type    | Required | Description |
|-------------------|---------|----------|-------------|
| `mesh_ref`        | string  | YES¹     | Must match an `id` in `assets.meshes`. May be omitted when exactly one mesh is declared. |
| `node`            | string  | YES      | glTF node name following the SVJ Naming Convention (§22.5) |
| `placement`       | string  | no       | `"rigid"` (default) or `"link_between_points"` (§22.6) |
| `mesh_axis`       | string  | no       | `link_between_points` only: `"+x"` (default), `"-x"`, `"+y"`, `"-y"`, `"+z"`, `"-z"` |
| `from_point`      | integer | no       | `link_between_points` only: index into the link's `inboard_points` |
| `scale_to_length` | boolean | no       | `link_between_points` only: default `false` |

¹ Required in practice whenever more than one mesh file is declared; the checker warns otherwise.

`x_`-prefixed extension keys and `_`-prefixed metadata keys are permitted inside `visual` (§20); no other unknown keys are.

### 22.4 Coordinate System Declaration

Physics data uses SAE J670 (§2.1) by default. The glTF asset may use a different convention (Blender exports Y-up, -Z-forward by default). Both can be declared in the same file:

```json
"_metadata": {
  "coordinate_system": { "up": "Y", "forward": "-Z", "handedness": "right" },
  "units": "meters"
}
```

When `coordinate_system` is an **object** (rather than the string `"SAE_J670"`), it specifies the glTF asset convention. The physics data coordinate system is always SAE J670 unless explicitly overridden.

**SAE J670 → Blender (Y-up) transform:**

| SVJ axis | Blender axis |
|----------|-------------|
| +X (forward) | −Z |
| +Y (right)   | +X |
| +Z (down)    | −Y |

Converters reading glTF assets from Blender should apply this mapping when positioning visual nodes relative to physics hardpoints.

### 22.5 SVJ Naming Convention

All `node` values in `visual` fields MUST follow the pattern:

```
SVJ::<category>::<id>
```

| Part | Description |
|------|-------------|
| `SVJ` | Literal prefix |
| `<category>` | One of the categories below |
| `<id>` | Lowercase alphanumeric with underscores (`[a-z0-9_]+`) |

**Categories** *(the set was `body`/`helper`/`lod` in the schema and `body`/`wheel`/`suspension`/`aero`/`powertrain` in this section before v0.99.2; both are now subsets of one list)*:

| Category | Used for |
|----------|----------|
| `body` | Chassis, decomposed mass bodies, and any rigid body with no better category. Also the legacy category for uprights (`SVJ::body::upright_fl`), which stays valid. |
| `suspension` | Uprights, links (wishbones, arms, rods), springs, dampers, anti-roll bars, axle beams |
| `steering` | Rack/gear housing, column, steering wheel |
| `wheel` | Rims and wheels, including the individual wheels of a dual set |
| `brake` | Discs, drums, calipers |
| `powertrain` | Engine, gearbox, clutch, transfer case, differentials, propshafts |
| `aero` | Wings, splitters, diffusers and other `aerodynamics.components` |
| `helper` | Non-physical markers: hardpoint locators, sensor origins, camera pivots. No id-matching rule. |
| `lod` | Level-of-detail variant of another node; `<id>` matches the body it replaces |

**Id rule.** Except for `helper`, the `<id>` segment MUST equal the id of the SVJ part that carries the binding, lowercased, with any character outside `[a-z0-9_]` replaced by `_`:

| Carrier | Id source |
|---------|-----------|
| `chassis` | the literal `chassis` |
| `chassis.mass_bodies[]` | that body's `id` |
| upright | `topology.upright.id` |
| link | the link's `name`, plus the corner suffix (below) |
| wheel | `wheel_<station>`, dual wheels `wheel_<station>_<positions[].label>` |
| spring / damper / arb | `spring_<station>`, `damper_<station>`, `arb_<station>` (or their own `id`/`bar_id` when present) |
| brake disc / caliper | `disc_<station>`, `caliper_<station>` |
| steering | `rack`, `column`, `wheel` |
| powertrain unit | `engine`, `gearbox`, `clutch`, `transfer_case`, or the differential/driveshaft `id` |
| aero component | that component's `id` |

**Corner suffix rule:** nodes for corner-specific parts MUST end with `_fl`, `_fr`, `_rl`, `_rr`, or the canonical `_a{n}l` / `_a{n}r` / `_a{n}c` form for multi-axle vehicles (§23.1). For dual wheels, append the position label: `wheel_a2l_inner`, `wheel_a2l_outer`. This applies to links as well: a link named `upper_wishbone` on station `FL` binds to `SVJ::suspension::upper_wishbone_fl`. If the link `name` already carries the suffix, it is not repeated.

See [`docs/naming_convention.md`](../docs/naming_convention.md) for the complete specification.

**Examples:**

| Part | `node` |
|------|--------|
| Main chassis | `SVJ::body::chassis` |
| Front-left upright | `SVJ::suspension::upright_fl` |
| Front-left upper wishbone | `SVJ::suspension::upper_wishbone_fl` |
| Front-left tie rod | `SVJ::suspension::tie_rod_fl` |
| Front-left wheel | `SVJ::wheel::wheel_fl` |
| Front-left brake disc | `SVJ::brake::disc_fl` |
| Steering wheel | `SVJ::steering::wheel` |
| Steering rack | `SVJ::steering::rack` |
| Third-axle right outer wheel | `SVJ::wheel::wheel_a3r_outer` |
| Front wing | `SVJ::aero::front_wing` |
| Engine | `SVJ::powertrain::engine` |

**Canonical part names.** `docs/naming_convention.md` lists a recommended name per common part (`upper_wishbone`, `lower_wishbone`, `trailing_arm`, `tie_rod`, `toe_link`, `pushrod`, `rocker`, `panhard_rod`, `torque_rod`, `upright`, `spring`, `damper`, `arb`, `disc`, `caliper`, `rack`, `column`, `wheel`, …) with the aliases other tools use, so exporters converge on the same ids. The vocabulary is a recommendation: the checker warns about an unlisted link name, it does not reject it. Note the order — part first, corner last (`upper_wishbone_fl`, not `fl_upper_wishbone`), which keeps one rule across two-axle, multi-axle and dual-wheel vehicles.

### 22.6 `placement` — Parts Defined by Hardpoints *(v0.99.2; bodies since v0.100)*

> Since v0.100 a link is a `mass_body` held by joints at two ends. A body with a joint where it is `body_b` (the inboard end) and a joint where it is `body_a` (the outboard end) may use `link_between_points`: its inboard points are the frames of the joints where it is `body_b`, its outboard end is the other joint.

A wishbone or tie rod has no body frame in SVJ: it is defined by its `inboard_points` and the upright hardpoint named by `outboard_ref`. `placement` tells the renderer how to put the mesh on that geometry.

| Value | Meaning |
|-------|---------|
| `rigid` (default) | The node follows the carrier's own frame, exactly as in v0.97. The mesh is authored in the vehicle frame and is neither moved nor scaled by the binding. |
| `link_between_points` | The node is placed and oriented from the carrier link's hardpoints. |

For `link_between_points`:

1. **Inboard end (origin).** `from_point` absent → the centroid of all `inboard_points`; `from_point: i` → `inboard_points[i]`. A two-point wishbone therefore rotates about the centre of its pivot axis by default, while a single-point rod uses its one inboard point either way.
2. **Outboard end.** The upright hardpoint resolved from `outboard_ref` (e.g. `hardpoints.lower_ball_joint`).
3. **Orientation.** `mesh_axis` (default `+x`) is the axis of the **mesh's own local frame** that points from the inboard end to the outboard end. The renderer rotates the mesh so that axis lies along the inboard→outboard vector. Roll about that axis is not defined by the binding; author the mesh with its intended roll.
4. **Scale.** `scale_to_length: false` (default) keeps the authored mesh size — the mesh is only translated and rotated, so an artist-correct part stays correct and any mismatch with the hardpoint distance is visible. `true` scales the mesh along `mesh_axis` only (never the other two axes) so that it spans the hardpoint distance exactly.
5. The binding is **live**: as suspension moves, the two points move, and the node follows. A renderer that only reads the static file places the node at the design position.

```json
"links": [
  {
    "name": "upper_wishbone",
    "inboard_points": [[0.18, -0.38, -0.56], [-0.19, -0.37, -0.57]],
    "outboard_ref": "hardpoints.upper_ball_joint",
    "visual": {
      "mesh_ref": "suspension_set",
      "node": "SVJ::suspension::upper_wishbone_fl",
      "placement": "link_between_points",
      "mesh_axis": "+y",
      "scale_to_length": false
    }
  }
]
```

`placement: "link_between_points"` is only meaningful on a carrier that has two resolvable ends — a `links[]` entry, or a `driveshafts[]` entry (`joint_front` → `joint_rear`). Elsewhere it is an error (§22.7, rule 5).

### 22.7 Integrity Checking

The `tools/integrity_check.py` script validates all visual bindings before commit:

```bash
python tools/integrity_check.py path/to/vehicle.svj.json
python tools/integrity_check.py path/to/vehicle.svj.json --strict
```

Rules checked:

1. **Node pattern** — every `node` value matches `^SVJ::<category>::[a-z0-9_]+$` with a category from the §22.5 list
2. **Id match** — the `<id>` suffix matches the id of the carrier part per §22.5 (uprights, links, wheels, brakes, steering, powertrain, aero); `helper` nodes are exempt
3. **mesh_ref validity** — every `mesh_ref` resolves to an entry in `assets.meshes`
4. **Uniqueness** — no two `visual` blocks share the same `node` value. Exception: one part shared by both stations of an axle (beam axle, de Dion tube, torsion beam) is bound from each station with the same node, which is correct and accepted.
5. **Placement** — `link_between_points` only on a carrier with two resolvable ends; `mesh_axis`, `from_point` and `scale_to_length` only with that placement; `from_point` within range of `inboard_points`
6. **Category fit and vocabulary** — the category matches the kind of part, and link names come from the canonical vocabulary (advisory warnings; `body` is accepted everywhere for backward compatibility, and house part names stay legal)

Rules 1–5 are errors. Rule 6, and a missing `mesh_ref` when several meshes are declared, are warnings. Using the legacy `body` category on a non-body part stays valid and is reported as a NOTE, so `--strict` still passes on v0.97 files. With `--strict` any warning is a non-zero exit.

### 22.8 Compatibility

- Files without `assets` or `visual` fields are valid SVJ — the visual binding layer is purely additive.
- A v0.96 parser encountering `visual` or `assets` SHOULD ignore them (unknown-key policy, §20).
- v0.97 bindings (`SVJ::body::upright_fl` at corner level, no `placement`) remain valid in v0.99.2: the category list was extended, not replaced, and `placement` defaults to `rigid`.
- A parser that does not understand `placement` treats every binding as `rigid`, which is the v0.97 behaviour.

---

## 23. Multi-Axle Vehicles *(v0.99)*

This section extends SVJ beyond the four-corner passenger car to trucks, trailers and special vehicles: any number of axles, more than one wheel per station, several steered axles, and suspensions that share load between axles. Everything here is **optional**. A two-axle file using `FL/FR/RL/RR` and none of the new keys is unchanged and fully valid.

The design separates two levels:

1. **Axle location** (per wheel station) — described with the existing corner vocabulary (§9): `system_type`, `upright`, `links`, `spring`, `damper`, `axle_body`.
2. **Inter-axle coupling** — rockers, walking beams, trunnion springs, shared air or hydraulic circuits — described once in the top-level `suspension_couplings` array (§23.5) and referenced from the corners.

### 23.1 Wheel Station Naming

Corner keys follow the pattern **`A{n}{side}`**:

| Part    | Meaning                                                                 |
|---------|-------------------------------------------------------------------------|
| `A{n}`  | Axle index, 1-based, counted from the front (`A1`, `A2`, … `A99`)       |
| `L`     | Left station (negative Y)                                               |
| `R`     | Right station (positive Y)                                              |
| `C`     | Single wheel on the centreline (reverse trikes, three-wheelers, special rigs) |

```json
"suspension": { "A1L": { }, "A1R": { }, "A2L": { }, "A2R": { }, "A3L": { }, "A3R": { } }
```

**Legacy aliases.** `FL`, `FR`, `RL`, `RR` are aliases of `A1L`, `A1R`, `A2L`, `A2R`.

Rules:

1. A file MUST use one naming form throughout: either all four legacy names or A-notation. Mixing (`FL` with `A2L`) is invalid.
2. Legacy names are only valid for two-axle vehicles. Any vehicle with three or more axles, or a centreline wheel, MUST use A-notation.
3. Axle indices MUST be contiguous from `A1`.
4. An axle has either side stations (`L` and `R`) or one centreline station (`C`), never both. An axle with only `L` or only `R` is allowed but produces a warning.
5. The same keys are used everywhere a per-station object appears: `chassis.mass_unsprung_per_corner`, `powertrain.half_shafts`.
6. A wheel station is one hub. Dual wheels on one hub are still one station (§23.4).

**Reference frame for vehicles without a front steer axle** (semi-trailers, modular trailers): the origin is the centre of `A1` at ground level, exactly as for cars. A semi-trailer's or centre-axle trailer's CG normally lies ahead of `A1` (positive X) because part of its weight rests on the king-pin or drawbar; validators MUST NOT flag this when `vehicle_info.vehicle_class` is `"semi_trailer"` or `"trailer"`. Hitch/king-pin geometry and articulated combinations are not part of this section (§23.8).

### 23.2 `axles` — Per-Axle Metadata

Optional top-level array. Ids match the corner prefix.

| Key           | Type    | Required | Description                                                         |
|---------------|---------|----------|---------------------------------------------------------------------|
| `id`          | string  | YES      | `"A1"`, `"A2"`, …                                                   |
| `label`       | string  | no       | Free text: `"steer"`, `"drive"`, `"pusher"`, `"tag"`                |
| `position_x`  | number  | no       | Axle centreline X in vehicle frame (m). Decreases rearwards.        |
| `track`       | number  | no       | Track at this axle, between station `wheel_center`s (centre of duals) (m). `0` for a `C` station. |
| `steered`     | boolean | no       | Wheels on this axle are steered (by any means, §8.6)                |
| `driven`      | boolean | no       | Axle receives drive torque                                           |
| `liftable`    | boolean | no       | Axle can be raised off the ground                                    |
| `lift`        | object  | no       | Lift geometry (below)                                                |
| `max_load`    | number  | no       | Rated axle load (N)                                                  |

`lift` object:

| Key                | Type   | Description                                                   |
|--------------------|--------|---------------------------------------------------------------|
| `mechanism`        | string | `"air_lift_spring"`, `"hydraulic"`, `"mechanical"`            |
| `placement`        | string | `"pusher"` (ahead of drive axles), `"tag"` (behind), `"trailer"` |
| `travel`           | number | Ground-to-tyre clearance when lifted (m)                      |
| `lift_spring_area` | number | Effective area of the lift air spring(s) (m²)                 |

> **Static description only.** Whether a lift axle is currently raised is operating state, not vehicle data. Describe the lifted and lowered configurations with an override file (§3.4) if both are needed.

### 23.2.1 `axle_groups` — Loads per Axle Group *(v0.99.1)*

Manufacturers usually publish loads for **groups** of axles, not for each axle: "front axles 14 200 kg", "rear bogie 21 000 kg", unladen "front axle 6 359 / rear axle 3 073 kg". Splitting those figures per axle would invent data, so SVJ stores them at group level.

| Key               | Type   | Required | Description                                                     |
|-------------------|--------|----------|-----------------------------------------------------------------|
| `id`              | string | YES      | Group id, e.g. `"front_axles"`, `"rear_bogie"`                  |
| `axle_refs`       | array  | YES      | Axles in the group, e.g. `["A1", "A2"]`                         |
| `label`           | string | no       | Free text, e.g. `"twin steer"`, `"tandem drive"`, `"tridem"`    |
| `max_load_design` | number | no       | Technical (design) load limit of the group (N)                  |
| `max_load_legal`  | number | no       | Legal plated load limit of the group (N)                        |
| `kerb_load`       | number | no       | Published unladen load on the group (N)                         |
| `jurisdiction`    | string | no       | Where `max_load_legal` applies, e.g. `"UK"`, `"EU"`, `"US-FHWA"` |

Rules:

- An axle SHOULD belong to at most one group. A single axle may form its own group.
- Loads are forces in N like `axles[].max_load`; convert published kg with g = 9.80665 m/s² and keep the original figure in `_source`.
- Group `kerb_load`s SHOULD sum to `chassis.mass_total × g` (trailers: minus the king-pin/drawbar load). Validators warn above 3 % difference.
- Vehicle-level plated figures (GVM, GCM, design vs legal) go in `chassis.plated_masses` (kg).

```json
"axle_groups": [
  { "id": "front_axles", "label": "twin steer", "axle_refs": ["A1", "A2"], "max_load_design": 139254, "kerb_load": 62359, "_source": "14200 kg design; 6359 kg unladen" },
  { "id": "rear_bogie",  "label": "tandem drive", "axle_refs": ["A3", "A4"], "max_load_design": 205940, "max_load_legal": 186326, "jurisdiction": "UK", "kerb_load": 30136 }
]
```

### 23.3 Steering on Several Axles

See §8.6 (`steering.axle_ref`, `steering.additional_axles`). Mark each steered axle `steered: true` in `axles`; tie rods and steering arms stay in the corner hardpoints as usual.

### 23.4 Multiple Wheels per Station

A station can carry more than one wheel on the same hub: dual (twin) rear wheels on pickups, tractors and trailers, or four tyres per side on modular trailer axle lines. Suspension kinematics are unaffected — only `wheel` changes.

| Key             | Type    | Required | Description                                                          |
|-----------------|---------|----------|----------------------------------------------------------------------|
| `multiplicity`  | integer | no       | Wheels at this station, 1–4. Default `1`.                            |
| `dual_spacing`  | number  | no       | Centre-to-centre spacing of the wheels (m), symmetric about `wheel_center` |
| `positions`     | array   | no       | Explicit per-wheel data; length MUST equal `multiplicity`            |

`positions[]` entries:

| Key                  | Type   | Required | Description                                                     |
|----------------------|--------|----------|-----------------------------------------------------------------|
| `offset_outboard`    | number | YES      | Lateral offset of this wheel's centreplane from the station `wheel_center` (m). Positive = outboard, on both sides. |
| `label`              | string | no       | `"inner"`, `"outer"`, …                                        |
| `tire`               | object | no       | Tire assignment for this wheel (§9.10). Overrides the corner `tire`. |
| `rim_offset`         | number | no       | Rim offset of this wheel (m)                                    |
| `mass`               | number | no       | Mass of this wheel + tyre (kg)                                  |
| `rotational_inertia` | number | no       | Spin inertia of this wheel (kg·m²)                              |

```json
"wheel": {
  "rim_diameter": 0.5715, "rim_width": 0.2286,
  "multiplicity": 2,
  "positions": [
    { "label": "inner", "offset_outboard": -0.165, "tire": { "set_ref": "drive_315_80r22_5", "pressure": 850000 } },
    { "label": "outer", "offset_outboard":  0.165, "tire": { "set_ref": "drive_315_80r22_5", "pressure": 850000 } }
  ]
}
```

Rules and conventions:

- `wheel_center` is the centre of the wheel group (the midpoint of the duals). Track is measured between these points, which matches the usual truck definition.
- If `positions` is absent and `dual_spacing` is given, the wheels are placed symmetrically at ±`dual_spacing`/2 and share the corner `tire`.
- `wheel.mass` / `rotational_inertia`, when given at station level, are totals for all wheels. `mass_unsprung_per_corner` includes every wheel at the station.
- One brake assembly (§9.9) and one half-shaft (§10.9) per station, regardless of wheel count.
- A consuming solver runs one tire model per wheel and sums the forces at the hub. Inner and outer wheels may have different pressure, wear or radius.
- Wheel formulas (`vehicle_info.wheel_formula`) count stations, not tyres: a 6×4 truck with duals has 10 tyres.

### 23.5 `suspension_couplings` — Inter-Axle Load Sharing

Optional top-level array. Each entry describes one element that makes the load on one axle depend on another. Corners stay complete definitions; couplings only reference them.

Common fields:

| Key            | Type   | Required | Description                                                          |
|----------------|--------|----------|----------------------------------------------------------------------|
| `id`           | string | YES      | Unique id, referenced by `spring.coupling_ref`                      |
| `type`         | string | YES      | See table below                                                      |
| `side`         | string | per type | `"L"`, `"R"`, `"C"`, `"both"` — mechanical bogies are usually one per side |
| `axle_refs`    | array  | per type | Axles joined by the element (`["A2", "A3"]`)                        |
| `pivot_position` | [x,y,z] | per type | Main pivot of the element (rocker pin, beam saddle, trunnion) (m) |
| `mass`         | number | no       | Mass of the coupling element itself (kg)                            |
| `inertia`      | object | no       | Inertia about its own CG (§7.1 format)                              |
| `description`  | string | no       |                                                                      |

| `type`               | Physical arrangement                                                    | Required fields |
|----------------------|-------------------------------------------------------------------------|-----------------|
| `equalizer_rocker`   | Adjacent leaf-spring ends hang from a rocker on a chassis hanger (tandem/triple leaf trailers, four-spring truck tandems, compensated twin-steer fronts) | `pivot_position`, `connections` |
| `walking_beam`       | Axles at the ends of a longitudinal beam pivoting at its centre on a spring saddle (vocational trucks; also Tatra-style shared leaf and passive rocker-bogies) | `side`, `axle_refs`, `pivot_position` |
| `trunnion_spring`    | One leaf pack per side pivoting on a trunnion between the axles, ends resting on axle seats, axles located by torque rods ("camelback") | `side`, `axle_refs`, `pivot_position`, `spring` |
| `pneumatic_circuit`  | Air springs sharing a supply / levelling valve                          | `members` |
| `hydraulic_circuit`  | Suspension cylinders plumbed together: 3- or 4-point support groups (modular trailers, SPMTs), hydropneumatic interconnection | `members` |
| `custom`             | Anything else; describe with `x_` keys                                  | — |

Type-specific fields:

| Key                   | Type    | Used by              | Description |
|-----------------------|---------|----------------------|-------------|
| `connections`         | array   | `equalizer_rocker`   | Items `{corner_ref, spring_end: "front"\|"rear", attach_point, arm_length, shackle_length}` — one per spring end on the rocker |
| `rocker_shape`        | string  | `equalizer_rocker`   | `"straight"`, `"medium_triangle"`, `"tall_triangle"`, `"other"` (informational — geometry is authoritative) |
| `beam_length`         | number  | `walking_beam`       | Distance between beam end joints (m) |
| `end_points`          | array   | `walking_beam`       | Beam end joint positions, one per axle in `axle_refs` order |
| `end_bushings`        | object  | `walking_beam`       | Bushing at the beam ends (§9.2.5) |
| `pivot_type`          | string  | `walking_beam`       | `"fixed"` centre bushing or `"floating"` (saddle without fixed pivot) |
| `centre_spring`       | object  | `walking_beam`       | Spring between saddle and frame (§9.3 format); rate is at the saddle, not the wheel |
| `spring`              | object  | `trunnion_spring`    | The trunnion leaf pack (§9.3 format), rate at the trunnion |
| `end_seats`           | array   | `trunnion_spring`    | Spring end contact positions on the axles |
| `torque_rod_refs`     | array   | `trunnion_spring`, `walking_beam` | Paths `"<corner>.links.<name>"` to the links that react drive/brake torque |
| `members`             | array   | circuits             | Corner keys whose `spring` is part of the circuit |
| `levelling_valves`    | integer | `pneumatic_circuit`  | Number of height control valves |
| `ride_height_setpoint`| number  | `pneumatic_circuit`  | Controlled ride height (m) |
| `supply_pressure`     | number  | circuits             | Pa |
| `orifice_diameter`    | number  | circuits             | Restriction between members (m); governs dynamic (vs static) sharing |
| `support_scheme`      | string  | `hydraulic_circuit`  | `"3_point"`, `"4_point"`, `"individual"`, `"cross_connected"` |
| `group`               | integer | `hydraulic_circuit`  | Group number within the support scheme |
| `interconnection`     | string  | `hydraulic_circuit`  | `"heave"`, `"roll"`, `"pitch"`, `"warp"`, `"load_group"` |
| `accumulator`         | object  | `hydraulic_circuit`  | `{gas_volume, gas_precharge_pressure, polytropic_index}` or `null` |
| `fluid_bulk_modulus`  | number  | `hydraulic_circuit`  | Pa |

```json
"suspension_couplings": [
  {
    "id": "rear_bogie_L", "type": "walking_beam", "side": "L",
    "axle_refs": ["A2", "A3"],
    "pivot_position": [-4.52, -0.55, -0.62],
    "beam_length": 1.37, "pivot_type": "floating", "mass": 95,
    "end_points": [[-3.835, -0.55, -0.50], [-5.205, -0.55, -0.50]],
    "centre_spring": { "type": "rubber_block", "rate": 900000 },
    "torque_rod_refs": ["A2L.links.lower_torque_rod", "A3L.links.lower_torque_rod"]
  },
  {
    "id": "drive_air", "type": "pneumatic_circuit",
    "members": ["A3L", "A3R", "A4L", "A4R"], "levelling_valves": 1
  }
]
```

**How corners refer to a coupling.** A station whose vertical support comes entirely from the coupling sets `spring.type: "none"` and `spring.coupling_ref: "<id>"`. A station with its own spring that is additionally coupled (leaf springs on a rocker, air springs on a circuit) keeps its spring and is referenced from the coupling (`connections`, `members`).

**Mass accounting.** `mass` of a coupling element is not included in `mass_unsprung_per_corner`; it MUST be included in `chassis.mass_total`.

**Engineering notes for converters:**

- **Torque reaction.** In mechanical bogies, drive and brake torque can move load from one axle to the other ("bogie hop"). The torque rods that counteract this are ordinary corner `links` (type `"torque_rod"`); list them in `torque_rod_refs` so a solver knows the reaction path.
- **Friction.** Load equalisation of leaf-spring bogies is strongly affected by friction at sliding spring ends. Use `spring.end_type_front` / `end_type_rear` and `spring.end_friction` (§9.3).
- **Static vs dynamic sharing.** Pneumatic and hydraulic circuits equalise static load fully; dynamic sharing depends on `orifice_diameter`.
- **Axle bodies stay per axle.** `axle_body` couples the two sides of one axle. It MUST NOT be shared across axles; inter-axle links belong here.

### 23.6 Composite Fields on Multi-Axle Vehicles

| Field                         | Meaning for N axles                                                              |
|-------------------------------|----------------------------------------------------------------------------------|
| `chassis.wheelbase`           | Measured as declared by `chassis.wheelbase_reference` (table below). `axles[].position_x` is authoritative whenever present; `wheelbase` is the published headline figure |
| `chassis.track_front`         | Track at `A1`                                                                     |
| `chassis.track_rear`          | Track at the last axle (`0` for a `C` station). Per-axle values: `axles[].track`  |
| `chassis.mass_unsprung_per_corner` | Keyed by station name; includes all wheels at the station                  |
| `static_setup.corner_weight`  | Per station; all stations SHOULD sum to `mass_total × g`                          |
| `powertrain.layout`           | `"multi_axle"`; the driveline is defined by `driveshafts`, `differentials` (`axle_ref`, `location: "inter_axle"`, `through_drive`) and `half_shafts` |
| `vehicle_info.wheel_formula`  | e.g. `"6x4"`, `"8x8/4"` (stations × driven / steered)                           |

**Wheelbase definitions.** Makers measure "wheelbase" differently on multi-axle vehicles. Declare which one the file uses:

| `wheelbase_reference` | Measured from → to | Typical use |
|-----------------------|--------------------|-------------|
| `"last_axle"` (default) | `A1` → last axle | Two-axle vehicles; many trailer sheets |
| `"bogie_centre"` | `A1` → centre of the rear axle group | EU tandem-drive rigids and tractors |
| `"bogie_centres"` | Centre of the front axle group → centre of the rear axle group | US / military practice (e.g. HEMTT) |
| `"first_rear_axle"` | Last axle of the front group → first axle of the rear group | UK body-builder sheets for twin-steer rigids (MAN "L1") |
| `"theoretical"` | Maker's load-equivalent wheelbase; not checked geometrically | Volvo "theoretical wheelbase", ISO 612 derived values |
| `"explicit"` | `chassis.wheelbase_from` → `chassis.wheelbase_to` (axle ids or `axle_groups` ids; a group means its centre) | Anything else |

Front and rear groups are taken from `axle_groups` (the group containing `A1`, and the group containing the last axle). Without `axle_groups`, the vehicle is split at the largest gap between consecutive axles: axles ahead of it form the front group, axles behind it the rear group (a two-axle vehicle gives `A1` and `A2`).

### 23.7 Validation Rules

`tools/validate.py` runs the JSON Schema and then `tools/multiaxle_check.py`, which enforces the rules above that a schema cannot express (the same rules ship in `svj-py` as `svj/multiaxle.py`):

- **Errors:** mixed naming forms; incomplete legacy set; non-contiguous axle indices; `C` together with `L`/`R` on one axle; `axles[]` id without stations; `wheel.positions` length ≠ `multiplicity`; unresolved `coupling_ref`, `axle_refs`, `members`, `connections`, `torque_rod_refs`; `axle_body` id shared across axles; `mass_unsprung_per_corner` / `half_shafts` keys without a matching station or in a different naming form; `steering.additional_axles` referring to a missing or the primary axle; `differentials[].axle_ref` missing.
- **v0.99.1 errors:** `axle_groups` ids duplicated or referring to missing axles; `wheelbase_from`/`wheelbase_to` missing or unresolved when `wheelbase_reference` is `"explicit"`.
- **v0.99.1 warnings:** an axle in more than one group; `chassis.wheelbase` differing from the declared definition by more than 10 mm; group `kerb_load`s differing from `mass_total × g` by more than 3 % (not for trailers).
- **Warnings:** stations without `axles[]` entry (or no `axles[]` on 3+ axles); `position_x` not decreasing; `system_type` expecting `axle_body` without one; `pendulum_axle` without `pendulum_pivot`; `spring.type: "none"` without `coupling_ref`; circuit members with the wrong spring type; wheelbase inconsistent with `axles[].position_x`; single-sided axles.

### 23.8 Not Covered Yet

- **Articulated combinations** — tractor + semi-trailer, drawbar trailers, dollies, articulated dump trucks. These are several bodies joined by a fifth wheel, hitch or articulation joint and need a separate "vehicle units & couplings" addendum. Today, describe each unit in its own file. Interfaces, the combination file and assembly are specified in §27 (research and UN R55 classes in `proposals/trailer_coupling_research.md`).
- **Operating state** — lift axle raised/lowered, hydraulic group re-plumbing, steering modes. Use override files (§3.4) for alternative configurations.

---

## 24. Movable Parts and Attachments *(v0.99.5)*

This section is **optional**. A file without `constraints` and `poses` is fully valid and describes the vehicle in a single rigid configuration. Readers that do not handle movable parts MUST ignore both and treat every body as welded to its `parent`.

### 24.1 Purpose and model

SVJ describes a vehicle as a set of rigid bodies with **mass properties**, connected by **constraints** and **force elements**. This section adds the missing connection layer so that doors, hoods, tilt cabs, tipper bodies, tractor loaders, three-point hitches, excavator arms and cranes are physical, simulatable assemblies and not frozen geometry:

- a **part** is a `chassis.mass_bodies[]` entry: mass, CG, full inertia tensor, named `markers` (§24.2);
- a **joint** removes degrees of freedom between two parts, with limits, end stops, friction, damping and optional compliance (§24.4);
- a **spring** is a passive force element between two markers (§24.5);
- an **actuator** is a linear drive (hydraulic or electric ram) with a stroke and force limits (§24.6);
- a **latch** holds a joint at a position until a force releases it, and a **coupling** makes one joint follow another (§24.6.1, §24.6.2);
- a **contact** stops a part against a pad, seal or seat (§24.6.3);
- a **pose** is a named set of joint coordinates (§24.7); every pose has a derived composite mass, CG, inertia and element lengths (§24.8).

All positions and orientations are in the vehicle frame **at the reference pose**: the configuration in which the file's geometry, meshes and `mass_bodies` positions are authored and every joint coordinate is zero.

### 24.2 Parts

| Field | Where | Description |
|---|---|---|
| `mass`, `position`, `inertia` | `mass_bodies[]` | Mass (kg), CG in the vehicle frame (m), inertia about the body's own CG |
| `inertia` as a matrix | `mass_bodies[]` | The full symmetric tensor `[[Ixx,-Ixy,-Ixz],[-Ixy,Iyy,-Iyz],[-Ixz,-Iyz,Izz]]` (kg·m²) instead of the object of §7.1; the two forms are equivalent |
| `inertia_orientation` | `mass_bodies[]` | Optional unit quaternion giving the frame in which `inertia` is expressed (typically the principal axes), relative to the vehicle axes. The vehicle-axes tensor is `R · I · Rᵀ`. Default identity |
| `markers` | `mass_bodies[]`, `chassis` | Named frames `{position, orientation}` fixed to the body (hinge points, cylinder ends, hitch pins). `chassis.markers` are the frames on the chassis side of a joint |
| `parent` | `mass_bodies[]` | Hierarchy (§7.2). A body no constraint mentions is **welded** to its `parent` and follows it; a body named by a joint moves as the joint allows |
| `category: "attachment"` | `mass_bodies[]` | Recommended for loaders, implements and bodies that are not part of the base vehicle |

`ground` and `chassis` are the two implicit root bodies. Body ids MUST NOT contain `.`: the dot is reserved for qualifying the bodies of an attached unit (`loader.boom`, planned §24.11). The recommended `category` set of §7.2.1 gains `"attachment"`.

**Names.** `id` is the stable key and should be the canonical part name of `docs/naming_convention.md` (lowercase, part first and side last: `door_fl`, `hood`, `tailgate`, `loader_boom`, `tipper_body`); an optional `name` carries the human label. The same vocabulary and the constraint, element and marker patterns (`hinge_<part>`, `<part>_cylinder`, `<part>_latch`, marker `hinge`, …) are defined there; `tools/constraints_check.py` flags an *alias* of a listed part (`hatch` for `tailgate`) and leaves unlisted names alone. *(v0.99.7)*

A body that moves needs a positive mass and a physically possible inertia tensor (positive definite and satisfying the triangle inequalities); a moving body without `inertia` is treated as a point mass and the checker warns.

### 24.3 `constraints[]`

Optional top-level array. Common fields:

| Key | Type | Required | Description |
|---|---|---|---|
| `id` | string | YES | Unique id |
| `name` | string | no | Short display label *(v0.99.7)* |
| `type` | string | YES | `"joint"`, `"spring"`, `"actuator"`, `"latch"`, `"coupling"`, `"contact"` |
| `body_a`, `body_b` | string | YES for joint, spring, actuator, contact | Body ids (`mass_bodies[].id`, `"chassis"`, `"ground"`); `body_a` is the reference (parent) side, `body_b` the moving side |
| `marker_a`, `marker_b` | string | joint, spring, actuator, contact: one of marker/frame per side | Marker names on the respective body (`mass_body.markers`, or `chassis.markers`) |
| `frame_a`, `frame_b` | object | | Inline `{position, orientation}` instead of a marker (required for `ground`) |
| `description` | string | no | |

**Frame convention.** The axis of a joint is the **+Z axis of its frame**; the frame's `orientation` quaternion therefore *is* the hinge, slide or hinge-plane direction (the ADAMS marker convention). At the reference pose the two frames of a joint **coincide** and their Z axes are parallel.

### 24.4 `joint`

`joint_type` selects the motion of `body_b` relative to `body_a`. The joint coordinate is a vector, measured in the `body_a` frame from the reference pose (all zero):

| `joint_type` | Coordinate | Motion |
|---|---|---|
| `revolute` | `[θ]` | rotation about frame Z |
| `translational` | `[d]` | translation along frame Z |
| `cylindrical` | `[θ, d]` | rotation about and translation along frame Z |
| `spherical` | `[rx, ry, rz]` | rotation vector (axis × angle) about the frame origin |
| `universal` | `[θx, θy]` | rotation about frame X, then about frame Y |
| `planar` | `[x, y, θ]` | translation in the frame XY plane and rotation about Z |
| `fixed` | `[]` | no motion: a rigid attachment that is still a separate body |

| Key | Description |
|---|---|
| `range` | `{min, max}`: numbers for a one-coordinate joint, arrays (`null` = free) otherwise; rad or m. The reference pose (0) MUST lie inside |
| `stop` | `{stiffness, damping, restitution}` of the end stops at `min` / `max`; omitted = rigid stop |
| `friction` | Coulomb friction torque (N·m) or force (N) |
| `damping` | Viscous damping (N·m·s/rad or N·s/m) |
| `bushing` | Compliance instead of a perfect joint: a `bushing_obj` (§9.2.5) in the frame |
| `drive` | Optional actuation of a one-coordinate joint (a motor, a powered hinge): `{mode, target, max_force, max_rate, stiffness, damping}` with `mode` `free` (unpowered), `position` (holds / seeks `target`), `velocity` (runs at `target`) or `force` (applies `target` as a constant torque / force); `max_force` is N·m or N, `max_rate` rad/s or m/s |

### 24.5 `spring`

A passive force element between the two markers.

| Key | Description |
|---|---|
| `rate` / `rate_curve` | Linear rate (N/m) or force–length curve (`curve2d`, strictly increasing x); exactly one |
| `free_length` | Length at zero force (m) |
| `preload` | Force at `free_length` (N) |
| `damping` | Viscous damping along the element (N·s/m) |

| `kind` | `"linear"` (default) or `"torsional"` (a torsion bar, an anti-roll bar half, a twist beam): a torsional spring acts about the +Z axis shared by its two frames, with `rate` in N·m/rad and `free_angle` in rad *(v0.100)* |
| `reference` | `"element"` (default) or `"wheel"`: whether `rate` / `rate_curve` are those of the element or quoted at the wheel (§25.3) *(v0.100)* |
| `spring_type`, `mass` | Informational: `coil`, `coilover`, `torsion_bar`, `leaf`, `air`, … and the element mass *(v0.100)* |

For a hydraulic or hydropneumatic spring (`spring_type` `hydraulic`, `hydropneumatic`, `none`) `rate` is not required.

#### 24.5.1 `damper` *(v0.100)*

A passive damping element between two frames.

| Key | Description |
|---|---|
| `bump_curve`, `rebound_curve` | `curve2d` of velocity along the element (m/s; rad/s if torsional) against force (N; N·m): compression and extension. Both are given, or a linear `damping` instead |
| `damping` | Linear damping (N·s/m, or N·m·s/rad) |
| `kind`, `reference` | As for `spring` (§25.3) |
| `mass` | Informational |

### 24.6 `actuator`

A linear drive between the two markers: a hydraulic cylinder or electric ram on a loader, tipper, tilt cab or hitch.

| Key | Description |
|---|---|
| `retracted_length` | Distance between the two frames fully retracted (m) |
| `stroke` | `{min, max}` extension from `retracted_length` (m); working length = `retracted_length + stroke` |
| `bore_diameter`, `rod_diameter`, `max_pressure` | m, m, Pa: push force limit = `p · π/4 · D²`, pull force limit = `p · π/4 · (D² − d²)` |
| `max_force` | N, an alternative to bore and pressure |
| `damping` | N·s/m |

An actuator produces force; it does not impose a kinematic relation. The poses set the joint coordinates and the checker derives each actuator's length from the geometry and verifies that it lies inside its reach, which is the solver-free test that a cylinder really lifts a boom to the stated pose.

#### 24.6.1 `latch`

Holds one coordinate of a joint at a position until the load on the joint exceeds a threshold: a door or hood latch, a door check (detent), a cab or tipper lock.

| Key | Required | Description |
|---|---|---|
| `joint_ref` | YES | `id` of a `joint` |
| `coordinate` | no | Which coordinate is held (default 0; one-coordinate joints only have 0) |
| `position` | YES | Coordinate value at which the latch engages (rad or m); inside the joint's `range` |
| `holding_force` | YES | Torque (N·m) or force (N) above which it lets go |
| `state` | no | `latched` or `released` (default) at the reference pose. A latch that is `latched` at the reference pose MUST engage at position 0 |

A joint may have several latches (a closed latch at 0 and a door check at 0.55). A latch has no frames: it acts on the joint it refers to.

#### 24.6.2 `coupling`

A kinematic relation between two joint coordinates: `q_b = ratio · q_a`. It models a linkage that makes one joint follow another (a self-opening tailgate, a parallel-lift loader that keeps the bucket level, a scissor hinge, mirrored doors).

| Key | Required | Description |
|---|---|---|
| `joint_a`, `joint_b` | YES | Ids of two different joint coordinates |
| `coordinate_a`, `coordinate_b` | no | Coordinate index on each joint (default 0) |
| `ratio` | YES | Non-zero; `q_b = ratio · q_a` (negative for opposed motion) |

In a pose, a joint that is coupled and **not named** takes its coordinate from the joint it is coupled to, in either direction, and chains of couplings propagate. A pose that names both joints must satisfy the relation.

#### 24.6.3 `contact`

A one-sided penalty contact between two shapes attached to two bodies: a hood resting on its rubber stops, a door on its seal, a flap on its seat. It acts between **any two bodies**, including a body and the parent it is hinged to (for the end of a joint's range prefer the joint's `stop`).

| Key | Required | Description |
|---|---|---|
| `body_a`, `body_b`, markers / frames | YES | As for any two-body constraint; each shape is centred on its frame |
| `shape_a`, `shape_b` | YES | `{type, …}` with `type` `point`, `plane`, `sphere`, `box` or `cylinder` |
| `law` | YES | `{gap, stiffness, damping, friction, restitution}`: `stiffness` (N/m) is required; `gap` is the signed distance at the reference pose (m, default 0: > 0 clearance, < 0 pre-compressed); `damping` (N·s/m); `friction` is a dimensionless coefficient; `restitution` is 0–1 |

Shapes: `point` (the frame origin); `plane` (through the origin, normal along the frame **+Z**, free side +Z — an *infinite half-space*, so use a `sphere` or `box` pad for a stop the part can swing away from in another direction); `sphere` (`radius`); `box` (`size` = the three full lengths along the frame axes); `cylinder` (`radius`, `length`, axis along the frame Z).

Supported pairs (either order): point / sphere / box / cylinder against a `plane`; sphere against sphere; point or sphere against a box. The **signed distance** is positive when apart, zero when touching, negative when interpenetrating. Contact with the ground or soil is not described here: tyre and terrain models cover vehicle–ground interaction.

### 24.7 `poses[]`

```json
"poses": [
  { "id": "closed" },
  { "id": "loader_dump", "values": { "hinge_loader_boom": 0.9, "hinge_loader_bucket": -0.8 } },
  { "id": "hood_up", "values": { "hinge_hood": 0.95 }, "aero_setting_ref": "hood_open" }
]
```

`values` maps a joint id to its coordinate (a number for one-coordinate joints, an array otherwise, rad / m); joints not named stay at 0 unless a `coupling` fixes them (§24.6.2). A pose without `values` is the reference pose. `aero_setting_ref` may name an `aerodynamics.components[].settings[].name` that applies in the pose.

### 24.8 Derived quantities

For a pose, a tool computes (`tools/constraints_check.py`, `svj.constraints`, `Vehicle.pose_*`):

0. **Coupled coordinates.** Couplings fill in the coordinates the pose does not name (§24.6.2).
1. **Body transforms.** Starting with the identity at `chassis` and `ground`, each joint gives its child `X_b = X_a ∘ M`, where `M` is the joint motion expressed about the `body_a` frame in reference-world coordinates (`M = F · L(q) · F⁻¹`, `F` the frame, `L` the local motion of the table above). Bodies welded through `parent` inherit their parent's transform.
2. **CG.** `CG(pose) = CG_ref + Σ mᵢ (Xᵢ(pᵢ) − pᵢ) / M`, with `M = mass_total`.
3. **Composite inertia.** From `chassis.inertia` (reference pose, about `CG_ref`): for every moved body replace its reference contribution `I_i + mᵢ·S(pᵢ − CG_ref)` by `R I_i Rᵀ + mᵢ·S(Xᵢ(pᵢ) − CG_ref)`, then move the reference point to the new CG (`I_cg = I_o − M·S(δ)`), where `S(d) = |d|²·1 − d dᵀ`. A body without inertia counts as a point mass. Returned as the §7.1 object or as the 3×3 matrix.
4. **Element lengths** of springs and actuators from their two frames after transformation.

`mass_total`, `center_of_gravity` and `inertia` keep describing the reference pose and, when attachments are modelled inside the file, MUST include them. Closed kinematic loops (a four-bar linkage) are allowed but are not solved: poses give the independent coordinates and the checker warns.

### 24.9 Mapping to multibody tools

| SVJ | Multibody entity (ADAMS terms) |
|---|---|
| `mass_bodies[]` (`mass`, `inertia`, `position`) | PART with mass, inertia and a centre-of-mass MARKER |
| `markers`, `chassis.markers`, inline frames | MARKER (position + orientation) |
| `constraints[]` `joint` | JOINT of the same type (revolute, translational, cylindrical, spherical, universal, planar, fixed) |
| `range` + `stop` | joint LIMIT / bump-stop force |
| `friction`, `damping` | joint friction and damping |
| `bushing` | BUSHING instead of a joint |
| `spring` (linear) | SPRINGDAMPER, translational |
| `spring` (torsional), `damper` | SPRINGDAMPER, rotational; translational damper |
| `actuator` | cylinder force element (SFORCE / hydraulic) driven by the stroke |
| `poses[]` | initial-condition sets (joint displacements with zero velocity) |
| `latch` | state-dependent holding force (engage position, release threshold) |
| `coupling` | COUPLER / GEAR between two joints |
| `drive` | MOTION / motor torque with a limit |
| `contact` | CONTACT (sphere / box / plane … with a penalty law) |

### 24.10 Validation rules

`tools/constraints_check.py` (run by `tools/validate.py`; mirrored as `svj-py/svj/constraints.py`) enforces:

- **Errors:** `body_a` / `body_b` exist and differ; each side has a marker or frame and the marker exists; unique constraint and pose ids; unit quaternions; `range.min ≤ range.max` per coordinate, array length matching the joint type, reference pose inside the range; pose values have the right length, are inside the ranges and name joints; the two frames of a joint coincide (1 mm) and their Z axes are parallel at the reference pose; no body is connected to the roots only through unreachable joints (no floating bodies); `spring` has one of `rate` / `rate_curve`; `actuator.stroke.min ≤ max` and `rod_diameter < bore_diameter`; for the reference pose and every pose, each actuator's derived length lies within its reach; `aero_setting_ref` resolves; an inertia matrix is symmetric; a moving body has positive mass; a `latch` refers to a joint and a coordinate that exist, engages inside the joint range, and engages at 0 when `latched` at the reference pose; a `coupling` joins two different existing coordinates with a non-zero ratio, and a pose that names both joints satisfies it; coordinates a coupling derives for a pose stay inside their ranges; a `contact` has two supported shapes with valid dimensions, `law.stiffness`, and at the reference pose the shapes are `law.gap` apart (1 mm); a `drive` is on a one-coordinate joint, has a `target` unless `free`, and a position target inside the range.
- **Warnings:** a moving body without an inertia tensor or with a physically impossible one; an actuator without `max_force` or `bore_diameter` + `max_pressure`; a body that is the child of more than one joint (closed loop / over-constraint); a body whose `parent` differs from its joint's `body_a`; a spring or actuator whose end frames coincide; `.` in a body id; a coupling whose source range maps outside the target range; a joint coordinate driven by more than one coupling; a powered `drive` without `max_force`; in a pose, a contact whose shapes interpenetrate by more than 1 mm.

### 24.11 Not covered yet

Planned in `proposals/svj_articulated_parts_proposal.md`: collision proxies from glTF nodes. Attachments defined in their own files are specified in §27, the loop-closure solver in §26.

---

## 25. Wheel Stations — the Unified Suspension *(v0.100)*

Since v0.100 a suspension is described by the same parts as everything else in SVJ: **bodies**, **joints** and **elements** (§24), plus a thin **`wheel_stations[]`** list for the data that is not mechanical. The corner-based `suspension` section of §9 is **deprecated**: it is still accepted for one more release (validators warn), and `tools/migrate_suspension.py` converts a file.

The mechanism is defined by its components, never by a name or a type. A double wishbone is an upright, two arms and a tie rod joined by the joints they really have; a five-link variant, a pushrod and rocker, or an arrangement nobody has a name for is written the same way. `topology_hint` may carry a label (`double_wishbone`), but nothing is derived from it.

### 25.1 What a wheel station is made of

| Part | Written as |
|---|---|
| Wheel carrier (upright, hub carrier, axle housing, De Dion tube) | a `mass_body`; its hardpoints are `markers` (`wheel_center`, `strut_lower`, `spring_pad`, …) |
| Control arms, links, tie rods, struts, torque rods | `mass_bodies`, with their canonical part names (§25.7) |
| Wheel (rim + tyre) | a `mass_body` joined to the carrier by a `revolute` joint about the lateral axis through the wheel centre |
| Link ends | `joint` constraints with coincident frames and stated types (spherical, revolute, translational, fixed, …); compliance as `joint.bushing` |
| Steering rack | a `mass_body` on a lateral `translational` joint; tie rods hang from it |
| Coil, air, torsion-bar spring | `spring` (§24.5) |
| Damper | `damper` (§24.5.1) |
| Bump and rebound stop | a `spring` whose force curve is zero until the stop engages |
| Leaf spring | a rigid body for the pack (front eye `revolute`, rear slipper `translational`, axle clamped by a `fixed` joint at the seat) and a `spring` at the seat; when the bending matters, a chain of segments with torsional springs (§25.10) |
| Torsion (twist) beam | two trailing-arm bodies and a `fixed` joint between them with a bushing soft in torsion (§25.11) |
| Anti-roll bar | `anti_roll_bars[]` as data (§25.5); as bodies and a torsional `spring` once its geometry is known |
| Tyre set, rim, brake, reference alignment | `wheel_stations[]` |

### 25.2 `wheel_stations[]`

One entry per wheel station; its `id` keeps the names of §23.1 (`FL`, `A2R`, …) and is also the key of `chassis.mass_unsprung_per_corner`.

| Key | Type | Required | Description |
|---|---|---|---|
| `id` | string | YES | Station name (§23.1) |
| `name` | string | no | Display label |
| `axle`, `side` | string | no | `A1`…, `L` / `R` / `C`; must agree with `id` |
| `wheel_body` | string | YES | `mass_bodies` id of the rotating wheel |
| `upright_body` | string | no | `mass_bodies` id of the wheel carrier the wheel is hinged to (shared by both stations of a beam axle) |
| `wheel_center_marker` | string | no | Marker of `upright_body` at the wheel centre (default `wheel_center`; `wheel_center_<station>` on a shared axle body) |
| `steering_joint` | string | no | id of the joint the steering drives (the rack slide); absent when the station is not steered |
| `coupling_ref` | string | no | `suspension_couplings` id that springs this station when it has no spring of its own |
| `topology_hint` | string | no | Descriptive label; nothing is derived from it |
| `wheel`, `tire`, `brake` | object | no | As before (§9.8, §11, §12): rim and wheel data, tyre set reference, brake |
| `alignment` | object | no | Declared reference alignment (camber, toe, caster, caster trail, KPI, scrub radius). It follows from the geometry, so a tool can compute it and compare |
| `static_setup`, `compliance_summary`, `visual` | | no | As before |

### 25.3 Springs and dampers

`spring` and `damper` (§24.5) are between two frames. Each has a **`kind`**: `linear` (default; along the line between the frames) or `torsional` (about their shared +Z axis: a torsion bar, an anti-roll bar half, a twist beam, a rotary damper), and a **`reference`**:

- `element` (default): rates and curves are those of the element itself (N/m, N, N·s/m, or N·m/rad …).
- `wheel`: rates and curves are quoted **at the wheel**, per metre of wheel travel, and the element stands for a vertical wheel-level spring or damper. Its two frames are nominal (the chassis above the wheel centre, the carrier at it). Most published data is of this form (Assetto Corsa, manufacturer sheets); a converter with no suspension geometry says `wheel`.

A wheel rate becomes an element rate through the **motion ratio** MR (element length change per unit of wheel travel): `rate_element = rate_wheel / MR²`; a force `F_wheel = F_element · MR` and a speed `v_element = v_wheel · MR`, so a wheel-referenced curve point `(v, F)` becomes `(v · MR, F / MR)`. The migration (§25.8) uses a given `motion_ratio`, otherwise estimates one from the geometry (the mount's first-order velocity along the element, divided by the vertical velocity of the wheel centre), and flags the result.

### 25.4 Steering

The rack is a body on a lateral `translational` joint to the chassis; each tie rod is a body with spherical joints to the rack and to the upright; the station's `steering_joint` names the rack joint. The steering wheel is a body on a `revolute` joint to the chassis (`hinge_steering_wheel`), and a `coupling` (§24.6.2) gives the rack its value, `q_rack = ratio · q_wheel`, with `ratio` in m per rad of wheel rotation (0.0063 m/rad is 39.6 mm of rack per turn): naming the wheel angle in a pose or in the solver's `joint_values` then steers the stations (§26). Power assist is `joint.drive` on the rack; the `steering` section still holds the lock-to-lock, assist and efficiency data.

### 25.5 Anti-roll bars

`anti_roll_bars[]`: `id`, `stations` (the stations it connects), `bar_rate` (N·m/rad), and optionally `wheel_rate_equiv`, `motion_ratio`, `mass`, `drop_link_mounts` (station → point). The old files carry no bar axis or lever geometry, so the bar stays data. With geometry it is two bar-half bodies on revolute joints to the chassis, a torsional `spring` between them and a drop-link rod from each half to the arm. The bar twist (the rotation of one half relative to the other about the bar axis) is what `element_angles()` returns for every torsional spring and damper; the torque is `rate` times that twist.

### 25.6 How an analysis finds the parts

A suspension analysis (wheel travel, camber and toe curves, bump steer, caster, kingpin inclination, roll centre) does not need to recognise a wishbone or an upright by name; the standard gives it the roles by reference:

| It needs | It reads |
|---|---|
| The wheel carrier and the wheel | `upright_body`, `wheel_body` |
| The wheel centre | the marker `wheel_center_marker` on the carrier |
| The wheel's spin axis (camber, toe) | the frame of the `revolute` joint between `upright_body` and `wheel_body` |
| The steering input (bump steer, caster, KPI) | `steering_joint`, with its `range` |
| The mechanism | every `joint` between the chassis (and the rack) and the carrier, with frames, types and bushings |
| Springs, dampers, stops | the elements between the same bodies |
| The driven coordinate for wheel travel | the vertical position of the wheel centre relative to the chassis |

Camber and toe are the angles of the spin axis to the vertical and to the longitudinal axis; caster, kingpin inclination and scrub follow from the steering axis, the screw axis of the carrier relative to the chassis under rack travel. Names help people and viewers; the analysis follows the references. Solving the loop for a given wheel travel is the job of §26.

### 25.7 Names

A body that corresponds to a well-known part keeps that part's canonical name (`upright_fl`, `upper_wishbone_fl`, `tie_rod_a2l`, `rack`, `leaf_spring_a1l`) with its meaning in `description` and a short label in `name` (`"Upright FL"`, *"Upright / knuckle / hub carrier"*), following `docs/naming_convention.md`; `tools/constraints_check.py` flags an *alias* of a known part (`knuckle_fr`). The vocabulary covers the suspension, steering and brake parts as well as panels and attachments (§24.2).

### 25.8 Migration and generated data

`tools/migrate_suspension.py` converts the corner section; it never invents data. Everything it creates carries **`x_derived: true`**: such bodies and joints may have no mass, an assumed axis or a missing joint type, and the checker reports these as warnings (never errors) until an author refines them and removes the flag. A zero `mass` is accepted by the schema only on `x_derived` bodies.

| Old | New |
|---|---|
| upright, links, axle body, wheel | bodies (existing `body_ref` bodies reused, shared axle bodies created once); hardpoints become markers on the carrier |
| implied or stated joint types | stated `joint` constraints (frames coincide at the reference pose) |
| tie rods | spherical joints to a `rack` body on a lateral slide |
| leaf spring link | leaf body: eye / slipper / seat joints (shackle swing not modelled) |
| `spring`, `damper` with both mounts | elements at the mounts, rates converted by the motion ratio (estimated and flagged `x_converted_from_wheel_rate` when not given) |
| `spring`, `damper` without mounts | `reference: "wheel"` elements at the wheel, values as quoted |
| `bump_stop`, `rebound_stop` | wheel-level `spring` with a curve zero until engagement |
| `arb` | `anti_roll_bars[]` |
| `system_type` | `topology_hint` |
| `wheel`, `tire`, `brake`, `alignment`, … | `wheel_stations[]` |

What the old data does not state is reported as a note: unknown joint types (leaf-sprung and swing axles), massless parts, assumed hinge axes, torsion-bar springs and axle-body fields without a unified counterpart (kept under `x_legacy_axle_body`).

### 25.9 Validation rules

`tools/constraints_check.py` adds to §24.10: `wheel_stations` ids unique and consistent with `axle` / `side`; `wheel_body` and `upright_body` are `mass_bodies` ids and a joint connects them; `steering_joint` is a joint; `wheel_center_marker` exists on the carrier; `anti_roll_bars` name existing stations; a `damper` has both curves (strictly increasing velocities) or a `damping`; torsional elements have parallel Z axes; generated (`x_derived`) items are exempt from the mass, parent, loop, connectivity and inertia rules (warnings only). `tools/multiaxle_check.py` and svj-py read the unified model through the same station ids.

### 25.10 Flexible leaf pack

A leaf pack loaded at the axle seat is two cantilevers clamped at the seat, each half the span `L` between the end attachments, with the bending stiffness `EI = E · n · b · t³ / 12` of `n` leaves of width `b` and thickness `t` (no inter-leaf friction; steel `E` = 206 GPa). It is written with the primitives that already exist, no new keys:

| Part | Written as |
|---|---|
| each half | `M` rigid segment bodies in a chain, each hinged to the previous one (the first to the axle) by a `revolute` joint about the lateral axis |
| bending | a torsional `spring` (§25.3) on every hinge, with rate `k = EI / l · (M + 1)(2M + 1) / (2M²)`, `l` being the segment length |
| front / rear end | an `eye` (`revolute` about the lateral axis) or a `slipper` (`translational` along x) between the last segment and the chassis; the default is an eye in front and a slipper behind, since two eyes would over-constrain the axle in x |
| seat | the chain starts at the axle body, so the axle is clamped by the first hinges |
| arch | the segments lie on a parabolic arch; every torsional spring is at rest in that shape (`free_angle` 0) |

The factor in `k` makes the tip deflection of the chain equal the exact cantilever value `F · (L/2)³ / (3EI)` for any `M`, so the vertical rate at the seat is `48 · EI / L³` however coarse the chain; more segments only give a better shape. The pack's mass is spread evenly over the segments, which are marked `x_derived` like every generated item. A flat rate at the seat (the `spring` of the old format) remains valid when bending shape does not matter.

`tools/leaf_pack.py` (and `svj.leafpack`) generates the bodies, joints and springs from `id`, `axle`, `x_front`, `x_rear`, `seat_x`, `y`, `z`, `leaves`, `width`, `thickness`, `mass` and optional `E`, `segments` (per half, default 4), `arch`, `end_front` / `end_rear`, `chassis`; `leaf_pack(p)["rate"]` is the seat rate. Shackles, inter-leaf friction and progressive (helper) leaves are not generated.

### 25.11 Torsion (twist) beam

A twist-beam axle is two trailing arms, each carrying its half of the cross beam, that meet at the middle of the beam. It needs no new keys:

| Part | Written as |
|---|---|
| each arm with its half beam | a body (`trailing_arm_rl`, `trailing_arm_rr`) on a `revolute` joint to the chassis about the lateral axis through the pivot; the wheel hangs on it as on any carrier (`upright_body`) |
| the beam | a `fixed` joint between the two arms at the middle of the beam, with a `bushing` (§24.4) that is **soft in torsion** about the lateral axis, `rate_ry = G · J / L`, and stiff in the rest (shear and bending of the beam) |

`J` is the torsion constant of the beam's open section (`Σ b·t³/3` over its plates, or given) and `L` the beam length between the arms. The beam lies on the line of the two pivots. A wheel moving alone then twists the beam by the difference of the two arm angles and the other side stays put; the roll stiffness the beam adds, springs excluded, is `k_twist · (track / arm length)²`. An offset beam, or pivot axes inclined in plan (roll steer), add a bending of the beam to its twist and are not represented by this model.

A bushing direction whose rate is below 10 000 (N/m or N·m/rad) is left free by the loop-closure solver (§26); the stiffer directions stay rigid. The static balance with the bushing force is not solved.

`tools/torsion_beam.py` (and `svj.torsionbeam`) generates the arms and the beam joint from `pivot_x`, `pivot_z`, `half_track_arms`, `half_track`, `wheel_x`, `wheel_z`, `plates` or `torsion_constant`, and optional `G`, `E`, `bending_I`, `arm_mass`, `beam_mass`; it returns `twist_rate` and `roll_rate` as well. The items are `x_derived`.

### 25.12 Not covered yet

The loop-closure solver exists (§26); still open: the physical anti-roll bar from its geometry; the bending of an offset or inclined twist beam; leaf-pack shackle swing, inter-leaf friction and helper leaves.

---

## 26. Loop-Closure Solver *(tooling, v0.100)*

`body_transforms()` (§24.4) walks the joint tree and ignores closed loops. A suspension is a closed loop (chassis, arm, upright, tie rod, rack, chassis), so its pose for a given wheel travel is *solved*, not read off. `tools/loop_solver.py` (mirrored as `svj-py/svj/loopsolver.py`) does this from the §25 model alone; the format gains no keys.

**Method.** The unknowns are the rigid motions of the bodies of one mechanism (chassis and ground fixed; wheel bodies are not loop members). Each `joint` contributes residuals for the motions its type forbids (a revolute joint: coincident frame origins, parallel z axes); its free coordinates stay free. Inputs add residuals: `joint_values` hold joint coordinates (the steering rack position, a door angle) and `travel` raises a station's wheel centre (`wheel_center_marker` on `upright_body`) by a height in metres, bump positive. Stations of the mechanism not named are held at zero travel, and steering joints at zero. Gauss-Newton with Levenberg-Marquardt damping and a finite-difference Jacobian; a sweep continues from the previous pose.

**Results.** Per station and travel: wheel-centre position, camber (negative = top inwards), toe (positive = toe-in), element lengths, the maximum residual and `converged` (residual below 1e-6 m or rad). `gains()` gives the camber gain and bump steer (deg per m) around the reference. The spin axis comes from the `revolute` joint between `upright_body` and `wheel_body` (§25.6).

**Limits.** Joints are rigid (bushings and compliance are not applied), except that a bushing direction with a rate below 10 000 is left free (§25.11); wheel spin and tyre deflection are not modelled; `roll_center()` gives the front-view roll centre from the instant centre of the upright (height above the ground; near zero for parallel horizontal arms). `steering_axis()` gives caster, kingpin inclination, scrub radius and caster trail from the upright's screw axis for a small rack movement. A mechanism with generated (`x_derived`) joints of assumed type may be under- or over-constrained, and the numbers then say little: check `converged`, and treat an unexpected result as a sign of missing data in the source, not of the solver.

```
python tools/loop_solver.py file.svj.json --station FL --range 0.05 --steps 5 [--steer 0.02]
```

Axes are SAE J670 (x forward, y right, z down): a bump lowers z; camber is positive with the top of the wheel leaning outwards, toe positive for toe-in, caster positive with the axis leaning back at the top, kingpin inclination positive leaning inwards (the `alignment` table's conventions for `alignment_convention: relative_to_centerline`). `check_alignment()` (`--check-alignment`) compares the `alignment` a station declares with what the geometry gives and reports differences above 0.5 deg or 10 mm.

svj-py: `Vehicle.solve_pose(travel, joint_values)`, `.wheel_sweep(station, travels, steer)`, `.suspension_gains(station)`.

---

## 27. Attachments and Combinations *(v0.101)*

A vehicle is rarely one file. A tractor takes a front loader, a three-point hitch and a mower; a truck takes a tipper body, a crane or a container; a tractor unit pulls a semi-trailer. In SVJ each of these is **a unit: an ordinary SVJ file**. A unit declares the places where it can be joined to another (**interfaces**); two units are joined by a **connection**, which is a joint (§24.4). A fitted unit therefore moves, has mass, CG and inertia, and can be posed, exactly like the parts inside one file.

### 27.1 `interfaces[]`

An interface is a named frame with a role.

| Key | Type | Required | Description |
|---|---|---|---|
| `id` | string | YES | Unique in the file; must not contain `.` (reserved for qualified ids) |
| `role` | string | YES | What it is: a role of the vocabulary in §27.2 |
| `gender` | string | no | `socket`, `plug` or `symmetric` (default). Two interfaces mate when their roles mate and the genders are not both `socket` or both `plug` |
| `body` | string | no | `chassis` (default) or a `mass_bodies` id the interface is fixed to |
| `marker` / `frame` | string / object | one of them | The frame: a marker of `body`, or an inline `{position, orientation}` in the file's own coordinates. Its z axis is the joint axis if the connection is a revolute / translational joint |
| `size` | object | no | Dimensions and classes that must agree: a number with the same key on both sides must match within 0.5 mm (`pin_diameter`, `kingpin_diameter`, `pin_spacing`); `category`, `class`, `type`, `standard` must be equal text |
| `max_load` | object | no | Loads through the interface (`vertical_N`, `drawbar_N`, `torque_Nm`, ...). `check_combination` compares `vertical_N` (the smaller of the two mated interfaces) with the static weight of every unit beyond the connection (units on their own wheels, such as a semi-trailer, are skipped: their axles carry most of the weight) and warns when it is exceeded; the other keys are informational |
| `name`, `description` | string | no | |

A unit of the kind that is only ever fitted (a loader, a tipper body) is marked `vehicle_info.vehicle_class: "attachment"`; its `chassis` then needs only `mass_total` and `center_of_gravity` (the mounting frame or sub-frame: it is the unit's body for the interfaces) and its coordinates are its own (typically with the origin at the main interface).

### 27.2 Interface roles

Each role mates with one other role (a symmetric role with itself). The table is part of the standard; an unlisted role is a warning and mates with nothing.

| Group | Role | Mates with |
|---|---|---|
| Road trailers | `fifth_wheel` / `kingpin` | each other |
| | `drawbar_eye` / `pintle_hook` | each other |
| | `ball_coupling` / `ball_hitch` | each other |
| | `gooseneck_ball` / `gooseneck_coupler` | each other |
| | `turntable` | itself (dolly, converter, swing-bolster) |
| Agriculture | `three_point_lower_link` / `three_point_lower_pin` | each other (ISO 730 categories in `size.category`) |
| | `three_point_top_link` / `three_point_top_pin` | each other |
| | `drawbar_clevis` / `drawbar_pin` | each other |
| | `pto_shaft` / `pto_stub` | each other |
| | `loader_mount` | itself |
| Earthmoving, handling | `quick_coupler` / `quick_coupler_pin` | each other (bucket, fork, hammer) |
| | `fork_carriage`, `boom_tip`, `crane_mount`, `body_mount`, `bed_mount`, `pallet_fork_mount` | themselves |
| | `container_corner_casting` / `container_twist_lock` | each other (ISO 1161 / 668) |
| Military, construction | `winch_mount`, `weapon_mount`, `ring_mount`, `bridge_interface`, `plough_blade_mount`, `dozer_blade_mount` | themselves |
| Generic | `generic_mount` | itself |

### 27.3 The combination file

`*.svj-combination.json` joins units:

| Key | Description |
|---|---|
| `_metadata` | `{"format": "svj-combination", "version": ...}` |
| `id`, `name` | |
| `units[]` | `{id, file, root?}`; `file` is relative to the combination file. Exactly one unit is the **root** (the first when none is marked); the composite keeps its coordinates and ids |
| `connections[]` | `{id, a: "unit.interface", b: "unit.interface", joint?}`; `joint` is the §24.4 joint object without bodies and frames (`joint_type`, `range`, `stop`, `friction`, `damping`, `bushing`, `drive`); default `fixed` |
| `poses[]` | Named configurations over the composite (§24.7); joint ids are qualified |

A rigid mount is `fixed`; a fifth wheel is a `spherical` or `universal` joint with a pitch / roll range; a pintle hook or drawbar eye a `spherical` joint; a three-point lower link a `spherical` joint or, with the top link, a `fixed` set. Connections may chain (a tool on a loader bucket) but the units form a tree: a connection that closes a loop between units is allowed and warned, and not solved.

### 27.4 `attachments[]` - the shorthand

A vehicle file may list the units fitted to it instead of a separate combination file:

```json
"attachments": [{"id": "loader", "file": "front_loader.svj.json",
                 "connections": [{"interface": "loader_mount", "attachment_interface": "mount",
                                  "joint": {"joint_type": "fixed"}}]}]
```

`interface` is an interface of this vehicle (or of the unit named in `to_unit`); `attachment_interface` one of the attached unit. The vehicle is the root.

### 27.5 Assembly

The assembly (`tools/assemble.py`, `svj.assemble`; `Vehicle.assemble()`) builds one SVJ document in the root's coordinates:

1. **Placement.** Each unit is moved rigidly so that its connected interface frame coincides, position and orientation, with the interface it joins (the reference pose). The checker's rule that joint frames coincide (§24.10) then holds for every connection.
2. **Ids.** The root keeps its ids. Every other unit's bodies, constraints and poses become `unit.id` (`loader.loader_boom`, `loader.hinge_loader_boom`, `loader.loader_dump`); references inside the unit are rewritten. `.` is reserved for this, in every file.
3. **Unit chassis.** A unit's `chassis` becomes a body `unit.chassis` (`category: attachment`, `x_derived: true`) with the mass not described by the unit's `mass_bodies` and its markers; `parent` references to the chassis point to it.
4. **Connections** become `joint` constraints of the given id between the bodies of the two interfaces, frames at the placed interface.
5. **Composite.** `mass_total`, `center_of_gravity` and, when every unit gives a `chassis.inertia`, `inertia` are those of the whole combination in the reference pose. A non-root unit's `wheel_stations[]` are carried over with qualified ids (`trailer.A1L`; `wheel_body`, `upright_body` and `steering_joint` qualified too), so its suspension is part of the composite mechanism (§26 works on it); its `axles`, `suspension_couplings`, `tires`, `brakes` and `powertrain` stay in the unit's file (noted by the assembler), where a simulator reads them with the same station ids. The result carries `x_assembled: true` and validates like any file; poses, CG, inertia and element lengths per pose (§24), contacts, and the loop solver (§26) work on it.

`examples/attachments/` splits `skeleton_tractor_loader_hitch` into `tractor_host` + `front_loader` and joins them both ways (`tractor_loader.svj-combination.json`, `tractor_with_loader.svj.json`); the composite reproduces the single-file example's CG and inertia in every pose. `tractor_semi_trailer.svj-combination.json` joins `skeleton_6x4_camelback_tractor` and `skeleton_3axle_air_semi_trailer` at a `fifth_wheel` / `kingpin` pair with a spherical joint; the pose `turning_left` yaws the trailer.

### 27.6 Validation rules

`tools/validate.py` (and `svj.validate()` for the interface rules): interface ids unique, without `.`, with a known gender and a frame or an existing marker of an existing body; role vocabulary (warning); in a combination, unit ids unique and without `.`, exactly one root, every connection end `unit.interface` existing, **roles mate, genders oppose, same-named sizes agree**, joint types valid, every unit reachable from the root; then the assembled composite is checked by §24.10 and the schema.

### 27.7 Not covered yet

`axles`, `suspension_couplings`, tyre sets, brakes and the powertrain of attached units are not merged into the composite (the unit files keep them; a trailer's air circuit is the unit's `suspension_couplings`); dynamic load checks (only the static `vertical_N` weight is compared); an attachment file that overrides host values; hydraulic and PTO power supply between units; the viewer.

---

## 28. Collision Proxies *(v0.102)*

Visual meshes are far too detailed to ask "does the lid hit the cab in this pose?". A body (or the chassis) can carry a few simple **proxy shapes** for that question. They are a different thing from `contact` (§24.6.3), which is a force element on two frames: a proxy has no force, it only answers where parts clash.

### 28.1 `collision[]`

An array on `chassis` or on any `mass_bodies` entry:

| Key | Type | Required | Description |
|---|---|---|---|
| `id` | string | YES | Unique in the file |
| `type` | string | YES | `sphere` (`radius`), `box` (`size`: the three full lengths along the shape axes) or `cylinder` (`radius`, `length`, axis along the shape Z) |
| `position` | `[x,y,z]` | YES | Centre of the shape in vehicle coordinates at the reference pose (like marker positions) |
| `orientation` | quaternion `[x,y,z,w]` | no | Shape axes in vehicle axes at the reference pose; identity by default |
| `margin` | number | no | Clearance that must stay free around the shape (m); added to the clearance of every pair it is in |
| `source_node` | string | no | Name of the glTF node the proxy approximates (informational) |

A proxy moves with its body: its place in any pose of the file is the body's transform (§24) applied to its reference position and orientation.

### 28.2 Which pairs are compared

All pairs of proxies of two different bodies, except:

- bodies in the same rigid group (welded together through `parent`, with no joint between them), which never move relative to each other;
- bodies joined directly by a `joint` (a hinge always touches its neighbour); use a `contact` when a stop between neighbours matters;
- pairs listed in the top-level **`collision_ignore`**: an array of `[body_id, body_id]` (`"chassis"` allowed).

### 28.3 Separation

The **separation** of a pair is positive when the shapes are apart and negative when they overlap (the penetration depth), minus the margins of both. `sphere` against `sphere` and against `box` is exact. Two boxes use the separating-axis test: the largest gap (or smallest penetration) over the face normals and edge cross products, exact for face contact and a lower bound of the distance otherwise. A `cylinder` is treated as its bounding box (conservative: it can report an overlap a true cylinder does not have).

### 28.4 Validation and tool

`tools/validate.py` (through `tools/collision_check.py`) reports as **errors** a proxy with a type other than the three above, with bad dimensions or a position that is not three numbers, a duplicate proxy id, and a `collision_ignore` entry that is not a pair of existing bodies; as **warnings**, a pair that overlaps by more than 1 mm in the reference pose or in any pose of `poses[]`. `python tools/collision_check.py file.svj.json [--pose ID] [--margin M]` lists the closest or overlapping pairs per pose; `svj.collision.clashes(doc, pose, tolerance)` returns them. A composite assembled from a combination (§27) is checked the same way, which finds a loader bucket in the cab or a trailer corner on the tractor.

### 28.5 Not covered yet

Proxies from glTF meshes (hulls), a capsule and a true cylinder pair test, and contact with the ground. A force between proxies is a `contact`.

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
| Aerodynamics      | v0.5  
| Drivetrain        | v0.6.0   | ✅ Done — engine to half-shafts, AWD/4WD            |
| Electric/Hybrid, cooling | v0.7.0 | ✅ Done                                      |
| Compliance        | v0.8.0   | ✅ Done — 3-tier model                              |
| Multi-model tires | v0.9.0   | ✅ Done — MF, TMeasy, brush, external               |
| Aerodynamics extension | v0.95 | ✅ Done — maps, components, ground effect         |
| Multibody topology| v0.96    | ✅ Done — joints, markers, body refs                |
| glTF visual binding | v0.97  | ✅ Done                                             |
| Validation, benchmarks, overrides | v0.98 | ✅ Done                                 |
| Multi-axle vehicles | v0.99  | ✅ Done — §23, 13 system_types, suspension couplings |
| Axle groups, plated masses, wheelbase definitions | v0.99.1 | ✅ Done — first real multi-axle example (MAN TGS 8x4) |
| Collision proxies (sphere / box / cylinder per body, pose clashes) | v0.102 | ✅ Done — §28 |
| Attachments and combinations (interfaces, combination file, assembly) | v0.101 | ✅ Done — §27 |
| Unified suspension (bodies, joints, elements, wheel stations); corner section deprecated | v0.100 | ✅ Done — §25, migration tool; loop solver planned |
| Movable parts, attachments (joints, springs, actuators, poses) | v0.99.5 | ✅ Done — §24; contacts, latches, attachment files planned |
| Articulated combinations (tractor/trailer/dolly) | — | Planned (§23.8)            |
| v1.0 freeze       | —        | After converter feedback on v0.99                   |
