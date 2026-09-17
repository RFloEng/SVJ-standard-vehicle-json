# Trailers, Coupling Points and Articulated Combinations — Research & Proposal

**Status:** Research complete, proposal draft (not yet in spec/schema). Target: SVJ v1.1 addendum "Vehicle Units & Couplings" (replaces spec §23.8 bullet 1).
**Date:** 2026-09-17

---

## 1. Where SVJ Stands Today

| Covered (v0.99.1) | Not covered |
|---|---|
| Trailers as standalone vehicles: `vehicle_class` `trailer`, `semi_trailer`, `modular_trailer`; any axle count, duals, couplings, lift axles | Where the coupling is (king-pin, drawbar eye, ball socket, fifth wheel, hitch jaw) |
| CG ahead of `A1` allowed for trailers (§23.1) | Coupling type, size and standard, so tools can check compatibility |
| Skeleton examples: 3-axle air semi-trailer, tandem leaf and torsion-axle trailers, 4-axle modular trailer | Coupling ratings (D, Dc, V, S, U) |
| | Joint freedoms and limits (articulation, pitch, roll), compliance, lash |
| | A file that joins units into a combination (tractor + semi, truck + drawbar trailer, A/B/C-doubles, dollies, ADT) |
| | Operating state (coupled or not, initial articulation angle, fifth-wheel slide position) |

**Answer to "does it define latching points?"** No. Today each unit is a separate file and nothing says where or how they join.

---

## 2. How Others Define It

### 2.1 ASAM OpenSCENARIO XML 1.3 — `TrailerHitch` / `TrailerCoupler`
- `TrailerHitch` sits on the towing vehicle; `TrailerCoupler` sits on the trailer.
- `dx` is required and gives the longitudinal position in the vehicle coordinate system. `dz` is optional; without it the joint is 2D (yaw in the XY plane only).
- Actions connect and disconnect trailers at runtime (`ConnectTrailerAction`, `DisconnectTrailerAction`).
- **Takeaway:** a joint is a point on each unit, and the combination is formed by pairing those points. Scenario tools need only x and z; SVJ should carry a full 3D position.

### 2.2 BeamNG JBeam — couplers
- The towing node has `couplerTag` (e.g. `"tow_hitch"`, `"fifthwheel_v2"`); the trailer node has a matching `tag`.
- `couplerStrength` (N) is the break force, and the lower of the two sides applies. Also `couplerRadius` (m, auto-attach capture distance), `couplerLock`, `couplerWeld` and `breakGroup`.
- `importElectrics` / `importInputs` pass signals such as lights and brakes across the joint.
- **Takeaway:** compatibility is a string tag, and strength is a number on each side. That maps cleanly onto the UN R55 class/size plus the D value.

### 2.3 TruckSim (Mechanical Simulation / Applied Intuition)
- Each trailer's front hitch point is located in the trailer sprung-mass frame (`H_H_FRONT` height). Global hitch coordinates are output per unit (`Xo_HF_i`, …).
- It has hitch types (ball/pintle/generic, fifth wheel), dolly screens and multi-unit combinations. Hitch compliance, lash and friction are properties of the joint.
- **Takeaway:** the joint has its own parameter set (stiffness, lash, friction, limits), separate from either vehicle. That supports a joint object in a combination file.

### 2.4 UN ECE Regulation 55 — mechanical coupling devices
Coupling classes, with the SVJ enum each maps to:

| Class | Device | SVJ `type` |
|---|---|---|
| A | 50 mm coupling ball + towing bracket | `ball` |
| B | Coupling head for 50 mm ball | `ball_socket` |
| C | Drawbar coupling (jaw), 40/50 mm pin | `drawbar_jaw` |
| D | Drawbar eye, 40/50 mm | `drawbar_eye` |
| E | Non-standard drawbar (incl. overrun device) | `drawbar` (body, §4.4) |
| F | Non-standard drawbeam | (mounting, not a point) |
| G | Fifth-wheel coupling, 50 / 90 mm king-pin | `fifth_wheel` |
| H | King-pin, 50 / 90 mm | `king_pin` |
| J | Fifth-wheel mounting plate | (mounting, not a point) |
| K | Hook coupling (pintle) | `hook` |
| L | Toroidal drawbar eye for class K | `toroidal_eye` |
| S | Special / heavy-transport devices | `custom` |
| T | Dedicated non-automatic matched pair | `custom` |

Characteristic values. R55 uses t and kN; SVJ stores N and kg.

| Value | Meaning | Formula (R55) |
|---|---|---|
| **D** | Horizontal reference force: ball, jaw, eye, drawbar trailers | D = g · T·R / (T+R) |
| **D** (fifth wheel) | Same, semi-trailer | D = g · 0.6·T·R / (T+R−U) |
| **Dc** | Centre-axle trailers | Dc = g · T·C / (T+C) |
| **V** | Vertical force amplitude, centre-axle trailer > 3.5 t | V = a · (X²/l²) · C, with X²/l² ≥ 1; a = 1.8 m/s² (air suspension on the towing vehicle) or 2.4 m/s² (other) |
| **S** | Static vertical mass on the coupling from a centre-axle trailer (kg) | — |
| **U** | Vertical mass on a fifth wheel from the semi-trailer (t) | — |

Here T = towing vehicle max mass (including U for a tractor), R = trailer max mass, C = centre-axle trailer axle load, X = length of the loading area, l = drawbar eye to axle-group centre distance.

### 2.5 ISO dimensional standards

| Standard | Content | SVJ use |
|---|---|---|
| ISO 1726-1/-2/-3 | Tractor ↔ semi-trailer interchangeability: coupling height, king-pin setting, swing radii, contact area; general cargo, low coupling, high volume | Default reference for fifth-wheel height and lead |
| ISO 3842 | Fifth wheel interchangeability (50 mm pin) | `standard` string |
| ISO 4086 | 90 mm (3.5 in) king-pin interchangeability | `standard` string |
| ISO 337 | 50 mm king-pin | `standard` string |
| ISO 8755 / ISO 1102 | 40 mm / 50 mm drawbar eyes | `standard` string |
| ISO 8718 | Drawbar coupling and eye strength tests | Ratings provenance |
| ISO 1103 | 50 mm coupling balls (caravans, light trailers) | `standard` string |
| SAE J133 / J2638 | North American fifth wheels / king-pins (2 in and 3.5 in) | `standard` string |

Common dimensions:

| Device | Diameter |
|---|---|
| King-pin | 50.8 mm (2 in) or 88.9 mm (3.5 in) |
| Coupling ball | 50 mm |
| Drawbar eye | 40 mm or 50 mm |

---

## 3. Design Principles

1. **Unit files stay self-contained.** A tractor file declares its fifth wheel and a semi-trailer file declares its king-pin, each in its own frame (origin = own `A1`, SAE J670). Neither file names the other.
2. **The combination is a separate file** (`*.svj-combination.json`), like override files (§3.4). It lists units by `$ref` and joins their coupling points.
3. **The joint's freedoms and compliance live on the combination's connection**, because a TruckSim-style joint belongs to the pair, not to one side. Each side can still declare its own limits, and the tighter one wins.
4. **Compatibility is checkable:** the type pair plus the size must match, the way BeamNG's `couplerTag`/`tag` works.
5. **Ratings follow UN R55** (D, Dc, V, S, U), converted to SI. A validator can compute the demanded D from unit masses and compare it with the rated D.
6. **Nothing breaks:** all fields are optional and additive, following the §23 pattern.

---

## 4. Proposed Schema — Vehicle Side: `coupling_points`

Optional top-level array on any vehicle file.

```json
"coupling_points": [
  {
    "id": "fifth_wheel",
    "role": "towing",
    "type": "fifth_wheel",
    "size": 0.0508,
    "standard": "ISO 3842",
    "approval_class": "UN R55 G50",
    "position": { "x": -4.035, "y": 0.0, "z": -1.15 },
    "position_reference": "king_pin_axis_at_plate_top",
    "slide": { "x_min": -4.235, "x_max": -3.835 },
    "oscillation": "semi_oscillating",
    "limits": { "pitch_min": -0.21, "pitch_max": 0.21, "roll_min": -0.05, "roll_max": 0.05 },
    "ratings": { "D": 150000, "U": 20000 },
    "mass": 210,
    "_source": "Fifth-wheel catalogue sheet"
  }
]
```

| Key | Type | Req | Description |
|---|---|---|---|
| `id` | string | YES | Unique in the file; referenced by combination connections |
| `role` | string | YES | `towing` (hitch on the pulling unit) or `towed` (king-pin or eye on the trailer). A dolly has both. |
| `type` | string | YES | `fifth_wheel`, `king_pin`, `ball`, `ball_socket`, `drawbar_jaw`, `drawbar_eye`, `hook`, `toroidal_eye`, `turntable`, `articulation_joint`, `custom` |
| `size` | number | no | Pin, ball or eye nominal diameter (m): 0.05, 0.0508, 0.0889, 0.04 |
| `standard` | string | no | Free text: `"ISO 1102"`, `"SAE J2638"` |
| `approval_class` | string | no | Free text: `"UN R55 D50-C"`, `"UN R55 G50"` |
| `position` | {x,y,z} | YES | Coupling point in the unit's own frame (m). Fifth wheel and king-pin: pin axis at the plate/skid contact plane. Ball: ball centre. Jaw/eye/hook: pin centre. |
| `position_reference` | string | no | Text naming the physical point used, when not the default above |
| `slide` | object | no | Sliding fifth wheel: `x_min`/`x_max` (m); `position` is the nominal setting |
| `oscillation` | string | no | `fixed`, `semi_oscillating` (pitch only), `fully_oscillating` (pitch + roll) |
| `limits` | object | no | Per-side freedom limits (rad): `yaw_min/max`, `pitch_min/max`, `roll_min/max` |
| `ratings` | object | no | `D`, `Dc`, `V` (N); `S`, `U` (kg). This is the device rating, not the vehicle's legal limit. |
| `mass` | number | no | Coupling device mass (kg), informational; already inside `mass_bodies` |
| `drawbar_ref` | string | no | `towed` eye on a drawbar trailer: id of a `drawbar` body (below) |
| `visual` | object | no | glTF binding (§v0.97), node `SVJ::coupling::<id>` |

**`drawbar` bodies.** A full drawbar trailer's drawbar is a moving body. It is declared in `mass_bodies` with `type: "drawbar"` plus:

| Key | Description |
|---|---|
| `pivot` | {x,y,z}, hinge on the trailer front |
| `pivot_axis` | `"y"` (pitch hinge) |
| `turntable_axle_ref` | e.g. `"A1"`, when the drawbar steers a turntable axle |
| `length` | Pivot to eye centre (m) |
| `eye_ref` | Id of the `drawbar_eye` coupling point |

A centre-axle trailer's drawbar is rigid, so it needs no extra body.

**Rules:**
- The semi-trailer CG stays ahead of `A1` (already allowed).
- A `towed` king-pin normally has `x > 0` in the trailer frame, and the checker warns if `x ≤ 0`.
- A `towing` fifth wheel normally lies between the first and last axle of the tractor.

---

## 5. Proposed Schema — Combination File: `*.svj-combination.json`

```json
{
  "_metadata": { "format": "svj-combination", "version": "1.1", "name": "6x4 tractor + 3-axle semi-trailer" },
  "units": [
    { "id": "tractor", "$ref": "skeleton_6x4_camelback_tractor.svj.json" },
    { "id": "semi",    "$ref": "skeleton_3axle_air_semi_trailer.svj.json",
      "override": "skeleton_3axle_air_semi_trailer_laden.svj-override.json" }
  ],
  "connections": [
    {
      "id": "c1",
      "towing": { "unit": "tractor", "point": "fifth_wheel" },
      "towed":  { "unit": "semi",    "point": "king_pin" },
      "joint": {
        "dof": ["yaw", "pitch"],
        "stiffness": { "roll": 2.5e6 },
        "damping":   { "roll": 1.0e4 },
        "lash": { "x": 0.0005 },
        "friction_torque": { "yaw": 800 },
        "limits": { "yaw_min": -1.57, "yaw_max": 1.57 }
      },
      "state": { "coupled": true, "articulation": { "yaw": 0.0 }, "slide_x": -4.035 }
    }
  ],
  "plated_masses": { "gcm_legal": 40000, "gcm_design": 44000 },
  "benchmarks": [ { "id": "offtracking_r12_5", "value": 0.0, "unit": "m", "type": "target" } ]
}
```

| Key | Description |
|---|---|
| `units[]` | `id`, `$ref` (relative path), optional `override` (§3.4) for the loaded or variant state |
| `connections[]` | `towing` / `towed` = {unit, point}. One towed point per connection. A unit may tow several connections (dolly, B-double). |
| `joint.dof` | Free rotations. Defaults by type pair: fifth wheel ↔ king-pin = yaw + pitch (fully oscillating adds roll); ball = yaw + pitch + roll; jaw/hook ↔ eye = yaw + pitch (+ limited roll); `articulation_joint` = yaw (+ roll on ADT oscillating joints) |
| `joint.stiffness` / `damping` | Per axis (N/m, N·m/rad, N·s/m, N·m·s/rad) for constrained axes that are modelled as compliant |
| `joint.lash` | Free play per translation axis (m) |
| `joint.friction_torque` | Per rotation axis (N·m); fifth-wheel plate friction goes on yaw |
| `joint.limits` | Combination-level limits, e.g. cab or trailer-front interference. Effective limit = tightest of the combination and both sides. |
| `state` | `coupled`, initial `articulation` (rad), `slide_x` for sliding fifth wheels |
| `plated_masses` | GCM (kg), design and legal |
| Positioning | Unit placement in the world follows from the coupling: the towed unit's point is placed on the towing unit's point. The first unit's frame is the combination frame. |

Articulated dump trucks, loaders and articulated buses are handled the same way. Front and rear frames are two units joined by `articulation_joint` points. A steering actuator on the joint is declared under `joint.actuator` (hydraulic cylinders: pivot points, bore, stroke), which reuses §8.6 vocabulary.

---

## 6. Validation Rules (proposed)

| # | Rule | Level |
|---|---|---|
| C1 | Every `$ref` resolves; unit ids are unique; every `connections[].point` exists with the right `role` | error |
| C2 | Type pairs are compatible: `fifth_wheel`↔`king_pin`, `ball`↔`ball_socket`, `drawbar_jaw`↔`drawbar_eye`, `hook`↔`toroidal_eye`, `turntable`↔`king_pin` (dolly), `articulation_joint`↔`articulation_joint`, `custom`↔any | error |
| C3 | `size` matches within 1 mm when both sides give it | error |
| C4 | Each towed point is used at most once; the combination graph is a tree rooted at the first unit | error |
| C5 | Demanded D (from unit plated masses and the R55 formula for the type pair) ≤ lowest rated D; same for Dc and V; U and S ≤ rated | warning |
| C6 | Coupling heights: \|z_towing − z_towed\| at the stated `state` ≤ 0.05 m, otherwise warn (unladen/laden override mismatch) | warning |
| C7 | Semi-trailer king-pin `x > 0`; fifth wheel between the tractor's first and last axle | warning |
| C8 | Swing clearance: tractor rear swing radius vs trailer front swing radius (ISO 1726) when both are given as `x_`-free fields `swing_radius_rear` / `swing_radius_front` | warning |

The C5 demanded values use the §4.4 formulas with T, R, C and U taken from the units' `plated_masses` / `axle_groups`:

```
fifth wheel:   D  = g · 0.6·T·R / (T + R − U)
drawbar:       D  = g · T·R / (T + R)
centre-axle:   Dc = g · T·C / (T + C);   V = a · max(1, X²/l²) · C
```

---

## 7. Worked Examples (numbers for the future example files)

| Combination | Inputs | Demanded | Typical device rating |
|---|---|---|---|
| 6x4 tractor + 3-axle semi | T = 26 t, R = 34 t, U = 18 t | **D = 123.9 kN** | 50 mm fifth wheel D ≈ 150 kN, U ≈ 20 t → OK |
| Rigid truck + full drawbar trailer | T = 18 t, R = 18 t | **D = 88.3 kN** | ISO 1102 jaw D ≈ 130 kN → OK |
| Rigid truck + centre-axle trailer | T = 18 t, C = 12 t, X = 7.3 m, l = 5.2 m, air suspension | **Dc = 70.6 kN, V = 42.6 kN** | Jaw Dc 90 kN, V 50 kN → OK |

Example files to add with the addendum:

1. **`skeleton_6x4_camelback_tractor` + `skeleton_3axle_air_semi_trailer`** — add `coupling_points` (fifth wheel / king-pin), plus `examples/combination_6x4_tractor_3axle_semi.svj-combination.json`.
2. **Tandem leaf trailer skeleton as a centre-axle trailer** behind a 2-axle rigid truck (jaw ↔ eye, Dc/V/S).
3. **Converter dolly (A-dolly)** — a unit with a `towed` drawbar eye and a `towing` fifth wheel, for an A-double.
4. **Tatra T815-7** — the data sheet gives a rear hitch 278 mm beyond the crane (`x_tatra_data_sheet.hitch_beyond_crane_mm`). The hitch x can be derived from the overall length and overhangs once the reference point is confirmed.
   - x ≈ −(6.65 + 1.20 + 0.278) = **−8.128 m**
   - Device type and height are not on the sheet, so it would be `_est`.

---

## 8. Tooling Impact

| Component | Change |
|---|---|
| `schema/svj.schema.json` | `coupling_points` array, `drawbar` body fields |
| `schema/svj-combination.schema.json` | New |
| `tools/combination_check.py` | Rules C1–C8; `tools/validate_combination.py` resolves units and overrides |
| `svj-py` | `Vehicle.coupling_points`, `Combination` class (units, connections, demanded D) |
| Viewer | Draw coupling points (fifth-wheel disc, king-pin, ball); later load a combination and place units by coupling at a yaw slider |
| Spec | New §24 "Vehicle Units & Couplings"; §23.8 bullet 1 points to it |

---

## 9. Open Questions

1. **Version:** ship as v0.99.2 (vehicle-side `coupling_points` only) and v1.1 (combination file)? Vehicle-side points are cheap and immediately useful for OpenSCENARIO and BeamNG export.
2. **Rating units:** R55 uses kN and t. SVJ rule is SI, so store N and kg, and let tools print kN/t.
3. **Operating state** (§23.8 bullet 2: lift axles raised, slide position) could share the combination `state` pattern, or use a per-vehicle `state` block.
4. **Electrical and pneumatic interfaces** (ISO 7638 ABS/EBS, ISO 12098 lighting, palm couplings) are not dynamics. Suggest `x_` or a later `interfaces` array, mirroring BeamNG `importElectrics`.

---

## Sources

- [UN ECE Regulation 55 (EUR-Lex OJ L 227, 2010)](https://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ%3AL%3A2010%3A227%3A0001%3A0061%3AEN%3APDF): classes A–T and D/Dc/V/S/U definitions
- [UNECE R55 Rev.2 (2015)](https://unece.org/fileadmin/DAM/trans/main/wp29/wp29regs/2015/r055r2e.pdf)
- [D-value (transport), Wikipedia](https://en.wikipedia.org/wiki/D-value_(transport))
- [VBG — UNECE Regulation 55, what does it say?](https://blog.vbg.eu/en/unece-regulation-55)
- ASAM OpenSCENARIO XML 1.3 model documentation — `TrailerHitch`, `TrailerCoupler`, trailer actions
- BeamNG documentation — JBeam couplers (`couplerTag`, `tag`, `couplerStrength`, `couplerRadius`, `couplerLock`, `couplerWeld`)
- [TruckSim New Features (Mechanical Simulation)](https://www.carsim.com/users/pdf/release_notes/trucksim/TruckSim_New_Features.pdf)
- ISO catalogue entries: ISO 1726-1/-2/-3, ISO 3842, ISO 4086, ISO 337, ISO 8755, ISO 1102, ISO 8718, ISO 1103
- [Wikipedia — Fifth-wheel coupling](https://en.wikipedia.org/wiki/Fifth-wheel_coupling)
