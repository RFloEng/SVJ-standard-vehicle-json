# Inventory: moving SVJ from SAE J670 to ISO 8855 axes

**Status:** decisions of section 7 taken by the project owner on 2026-11-12. The goal is a coherent system that is **ISO 8855 throughout: vehicle, tyre and assets**. Implemented in v0.109 for the format, the tools, the viewer, the shipped examples and the tyre evaluator (steps 0 to 4 of section 8); the external converters (section 5) remain.

**Why:** ISO 8855 (X forward, Y left, Z up) is the frame of OpenDRIVE/OpenCRG, Blender, USD (Z-up), STJ and Chrono::Vehicle. SVJ uses SAE J670 (X forward, Y right, Z down), so every meeting point with those carries a fixed rotation (STJ §4.6, glTF/USD conversion, every converter from an ISO source). SVJ currently has one user, so the cost of changing is lowest now.

**How the inventory was made:** a scan of the spec, the schema, the 29 shipped example and template files (every 3-number array and 4-number array, by key path), the tools, the Python package, the viewer and the converter folders in `D:\Claude\SVJson`. It finds what is written as a vector, quaternion or tensor, or is described with a sign in words. Items that sit in free-form extension keys (`x_`) or in prose only are listed under "Not covered".

## 1. The transformation

The two frames differ by one fixed rotation of **180 degrees about X**: `R = diag(1, -1, -1)`, quaternion `(qx, qy, qz, qw) = (1, 0, 0, 0)`. It is a proper rotation (det = +1), so nothing mirrors: left stays left, a left-hand part stays a left-hand part. The origin (centre of the front axle at ground level) can stay as it is; this only changes the sign of Y and Z.

| Quantity | Rule SAE to ISO |
|---|---|
| Position or direction `[x, y, z]` | `[x, -y, -z]` |
| Orientation quaternion of a frame (joint frames of the unified suspension, hardpoints, bushings, markers) | `q' = (1, 0, 0, 0) * q` (left-multiply). The joint axis is the frame's +Z and the frame keeps its physical identity, so a hinge is the same hinge |
| Inertia tensor in vehicle axes | `Ixx, Iyy, Izz, Iyz` unchanged; `Ixy` and `Ixz` change sign |
| Rotation angle about X (roll, absolute camber) | unchanged |
| Rotation angle about Y or Z (pitch, yaw, absolute toe) | sign changes |
| Quantities defined in words (camber "top inward", toe "toe-in", bump/rebound, compression positive, `Cl` lift, `Cpm` nose up, `Cym` nose right, drag rearward) | unchanged: they are physical, only the prose that mentions "SAE Z-down" changes |
| Scalars (masses, lengths, track, wheelbase, `position_x` of axles) | unchanged |

## 2. Data that changes (shipped files, by key)

Counts are occurrences in the 29 example and template files.

| Class | Fields (key paths) | Count | Rule |
|---|---|---|---|
| Joint and constraint frames | `constraints[].frame_a.position`, `frame_b.position` | 1020 each | flip Y, Z |
| Mass bodies | `mass_bodies[].position` | 566 | flip |
| Hardpoints and mounts | `wheel_center`, `upper_ball_joint`, `lower_ball_joint`, `damper_outboard`, `steering_tie_rod_end`, `strut_top`, `strut_lower`, `cv_inner`, `cv_outer`, `spring_pad`, `upper/lower_rod_end`, `upper/lower_link_end`, `panhard_axle_end`, `toe_link_end`, `hinge`, `swing_pivot`, per-station variants (`..._a1l` and so on) | about 400 | flip |
| Centre of gravity | `chassis.center_of_gravity` (**z changes sign**: negative values become positive, and the viewer's "CG Z should be negative" check inverts) | 28 | flip |
| Steering | `steering.rack_position` | 19 | flip |
| Couplings | `suspension_couplings[].end_points`, `.end_seats`, `.pivot_position` | 26 | flip |
| Drivetrain | `differentials[].position`, `caliper.position`, `output_flange`, `output_front/rear/left/right`, `input_flange` | about 20 | flip |
| Attachments | `connections[].attach_point`, `interfaces[]` frames | 4 + | flip |
| Legacy extension keys | `x_legacy_axle_body.pendulum_pivot`, `.pendulum_axis` (a direction) | 4 each | flip |
| Quaternions | `frame_a.orientation`, `frame_b.orientation`, hardpoint `orientation`, `bushings[].orientation`, `markers.*.orientation` | many | left-multiply |
| Inertia | `chassis.inertia`, `mass_bodies[].inertia`, upright `inertia`, §7.1 full tensor | many | negate `Ixy`, `Ixz` |
| Bushing preload | `bushings[].preload` | few | none (bushing local frame) once the bushing `orientation` is transformed |
| Absolute alignment | `alignment` when `alignment_convention` is `absolute` (spec line 1035) | few | camber unchanged, toe and any Y/Z rotation negated; `relative_to_centerline` values unchanged |
| Metadata | `_metadata.coordinate_system` (spec says "Always SAE_J670") | 29 | becomes a declared value, see 5.1 |

Scalars that depend on a *position's sign only by convention* need a second look during the work: spec §23 axle `position_x` ("decreases rearwards") stays as it is; station sides are named by the letter but **defined by the sign of Y** (spec §23.1 table: `L` is negative Y, `R` is positive Y), which inverts.

## 3. The tyre needs a decision of its own

The Magic Formula equations (§11.13) are used "as written" and the sign of the result follows the file's coefficients (`tools/tire_model.py`, spec line 1880). The shipped MF example has `pKy1 = -18.5`: SAE-style tyre axes, where a positive slip angle gives a negative `Fy`. The tyre model is therefore tied to the SAE sign convention through its *coefficients*, not through the vehicle frame. If the vehicle frame becomes ISO, a vehicle solver passing slip angles and receiving forces in ISO axes would get the wrong sign from an SAE-coefficient tyre. Two ways:

- **A (decided): ISO is the tyre's default too, and an optional `axis_system` marks legacy sets.** New files use ISO signs for slip angle, `Fy`, `Mz` and `My`. A tyre declared `axis_system: "SAE"` (every existing set) is read by converting at the interface, so nothing is refitted; the conversion tool can rewrite such a set to ISO coefficients, after which the declaration disappears. The end state has no SAE anywhere.
- B (rejected as the only route): rewrite all coefficients by hand. Error-prone and it breaks the link to the lab data.

**The signs must be verified, not assumed.** My first derivation says that for the same physical situation the slip ratio, slip angle and camber keep their numbers, `Fx`, `Fz` and `Mx` keep theirs, and `Fy`, `Mz`, `My` change sign. A web search on SAE and ISO tyre axes (SAE J670 and ISO 8855:2011 are the authority) found sources that also *reverse the slip angle* in some conversions, and a 1996 SAE paper arguing that J670's slip-angle and inclination definitions are themselves loose. The definitions differ between documents, so the rule cannot be settled by reading prose. It is settled by **physical test cases**, written once and used as the oracle for both conventions:
1. A car moving forward whose velocity points to its right of the heading (slip to the right) gets a lateral tyre force to the **left** (restoring), whatever the axes.
2. A tyre driven with positive longitudinal slip (driving) gets a force in the **forward** direction on the car.
3. A cambered tyre with its top leaning to the right produces a lateral thrust to the **right** (camber thrust).
4. The aligning moment of case 1 turns the tyre **back toward** the direction of travel (restoring), and the rolling resistance moment opposes the rotation.
The evaluator is then written to satisfy these in each declared convention, and the conversion is accepted only when the same four cases give the same physical result in both.

## 4. Code that depends on the frame

**Tools (`tools/`, mirrored in `svj-py/svj/`)**
- `loop_solver.py` (and `loopsolver.py`): the bump residual `p[2] - ref_centre[2] + travel` assumes "bump lowers z" (line 257); camber and toe are computed with SAE axes (lines 340, 390); the side of a station comes from the sign of `centre[1]` (lines 346, 411). All three flip.
- `suspension_view.py` (and mirror), `migrate_suspension.py` (`UP = [0, 0, -1]`, line 48), `multiaxle_check.py` (comment), `constraints_check.py`, `collision_check.py`, `assemble.py`: each reads positions in the vehicle frame; check each for a hard-coded sign.
- `mesh_check.py`: `convention()` maps asset axes **to SAE J670**; `_to_sae`, the candidate list and the shift message ("SAE x, y, z") all assume it. They become "to the file's frame". The glTF/USD default (no declaration means SAE axes) changes.
- `gltf2usd.py`, `usd2gltf.py`: keep the asset's own axes; no change, but the docs mention SAE.
- `validate.py` / `validator.py`: the CG sign check; side checks.
- `engine_check.py`, `powertrain_check.py`, `tire_model.py`: no dependence on the vehicle frame (the tyre one is section 3).

**Viewer (`viewer/svj_viewer_v4.9.html`, 61 references)**
- `sae2three = p => (p[1], -p[2], -p[0])` and the matrix `SAE_TO_THREE`; for ISO the map is `(-y, z, -x)`. About 40 call sites use it unchanged once the function changes.
- The JavaScript ports of the loop solver and the tyre evaluator, the CG sanity warning (line 1014), the wheel-travel text and the "SAE axes" captions.
- Anything that adds lift or travel to Y/Z directly (the `liftRaised` code adds to three's Y, which stays up).

**Tests:** `test_vehicle.py` (4 references), `test_mesh_check.py` (8), `test_gltf2usd.py`, `test_usd2gltf.py`, the `legacy_*` fixtures, and every example-based test that depends on the numbers.

**Spec text mentioning SAE or Z-down:** §2.1 (the section itself), the note after it (Y signs), §7.1 inertia, spring and damper conventions (lines 960, 1004), alignment (1029-1042), aero (2193-2197), the glTF section (2810-2830, the "SAE J670 to Blender" transform), the USD section (2987), station sides (3018-3019), §26 solver text (3620 onward).

## 5. External converters (`D:\Claude\SVJson`)

Source files that mention the frame or a sign flip, out of all source files in the folder (counted by text search for `SAE`, `J670`, `z down`, `-z`, "negat... y/z"):

| Converter | Files that mention it |
|---|---|
| AC_to_SVJ | 21 of 80 |
| FH to svj | 19 of 57 |
| PC 2 to svj | 22 of 62 |
| race07 to svj | 16 of 49 |
| rbr to svj | 11 of 28 |
| rf to svj | 8 of 23 |
| SVJ to AC | 7 of 36 |
| beamng to svj | 5 of 8 |
| svj_analyze | 1 of 1 |
| SVJSim | 59 of 925 |
| gpl_to_svj, Project Cars converter, SVJ to ac EVO | none found (not all have source files in the folder) |

Most converters do their axis flips in a few helpers, so the real work is smaller than the counts suggest, but each needs reading. Converters from ISO sources (Chrono, BeamNG, OpenDRIVE-based data) get *simpler*: the rotation disappears.

## 6. Not covered by this scan

- Fields inside `x_` extension keys, other than the legacy pendulum fields found above.
- Prose-only conventions I could not find by search (anything defined by "left" or "right" in text without a sign).
- The 4x4 `x_transform` and asset `rotation` entries: these are about the *asset's* frame and probably need only the default flipped.
- The history of why SAE was chosen: not recorded anywhere in the repo.

## 7. Decisions (taken 2026-11-12)

1. **Origin:** unchanged, the front axle centre at ground level; only Y and Z flip. `CG.x` stays negative, every X value is unchanged.
2. **Tyre:** ISO is the default and the target; `axis_system` declares legacy SAE sets, which are converted at the interface or rewritten by the tool (section 3).
3. **Old files:** both. `_metadata.coordinate_system` declares the frame; loaders normalise to ISO on load; the same frame map drives the conversion tool.
4. **Version:** 0.109. ISO is the default for new files; an SAE file stays readable while it declares its frame, and the shipped examples and templates are converted to ISO, so nothing in the repository remains SAE.
5. **Camber (step 0 finding, decided 2026-11-12):** in both shipped sets a positive inclination angle gives a lateral force of the same sign as a positive slip angle, which physically means positive gamma behaves as leaning left. Decision: in ISO, positive gamma is the top of the wheel leaning RIGHT (positive rotation about X), and lean right pushes the tyre right (negative Y). The camber coefficients (pKy6/pKy7/pVy3/pVy4/pDy3, pHy3 for MF 5.2) of every shipped set are corrected in sign to match; the oracle test for camber changes from the recorded behaviour to this physical statement.

## 8. Proposed order of work, and how to know it is right

0. **The tyre sign oracle** (section 3): the four physical test cases, written first and run against the existing evaluator in its SAE form.
1. **One frame map** (a table of key paths and rules from sections 1 and 2) and `tools/convert_frame.py` that applies it in both directions, with a round-trip test: SAE to ISO to SAE must return the original file exactly.
2. **Physical invariants as tests**, run on every shipped file before and after the conversion: loop-solver results (camber, toe, gains, caster, kingpin inclination, scrub, trail), static weight distribution and wheelbase, the CG distance from the axles, the principal moments of inertia, `validate.py` warnings, tyre force at fixed physical inputs, mesh-check results with the asset conventions declared. Any difference is a sign error.
3. Spec §2.1 and the other text; schema (`coordinate_system` accepts both).
4. The tools and the Python package normalise on load; `loop_solver`, `mesh_check`, `migrate_suspension` updated.
5. The viewer.
6. Convert the examples and templates with the tool; regenerate the viewer demo.
7. The external converters, one at a time, each against its own sample.

The danger is silent sign errors, not crashes: a converted file still loads. Step 2 is the guard, and no step after it should start before the guard passes on every shipped file.
