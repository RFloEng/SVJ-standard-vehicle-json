# Multi-Axle Suspension Arrangements — Catalogue & SVJ Mapping

## Document Information
- **Date:** 2026-09-16
- **Companion to:** `proposals/multi_axle_multi_wheel_research.md` (axle naming, `axles` array, dual wheels)
- **Target Specification:** post-v0.98 multi-axle addendum
- **Proposal Type:** Research — suspension taxonomy for trucks, trailers and special vehicles
- **Status:** Implemented in v0.99 (spec §9.2.1, §9.3, §23.5; schema; `tools/multiaxle_check.py`; 10 skeleton examples)

---

## 1. The key modelling insight

Every multi-axle suspension can be described at **two independent levels**:

1. **Axle location (per axle / per corner)** — how each wheel or axle is located and sprung relative to the chassis. This is what SVJ already models with `system_type`, `links`, `hardpoints`, `spring`, `damper`, `axle_body`.
2. **Inter-axle coupling (between axles)** — whether, and how, the load on one axle is influenced by another. This is the genuinely new thing trucks bring: rockers, walking beams, trunnion springs, shared air or hydraulic circuits.

A 3-axle air-ride trailer is 3 × level-1 with a pneumatic level-2 coupling. A Mack camelback is 2 × solid axles located by torque rods (level 1) plus a trunnion spring that *is* the coupling (level 2). A TAK-4 8×8 is 8 × double wishbones with no level-2 coupling at all.

Keeping these separate means the existing per-corner vocabulary survives almost unchanged, and all the new complexity lives in one new top-level array (`suspension_couplings`, §4.3).

---

## 2. Catalogue of arrangements

### 2.A — Independent axles (no inter-axle coupling)

Each axle behaves as if it were alone; multi-axle only means "more corners."

| Arrangement | Typical use | Axle location | Spring | SVJ today |
|---|---|---|---|---|
| **Trailing-arm air suspension** (one arm + air bag per side, per axle) | Semi-trailers (BPW, SAF), tag axles | Trailing arm to beam axle, axle clamped to arms | Air spring, shock | `trailing_arm` + `axle_body` + `spring.type: air` — **fits**, except arm clamps a beam axle (trailing arm *with* axle_body not documented as a combination) |
| **Rubber torsion axle** (Torflex-type) | Light/medium trailers, caravans | Short trailing arm per wheel, independent | Rubber cords in square tube, torsional | `trailing_arm` — **needs** `spring.type: rubber_torsion` |
| **Parallelogram lift axle** (steerable or fixed) | Tag/pusher axles on trucks | Parallel upper+lower beams (4-bar), axle stays upright through travel | Load air springs + separate **lift** air springs | **Missing** — needs `parallelogram` system_type and a lift mechanism |
| **Independent double wishbone on every axle** | Oshkosh TAK-4 (MTVR, M-ATV, JLTV, Striker 6×6/8×8 ARFF) | Unequal-length A-arms per wheel | Coil or hydropneumatic (TAK-4i) | `double_wishbone` — **fits**, just more corners |
| **Swing half-axles on a backbone tube** | Tatra 815/T815-7 (4×4 to 12×12) | Each half-axle pivots on the central tube, near the diff | Torsion bars / leaf / air bellows | **Missing** — no `swing_axle` system_type (also a gap for classic cars, e.g. VW Beetle rear) |
| **Portal axles** | Unimog, 6×6 conversions | Solid axle with hub reduction — wheel centre lower than axle tube | Coil | `solid_axle` — **needs** a portal drop/hub reduction attribute; not a new topology |
| **Six-wheel racing car** | Tyrrell P34 (4 small front wheels) | Double wishbone on each front axle | Coil | `double_wishbone` — **fits**; complexity is steering (twin-steer), not suspension |

### 2.B — Mechanically coupled tandems

Load sharing through a physical lever, beam or spring between axles. These dominate vocational trucks and leaf-sprung trailers.

| Arrangement | Typical use | How load is shared | Key geometry / parameters |
|---|---|---|---|
| **Leaf springs + equalizer (rocker)** | Tandem/triple leaf trailers; "four-spring" truck tandems | Adjacent spring ends hang from a rocker pivoting on a chassis hanger; one axle rising pushes the other down | Rocker pivot position, arm lengths (shape: straight / medium / tall triangle changes the load bias), shackle lengths, spring-end type (slipper vs double-eye) |
| **Walking beam** (rubber or leaf spring at centre) | Vocational trucks: dump, mixer, logging, refuse (e.g. Hendrickson HAULMAAX) | Axles bolted to the ends of a longitudinal beam that pivots at its centre; the spring sits between the beam saddle and the frame | Beam length (= axle spacing), centre pivot/saddle position, beam mass & pitch inertia, end bushings, spring stack; torque rods for lateral/longitudinal location |
| **Trunnion / inverted leaf ("camelback")** | Mack SS-series, heavy haul, road trains | One arched leaf pack per side pivots on a trunnion shaft between the axles; ends rest on axle seats; torque rods form a parallelogram so load stays shared under drive/brake torque | Trunnion position, spring pack rate, end seat positions, **slide friction at spring ends**, torque-rod geometry |
| **Six-rod trunnion with elastomer bushings** | Heavy vocational (e.g. TufTrac-type) | Same principle as trunnion, rubber-isolated joints | As above + bushing rates |
| **Shared leaf on swing half-axles** | Tatra tandem rear bogies | A longitudinal spring spans the two half-axles on each side, pivoted in between | Effectively a walking beam made of spring steel; same parameter set |
| **Compensated twin-steer front** | 8×4 tippers/mixers | Front leaf springs of axle 1 and 2 linked by a compensating lever | Same as equalizer rocker, between two steered axles |

**Engineering note (important for simulation fidelity):** mechanically coupled bogies are sensitive to **drive and brake torque reaction** — torque at the axle can unload one axle and load the other ("bogie hop" under traction/braking), which is exactly what torque rods in camelback and walking-beam designs are there to counteract. Measured equalisation also depends heavily on **friction at sliding spring ends**: the UK bogie study found steel-leaf bogies equalised poorly, and cutting slipper friction from μ≈0.4 to ≈0.08 visibly improved sharing. So a friction coefficient at slipper contacts is a first-class parameter, not a detail.

### 2.C — Fluid-coupled suspensions

| Arrangement | Typical use | How load is shared | Key parameters |
|---|---|---|---|
| **Interconnected air springs** (common levelling valve) | Tandem-drive tractors and air-ride trucks (e.g. Hendrickson PRIMAAX: trailing U-beam per axle, longitudinal + transverse torque rods, air springs, one height-control valve) | Air springs on both axles share a supply/levelling circuit, so static load equalises; dynamic sharing depends on line restriction | Which springs share a circuit, line/orifice restriction, levelling valve (height set point), per-spring effective area |
| **Hydraulic support groups** | Hydraulic modular trailers, SPMTs | Each axle line has a suspension cylinder; cylinders are plumbed into **3 or 4 groups**, giving a statically determinate 3-point (or 4-point) support for the load; axles also pendulum transversely | Group membership per cylinder, cylinder area and stroke, pendulum axle angle limit, all-wheel steering (up to ~50–60°) |
| **Hydropneumatic struts** | Mining haul trucks, Oshkosh LVSR rear, TAK-4i | Gas-over-oil strut per corner; may be cross-connected (roll/pitch interconnection) | Gas precharge volume & pressure, polytropic index, oil orifice damping, interconnection map |

Physically, 2.C is the fluid equivalent of 2.B: a circuit replaces the lever. Modelling them under the same coupling concept (§4.3) is deliberate.

### 2.D — Special / edge arrangements

| Arrangement | Typical use | Notes for SVJ |
|---|---|---|
| **Pendulum / oscillating axle** (beam pivoting about X on a central pin, often unsprung or cylinder-supported) | Modular trailer axle lines, articulated dump truck and loader axles | New `pendulum_axle` system_type: one longitudinal pivot, roll limit, optional cylinder |
| **Rocker-bogie** (passive, no springs, beams on differential pivots) | Planetary rovers, some robots | Same coupling concept as walking beam but with a chassis differential instead of springs — worth covering by the generic `rocker` coupling rather than a special case |
| **Articulated combinations** (tractor + semi-trailer, dollies, ADT centre joint) | Everywhere in trucking | **Out of scope for suspension.** These are multiple bodies joined by a fifth wheel / hitch / articulation joint. Needs a separate "vehicle units & couplings" addendum; flag, don't solve here |

---

## 3. What the catalogue tells us SVJ is missing

**New per-corner `system_type` values (level 1):**

- `swing_axle` — half-axle pivoting near the vehicle centreline (Tatra; classic cars too).
- `parallelogram` — 4-bar trailing linkage keeping axle orientation constant (lift axles, several air-ride designs).
- `pendulum_axle` — beam axle oscillating about a longitudinal pivot.
- Clarify that `trailing_arm` may locate an `axle_body` (trailer air suspension), rather than only an independent wheel.

**New `spring.type` values:**

- `rubber_torsion` (Torflex-type trailer axles)
- `rubber_block` / `rubber_shear` (walking-beam and bolster springs; highly progressive)
- `hydropneumatic` (needs gas precharge fields, see below)
- existing `leaf`, `air`, `torsion_bar`, `coil` cover the rest

**New attributes:**

- `axle_body.portal_drop` (m) and `hub_reduction_ratio` — portal axles.
- `spring.end_type`: `"eye"`, `"slipper"`, `"shackle"` + `end_friction` (μ) — matters a lot for leaf bogies.
- `hydropneumatic` block: `gas_precharge_pressure`, `gas_volume`, `polytropic_index`, `piston_area`.
- Lift axle: `lift_mechanism` (`air_lift_spring`, `none`) and `lift_travel` — static geometry only, lift *state* stays a runtime concern.

**New top-level concept (level 2):** `suspension_couplings` — described next.

---

## 4. Proposed shape: `suspension_couplings`

Replaces the narrower `bogies` sketch in the companion doc, since walking beams are just one of six coupling families.

### 4.1 Design rules

- Couplings are **optional**. No coupling = axles are independent (§2.A), which is also how every current 2-axle SVJ file already behaves.
- A coupling references existing elements by id (`axle_ref`, `corner_ref`, `spring_ref`), so per-corner data is never duplicated.
- One `type` enum, type-specific fields, `additionalProperties: true` like the rest of SVJ.
- Side matters: mechanical bogies are usually **per side** (`"side": "L"` / `"R"`), fluid circuits are often cross-vehicle.

### 4.2 Types

| `type` | Covers (§2) |
|---|---|
| `equalizer_rocker` | Leaf + rocker trailers, four-spring tandems, compensated twin-steer |
| `walking_beam` | Rubber/leaf walking beams, Tatra shared leaf, rocker-bogie |
| `trunnion_spring` | Camelback, six-rod trunnion |
| `pneumatic_circuit` | Interconnected air springs / shared levelling valve |
| `hydraulic_circuit` | Modular trailer support groups, hydropneumatic interconnection |
| `custom` | Anything else, described with `x_` keys |

### 4.3 Field sketches

```json
"suspension_couplings": [
  {
    "id": "rear_bogie_L",
    "type": "walking_beam",
    "side": "L",
    "axle_refs": ["A2", "A3"],
    "pivot_position": [-4.85, -0.52, -0.45],
    "beam_length": 1.37,
    "beam_mass": 95,
    "beam_pitch_inertia": 18.0,
    "centre_spring": { "type": "rubber_block", "rate_curve": [[0.0, 0], [0.05, 60000], [0.08, 140000]] },
    "end_bushings": { "rate_z": 1.5e7, "rate_x": 4.0e6 },
    "pivot_type": "floating"
  },
  {
    "id": "trailer_rocker_L",
    "type": "equalizer_rocker",
    "side": "L",
    "spring_refs": ["A2L.spring", "A3L.spring"],
    "pivot_position": [-6.10, -0.60, -0.30],
    "arm_front": 0.12,
    "arm_rear": 0.12,
    "rocker_shape": "medium_triangle",
    "shackle_length": 0.09
  },
  {
    "id": "camelback_R",
    "type": "trunnion_spring",
    "side": "R",
    "axle_refs": ["A2", "A3"],
    "trunnion_position": [-4.85, 0.55, -0.55],
    "spring": { "type": "leaf", "rate": 1.2e6, "end_type": "slipper", "end_friction": 0.35 },
    "torque_rod_refs": ["A2R.links.upper_torque_rod", "A3R.links.upper_torque_rod"]
  },
  {
    "id": "drive_air_circuit",
    "type": "pneumatic_circuit",
    "spring_refs": ["A2L.spring", "A2R.spring", "A3L.spring", "A3R.spring"],
    "levelling_valves": 1,
    "line_restriction": "orifice_4mm",
    "ride_height_setpoint": 0.25
  },
  {
    "id": "spmt_group_1",
    "type": "hydraulic_circuit",
    "support_scheme": "3_point",
    "group": 1,
    "cylinder_refs": ["A1L.spring", "A1R.spring", "A2L.spring", "A2R.spring"],
    "accumulator": null
  }
]
```

Notes on the sketch:

- `pivot_type: "floating"` vs `"fixed"` exists because newer walking beams deliberately drop the fixed centre bushing to reduce wheel hop — the kinematics differ.
- `rocker_shape` is informational; the authoritative geometry is pivot + arm lengths + shackle length (same "explicit overrides derived" rule used elsewhere in SVJ).
- For a truly accurate trunnion or walking beam, the *reaction path* of drive/brake torque is set by the torque rods, which are ordinary `links` on the axle corners — the coupling just references them. No separate torque model needed in the format.

---

## 5. Reference vehicles to prove the proposal

| Example | Exercises |
|---|---|
| 3-axle semi-trailer, trailing-arm air, one lift axle | `trailing_arm` + `axle_body`, `pneumatic_circuit`, lift axle, dual wheels |
| 6×4 dump truck, walking-beam rear, parallelogram pusher | `walking_beam`, `rubber_block`, `parallelogram`, torque rods |
| Tandem leaf trailer with equalizers | `equalizer_rocker`, `slipper` spring ends + friction |
| Mack-style camelback tractor | `trunnion_spring`, torque rods |
| Tatra 815 8×8 | `swing_axle`, twin-steer, shared leaf on rear bogies |
| Oshkosh-style 6×6 independent | `double_wishbone` ×6, no couplings — proves "independent" needs nothing new |

---

## 6. Open questions / needs more research

- **Reactive vs non-reactive bogies**: quantifying torque-induced load transfer needs either explicit torque-rod geometry (already expressible) or a simplified `torque_reaction_coefficient` for low-fidelity consumers (the AC-style Tier 2 idea). Decide whether a Tier-2 scalar is worth it.
- **Leaf spring modelling depth**: SVJ's `leaf` is a rate + curve today. Bogies make inter-leaf friction/hysteresis matter; a `hysteresis` or `interleaf_friction` field may be needed. Probably Tier 3 only.
- **Hydraulic group topology**: 3-point vs 4-point support is well defined, but real modular trailers let operators re-plumb groups — static file vs configuration; lean towards one file = one configuration (overrides §3.4 can express alternatives).
- **Vehicle combinations** (tractor/trailer/dolly/ADT) are a separate addendum — flagged, not solved.
- Real published data for at least one example vehicle (hardpoints, spring rates) before calling any of this final; current sources are manufacturer brochures and general references, fine for taxonomy, not for numbers.

---

## Sources

- [Tandem axle truck/trailer suspension types — Which truck suspension meets your construction needs (For Construction Pros)](https://www.forconstructionpros.com/trucks/trucks-accessories/heavy-trucks-class-7-8/article/21563288/which-truck-suspension-meets-your-construction-truck-needs)
- [Equalisation of truck bogie axle weights — HVTT Forum (Simmons)](https://hvttforum.org/wp-content/uploads/2019/11/THE-EQUALISATION-OF-TRUCK-BOGIE-AXLE-WEIGHTS-Simmons-.pdf)
- [Trailer suspension equalizer link action — Mechanical Elements](https://mechanicalelements.com/suspension-equalizer-link-action/)
- [Trailer axle types — Mechanical Elements](https://mechanicalelements.com/trailer-axle-types-choosing-the-right-suspension/)
- [Hendrickson HAULMAAX EX](https://micro.hendrickson-intl.com/HMX/index.html)
- [Hendrickson PRIMAAX EX maintenance manual](https://www.hendrickson-intl.com/getattachment/9510ede8-522d-41ca-93da-2055a942bf2e/97117-212_PRIMAAX-EX-Preventative-Maintenance_Rev-B.pdf)
- [Hendrickson truck lift axle suspensions (H769)](https://www.hendrickson-intl.com/getattachment/6edd055f-0e0f-4425-b267-bca151183234/H769.pdf)
- [Link Mfg — Lift axle spec'ing 101](https://www.linkmfg.com/blog/lift-axle-specing-101)
- [How a Mack Camelback suspension works — Australian Roadtrains](https://www.roadtrains.com.au/tech-tips/how-a-mack-camelback-suspension-works/)
- [Oshkosh TAK-4 independent suspension — Wikipedia](https://en.wikipedia.org/wiki/Oshkosh_TAK-4_Independent_Suspension_System)
- [Tatra 815 — HandWiki](https://handwiki.org/wiki/Engineering:Tatra_815)
- [Hydraulic modular trailer — Wikipedia](https://en.wikipedia.org/wiki/Hydraulic_modular_trailer)
- [Hydraulic modular trailer specs & designs — Anster Trailer](https://anstertrailer.com/hydraulic-modular-trailer-specs-designs/)
- [Equalising beam — Wikipedia](https://en.wikipedia.org/wiki/Equalising_beam)
- [Tandem twin axle bogie vs uncompensated — MechGuru](https://mechguru.com/how-it-works/how-tandem-twin-axle-bogie-suspension-system-heavy-duty-truck-works/)

---

## Implementation notes (v0.99)

Implemented as proposed, with these refinements:

- Coupling reference: corners point to a coupling with `spring.coupling_ref`; stations sprung only by the coupling use `spring.type: "none"`.
- Leaf spring ends are split into `end_type_front` / `end_type_rear` (one leaf has two different ends, e.g. eye + slipper).
- Rocker `connections[]` name the `spring_end` (`front`/`rear`) instead of `spring_refs`.
- Added `hydraulic` spring type (fluid column without gas) next to `hydropneumatic`, and damper types `hydraulic_strut` / `none`.
- Added link types `torque_rod` and `pivot`, `lateral_location` values `torque_rods` and `pendulum_pin`.
- Added a centreline station side `C` (trikes, special rigs) beyond the original L/R plan.
- Truck tyre `size_code` pattern widened — the old pattern rejected every 22.5" truck size.
- Not implemented (unchanged from §6): Tier-2 torque-reaction scalar, inter-leaf hysteresis beyond a single `hysteresis_force`, articulated combinations.
