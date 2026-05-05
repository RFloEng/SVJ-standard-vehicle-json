# SVJ Project Brief — For Cowork Continuation

## What This Is

SVJ (Standard Vehicle JSON) is a universal exchange format for vehicle dynamics data — a "Rosetta Stone" that lets any simulator read the same vehicle definition. Current version: **v0.96**.

## Repo Structure

```
spec/SVJ_Spec.md                        THE specification (2184 lines, 124 sections)
schema/svj.schema.json                  JSON Schema Draft-07 (3447 lines)
templates/mazda_mx5_nd2_2024.svj.json   Full reference template (3555 lines)
examples/                               7 examples (4 real cars + 3 skeletons)
tools/validate.py                       Schema + consistency validation
viewer/index.html                       Interactive SVJ file viewer (drag & drop)
svj-py/                                 Python parser library with CLI
```

## Key Conventions

- **Coordinates:** SAE J670 — X forward, Y right, Z down. Origin at front axle center. CG.x is NEGATIVE (behind front axle).
- **Units:** SI everywhere (m, kg, N, rad, Pa, s). No exceptions.
- **Alignment:** `alignment_convention: "relative_to_centerline"` — negative camber = inward on BOTH sides.
- **Tire data:** Tire dimensions live ONLY in `tires.sets`. Corner `wheel` has rim + `set_ref`, NO tire dimensions.
- **Inertia:** Full 6-component tensor (Ixx, Iyy, Izz, Ixz, Ixy, Iyz), about component's own CG, in vehicle frame axes.
- **Mass:** `mass_bodies` = sprung decomposition. `mass_unsprung_per_corner` = unsprung. `mass_total` = everything. No double counting.
- **Estimates:** Marked with `_est: true`. Factory data has `_source` strings.
- **Extensions:** `x_` prefix for simulator-specific data, `additionalProperties: true` everywhere.

## Topology Coverage (9/10 with examples)

✅ double_wishbone (MX-5 front, Alfa 75, Corvette C3, AWD EV)
✅ macpherson (BMW E30, FF hatch, 4WD truck)
✅ multi_link (MX-5 rear)
✅ chapman_strut (Corvette C3 rear)
✅ trailing_arm (Citroën 2CV front + rear)
✅ semi_trailing_arm (BMW E30 rear)
✅ torsion_beam (FF hatch rear)
✅ solid_axle (4WD truck rear)
✅ de_dion (Alfa 75 rear)
⬜ custom (by design — no example needed)

## MX-5 ND2 Template — Factory Data Sources

17 factory-confirmed values: steering ratio 15.5:1, 2.7 turns L2L, gear ratios (5.087/3.063/2.028/1.522/1.241/1.000), final drive 2.866, track F/R 1495/1505, wheelbase 2310mm, kerb weight 1077kg, tire 205/45R17, brakes 280mm F/R ventilated, ABS 4-channel + EBD, asymmetric LSD (2024 Club). ~60 sections estimated, all marked `_est: true`.

## Pending / Roadmap

### Immediate (before v1.0 tag)
- Parser development (`svj-py`) — separate project, uses spec+schema+template as inputs
- Converter: Assetto Corsa ↔ SVJ (reads suspensions.ini, tyres.ini, engine.ini)
- Any ambiguities found during parser development become spec patches

### Future (v1.x)
- Multi-axle addendum implementation (currently documented in §21.1, not in schema)
- BeamNG converter
- rFactor2 converter

## Design Decisions — Do Not Change

These are load-bearing architectural choices. Changing them would break everything:

1. **4-corner model (FL/FR/RL/RR)** for standard vehicles. Multi-axle is an addendum, not a replacement.
2. **SAE J670 coordinates** with origin at front axle center.
3. **`$ref` for modular files** — JSON Pointer or relative file paths.
4. **`x_` prefix** for extensions — never in the core spec.
5. **`additionalProperties: true`** on all objects — extensibility over strictness.
6. **Tire library with per-corner `set_ref` + override** — no tire dimensions in wheel objects.
7. **3-tier compliance** — rigid / scalar summary / full 6-DOF bushings.
8. **Inertia about own CG, vehicle frame axes** — parallel axis theorem required for composite.
9. **`_est: true`** for estimates, `_source` for factory data — traceability.
10. **`final_drive` in differentials, not gearbox** — supports different F/R ratios in AWD.

## Validation

Always run after any change:
```bash
python tools/validate.py templates/mazda_mx5_nd2_2024.svj.json
# Or for all files:
for f in templates/*.svj.json examples/*.svj.json; do python tools/validate.py "$f"; done
```

Schema validation catches structure. The validator script also checks:
- mass_total ≈ Σ mass_bodies + Σ mass_unsprung_per_corner
- CG.x between 0 and -wheelbase
- Corner weight sum ≈ mass_total × g

## How to Work on This Project

1. **Read the spec first** for any section you're modifying — it's the source of truth.
2. **Change spec text → update schema → update template → validate** — always in this order.
3. **Bump version in ALL files** when making changes: spec title, schema $id + version const, template _metadata.version, all examples.
4. **Update CHANGELOG.md** with every version bump.
5. **Test with deliberately broken input** after schema changes to verify error detection.
