<p align="center">
  <img src="docs/logoSVJ.png" alt="SVJ — Standard Vehicle JSON" width="200"/>
</p>

# SVJ — Standard Vehicle JSON

**A Rosetta Stone for vehicle simulation.**

Every simulator speaks its own language. Assetto Corsa has `suspensions.ini` and `tyres.ini`. BeamNG uses JBeam node-beam meshes. Adams Car wants `.adm` templates with bushing matrices. CarMaker needs its own parameter files. rFactor2 has yet another format. Unity and Unreal don't even model suspension geometry — they just want a spring rate and a wheel radius.

If you've ever tried to move a car between any two of these, you know the pain. There's no common ground. You end up writing one-off scripts, guessing at unit conversions, and losing data at every step.

SVJ fixes this. It's a single, human-readable JSON format that can describe a complete vehicle — from a 1077 kg Mazda MX-5 with its double-wishbone front suspension and asymmetric LSD, down to the individual bushing stiffness at each pickup point and the Pacejka coefficients on each tire. Every simulator gets what it needs from the same file. What it can't use, it ignores.

The idea is simple: define the car once, in engineering terms, with real physics. Then let converters translate that into whatever each target needs. A converter to Assetto Corsa picks the 40 fields it understands. Adams Car reads 90% natively. UE5 Chaos gets the 15% it can handle. The data is always there — the converter decides the fidelity.

SVJ is not a simulator. It's not a physics engine. It's a vocabulary — a way to write down what a car is, so that any tool can read it.

---

## What's Inside

An SVJ file describes the complete physical vehicle:

**Chassis** — mass, CG, full inertia tensors, decomposition into individual rigid bodies (engine, gearbox, fuel, driver...), torsional stiffness

**Steering** — rack geometry, ratio, electric power assist, column dynamics, additional steered axles

**Suspension** — 13 topology types (double wishbone, MacPherson, multi-link, torsion beam, solid axle, De Dion, swing axle, parallelogram, pendulum axle...) with hardpoints, links, bushings (3-tier: rigid → scalar compliance → full 6-DOF), springs (coil, leaf, air, torsion, rubber, hydropneumatic, hydraulic), dampers, ARBs, alignment

**Multi-axle vehicles** — any number of axles (`A1L`, `A2R`, … `A3C`), dual/twin wheels per hub, several steered axles (linked, self-steer, command, active), lift axles, and inter-axle load sharing: equalizer rockers, walking beams, trunnion (camelback) springs, pneumatic and hydraulic circuits

**Tires** — 4 model types in one file: Pacejka MF 5.2/6.2 (80+ coefficients), TMeasy (~20 params), brush model (~10 params), plus external file references for FTire, CDTire, MF-Swift

**Brakes** — full force chain from pedal through booster and master cylinder to caliper, per-corner discs with mass and thermal properties, ABS/ESC

**Drivetrain** — engine, clutch, gearbox, transfer case (including torque-limited on-demand couplings), propshafts with joints, differentials (including asymmetric LSD ramp angles and state-dependent lock control), half-shafts with CV joints that match the upright hardpoints

**Aerodynamics** — coefficients, 1D/2D sensitivity maps (ride height, yaw, pitch, speed), individual components with cross-influences, wake/dirty air model, ground effect (underbody, tire squirt, sealing), active systems (DRS, PID-controlled active wings, active ride height)

**Electric/Hybrid** — motors (P0 through P4 and in-wheel), battery pack with thermal model, inverters, regenerative braking

**Cooling** — thermal circuits with radiator, pump, thermostat

**Movable parts and attachments** — joints, springs and hydraulic actuators between rigid bodies with full mass properties, named poses with derived CG and inertia (doors, hoods, tilt cabs, tractor loaders and hitches)

**Driver controls** — throttle mapping, brake feel, traction control, launch control

Everything is optional. A file with just metadata and suspension is valid — useful for sharing a setup. A file with everything filled in is a complete vehicle ready for multi-body dynamics.

---

## v0.102 — Collision proxies *(new)*

A body or the chassis can carry **`collision[]`**: a few `sphere` / `box` / `cylinder` proxies in vehicle coordinates, with an optional `margin`. They answer "does the lid hit the cab in this pose?" without the visual mesh: pairs of bodies that can move relative to each other (not welded together, not joined directly by a hinge, not listed in `collision_ignore`) are compared in the reference pose and in every pose, and the validator warns about overlaps. `python tools/collision_check.py file.svj.json` lists the closest pairs per pose; `Vehicle.clashes(pose)` does the same from Python; an assembled combination carries its units' proxies with qualified ids. Details: [`spec/SVJ_Spec.md` §28](spec/SVJ_Spec.md).

## v0.101 — Attachments and combinations

A loader, a mower, a tipper body, a crane or a semi-trailer is a **unit: an ordinary SVJ file** that declares **`interfaces[]`** (a frame, a role such as `loader_mount`, `three_point_lower_link`, `fifth_wheel` or `container_corner_casting`, a gender and sizes). Roles mate in pairs from a table in the standard, sizes must agree, and a connection is a joint, so a fitted unit moves, has mass and inertia and takes poses like any part. List the units in a vehicle's **`attachments[]`** or in a `*.svj-combination.json` file; **`python tools/assemble.py file -o composite.svj.json`** places the units so the interface frames coincide, qualifies their ids (`loader.loader_boom`) and builds one composite document (mass, CG, inertia) that validation, poses and the loop solver then work on. `examples/attachments/` splits the loader tractor into host + loader; the composite reproduces the single-file CG and inertia in every pose. The tractor and semi-trailer examples join at a fifth wheel (`tractor_semi_trailer.svj-combination.json`). Not yet: axles, tyres, brakes and power flow of attached units, capacity checks. Details: [`spec/SVJ_Spec.md` §27](spec/SVJ_Spec.md).

## v0.100 — Unified suspension *(breaking, one release of transition)*

A suspension is no longer a typed corner: it is **bodies, joints and elements** (the §24 model) plus a thin `wheel_stations[]` list. The component defines the mechanism, never a type name: an upright, arms and a tie rod joined by the joints they have; a `spring` (linear or `kind: torsional`) and a `damper`; a rack on a slide; a leaf pack with eye, slipper and seat joints. `wheel_stations[]` names the roles an analysis needs (`wheel_body`, `upright_body`, `wheel_center_marker`, `steering_joint`) and keeps tyre, brake and reference alignment; `anti_roll_bars[]` holds bar data until its geometry exists. Data quoted at the wheel is written as `reference: "wheel"` elements; a wheel rate converts to an element rate through the motion ratio (given, or estimated from the geometry and flagged). Generated items carry `x_derived: true` and are checked leniently until refined. The `suspension` section is deprecated: still accepted, validators warn. **`python tools/migrate_suspension.py old.svj.json -o new.svj.json`** converts a file; all shipped examples and the template are migrated. Wheel travel, camber, toe and bump steer come from `tools/loop_solver.py` (spec §26). Not yet: caster / kingpin results, steering-wheel coupling, physical anti-roll bar. The viewer (v4.6) shows the unified suspension read-only, through a view derived from the bodies and joints. Details: [`spec/SVJ_Spec.md` §25](spec/SVJ_Spec.md), [`proposals/svj_unified_suspension_proposal.md`](proposals/svj_unified_suspension_proposal.md).

## v0.99.8 — Contact

A **`contact`** constraint stops a part against a pad, seal or seat: primitive shapes (point, plane, sphere, box, cylinder) on markers and a penalty law (`gap`, `stiffness`, `damping`, `friction`, `restitution`), between any two bodies, including a hinged part and its parent. The checker computes the signed distance between the shapes at the reference pose and in every pose, so a hood that does not actually touch its rubber stops, or a pose that pushes a part through a stop, is reported. The panels example gains rubber stops under the hood and tailgate. The part-name vocabulary now also covers the suspension, steering and brake parts, so an upright keeps the name *upright*. `tools/suspension_view.py` expands an authored suspension into the same body / joint model (the first step of [`proposals/svj_unified_suspension_proposal.md`](proposals/svj_unified_suspension_proposal.md), which makes the components define the mechanism).

---

## v0.99.7 — Part Names

Parts need names other people (and other tools) understand. Bodies, constraints and poses may now carry a short display **`name`** next to their stable `id`, and [`docs/naming_convention.md`](docs/naming_convention.md) gains a recommended **vocabulary for movable parts and attachments**: doors, hood, trunk, tailgate, flaps, mirrors, cab, tipper body, front loader, excavator parts, three-point hitch parts and implements, each with the aliases other tools use, side suffixes (`door_fl`, `mirror_r`), patterns for joint, cylinder, strut, latch and pose ids (`hinge_door_fl`, `loader_boom_cylinder`, `door_fl_latch`) and marker names (`hinge`, `<part>_hinge`, `<element>_base` / `_rod`). The checker flags an *alias* of a listed part (`hatch` for `tailgate`) and leaves unlisted names alone. The three movable-part examples follow it.

---

## v0.99.6 — Constraint Set Completed

The movable-parts model of v0.99.5 gains the rest of what a real assembly needs:

- **`latch`** — holds a joint at a position until a force releases it: door and hood latches, door-check detents, cab and tipper locks.
- **`coupling`** — `q_b = ratio · q_a`: a linkage that makes one joint follow another (self-opening tailgate, a parallel-lift loader keeping the bucket level, mirrored doors). A pose names one joint and the coupled one is derived.
- **`joint.drive`** — a motor or powered hinge on a one-coordinate joint (`position`, `velocity` or `force` mode, with torque / force and speed limits): a power liftgate, a slew drive.
- **Partial decompositions** — `mass_bodies` no longer has to cover the whole vehicle: listing only the movable parts and attachments is valid (the remainder is the rest of the vehicle); `chassis.mass_bodies_complete: true` asks for the exhaustive check.
- **`examples/skeleton_dump_truck_tipper_cab.svj.json`** — tilting cab on a ram with a lock, tipper body on a ram with a hook, tailgate opened by a linkage as the body tips (coupling), poses for transport, cab tilted, 30° and full tip with the per-pose CG and ram lengths.

---

## v0.99.5 — Movable Parts and Attachments

A vehicle can now carry **physical, articulated parts**: doors, hood, tilt cab, tipper body, and equipment such as a tractor's front loader or three-point hitch. A part is a `mass_body` (mass, CG, full inertia tensor, markers); `constraints[]` connect parts, and `poses[]` name configurations.

- **`joint`** — revolute, translational, cylindrical, spherical, universal, planar or fixed, with vector coordinates, ranges, end stops, friction, damping and optional bushing compliance. The joint axis is the +Z axis of its marker frame.
- **`spring`** — a passive force element (gas strut, return spring) between two markers.
- **`actuator`** — a linear drive with stroke and force limits (`bore_diameter` × `max_pressure`): the loader, tipper and lift cylinders.
- **Inertia** — `mass_body.inertia` may be the full symmetric 3×3 matrix as well as the Ixx/Iyy/Izz/products object, with an optional `inertia_orientation` for principal axes.
- **Poses** — for any pose a tool derives the body transforms, the composite **CG and inertia**, and the **length of every spring and actuator**, and checks each actuator can reach it.

```json
"constraints": [
  { "id": "hinge_loader_boom", "type": "joint", "joint_type": "revolute", "body_a": "chassis", "marker_a": "loader_boom_hinge",
    "body_b": "loader_boom", "marker_b": "hinge", "range": { "min": -0.15, "max": 0.95 } },
  { "id": "loader_boom_cylinder", "type": "actuator", "body_a": "chassis", "marker_a": "loader_boom_cylinder_base",
    "body_b": "loader_boom", "marker_b": "loader_boom_cylinder_rod", "retracted_length": 0.82, "stroke": { "min": 0, "max": 0.55 },
    "bore_diameter": 0.08, "rod_diameter": 0.045, "max_pressure": 18000000 }
],
"poses": [ { "id": "transport" }, { "id": "loader_dump", "values": { "hinge_loader_boom": 0.9, "hinge_loader_bucket": -0.8 } } ]
```

`python tools/constraints_check.py --poses examples/skeleton_tractor_loader_hitch.svj.json` prints the CG, inertia and element lengths of every pose. `tools/constraints_check.py` runs from `tools/validate.py` (mirrored in `svj-py`, with `Vehicle.pose_cg()`, `pose_inertia()`, `element_lengths()`, `body_transforms()`). Contacts, latches, linked joints and attachments in their own files are planned; viewer animation of poses is the next step. Details: [`spec/SVJ_Spec.md` §24](spec/SVJ_Spec.md), [`proposals/svj_articulated_parts_proposal.md`](proposals/svj_articulated_parts_proposal.md).

---

## v0.99.4 — Strut and Damper Conventions

Three points raised by converter authors when they checked converted vehicles against the spec:

- **MacPherson / Chapman strut:** the spec gave `strut_top` as both ends of the strut link, so a strut written as specified had zero length and a solver could not locate the corner. The link now ends at the new **`strut_lower`** hardpoint, the strut's lower clamp on the upright; `strut_top` stays the body-side end. `tools/multibody_check.py` warns about any zero-length link, and the five shipped MacPherson/Chapman examples were corrected (their `strut_lower` values are estimates on the strut axis through the lower ball joint).
- **`damper.reference`** (`"damper"` default, or `"wheel"`): says where the force-velocity curves are defined. Simulators that work at the wheel can now state their values as wheel values instead of inventing a damper geometry; the spec gives the conversion (`v_damper = v_wheel × MR`, `F_damper = F_wheel ÷ MR`).
- **Mount names:** spring and damper use `inboard_mount` / `outboard_mount`. The `inboard_point` / `outboard_point` spellings some converters wrote were silently ignored; `validate.py` now warns.

All additive: older files stay schema-valid (the zero-length strut is a warning, not an error).

---

## v0.99.3 — Differential Control

Auditing the Assetto Corsa → SVJ converter against 1,398 AC cars showed two AWD driveline features SVJ could not express. Both are additive and optional; every earlier file still validates.

- **`lock_control`** — a differential lock that is *modulated* by the driving state instead of being constant. A chain of stages, each reading an input (`gear`, `brake`, `throttle`, `speed`, `rear_speed_ratio`, `oversteer_factor`, `slip_angle_front/rear`), mapping it through a curve and combining it with `multiply` or `add`, with an optional filter time constant and clamps. Allowed on any differential and on `transfer_case.center_diff`; an array of chains gives separate power and coast control.
- **`transfer_case.coupling`** — a torque-limited centre coupling for on-demand AWD (`max_torque`, `ramp_torque`, `mechanism`).

```json
"transfer_case": {
  "type": "on_demand",
  "coupling": { "mechanism": "clutch_pack", "ramp_torque": 40.9, "max_torque": 816.6 },
  "center_diff": { "type": "lsd_clutch", "lock_power": 0.4, "lock_coast": 0.2,
    "lock_control": { "target": "lock", "stages": [
      { "input": "gear",  "combine": "multiply", "curve": [[1, 1.0], [2, 0.8], [3, 0.6]] },
      { "input": "brake", "combine": "multiply", "curve": [[0, 1], [1, 0]], "filter_time_constant": 0.1 }
    ] } }
}
```

Alongside it, tooling for the older v0.96 multibody fields (`joint_type`, `body_ref`, marker orientations) was completed:

- **`tools/drivetrain_check.py`** and **`tools/multibody_check.py`** run automatically from `tools/validate.py` (mirrored in `svj-py`). The multibody checker verifies `body_ref` / `parent` / `outboard_ref` cross-references and unit quaternions, and defines one shared joint-type inference (spec §9.2.3.2) — `python tools/multibody_check.py --joints file.svj.json` prints every link's effective joints.
- **Viewer v4.3** shows the coupling, the centre differential and every lock chain in the Powertrain tab, shows effective joint types in the Suspension tab and draws orientation frames in 3D. It also fixes a crash on files that use the marker form `{position, orientation}` for hardpoints.
- **`examples/skeleton_awd_ondemand_diff_control.svj.json`** — a worked example. The control curves are illustrative.
- Every example and the template were brought up to the then-current `_metadata.version` (each version is a strict superset of the previous one, so no content changed).

Details: [`proposals/svj_differential_control_proposal.md`](proposals/svj_differential_control_proposal.md), [`spec/SVJ_Spec.md` §10.6.1, §10.8.1](spec/SVJ_Spec.md).

---

## v0.99.2 — Visual Binding Layer, Part 2

The glTF layer (§22) now reaches every mechanical part, and the schema and the spec agree on one category set:

- **One category list** — `body`, `suspension`, `steering`, `wheel`, `brake`, `powertrain`, `aero`, `helper`, `lod`. Before this patch the schema accepted only `body`/`helper`/`lod` while the spec text used `suspension`, `wheel` and `aero`, so the spec's own examples failed validation.
- **`visual` everywhere it is needed** — suspension links (wishbones, arms, tie rods), uprights, axle bodies, wheels and each wheel of a dual set, springs, dampers, ARBs, brake discs and calipers, steering rack/column/wheel, powertrain units, driveshafts and aero components.
- **`placement`** — a wishbone has no body frame, so `placement: "link_between_points"` places the mesh from the link's own hardpoints (`mesh_axis`, `from_point`, `scale_to_length`). The default `rigid` is exactly the v0.97 behaviour.
- **Canonical part names** — `docs/naming_convention.md` lists the recommended name for each common part and the aliases other tools use, so exporters converge: `SVJ::suspension::upper_wishbone_fl`, `SVJ::brake::disc_fl`, `SVJ::steering::wheel`.
- **`examples/skeleton_visual_binding_dw_corner.svj.json`** — a worked example with 45 bindings.

All additive: every earlier file, and every `SVJ::body::upright_fl` binding, still validates.

---

## v0.99.1 — Real-Vehicle Data Patch

Added while building the first real multi-axle example, because published truck data didn't fit v0.99:

- **`axle_groups`**: loads per axle group (design, legal and unladen), since makers publish "front axles 14 200 kg", not per-axle figures.
- **`chassis.plated_masses`**: gross vehicle and combination masses, design vs legal.
- **`wheelbase_reference`**: new values `bogie_centres`, `first_rear_axle`, `theoretical` and `explicit` (with `wheelbase_from` / `wheelbase_to`), because every maker measures "wheelbase" differently on multi-axle vehicles.
- **First real-vehicle multi-axle example:** `man_tgs_32_430_8x4_twin_steer_tipper.svj.json`, built from MAN's UK body-builder chassis sheet.

---

## v0.99 — Multi-Axle Vehicles

SVJ now describes trucks, trailers and special vehicles, not just four-corner cars. All additions are optional; existing `FL/FR/RL/RR` files are unchanged.

- **Station naming** `A{n}{L|R|C}` for any axle count; `FL/FR/RL/RR` stay valid as aliases for two-axle vehicles.
- **`axles`** — position, track, steered/driven, lift axles.
- **Multiple wheels per hub** — `wheel.multiplicity` + `positions` for duals.
- **Multi-axle steering** — `steering.additional_axles` (mechanical link, self-steer, command, hydraulic, active).
- **`suspension_couplings`** — walking beams, equalizer rockers, trunnion springs, air and hydraulic circuits.
- **New suspension types** `swing_axle`, `parallelogram`, `pendulum_axle`; new spring types `rubber_torsion`, `rubber_block`, `hydropneumatic`, `hydraulic`, `none`; portal axles; truck tyre size codes.

```json
"suspension": { "A1L": {…}, "A1R": {…}, "A2L": {…}, "A2R": {…}, "A3L": {…}, "A3R": {…} },
"axles": [ { "id": "A1", "steered": true }, { "id": "A2", "driven": true }, { "id": "A3", "driven": true } ],
"suspension_couplings": [
  { "id": "rear_bogie_L", "type": "walking_beam", "side": "L", "axle_refs": ["A2", "A3"], "pivot_position": [-4.52, -0.55, -0.63] }
]
```

`tools/validate.py` now also runs `tools/multiaxle_check.py`, which checks the cross-references a schema can't (naming form, contiguous axles, coupling and torque-rod references, dual-wheel positions). The Python library (`svj-py` 0.2.0) and the 3D viewer (v4.2) read any number of axles, dual wheels and couplings; the viewer also draws a top-view axle layout, axle beams and frame, and can add, remove and edit axles and dual wheels. Full details: [`spec/SVJ_Spec.md` §23](spec/SVJ_Spec.md).

---

## v0.98 — Validation, Benchmarks & Override Files

Three additive, optional pieces of metadata/tooling:

- **`validation`** — records whether/how the assembled vehicle has been correlated against physical test data (`status`, `method`, `test_reference`, `correlation_quality`, ...). Field-level provenance already existed (`_est`, `_source`); this adds the same idea at the vehicle level.
- **`benchmarks`** — an array of KPI entries (`id`, `value`, `unit`, `type: target|measured|simulated`) so performance targets travel with the model instead of a side spreadsheet.
- **Override files** (`*.svj-override.json`) — a `base` + RFC 7396 JSON Merge Patch `patch`, for DOE variants and partial-disclosure supplier hand-offs without duplicating the whole vehicle. See [`spec/SVJ_Spec.md` §3.4](spec/SVJ_Spec.md#34-override-files-v098).

```json
"validation": {
  "status": "correlated",
  "method": "physical_test",
  "correlation_quality": "good"
},
"benchmarks": [
  { "id": "skidpad_lateral_g", "value": 0.95, "unit": "g", "type": "target" }
]
```

```json
{
  "_metadata": { "specification": "SVJ-OVERRIDE", "version": "0.98", "base": "./mazda_mx5_nd2_2024.svj.json" },
  "patch": { "suspension": { "FL": { "spring": { "rate": 32000 } } } }
}
```

Validate an override file (resolves `base` + `patch`, then validates the result against the standard schema):

```bash
python tools/validate_override.py examples/bmw_e30_325i_stiffer_front.svj-override.json
```

---

## v0.97 — glTF Visual Binding Layer

SVJ v0.97 adds an optional layer for connecting physics bodies to their 3D visual representations in glTF assets. This is designed for pipelines that use Blender, Maya, or other DCC tools alongside a simulation environment.

### Asset Manifest

Declare the glTF files your vehicle uses:

```json
"assets": {
  "meshes": [
    { "id": "chassis_body", "uri": "meshes/car_body.glb" },
    { "id": "wheel_set",    "uri": "meshes/wheels.glb" }
  ]
}
```

### Visual Binding

Attach a `visual` field to any body in the file:

```json
"chassis": {
  "mass_total": 1077,
  "visual": {
    "mesh_ref": "chassis_body",
    "node": "SVJ::body::chassis"
  }
}
```

Since v0.99.2 the same field also sits on suspension links, uprights, wheels, springs, dampers, brakes, steering parts, powertrain units and aero components, and a part defined by hardpoints says so:

```json
{
  "name": "lower_wishbone",
  "inboard_points": [[0.20, -0.26, -0.16], [-0.18, -0.26, -0.15]],
  "outboard_ref": "hardpoints.lower_ball_joint",
  "visual": {
    "mesh_ref": "suspension_set",
    "node": "SVJ::suspension::lower_wishbone_fl",
    "placement": "link_between_points",
    "mesh_axis": "+y"
  }
}
```

The `node` value must follow the **SVJ Naming Convention** — see [`docs/naming_convention.md`](docs/naming_convention.md) for the full specification, including the canonical part names.

### Flexible Coordinate System Declaration

The `_metadata.coordinate_system` field now accepts an explicit axis object for glTF compatibility (Blender default is Y-up, -Z-forward):

```json
"_metadata": {
  "coordinate_system": { "up": "Y", "forward": "-Z", "handedness": "right" },
  "units": "meters"
}
```

The physics data coordinate system (SAE_J670 by default) is separate from the glTF asset convention and both can be documented in the same file.

### Integrity Checker

Validate all visual bindings before committing:

```bash
python tools/integrity_check.py path/to/vehicle.svj.json
python tools/integrity_check.py path/to/vehicle.svj.json --strict
```

### Fitting meshes to the SVJ (viewer v4.4)

The viewer can line a glTF up with the physics data part by part, then save both files:

1. Drop the SVJ and its `.glb` files on the viewer, open the **Meshes** tab.
2. Select a part — click it in 3D or pick it in the node tree (a part is one glTF node; *whole asset* moves the file as a unit). **▲ Parent** climbs the hierarchy, 👁 / **Isolate** help to see what you are moving.
3. Move or rotate it with the gizmo (G / R / S), by typing exact local values, or with the keys: arrows = SAE X/Y, PgUp / PgDn = Z, **Alt** rotates, **Shift** ×10 (step 0.1 – 100 mm). **Snap to** puts the part's centre or origin exactly on any SVJ point (a hardpoint, a spring mount, the CG), which is the quick way to fit a wheel or an upright. Ctrl+Z undoes every edit.
4. **Save SVJ + GLB** writes the corrected `.svj.json` and one `.glb` per changed file. Only the glTF node transforms are rewritten (`matrix` nodes become translation/rotation/scale); geometry, materials and textures are copied byte for byte. A whole-asset offset is baked into the GLB and removed from the SVJ, so the saved pair needs no viewer-specific data. Hardpoint edits made in the other tabs are saved in the same SVJ.

The mesh is assumed to be in metres and in the viewer's glTF frame (Y up, −Z forward); fitting moves the mesh to the physics data, it never rescales it.

---

## Design Principles

- **Explicit over implicit** — every value is stated, no hidden defaults
- **Station independence** — each wheel station (FL…RR or A1L…A{n}R) is fully self-contained; inter-axle load sharing is declared explicitly in `suspension_couplings`
- **Multi-fidelity** — use what you have (3-tier compliance, 4 tire models, optional everything)
- **Human-readable** — JSON with meaningful names, SI units, no binary blobs
- **Extensible** — simulator-specific data lives in `x_` prefixed keys, ignored by everyone else
- **Validatable** — JSON Schema catches structural errors before they become physics bugs

---

## Quick Start

```bash
pip install jsonschema
python tools/validate.py examples/formula_f1_2025_aero.svj.json
python tools/validate.py examples/skeleton_6x4_walking_beam_dump_truck.svj.json   # multi-axle
python tools/validate.py examples/skeleton_awd_ondemand_diff_control.svj.json     # differential control
python tools/multibody_check.py --joints examples/bmw_e30_325i_semi_trailing.svj.json   # effective joint types
```

---

## Tools

| Tool | Purpose |
|---|---|
| `tools/validate.py` | Validates any SVJ file against the JSON Schema, then runs the cross-reference checkers (`multiaxle_check`, `drivetrain_check`, `multibody_check`). Accepts one or more files, exits non-zero on errors. |
| `tools/integrity_check.py` | Validates glTF visual bindings: node naming pattern and category, id match for every carrier (uprights, links, wheels, brakes, steering, powertrain, aero), mesh_ref validity, uniqueness, `placement` rules, and advisories on category fit and part naming. Use `--strict` to also fail on warnings. |
| `tools/multiaxle_check.py` | Multi-axle cross-reference rules (spec §23.7). Run automatically by `validate.py`; also usable standalone. |
| `tools/multibody_check.py` | Multibody cross-references (spec §9.2.3.2–9.2.3.3): `body_ref`, `parent`, `outboard_ref`, unit quaternions, mass/CG consistency; `--joints` prints every link's effective (explicit or inferred) joint types. Run automatically by `validate.py`. |
| `tools/constraints_check.py` | Movable parts (spec §24): constraint and pose references, joint ranges, frame coincidence, graph connectivity, inertia plausibility, actuator reach in every pose; also computes body transforms, CG, composite inertia and element lengths (`--poses`). Run automatically by `validate.py`. |
| `tools/assemble.py` | Attachments and combinations (spec §27): checks interfaces and connections (roles mate, sizes agree, one root) and assembles units into one composite document. |
| `tools/loop_solver.py` | Loop-closure solver (spec §26): wheel-travel sweeps with camber, toe, bump steer and camber gain from the bodies and joints. |
| `tools/leaf_pack.py` | Flexible leaf pack generator (spec §25.10): segment bodies, hinges and torsional springs from the pack's leaves and span. |
| `tools/collision_check.py` | Collision proxies (spec §28): clearance between the proxy shapes of bodies that move relative to each other, per pose. |
| `tools/torsion_beam.py` | Twist-beam axle generator (spec §25.11): trailing arms and a beam joint whose bushing is soft in torsion. |
| `tools/migrate_suspension.py` | Converts the deprecated corner-based `suspension` to the unified model (spec §25.8): bodies, joints, elements, `wheel_stations[]`, `anti_roll_bars[]`; `estimate_motion_ratio()`. |
| `tools/suspension_view.py` | Expands an authored suspension (corners, uprights, links, hardpoints) into bodies and `joint` constraints with coincident frames, reusing existing `body_ref` bodies and noting what the data does not say (unknown joint types, massless parts). `--json` prints the expansion. A transition tool toward the unified suspension model. |
| `tools/drivetrain_check.py` | Differential-control rules (spec §10.6.1, §10.8.1): `lock_control` curves/targets/limits and `transfer_case.coupling`. Run automatically by `validate.py`; also usable standalone. |
| `tools/validate_override.py` | Resolves an `*.svj-override.json` file's `base` + `patch` (new in v0.98) and validates the resulting document against the standard schema. |

---

## Examples

All example files validate against the current schema (`tools/validate.py`). The two-axle cars cover the original 10 suspension topologies; the v0.99 multi-axle skeletons cover the three new types and every coupling family.

| File | Layout | Front | Rear |
|---|---|---|---|
| `formula_f1_2025_aero.svj.json` | RWD | `double_wishbone` (pushrod) | `double_wishbone` (pullrod) |
| `alfa_romeo_75_de_dion.svj.json` | RWD | `double_wishbone` | `de_dion` |
| `bmw_e30_325i_semi_trailing.svj.json` | RWD | `macpherson` | `semi_trailing_arm` |
| `corvette_c3_chapman_strut.svj.json` | RWD | `double_wishbone` | `chapman_strut` |
| `citroen_2cv_trailing_arm.svj.json` | FWD | `trailing_arm` | `trailing_arm` |
| `skeleton_ff_macpherson_torsion.svj.json` | FWD | `macpherson` | `torsion_beam` |
| `skeleton_awd_ev_dual_motor.svj.json` | AWD | `double_wishbone` | `double_wishbone` |
| `skeleton_4wd_solid_axle.svj.json` | 4WD | `macpherson` | `solid_axle` |
| `skeleton_awd_ondemand_diff_control.svj.json` | AWD | `macpherson` | `solid_axle` — on-demand coupling, modulated centre lock, separate power/coast chains on the rear LSD *(v0.99.3)* |
| `skeleton_visual_binding_dw_corner.svj.json` | — | `double_wishbone` corner with 45 glTF bindings *(v0.99.2)* | — |
| `skeleton_ff_articulated_panels.svj.json` | FWD | `macpherson` | `torsion_beam` — two doors with latches and door-check detents, hood, and a power-operated tailgate, as hinged bodies with gas struts, rubber-stop contacts and poses *(v0.99.8)* |
| `skeleton_dump_truck_tipper_cab.svj.json` | 6x4 | leaf | walking-beam tandem — tilting cab, tipper body on rams, tailgate linked to the body, locks *(v0.99.6)* |
| `skeleton_tractor_loader_hitch.svj.json` | 4WD | `macpherson` | `solid_axle` — tractor with front loader (boom, bucket, three cylinders), rear hitch and implement; composite mass, CG and inertia include the attachments *(v0.99.5)* |
| `tire_mf62_245_40r18.svj.json` | — | Standalone Pacejka MF 6.2 tire file | — |

**Real multi-axle vehicle (v0.99.1)** — published manufacturer data plus marked estimates:

| File | Wheel formula | Suspension types | Published data used |
|---|---|---|---|
| `man_tgs_32_430_8x4_twin_steer_tipper.svj.json` | 8x4/4 | `solid_axle` leaf on all four axles | Axle spacings, overhangs, group loads (design/legal/unladen), tyres, rims, suspension type, engine, gearbox ratios, axle ratio, turning circle |
| `man_tgs_36_430_8x4_4_tridem_lift_tag.svj.json` | 8x4/4 | leaf steer axle; air-sprung drive tandem and steered lift tag axle | Same as above, plus lift/steer tag axle, mixed tyre sizes, GCW; air circuit as `pneumatic_circuit` |
| `tatra_t815_7_8x8_swing_axle.svj.json` | 8x8/4 | `swing_axle` with air springs on all four axles (backbone tube) | Axle spacings, overhangs, length, width, track, clearance, angles, curb/payload/GVW, tyres, powertrain, performance |
| `oshkosh_hemtt_a4_m977a4_8x8.svj.json` | 8x8/4 | air-sprung beam axles (NEWAY) on all four axles | Wheelbase (bogie centres), track, dimensions, curb/GVWR/GCWR, 16.00R20 tyres, suspension and axle models, powertrain models; axle spreads measured from the to-scale drawing (low confidence) |

**Multi-axle skeletons (v0.99)** — representative estimates, not production data:

| File | Wheel formula | Suspension types | Coupling / special feature |
|---|---|---|---|
| `skeleton_6x4_walking_beam_dump_truck.svj.json` | 6x4 | `solid_axle` (leaf, torque rods) | `walking_beam`, `rubber_block`, duals, inter-axle diff |
| `skeleton_6x4_camelback_tractor.svj.json` | 6x4 | `solid_axle` | `trunnion_spring`, slipper-end friction |
| `skeleton_8x4_pusher_lift_axle_truck.svj.json` | 8x4/4 | `solid_axle`, `parallelogram` | self-steer lift axle, `pneumatic_circuit` |
| `skeleton_8x8_swing_axle_backbone_truck.svj.json` | 8x8/4 | `swing_axle` | twin steer (`mechanical_link`), shared leaf `walking_beam` |
| `skeleton_6x6_portal_hydropneumatic.svj.json` | 6x6/2 | `solid_axle` (portal) | `hydropneumatic`, roll/pitch `hydraulic_circuit` |
| `skeleton_3axle_air_semi_trailer.svj.json` | — | `trailing_arm` + beam axle | lift axle, duals, `pneumatic_circuit` |
| `skeleton_tandem_leaf_trailer_equalizer.svj.json` | — | `solid_axle` (leaf) | `equalizer_rocker` |
| `skeleton_tandem_torsion_axle_trailer.svj.json` | — | `trailing_arm` | `rubber_torsion`, independent axles |
| `skeleton_4axle_modular_trailer_pendulum.svj.json` | — | `pendulum_axle` | 3-point `hydraulic_circuit`, 4 tyres per axle line |
| `skeleton_reverse_trike_center_wheel.svj.json` | 3x1 | `double_wishbone`, `trailing_arm` | centreline `A2C` station |

---

## Repository Structure

```
schema/
  ├── svj.schema.json             JSON Schema Draft-07 (v0.102)
  └── svj-override.schema.json    Override file structure (v0.98)
spec/
  └── SVJ_Spec.md                 Human-readable specification (§1–§23)
docs/
  └── naming_convention.md        SVJ::category::name glTF convention + canonical part names
examples/
  ├── *.svj.json                  Two-axle cars, skeletons and a standalone tire file
  ├── skeleton_*x*_*.svj.json     Multi-axle skeletons (v0.99)
  └── *.svj-override.json         Override file example
templates/
  └── mazda_mx5_nd2_2024.svj.json Full vehicle template
tools/
  ├── validate.py                 Schema + cross-reference validation (multi-axle, drivetrain, multibody, constraints)
  ├── multiaxle_check.py          Multi-axle cross-reference rules (v0.99)
  ├── drivetrain_check.py         Differential-control rules (v0.99.3)
  ├── constraints_check.py        Movable parts: checks, kinematics, per-pose CG / inertia, contacts (v0.99.5–0.99.8)
  ├── suspension_view.py          Deprecated suspension expanded to bodies and joints (v0.99.8)
  ├── migrate_suspension.py       Deprecated suspension -> unified model (v0.100)
  ├── assemble.py                 Attachments: interfaces, combination file, composite (spec §27)
  ├── loop_solver.py              Loop-closure solver: wheel travel, camber, toe (spec §26)
  ├── leaf_pack.py                Flexible leaf pack generator (spec §25.10)
  ├── torsion_beam.py             Twist-beam axle generator (spec §25.11)
  ├── collision_check.py          Collision proxy clearances per pose (spec §28)
  ├── multibody_check.py          Multibody cross-references + joint-type inference (v0.96 fields)
  ├── validate_override.py        Override file resolution + validation (v0.98)
  └── integrity_check.py          glTF visual binding checks (v0.99.2)
svj-py/                           Python library + CLI (v0.2.0, multi-axle aware, runs the same cross-reference checks, `Vehicle.joints()`)
viewer/
  └── svj_viewer_v4.6.html        3D inspector/editor — drag & drop any SVJ file; multi-axle layout, axle/wheel editor, performance tab, differential control, joint types and marker frames, per-part mesh fitting with SVJ + GLB save
proposals/                        Design proposals and research notes
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
