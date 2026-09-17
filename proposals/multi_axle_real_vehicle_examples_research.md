# Real-World Multi-Axle Examples — Source Research

## Document Information
- **Date:** 2026-09-16
- **Target Specification:** SVJ v0.99
- **Proposal Type:** Research — candidate real vehicles for `examples/`
- **Status:** In progress — §4 patches landed in v0.99.1; A1 built as `examples/man_tgs_32_430_8x4_twin_steer_tipper.svj.json`, A2 as `examples/man_tgs_36_430_8x4_4_tridem_lift_tag.svj.json`, A3 as `examples/oshkosh_hemtt_a4_m977a4_8x8.svj.json`; Tatra built as `examples/tatra_t815_7_8x8_swing_axle.svj.json` from the T815-7N0R99 data sheet (axle spacings 1950 / 3250 / 1450 mm), source https://mzv.gov.cz/file/612403/Tatra_8x8_specs_7N0R99.pdf

---

## 1. Goal and rules

The ten v0.99 multi-axle examples are skeletons with estimated numbers. A real-vehicle example should carry **published** data wherever it exists and mark everything else as an estimate, exactly like the existing car examples (`_source`, `_est`, `data_origin`).

Rules used for this shortlist:

- **Facts only from manufacturer sheets** (dimensions, axle loads, tyre sizes, suspension type). Numbers are facts and can be restated with a source link; drawings, photos and brochure text are not copied into the repo.
- **Axle geometry must be derivable.** Without published axle-to-axle distances a multi-axle example is mostly guesswork, so this is the deciding criterion.
- **Everything not published is `_est: true`**: hardpoints, CG height, spring/damper rates, inertias.

## 2. Key finding: axle spacings live in dimension drawings

Most spec sheets list wheelbase, weights and tyres in text but give individual axle distances only as labelled drawings. The best sources are UK body-builder chassis sheets (MAN) which have both a labelled side view and a dimension table. Where a sheet has an unlabelled but to-scale drawing (Oshkosh), spacings can be measured against the published wheelbase and recorded as estimates.

## 3. Shortlist

### Tier A — buildable now (explicit or measurable axle geometry)

#### A1. MAN TGS 32.400–32.510 8x4 BB CH — twin-steer tipper chassis

| Item | Published value |
|---|---|
| Axles | A1 + A2 steered (drop beam), A3 + A4 driven (cross-axle and inter-axle diff locks) |
| L3 — A1→A2 (front axle spread) | 1795 mm (WB 3205) / 1759 mm (WB 3505) |
| L1 — A2→A3 ("wheelbase") | 3205 / 3505 mm |
| L2 — A3→A4 (rear bogie spread) | 1400 mm |
| Overhangs front / rear | 1475 / 800 mm |
| Width across rear tyres | 2462 mm |
| Frame height at rear wheel centre | 966 laden / 1046 unladen mm |
| Tyres | 295/80R22.5 steer and drive |
| Suspension | 3-leaf parabolic springs + dampers + stabiliser, both steer axles and the rear bogie |
| Unladen weights | front axles 6359 / rear axles 3073 kg (WB 3205) |
| Plated weights | GVW 34000 design / 32000 UK; front axles 14200; rear bogie 21000 design / 19000 UK |
| Turning circle | 20.1 m kerb-to-kerb (WB 3205) |
| Driveline | 12-speed TipMatic, axle ratio 3.70:1 |

**Estimated:** hardpoints, leaf rates, CG height, twin-steer ratio (typical ≈0.75–0.8), rear bogie spring arrangement (leaf with or without rocker is not stated).
**Exercises:** A-notation, twin steer (`steering.additional_axles` `mechanical_link`), leaf springs on all axles, dual rear wheels, inter-axle differential.
Source: [MAN TGS 8x4 Normal Height Tipper chassis specification (May 2022)](https://www.man-bodybuilder.co.uk/specs/pdf/2022/TGS/8x4-Normal-Height-Tipper.pdf)

#### A2. MAN TGS 36.430–36.510 8x4-4 BL CH — tridem with steered lift tag axle

| Item | Published value |
|---|---|
| Axles | A1 steered (drop beam); A2 + A3 driven; A4 rear axle listed as "Rear Lift / Steering" |
| L1 — A1→A2 | 3600 / 3900 / 4200 mm |
| L3 — A2→A3 ("front bogie spread") | 1350 / 1350 / 1450 mm |
| L2 — A3→A4 ("rear bogie spread") | 1450 mm |
| Overhangs front / rear | 1475 / 2000 mm |
| Width across rear tyres | 2470 mm |
| Frame height at rear wheel centre | 981 laden / 1011 unladen mm |
| Tyres | 385/65R22.5 front, 315/80R22.5 rear |
| Suspension | Front: parabolic leaf + dampers + stabiliser; rear: air suspension with dampers and stabiliser |
| Unladen weights | front 4853 / rear 5005 kg (WB 3600) |
| Plated weights | GVW 32000; GTW 44000; front 9000; rear 27000 design / 24000 UK |
| Turning circle | 17.0 m kerb-to-kerb (WB 3600) |

**Estimated:** tag-axle steering type, ratio and lock-out speed; lift travel; hardpoints; air spring data; CG. Single tyres on the tag axle follow MAN's "-4" suffix (steered trailing axle, single tyres); the sheet lists only one rear tyre size, 315/80R22.5.
**Exercises:** lift axle (`axles[].lift`, placement `tag`), steered tag axle, air-sprung tridem on a `pneumatic_circuit`, mixed tyre sizes.
Source: [MAN TGS 8x4 Tridem chassis specification (May 2022)](https://www.man-bodybuilder.co.uk/specs/pdf/2022/TGS/8x4-Tridem.pdf)

#### A3. Oshkosh HEMTT A4 M977A4 — 8x8 tactical cargo truck

| Item | Published value |
|---|---|
| Axles | 8x8, power-assisted steering on the front tandem |
| Wheelbase | 210 in (5334 mm) |
| Track | 79 in (2007 mm) |
| Length / width / height | 10389 / 2438 / 2997 mm |
| Curb weight / GVWR | 18943 kg / 29030 kg (32885 kg armoured) |
| Tyres | 16.00R20 Michelin XZL, 8 + spare |
| Suspension | Air ride with 4 height control valves — front NEWAY ADS-240, rear NEWAY AD-246 |
| Axles | Front Oshkosh 46K; rear Dana DS480 |
| Powertrain | Caterpillar C15 500 hp; Allison 4500SP 5-speed; Oshkosh 55000 2-speed transfer case |

**Measured from the to-scale side view (estimates, about ±30 mm):** front tandem spread ≈1525 mm, rear tandem spread ≈1490 mm. Scale check: with the drawing scaled to the 5334 mm bogie-centre wheelbase, its overall length measures 10383 mm against the published 10389 mm (0.06 %). The published 5334 mm wheelbase is reproduced exactly when it is measured from front tandem centre to rear tandem centre (A1→A3 is also ≈5350 mm because both spreads are nearly equal).
**Exercises:** 8x8, twin steer, four air circuits (`pneumatic_circuit` with 4 levelling valves), wheelbase measured between bogie centres.
Sources: [Oshkosh Defense HEMTT A4 M977A4 product sheet (2015)](https://oshkoshdefense.com/wp-content/uploads/2018/12/17311_HEMTT-A4-Cargo_LowRes_4.29.2015.pdf), [GlobalSecurity HEMTT specifications](https://www.globalsecurity.org/military/systems/ground/hmett-specs.htm)

### Tier B — promising, axle spacings still missing

| Vehicle | Published so far | Missing | Sources |
|---|---|---|---|
| **Tatra T815-7T3RC1 8x8** (swing half-axles) | Track 2072 mm; ground clearance 400 mm (+90/−125 adjustable); curb 14300 kg; GVW 38000 kg; tyres 16.00R20 with CTIS; front steered + driven and rear driven swinging half-axles, **air springs**, dampers, sway bars; hub reductions; V8 12.7 l 300 kW / 2100 Nm; turning circle 23 ± 1 m | Axle spacings and axle loads are in the data sheet drawing, which could not be downloaded from this session | [Tatra Force T815-7T3RC1 8x8 data sheet](https://www.tatratrucks.com/underwood/download/files/tatra-force-t815-7t3rc1-8x8-chassis-double-cab_en.pdf), [Tatra 815-7 (Wikipedia)](https://en.wikipedia.org/wiki/Tatra_815-7) |
| **Mack Granite 10x4 dump** (104FR / 104BR) | WB 262 in / 238 in; front FXL18/FXL20 taperleaf; rear S440 + **SS44 camelback** (104FR) or S462R + mRIDE 46 (104BR); 2 × Hendrickson 13k COMPOSILITE steerable pushers; tyres 315/80R22.5 or 425/65R22.5 front, 11R22.5 rear | Axle spacings, pusher positions | [Mack Granite dealer spec sheet](https://s18391.pcdn.co/wp-content/uploads/2022/09/Mack-Granite-Specs.pdf) |
| **Volvo FH13 8x4 pusher tridem** | WB 4300–5600 mm with theoretical WB 4428–5728; kerb front / bogie per WB (e.g. 5020 / 4755 kg at 4300); plated front 8000 / bogie 24000 kg; 315/80R22.5 all axles; parabolic front, rear air (1 pusher + 2 driven), electro-hydraulically steered pusher | Individual axle distances (drawing only) | [Volvo FH 8x4 rigid pusher tridem](https://stpi.it.volvo.com/STPIFiles/Volvo/ModelRange/fh84rp3a_gbr_eng.pdf) |
| **Tyrrell P34** (6-wheel F1, 1976–77) | WB 2453 mm; tracks 1234 front / 1473 rear; 595 kg (1976) / 620 kg (1977); double wishbones with coil-over dampers and anti-roll bars front and rear; four 10 in front wheels; Cosworth DFV | Spacing between the two front axles; tyre sizes | [Tyrrell P34 (Wikipedia)](https://en.wikipedia.org/wiki/Tyrrell_P34), [F1technical](https://www.f1technical.net/f1db/cars/367/tyrrell-p34) |
| **Mercedes-AMG G 63 6x6** | WB 4196 mm (front to rearmost axle); 5875 × 2110 × 2210 mm; curb 4083 kg; ground clearance 460 mm; 37 in tyres on 18 in beadlocks; portal axles; 5.5 l V8 | Track, A2–A3 spacing, spring data | [Mercedes-AMG G 63 6x6 (Wikipedia)](https://en.wikipedia.org/wiki/Mercedes-AMG_G_63_6x6) |
| **Mercedes-Benz Arocs 8x4 / 8x8** | Ranges only: 8x4 WB 4250–7550 mm, front axles 2 × 6.3–10.0 t, rear 2 × 9.0–13.0 t; 8x8 WB 4850–7550 mm, ground clearance 312 mm | Any single-configuration geometry | [Arocs defence technical data](https://defence.mercedes-benz-trucks.com/fileadmin/Defence/Downloads/D_Technische-Daten_Arocs_ENG_screen.pdf) |

### Tier C — not viable yet

| Vehicle | Why |
|---|---|
| Goldhofer THP/SL modular trailer | Public web data gives only axle load 45 t and loading height 1175 mm; the full tables are images in the brochure |
| Schmitz Cargobull S.KO COOL semi-trailer | Product pages give body dimensions and "ROTOS running gear with MRH air suspension", no chassis numbers |
| Morgan Super 3 (trike, `A2C`) | Sources found lack wheelbase, track and tyre sizes |

## 4. Spec gaps these vehicles expose

1. **Wheelbase definitions differ by maker.** MAN's L1 is A2→A3 on the twin-steer chassis but A1→A2 on the tridem; Volvo publishes a nominal and a "theoretical" wheelbase; Oshkosh measures between bogie centres. SVJ v0.99 only offers `last_axle` or `bogie_centre` (A1 to rear bogie centre). Proposed patch: extend `chassis.wheelbase_reference` with `"bogie_centres"` (front group centre to rear group centre), `"first_rear_axle"` (last front axle to first rear axle) and `"theoretical"`, and state that `axles[].position_x` is authoritative whenever present.
2. **Loads are published per axle group, not per axle.** Examples: "front axles 14200 kg", "rear bogie 21000 kg", kerb weight "front axle 6359 / rear axle 3073". SVJ has `axles[].max_load` per axle only. Proposed patch: an optional `axle_groups` array (`id`, `axle_refs`, `max_load_design`, `max_load_legal`, `kerb_load`), so published group figures can be stored without inventing a per-axle split.
3. **Design vs legal plated weights** (MAN: GVW 34000 design / 32000 UK legal). This is the same need as item 2; `max_load_design` / `max_load_legal` covers it.

## 5. Recommended build order

1. **MAN TGS 8x4 BB twin-steer tipper**: most complete published geometry and weights; all leaf springs; twin steer.
2. **MAN TGS 8x4-4 BL tridem**: same data quality; adds air suspension and a steered lift tag axle.
3. **Oshkosh HEMTT A4**: 8x8 with bogie-centre wheelbase; spacings marked as measured estimates.
4. **Tatra T815-7 8x8**: once the data sheet drawing (axle spacings) is available, it is the real counterpart of the swing-axle skeleton.

Patch items 1–2 of §4 should land before or alongside the first two examples, since both MAN sheets publish group loads and a non-standard wheelbase definition.
