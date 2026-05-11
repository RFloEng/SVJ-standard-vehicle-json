# SVJ Project Brief — For Cowork Continuation

## What This Is

SVJ (Standard Vehicle JSON) is a universal exchange format for vehicle dynamics data — a "Rosetta Stone" that lets any simulator read the same vehicle definition. Current version: **v0.97**.

## Repo Structure

```
spec/SVJ_Spec.md                        THE specification (2213 lines, §1–§22)
schema/svj.schema.json                  JSON Schema Draft-07
examples/                               9 examples (real cars + skeletons + tire file)
docs/naming_convention.md               SVJ::category::id glTF naming convention
tools/validate.py                       Schema validation (v0.97)
tools/integrity_check.py                glTF visual binding checks (v0.97)
viewer/svj_viewer_v3.9.html             Interactive SVJ file viewer (drag & drop)
svj-py/                                 Python parser library with CLI
proposals/                              Historical design proposals (read-only)
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

## v0.97 — glTF Visual Binding Layer

New in v0.97 (all optional, fully backward-compatible):

- **`assets.meshes`** — top-level manifest declaring glTF/glb files used by the vehicle
- **`visual` field** on any body object — binds physics body to a glTF node via `mesh_ref` + `node`
- **`coordinate_system` object** — explicit axis declaration for glTF assets (Blender Y-up / -Z-forward)
- **SVJ Naming Convention** — `SVJ::<category>::<id>` pattern for all glTF node names
- **`tools/integrity_check.py`** — validates 4 binding rules: node pattern, id-suffix match, mesh_ref validity, uniqueness
- **`tools/validate.py`** — validates any SVJ file against the JSON Schema

## Topology Coverage (all 10 with examples)

✅ double_wishbone (Alfa 75 front, Corvette C3 front, F1 front/rear, AWD EV)
✅ macpherson (BMW E30 front, FF hatch front, 4WD truck front)
✅ multi_link (skeleton AWD EV rear)
✅ chapman_strut (Corvette C3 rear)
✅ trailing_arm (Citroën 2CV front + rear)
✅ semi_trailing_arm (BMW E30 rear)
✅ torsion_beam (FF hatch rear)
✅ solid_axle (4WD truck rear)
✅ de_dion (Alfa 75 rear)
✅ custom (by design — no example needed)

## Pending / Roadmap

### Immediate (before v1.0 tag)
- Parser development (`svj-py`) — separate project, uses spec + schema + examples as inputs
- Converter: Assetto Corsa ↔ SVJ — separate repo (not in this spec repo)
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
python tools/validate.py examples/formula_f1_2025_aero.svj.json
# Or for all examples:
for f in examples/*.svj.json; do python tools/validate.py "$f"; done
# Check glTF bindings:
python tools/integrity_check.py examples/formula_f1_2025_aero.svj.json --strict
```

## How to Work on This Project

1. **Read the spec first** for any section you're modifying — it's the source of truth.
2. **Change spec text → update schema → update examples → validate** — always in this order.
3.