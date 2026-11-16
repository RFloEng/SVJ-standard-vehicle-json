# SVJ response to the simulator team proposals (S1 to S16)

Reply to `proposals_svj.md`. Everything below is in spec and schema **v0.111** and in the MX-5 template at that version. Run `python tools/validate.py templates/mazda_mx5_nd2_2024.svj.json` and `python tools/reference_check.py <file>` to see the checks.

| # | Title | Status |
|---|---|---|
| S1 | One force law for springs | resolved |
| S2 | Reference pose | resolved |
| S3 | Consistent mass properties | resolved |
| S4 | Engine braking | resolved (data estimated) |
| S5 | Clutch, driveline inertias, driver limits | open |
| S6 | Brake bias | resolved (hardware figures not verified) |
| S7 | Tyre class and reference surface | open (needs STJ) |
| S8 | Bushing data | resolved |
| S9 | LSD semantics | resolved |
| S10 | Sign conventions | resolved |
| S11 | Aero pitching moment | resolved |
| S12 | Rolling resistance | resolved (data estimated) |
| S13 | Derived values against geometry | open |
| S14 | Validator as a library | open |
| S15 | Tool fixes | open |
| S16 | Example and template data | open |

## S1 spring law: resolved
- Spec 24.5: `F = preload + rate * (L_ref - L)`. `preload` is the force at the reference pose, `L_ref` the mount-to-mount length there. `free_length` is informative (the coil's own length), `installed_length` is derived.
- Validator: warns on a negative preload of a compression spring.
- MX-5: preloads are recomputed so each corner carries its sprung weight through the motion ratio from the loop solver (0.805 front, 0.661 rear): 2958 N front, 3198 N rear. The adjustment ranges and the `road` and `track` setups were rescaled to match.

## S2 reference pose: resolved
- New `reference_pose { condition: static_equilibrium | unloaded | other, load_case: kerb | kerb_plus_driver | gvw }` (7.4).
- With `static_equilibrium` the checker verifies, by virtual work through the solved geometry, that the springs balance the corner loads per axle (20 % tolerance).
- MX-5: `static_equilibrium`, `kerb_plus_driver`, because `mass_total` includes the 75 kg driver body.

## S3 mass properties: resolved
- Spec 7.2.3 and 7.4: the chassis remainder (composite minus the listed bodies) must be physical: mass >= 0, centre inside the vehicle, inertia positive definite and obeying the triangle inequality. Inertia is required on every body with mass from v0.111 (an error). `mass_unsprung_per_corner` is derived and checked against the corner bodies.
- MX-5: the body shell now carries the remainder (410 kg, position solved from the declared CG), so the listed bodies add up to `mass_total`. The rack has its mass and inertia. The bodies without inertia got a slender-rod estimate between their joints (marked estimated). Chassis inertia is recomputed from the bodies: Ixx 320.7, Iyy 1076.6, Izz 1170.6 kg m2.
- The checker also reports listed bodies heavier than `mass_total`.

## S4 engine braking: resolved, values estimated
- The MX-5 has `torque_curve_closed` from your law: FMEP = 0.8 bar + 0.35 bar per 1000 rpm, `T = -Vd * FMEP / (4 pi)`. This is your default, not measured data, and is marked as such.
- Not done: `engine.inertia_block` (it belongs with S5).

## S5 clutch and driveline: open
- Needs new spec fields (`torque_capacity`, `engagement_point_basis`, driveline inertias, shift time, pedal force limit). Not started. The values in your proposal are the starting set; tell us if any should change before the fields are written.

## S6 brake bias: resolved, hardware not verified
- Spec 12.6: the hydraulic chain decides the front share. Optional `brakes.proportioning` (`none | fixed_ratio | knee`). `bias` is informative; a difference above 0.02 gives a warning.
- MX-5: `bias` is now 0.581, the share the chain gives.
- Not verified: the caliper areas (25 / 18 cm2) and the booster figures. The MX-5 hardware may still be over-strong, as you found; that is a data question we have not resolved.

## S7 tyre class and reference surface: open
- Must be agreed with STJ first: one list of class names and the reference-surface reference form. Nothing was changed.

## S8 bushings: resolved
- Spec 24.4: default axes are the joint frame, else the vehicle frame. An absent rate is rigid where the joint type constrains and free elsewhere. The checker warns when static corner load over the lowest rate asks for more than 10 mm.
- MX-5: translational rates raised x100. The old rates were estimates and so are the new ones.

## S9 LSD: resolved
- Spec 10.8: `T_lock = preload + lock * |T_in|`, with the power or coast factor chosen by the sign of the input torque. The ramp angles are informative and the lock factors win.

## S10 signs and positions: resolved
- Wheel spin: the hinge +Z points left, so a positive coordinate rolls the wheel forward (24.4). From v0.111 the checker warns on the opposite sense. The MX-5 hinges were reversed; the 0.7 degree camber tilt is kept.
- Dampers: velocity is positive in extension, the rebound curve applies for v > 0, both curves give positive magnitudes (24.5.1).
- Positions: gearbox, output flange and propshaft x were mirrored and are fixed. The centre of pressure was a copy of the gearbox position; it is now at the wheelbase midpoint, 0.45 m high (estimated).

## S11 aero pitch: resolved
- Spec 13.3: `Cl_front` / `Cl_rear` win over `Cl` + `Cpm`; `cpm_reference` defaults to the wheelbase midpoint; the implied `Cpm = (Cl_front - Cl_rear) / 2` is checked.
- MX-5: `Cpm` set to the derived value.

## S12 rolling resistance: resolved, values estimated
- The standard already has the Magic Formula group (`pacejka.rolling_resistance`, `qsy1..qsy8`, spec 11); the top-level `{k0,k1,k2}` was never defined. The MX-5 sets now use `qsy1 = 0.010`, `qsy4 = 0.0004`: generic road-tyre figures, not measured. The old block is kept as `x_rolling_resistance_legacy`.

## S13 derived values against geometry: open
- Not implemented. The steering ratio against the solved geometry is already checked (10 %); the spring motion ratios in `x_converted_from_wheel_rate` against the loop solver are not. The new preloads use the solver's motion ratios, not the old 0.9 / 0.85.

## S14 to S16 tooling and data: open
- Not started: the validator callable and the module-name clash, the `tire_model.py` fixes, the E30 override and semi-trailing-arm joint, and loop closure on the De Dion and torsion-beam cars. The library `svj.validator` in `svj-py` already returns errors and warnings; `tools/validate.py` still prints.

## MX-5 values that are estimates, not data
Closed-throttle curve, `qsy1`, `qsy4`, centre of pressure, rod inertias, body-shell position, bushing rates, spring preloads (computed from the geometry and the mass), `Cpm` (derived), chassis inertia (computed from estimated body inertias).
