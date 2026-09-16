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

**Drivetrain** — engine, clutch, gearbox, transfer case, propshafts with joints, differentials (including asymmetric LSD ramp angles), half-shafts with CV joints that match the upright hardpoints

**Aerodynamics** — coefficients, 1D/2D sensitivity maps (ride height, yaw, pitch, speed), individual components with cross-influences, wake/dirty air model, ground effect (underbody, tire squirt, sealing), active systems (DRS, PID-controlled active wings, active ride height)

**Electric/Hybrid** — motors (P0 through P4 and in-wheel), battery pack with thermal model, inverters, regenerative braking

**Cooling** — thermal circuits with radiator, pump, thermostat

**Driver controls** — throttle mapping, brake feel, traction control, launch control

Everything is optional. A file with just metadata and suspension is valid — useful for sharing a setup. A file with everything filled in is a complete vehicle ready for multi-body dynamics.

---

## v0.99.1 — Real-Vehicle Data Patch *(new)*

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

`tools/validate.py` now also runs `tools/multiaxle_check.py`, which checks the cross-references a schema can't (naming form, contiguous axles, coupling and torque-rod references, dual-wheel positions). The Python library (`svj-py` 0.2.0) and the 3D viewer (v4.0) read any number of axles, dual wheels and couplings. Full details: [`spec/SVJ_Spec.md` §23](spec/SVJ_Spec.md).

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

The `node` value must follow the **SVJ Naming Convention** — see [`docs/naming_convention.md`](docs/naming_convention.md) for the full specification.

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
```

---

## Tools

| Tool | Purpose |
|---|---|
| `tools/validate.py` | Validates any SVJ file against the JSON Schema. Accepts one or more files, exits non-zero on errors. |
| `tools/integrity_check.py` | Validates glTF visual bindings: node naming pattern, id-suffix match, mesh_ref validity, uniqueness. Use `--strict` to also fail on warnings. |
| `tools/multiaxle_check.py` | Multi-axle cross-reference rules (spec §23.7). Run automatically by `validate.py`; also usable standalone. |
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
| `tire_mf62_245_40r18.svj.json` | — | Standalone Pacejka MF 6.2 tire file | — |

**Real multi-axle vehicle (v0.99.1)** — published manufacturer data plus marked estimates:

| File | Wheel formula | Suspension types | Published data used |
|---|---|---|---|
| `man_tgs_32_430_8x4_twin_steer_tipper.svj.json` | 8x4/4 | `solid_axle` leaf on all four axles | Axle spacings, overhangs, group loads (design/legal/unladen), tyres, rims, suspension type, engine, gearbox ratios, axle ratio, turning circle |

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
  ├── svj.schema.json             JSON Schema Draft-07 (v0.99)
  └── svj-override.schema.json    Override file structure (v0.98)
spec/
  └── SVJ_Spec.md                 Human-readable specification (§1–§23)
docs/
  └── naming_convention.md        SVJ::category::name glTF convention
examples/
  ├── *.svj.json                  Two-axle cars, skeletons and a standalone tire file
  ├── skeleton_*x*_*.svj.json     Multi-axle skeletons (v0.99)
  └── *.svj-override.json         Override file example
templates/
  └── mazda_mx5_nd2_2024.svj.json Full vehicle template
tools/
  ├── validate.py                 Schema + multi-axle validation
  ├── multiaxle_check.py          Multi-axle cross-reference rules (v0.99)
  ├── validate_override.py        Override file resolution + validation (v0.98)
  └── integrity_check.py          glTF visual binding checks (v0.97)
svj-py/                           Python library + CLI (v0.2.0, multi-axle aware)
viewer/
  └── svj_viewer_v4.0.html        3D inspector/editor — drag & drop any SVJ file (v0.99 multi-axle)
proposals/                        Design proposals and research notes
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
