# SVJ — Standard Vehicle JSON

### A Rosetta Stone for vehicle simulation.

Every simulator speaks its own language. Assetto Corsa has `suspensions.ini` and `tyres.ini`. BeamNG uses JBeam node-beam meshes. Adams Car wants `.adm` templates with bushing matrices. CarMaker needs its own parameter files. rFactor2 has yet another format. Unity and Unreal don't even model suspension geometry — they just want a spring rate and a wheel radius.

If you've ever tried to move a car between any two of these, you know the pain. There's no common ground. You end up writing one-off scripts, guessing at unit conversions, and losing data at every step.

**SVJ fixes this.** It's a single, human-readable JSON format that can describe a complete vehicle — from a 1077 kg Mazda MX-5 with its double-wishbone front suspension and asymmetric LSD, down to the individual bushing stiffness at each pickup point and the Pacejka coefficients on each tire. Every simulator gets what it needs from the same file. What it can't use, it ignores.

The idea is simple: **define the car once, in engineering terms, with real physics.** Then let converters translate that into whatever each target needs. A converter to Assetto Corsa picks the 40 fields it understands. Adams Car reads 90% natively. UE5 Chaos gets the 15% it can handle. The data is always there — the converter decides the fidelity.

SVJ is not a simulator. It's not a physics engine. It's a **vocabulary** — a way to write down what a car *is*, so that any tool can read it.

---

## What's inside

An SVJ file describes the complete physical vehicle:

- **Chassis** — mass, CG, full inertia tensors, decomposition into individual rigid bodies (engine, gearbox, fuel, driver...), torsional stiffness
- **Steering** — rack geometry, ratio, electric power assist, column dynamics
- **Suspension** — 10 topology types (double wishbone, MacPherson, multi-link, torsion beam, solid axle, De Dion...) with hardpoints, links, bushings (3-tier: rigid → scalar compliance → full 6-DOF), springs, dampers, ARBs, alignment
- **Tires** — 4 model types in one file: Pacejka MF 5.2/6.2 (80+ coefficients), TMeasy (~20 params), brush model (~10 params), plus external file references for FTire, CDTire, MF-Swift
- **Brakes** — full force chain from pedal through booster and master cylinder to caliper, per-corner discs with mass and thermal properties, ABS/ESC
- **Drivetrain** — engine, clutch, gearbox, transfer case, propshafts with joints, differentials (including asymmetric LSD ramp angles), half-shafts with CV joints that match the upright hardpoints
- **Aerodynamics** — coefficients, sensitivity maps, individual components (wings, splitters, diffusers), active systems (DRS, active ride height)
- **Electric/Hybrid** — motors (P0 through P4 and in-wheel), battery pack with thermal model, inverters, regenerative braking
- **Cooling** — thermal circuits with radiator, pump, thermostat
- **Driver controls** — throttle mapping, brake feel, traction control, launch control

Everything is optional. A file with just metadata and suspension is valid — useful for sharing a setup. A file with everything filled in is a complete vehicle ready for multi-body dynamics.

## Design Principles

1. **Explicit over implicit** — every value is stated, no hidden defaults
2. **Four-corner independence** — each wheel station is fully self-contained
3. **Multi-fidelity** — use what you have (3-tier compliance, 4 tire models, optional everything)
4. **Human-readable** — JSON with meaningful names, SI units, no binary blobs
5. **Extensible** — simulator-specific data lives in `x_` prefixed keys, ignored by everyone else
6. **Validatable** — JSON Schema catches structural errors before they become physics bugs

## Quick Start

```bash
pip install jsonschema
python tools/validate.py templates/mazda_mx5_nd2_2024.svj.json
```

## Reference Template

**Mazda MX-5 ND2 2024 Club 6MT** — the included template uses factory data where available (steering ratio, gear ratios, track width, brake sizes, tire dimensions) and marks engineering estimates with `_est: true`. It's a real car, not a generic placeholder.

## Examples

Real vehicles and skeleton files covering all 10 suspension topologies:

| Vehicle | Layout | Front Suspension | Rear Suspension | Source |
|---------|--------|-----------------|-----------------|--------|
| **Mazda MX-5 ND2** (template) | FR | `double_wishbone` | `multi_link` (5-link) | Factory + estimated |
| BMW E30 325i | FR | `macpherson` | `semi_trailing_arm` | Factory specs |
| Alfa Romeo 75 TS | FR | `double_wishbone` (torsion bar) | `de_dion` + Watts link | Factory specs |
| Corvette C3 | FR | `double_wishbone` | `chapman_strut` | Factory specs |
| Citroën 2CV6 | FF | `trailing_arm` (leading) | `trailing_arm` | Factory specs |
| FF Hatchback (skeleton) | FF | `macpherson` | `torsion_beam` | Generic |
| AWD EV Sedan (skeleton) | AWD | `double_wishbone` | `double_wishbone` | Generic |
| 4WD Pickup (skeleton) | 4WD | `macpherson` | `solid_axle` + Panhard | Generic |

## Repo Structure

```
spec/SVJ_Spec.md                        Full specification (2026 lines, 124 sections)
schema/svj.schema.json                  JSON Schema Draft-07
templates/mazda_mx5_nd2_2024.svj.json   Complete reference vehicle (3285 lines)
examples/                               7 example vehicles (4 real + 3 skeletons)
tools/validate.py                       Schema + consistency validation
```

## Coordinate System & Units

**SAE J670** — X forward, Y right, Z down. All values in **SI**: meters, kilograms, Newtons, radians, Pascals, seconds. No ambiguity, no conversion tables.

## Conversion

SVJ to any target is a deterministic downsampling — you're projecting rich data into a simpler model, which always works. The other direction (game → SVJ) produces a partial file that a human fills in. Coordinate transforms for Assetto Corsa and BeamNG are included in the spec.

## Status

**v0.94 — v1.0 Release Candidate.** Spec frozen for parser development. See [CHANGELOG.md](CHANGELOG.md) for full history.

## What's Next

- Parser library (`svj-py`) — load, validate, resolve `$ref`, query, export
- Converters — AC↔SVJ, BeamNG↔SVJ
- v1.x addendum for multi-axle / commercial vehicles (trucks, trailers, 6×4, 8×8)

## License

[MIT](LICENSE)
