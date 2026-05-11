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

**Steering** — rack geometry, ratio, electric power assist, column dynamics

**Suspension** — 10 topology types (double wishbone, MacPherson, multi-link, torsion beam, solid axle, De Dion...) with hardpoints, links, bushings (3-tier: rigid → scalar compliance → full 6-DOF), springs, dampers, ARBs, alignment

**Tires** — 4 model types in one file: Pacejka MF 5.2/6.2 (80+ coefficients), TMeasy (~20 params), brush model (~10 params), plus external file references for FTire, CDTire, MF-Swift

**Brakes** — full force chain from pedal through booster and master cylinder to caliper, per-corner discs with mass and thermal properties, ABS/ESC

**Drivetrain** — engine, clutch, gearbox, transfer case, propshafts with joints, differentials (including asymmetric LSD ramp angles), half-shafts with CV joints that match the upright hardpoints

**Aerodynamics** — coefficients, 1D/2D sensitivity maps (ride height, yaw, pitch, speed), individual components with cross-influences, wake/dirty air model, ground effect (underbody, tire squirt, sealing), active systems (DRS, PID-controlled active wings, active ride height)

**Electric/Hybrid** — motors (P0 through P4 and in-wheel), battery pack with thermal model, inverters, regenerative braking

**Cooling** — thermal circuits with radiator, pump, thermostat

**Driver controls** — throttle mapping, brake feel, traction control, launch control

Everything is optional. A file with just metadata and suspension is valid — useful for sharing a setup. A file with everything filled in is a complete vehicle ready for multi-body dynamics.

---

## v0.97 — glTF Visual Binding Layer *(new)*

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
- **Four-corner independence** — each wheel station is fully self-contained
- **Multi-fidelity** — use what you have (3-tier compliance, 4 tire models, optional everything)
- **Human-readable** — JSON with meaningful names, SI units, no binary blobs
- **Extensible** — simulator-specific data lives in `x_` prefixed keys, ignored by everyone else
- **Validatable** — JSON Schema catches structural errors before they become physics bugs

---

## Quick Start

```bash
pip install jsonschema
python tools/validate.py templates/mazda_mx5_nd2_2024.svj.json
```

## Repository Structure

```
schema/           JSON Schema (svj.schema.json)
examples/         Reference vehicle implementations
  ├── alfa_romeo_75_de_dion.svj.json
  ├── bmw_e30_325i_semi_trailing.svj.json
  ├── formula_f1_2025_aero.svj.json   ← updated in v0.97 (visual bindings)
  └── ...
docs/
  └── naming_convention.md            ← new in v0.97
tools/
  ├── validate.py                     schema validation
  └── integrity_check.py              ← new in v0.97, visual binding checks
proposals/        Accepted and draft proposals
spec/             Human-readable specification
templates/        Ready-to-use vehicle templates
svj-py/           Python library
viewer/           Browser-based SVJ viewer
```

## Reference Template

Mazda MX-5 ND2 2024 Club 6MT — the included template uses factory data where available (steering ratio, gear ratios, track width, brake sizes, tire dimensions) and carefully sourced estimates for the rest.

---

## License

See [`LICENSE`](LICENSE).
