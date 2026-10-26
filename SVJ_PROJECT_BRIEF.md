# SVJ Project Brief — For Cowork Continuation

## What This Is

SVJ (Standard Vehicle JSON) is a universal exchange format for vehicle dynamics data — a "Rosetta Stone" that lets any simulator read the same vehicle definition. Current version: **v0.104** (spec §1–§29; `_metadata.version` accepts every release from 0.96 on). The full per-release history is in `CHANGELOG.md`; this brief summarises it.

## Repo Structure

```
spec/SVJ_Spec.md                        THE specification (§1–§28)
schema/svj.schema.json                  JSON Schema Draft-07 (v0.102)
schema/svj-override.schema.json         Override file structure (v0.98)
schema/svj-combination.schema.json     Combination file structure (v0.101)
examples/                               ~30 examples (real cars, 2-axle skeletons, multi-axle skeletons, real multi-axle trucks, visual-binding, articulated-parts, tire file)
examples/attachments/                   Host/attachment units and *.svj-combination.json files (tractor + loader, tractor + semi-trailer)
docs/naming_convention.md               SVJ::category::id glTF naming convention + canonical part names
tools/validate.py                       Schema + all cross-reference checks (also combination files and their assembled composite)
tools/multiaxle_check.py                Multi-axle rules (§23.7)
tools/multibody_check.py                Mass-body / marker / joint-type rules (v0.96)
tools/drivetrain_check.py               Differential lock_control / coupling rules (v0.99.3)
tools/constraints_check.py              Joints, springs, actuators, latches, couplings, contacts, poses (§24)
tools/loop_solver.py                    Loop-closure solver, suspension gains and alignment (§26)
tools/assemble.py                       Interfaces, attachments, combination assembly (§27)
tools/collision_check.py                Collision-proxy separation per pose (§28)
tools/setup_check.py                    Adjustment ranges, setups, apply_setup (§29)
tools/tire_model.py                     Magic Formula evaluator: Fx, Fy, Mz, My, characteristics (§11.13)
tools/migrate_suspension.py, suspension_view.py, anti_roll_bar.py, leaf_pack.py, torsion_beam.py   Unified-suspension migration and component builders (§25)
tools/validate_override.py              Override resolution + validation (v0.98)
tools/integrity_check.py                glTF visual binding checks (v0.99.2)
viewer/svj_viewer_v4.7.html             Interactive viewer/editor: multi-axle layout, performance tab, mesh fitting, poses panel, unified-suspension reader, combinations, collision proxies
svj-py/                                 Python library with CLI (0.2.0); mirrors of the tools/ checkers in svj-py/svj/ (sync enforced by tests)
templates/mazda_mx5_nd2_2024.svj.json   Full vehicle template (unified suspension)
proposals/                              Historical design proposals (read-only)
```

## Key Conventions

- **Coordinates:** SAE J670 — X forward, Y right, Z down. Origin at front axle (A1) center, ground level. CG.x is NEGATIVE (behind front axle) — except trailers/semi-trailers, whose CG sits ahead of A1.
- **Units:** SI everywhere (m, kg, N, rad, Pa, s). No exceptions.
- **Alignment:** `alignment_convention: "relative_to_centerline"` — negative camber = inward on BOTH sides.
- **Tire data:** Tire dimensions live ONLY in `tires.sets`. Corner `wheel` has rim + `set_ref`, NO tire dimensions.
- **Inertia:** Full 6-component tensor (Ixx, Iyy, Izz, Ixz, Ixy, Iyz), about component's own CG, in vehicle frame axes.
- **Mass:** `mass_bodies` = sprung decomposition. `mass_unsprung_per_corner` = unsprung. `mass_total` = everything. No double counting.
- **Estimates:** Marked with `_est: true`. Factory data has `_source` strings.
- **Extensions:** `x_` prefix for simulator-specific data, `additionalProperties: true` everywhere. `_`-prefixed keys (`_est`, `_note`, `_source_detail`) are allowed metadata, including inside station-keyed objects and pacejka groups.
- **Wheel stations:** FL/FR/RL/RR (two axles) or A{n}{L|R|C}; one station = one hub (duals via `wheel.multiplicity`).

## v0.97 — glTF Visual Binding Layer

New in v0.97 (all optional, fully backward-compatible):

- **`assets.meshes`** — top-level manifest declaring glTF/glb files used by the vehicle
- **`visual` field** on any body object — binds physics body to a glTF node via `mesh_ref` + `node`
- **`coordinate_system` object** — explicit axis declaration for glTF assets (Blender Y-up / -Z-forward)
- **SVJ Naming Convention** — `SVJ::<category>::<id>` pattern for all glTF node names
- **`tools/integrity_check.py`** — validates 4 binding rules: node pattern, id-suffix match, mesh_ref validity, uniqueness
- **`tools/validate.py`** — validates any SVJ file against the JSON Schema

## v0.98 — Validation, Benchmarks & Override Files

New in v0.98 (all optional, fully backward-compatible; prompted by a review of VI-Grade's VI-CarRealTime white paper — see `proposals/vi_carrealtime_whitepaper_insights.md`):

- **`validation`** — vehicle-level correlation status against physical test data (`status`, `method`, `test_reference`, `correlated_channels`, `correlation_quality`, `date`, `notes`)
- **`benchmarks`** — array of KPI entries (`id`, `value`, `unit`, `type: target|measured|simulated`, `source`)
- **Override files** (`*.svj-override.json`) — `base` file path + RFC 7396 JSON Merge Patch `patch`, for DOE variants and partial-disclosure supplier hand-offs. Spec §3.4.
- **`schema/svj-override.schema.json`** — structural schema for override files
- **`tools/validate_override.py`** — resolves `base` + `patch` and validates the result against `schema/svj.schema.json`
- **`examples/bmw_e30_325i_stiffer_front.svj-override.json`** — example override; `examples/bmw_e30_325i_semi_trailing.svj.json` demonstrates `validation` + `benchmarks`

## v0.99 — Multi-Axle Vehicles

Spec §23, all optional and backward-compatible:

- **Station naming** `A{n}{L|R|C}`; `FL/FR/RL/RR` = aliases of `A1L/A1R/A2L/A2R`, two-axle vehicles only; forms never mixed
- **`axles`** array (position_x, track, steered, driven, liftable/lift, max_load)
- **`wheel.multiplicity` / `dual_spacing` / `positions`** — dual wheels on one hub (one station = one hub)
- **`steering.axle_ref` / `additional_axles`** (§8.6) — mechanical_link, self_steer, command_steer, hydraulic, active
- **`suspension_couplings`** (§23.5) — equalizer_rocker, walking_beam, trunnion_spring, pneumatic_circuit, hydraulic_circuit, custom; corners reference them via `spring.coupling_ref`
- **New system_types** swing_axle, parallelogram, pendulum_axle; **spring types** rubber_torsion, rubber_block, hydropneumatic, hydraulic, none (+ leaf end type/friction, hydropneumatic block); **damper types** hydraulic_strut, none; **axle_body** portal_drop, hub_reduction_ratio, pendulum fields; **link types** torque_rod, pivot
- `vehicle_info.wheel_formula` / `vehicle_class`; `differentials[].axle_ref`, `location: inter_axle`, `through_drive`; truck tyre `size_code`s
- **`tools/multiaxle_check.py`** — cross-reference rules (§23.7), run by `validate.py` and `validate_override.py`; identical copy in `svj-py/svj/multiaxle.py` (a test enforces sync)
- **`svj-py` 0.2.0** — `stations`, alias-aware `corner()`, `axles`, `axle_count`, `wheel_count`, `tyre_count`, `wheel_formula`, `suspension_couplings`; CLI `info` shows axles and couplings
- **Viewer v4.0** — renders any station set, dual wheels and coupling pivots/beams; axles and couplings panels; camera fits vehicle length
- **Viewer v4.1** — axle beams, frame rails / backbone, 3D axle labels, lift axles raised toggle, circuit links; top-view axle layout diagram; Station & Axle panel; axle/wheel editor (add/remove axle, X, track, steered/driven/liftable, single/dual, dual spacing) with whole-document undo
- **Viewer v4.2** — Performance tab: full-throttle longitudinal model from engine/motor torque, gearbox, final drive (+ transfer case, hub reduction), tyres, mass and aero. Speed vs time, rpm vs speed, tractive force vs speed; 0–100/0–50/0–200, 400 m, top speed, gradeability; compared with `benchmarks`; every input tagged file/default. Known spec gaps the model has to default: scalar tyre rolling resistance, torque-converter stall ratio, truck aero (most examples have no `aerodynamics`)
- **Schema fixes found during v0.99 audit:** truck tyre `size_code`s; `_` metadata keys allowed in pacejka groups (Mazda template now validates)
- Note: the v0.94 changelog entry described a multi-axle convention (§21.1) that never landed in the spec; §23 is the real implementation.

## v0.99.2 — Visual Binding Layer, Part 2

- One category set in schema, spec §22.5 and `docs/naming_convention.md`: `body`, `suspension`, `steering`, `wheel`, `brake`, `powertrain`, `aero`, `helper`, `lod` (the schema previously allowed only `body`/`helper`/`lod`, so the spec's own examples failed validation)
- `visual` defined on links, uprights, axle bodies, wheels and dual-wheel positions, springs, dampers, ARBs, brake discs/calipers, steering rack/column/wheel, powertrain units, driveshafts, aero components
- `placement`: `rigid` (default) or `link_between_points` (+ `mesh_axis`, `from_point`, `scale_to_length`) for parts defined by hardpoints
- Canonical part-name vocabulary with aliases; id-match rule extended from uprights to every carrier
- `tools/integrity_check.py` rewritten; `examples/skeleton_visual_binding_dw_corner.svj.json` added
- Follow-up not done here: the AC → SVJ converter's `map_ac_nodes_to_svj` still emits only chassis + four uprights

---

## v0.99.1 — Real-Vehicle Data Patch

- **`axle_groups`** (§23.2.1) — `axle_refs`, `max_load_design`, `max_load_legal`, `kerb_load` (N), `jurisdiction`
- **`chassis.plated_masses`** — GVM/GCM design and legal (kg)
- **`wheelbase_reference`** — `last_axle`, `bogie_centre`, `bogie_centres`, `first_rear_axle`, `theoretical`, `explicit` (+ `wheelbase_from`/`wheelbase_to`); definition table in §23.6. Groups default to a split at the largest axle gap
- `gearbox.type: "amt"`; checker validates groups, kerb-load sum and the declared wheelbase; svj-py `axle_groups`, `plated_masses`, weight share from group loads or front/rear group centres; viewer axle-groups panel and correct F/R bias on multi-axle vehicles
- **`examples/man_tgs_32_430_8x4_twin_steer_tipper.svj.json`** — first real multi-axle vehicle (MAN UK body-builder sheet, May 2022)

## v0.99.3 → v0.104 — Summary (details in CHANGELOG.md)

- **v0.99.3** Differential control: `lock_control` stage chains, `transfer_case.coupling` (§10.6.1)
- **v0.99.4** Strut/damper conventions: `strut_lower` hardpoint, `damper.reference` (`damper`|`wheel`)
- **v0.99.5–0.99.8** Movable parts (§24): `constraints[]` (joint, spring, actuator, latch, coupling, contact), `poses[]`, `chassis.markers`, partial `mass_bodies` decomposition, canonical part-name vocabulary
- **v0.100** *Breaking, one release of transition:* unified suspension (§25) — bodies, joints, elements plus `wheel_stations[]`; the old `suspension` section is deprecated (accepted, validators warn). All shipped examples and the MX-5 template are migrated; legacy copies live in `svj-py/tests/fixtures/legacy_*.svj.json`. Loop-closure solver (§26)
- **v0.101** Attachments and combinations (§27): `interfaces[]`, `attachments[]`, `*.svj-combination.json`, role mating table, `vehicle_class: attachment`; `.` in ids is reserved for qualified ids (`unit.id`)
- **v0.102** Collision proxies (§28): `collision[]` on chassis and mass bodies, `collision_ignore`; interface `supply`/`demand`
- **v0.103** Adjustments and setups (§29): `adjustments[]` (range or list of values on a path or linked paths), `setups[]` (`{path: value}`), `active_setup`; paths use `id` selectors, e.g. `constraints[spring_fl].preload`
- **v0.104** Tyre evaluation (§11.13): the MF-Tyre 6.1 equations written into the spec, `pacejka.reference_load_N` / `scaling`, friction-circle fallback; evaluator `tools/tire_model.py`. No evaluator yet for `tmeasy` and `brush`, nor `Mx`
- Generated (`x_derived`) bodies and joints are exempt from the mass, inertia and parent rules, including in assembled composites

## Topology Coverage (all 13 with examples)

✅ double_wishbone (Alfa 75 front, Corvette C3 front, F1 front/rear, AWD EV)
✅ macpherson (BMW E30 front, FF hatch front, 4WD truck front)
✅ multi_link (skeleton AWD EV rear)
✅ chapman_strut (Corvette C3 rear)
✅ trailing_arm (Citroën 2CV front + rear)
✅ semi_trailing_arm (BMW E30 rear)
✅ torsion_beam (FF hatch rear)
✅ solid_axle (4WD truck rear)
✅ de_dion (Alfa 75 rear)
✅ swing_axle (8x8 backbone truck skeleton, Tatra T815-7 8x8)
✅ parallelogram (8x4 pusher lift axle)
✅ pendulum_axle (modular trailer)
✅ custom (by design — no example needed)

## Pending / Roadmap

### Immediate (before v1.0 tag)
- Parser development (`svj-py`) — separate project, uses spec + schema + examples as inputs
- Converter: Assetto Corsa ↔ SVJ — separate repo (not in this spec repo)
- Any ambiguities found during parser development become spec patches

### Future (v1.x)
- Articulated combinations: ✅ implemented in v0.101 (§27, `tools/assemble.py`). Still open from `proposals/trailer_coupling_research.md`: R55 D-value checks, dolly and ADT examples
- STEP visual binding (`proposals/svj_step_visual_binding_proposal.md`) — feasibility study only, nothing implemented
- Known data issues: `examples/formula_f1_2025_aero.svj.json` breaks SAE conventions (CG.x/Z positive, left wheels at +Y, rear axle at -2.8 vs wheelbase 3.6); Mazda template mass_bodies + unsprung (1145 kg) ≠ mass_total (1077 kg)
- Real-vehicle multi-axle examples — ✅ MAN TGS 8x4 twin-steer, ✅ MAN TGS 8x4-4 tridem, ✅ Oshkosh HEMTT A4 (spreads measured from drawing), ✅ Tatra T815-7N0R99 8x8 (swing axles) (shortlist: `proposals/multi_axle_real_vehicle_examples_research.md`)
- BeamNG converter
- rFactor2 converter

## Design Decisions — Do Not Change

These are load-bearing architectural choices. Changing them would break everything:

1. **Station model** — FL/FR/RL/RR for standard two-axle vehicles, `A{n}{L|R|C}` for everything else (§23). Multi-axle is an addendum, not a replacement; inter-axle links live in `suspension_couplings`, never in merged corners.
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
for f in examples/*.svj.json; do python tools/validate.py "$f"; done   # includes multiaxle_check
# Check glTF bindings:
python tools/integrity_check.py examples/formula_f1_2025_aero.svj.json --strict
# Override files:
python tools/validate_override.py examples/bmw_e30_325i_stiffer_front.svj-override.json
# Combination files (also validates the assembled composite):
python tools/validate.py examples/attachments/tractor_semi_trailer.svj-combination.json
# Python library tests (also checks tools/ and svj-py checker copies are in sync):
cd svj-py && python -m pytest -q
```

## How to Work on This Project

1. **Read the spec first** for any section you're modifying — it's the source of truth.
2. **Change spec text → update schema → update examples → validate** — always in this order.
3. **Mirrored checkers:** each `tools/*_check.py` has an identical copy in `svj-py/svj/`; edit both (a test enforces sync).
4. **Record the change** in `CHANGELOG.md` and bump `_metadata.version` handling in `tools/validate.py` for any spec/schema release.