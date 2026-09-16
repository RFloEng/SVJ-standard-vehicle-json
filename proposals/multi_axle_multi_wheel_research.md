# Multi-Axle & Multi-Wheel-Per-Side — Research Notes

## Document Information
- **Date:** 2026-09-16
- **Target Specification:** SVJ v0.98 → future (likely v0.99/v1.0-track — see §6)
- **Proposal Type:** Research / gap analysis (no schema changes yet)
- **Status:** Implemented in v0.99 (spec §23) — see `multi_axle_suspension_types.md` for the coupling model that replaced the `bogies` sketch

---

## 1. Goal

Extend SVJ to describe trucks and special arrangements that don't fit the 4-corner passenger-car model:

- **Multi-axle**: 3+ axles along the vehicle (straight trucks, tandem-axle trailers, 6-wheel exotics like the Tyrrell P34).
- **Multi-wheel-per-side**: more than one tire at a single axle end (dually/twin rear wheels on pickups and semi tractors, trailer bogies).

These are two **independent** axes of variation — a vehicle can have extra axles with single wheels (a 3-axle motorhome), a single rear axle with dual wheels (a 1-ton dually pickup), or both (a 6x4 tractor unit: 2 rear axles, dual wheels on each).

## 2. What's actually there today — audit

### 2.1 A discrepancy worth flagging first

`spec/SVJ_Spec.md`'s own changelog (line ~2153) claims:

> `0.94` — **Multi-axle naming convention** (§21.1): formalized `A{n}{side}` corner naming (A1L, A2R, ...). FL/FR/RL/RR are aliases for A1L/A1R/A2L/A2R. Axle metadata array with `steered`, `driven`, `lift` flags. Multi-axle steering linkage with per-axle ratio and phase. Tyrrell P34 example.

`SVJ_PROJECT_BRIEF.md` repeats this: "Multi-axle addendum implementation (currently documented in §21.1, not in schema)."

**Neither is actually true of the current file.** I checked directly:
- There is no `§21.1` — `## 21. Roadmap` exists but the file ends mid-table right after it (line 2307, no further content).
- No `A1L`/`A2R`/`axle_metadata` pattern appears anywhere in `spec/`, `schema/`, or `examples/`.
- No Tyrrell P34 example exists.
- `schema/svj.schema.json` hard-requires exactly `["FL", "FR", "RL", "RR"]` on `suspension` (closed object) and `chassis.mass_unsprung_per_corner` (required keys). *(Correction: `powertrain.half_shafts` already allowed extra keys.)*

So the naming convention that this proposal was going to build on doesn't exist — it looks like the §21.1 content was written up in someone's head (or a prior session) and the changelog/brief were updated to describe it, but it never got committed to the actual spec/schema files. This research doc writes that section for real, from scratch, informed by the intent the changelog describes.

### 2.2 What does generalize cleanly already

- `powertrain.differentials` and `powertrain.driveshafts` are **arrays**, not fixed-key objects — already support an arbitrary number of diffs/propshafts (e.g. front, center, rear-1, rear-2 for a tandem-drive truck). No change needed here.
- `chassis.mass_bodies` is an open array — extra unsprung/sprung masses are not a problem.
- The `x_` extension prefix and `additionalProperties: true` convention (used everywhere except the four corner-keyed objects) is the established escape hatch, but it's not a substitute for real schema support if trucks are meant to be first-class.

### 2.3 What's hard-coded to exactly 4 corners

| Location | Constraint |
|---|---|
| `schema.properties.suspension` | `required: [FL,FR,RL,RR]`, `additionalProperties: false` |
| `schema.properties.chassis.properties.mass_unsprung_per_corner` | same |
| `schema.properties.powertrain.properties.half_shafts` | keyed FL/FR/RL/RR by convention (schema already allowed extra keys — correction after implementation) |
| §9.8 `wheel` (per corner) | exactly one rim + one `tire.set_ref` — no concept of a second tire at the same station |
| §9.2.4 `axle_body` (solid_axle/de_dion/torsion_beam) | shared rigid body between exactly **two** corners (hardcoded pair, not N) |
| `steering` | one rack, `tie_rod_inboard.{left,right}` — one steered axle only |
| §12 `brakes` | per-corner only via the same FL/FR/RL/RR corners |

Every one of these needs to generalize for trucks. This is bigger than the v0.98 changes — it touches required fields on 4 different top-level sections, which is why PROJECT_BRIEF correctly flagged it as an "addendum" rather than a drop-in add.

## 3. Problem 1 — Multi-axle (N axles, 1 wheel per side per axle)

### 3.1 Naming

Generalize corner keys from the fixed set to a pattern: `A{n}{L|R}` where `n` is a 1-based axle index counting front-to-back (`A1L`, `A1R`, `A2L`, `A2R`, `A3L`, `A3R`, ...).

`FL`/`FR`/`RL`/`RR` remain valid and are defined as **aliases** for `A1L`/`A1R`/`A2L`/`A2R` — this is what makes the change additive: every existing 2-axle file (all 9 current examples) stays valid unchanged, and a parser that only knows `FL/FR/RL/RR` continues to work for 2-axle vehicles.

```
suspension.{A1L, A1R, A2L, A2R, A3L, A3R}   // 3-axle truck, alias-compatible with FL/FR/RL/RR for A1/A2
```

Schema change: `suspension`, `mass_unsprung_per_corner`, and `half_shafts` go from a closed 4-key object to `patternProperties` matching `^(A[1-9][0-9]?[LR]|FL|FR|RL|RR)$`, with a validator-level rule (not expressible in JSON Schema alone) that `FL == A1L`, etc. cannot both be present with conflicting content.

### 3.2 `axles` — top-level metadata array

A new optional top-level key describing each axle as a physical entity, separate from its two corner objects:

```json
"axles": [
  { "id": "A1", "position_x": 0.0,  "steered": true,  "driven": false, "lift": false, "track": 2.05 },
  { "id": "A2", "position_x": -4.2, "steered": false, "driven": true,  "lift": false, "track": 1.86 },
  { "id": "A3", "position_x": -5.5, "steered": false, "driven": true,  "lift": true,  "track": 1.86 }
]
```

| Key | Type | Description |
|---|---|---|
| `id` | string | `"A1"`, `"A2"`, ... matches the corner prefix |
| `position_x` | number | Axle centerline X position in vehicle frame (m) — replaces the implicit "front axle = origin" assumption for anything past A1 |
| `steered` | boolean | Whether this axle's wheels respond to driver steering input |
| `driven` | boolean | Whether this axle receives drive torque |
| `lift` | boolean | Whether this is a liftable/tag axle (static geometry only — operational lift state is a runtime concern, out of scope) |
| `track` | number | Track width at this axle (m) — axles don't have to share the same track |

Note `wheelbase` (§7, currently a single front-to-rear number) needs a documented rule for N-axle vehicles: it stays defined as the distance from `A1` to the **last** axle, with intermediate axle spacing fully described by each axle's `position_x` — no new field needed, just a clarification.

### 3.3 Multi-axle steering linkage

Trucks with a steered tag/pusher axle (self-steer) or double-steer front axles (some fire trucks, the Tyrrell P34's twin-steered fronts) need a per-axle steering relationship, not just the single rack in §8.

Proposed addition to `steering`:

```json
"steering": {
  ...,
  "additional_axles": [
    { "axle_ref": "A2", "ratio": -0.15, "phase": "opposed", "type": "self_steer" }
  ]
}
```

`ratio` relative to the primary rack's road-wheel angle; `phase`: `"same"` (front-steer tag axle, same direction) or `"opposed"` (rear-steer axle, e.g. active rear steer or a self-steering tag axle that castors opposite to reduce scrub); `type`: `"mechanical_link"` (physically tied to the main rack), `"self_steer"` (passive, caster-driven, no direct link — `ratio` is nominal/approximate), `"active"` (electronically actuated, independent).

### 3.4 Shared axle bodies beyond a pair

§9.2.4 `axle_body` today couples exactly 2 corners (the two sides of one beam axle). For a tandem beam-axle bogie (two solid axles on a walking beam, common on trucks/trailers) there's a second-order coupling: axle A2 and A3 share a **rocker/walking-beam** that equalizes load between them, independent of the left/right coupling each axle already has.

This needs a distinct concept, not a reuse of `axle_body` — proposed as a new optional `bogie` object at the top level, referencing two (or more) axle ids:

```json
"bogies": [
  { "id": "bogie_rear", "axle_refs": ["A2", "A3"], "type": "walking_beam", "pivot_position": [-4.85, 0, 0.4], "equalization": "mechanical" }
]
```

This is the piece I'd flag as needing the most real-world reference material before locking down fields — walking-beam/bogie suspensions have their own kinematics (the beam itself rotates about a pivot, redistributing load between the two axles) that don't map onto the existing `links`/`hardpoints` vocabulary cleanly. Worth a follow-up focused only on this.

## 4. Problem 2 — Multi-wheel-per-side (dual/twin wheels)

This is the more common real-world need (any 1-ton dually pickup, most semi-tractor drive axles, many motorhomes) and is a **different** problem from axle count: one suspension station, two tire contact patches.

### 4.1 Where it lives

A dual-wheel setup shares one hub, one upright, one spring/damper — the suspension kinematics in §9.2 don't change at all. Only §9.8 `wheel` needs to grow: from "one rim, one tire" to "one hub, N wheel positions."

Proposed restructure of `wheel` (backward compatible — single-wheel case is the default and needs zero changes):

```json
"wheel": {
  "rim_diameter": 0.5588,
  "rim_width": 0.19,
  ...,
  "multiplicity": 2,
  "dual_spacing": 0.34,
  "positions": [
    { "offset_y": -0.17, "tire": { "set_ref": "drive_axle_dual_inner" } },
    { "offset_y":  0.17, "tire": { "set_ref": "drive_axle_dual_outer" } }
  ]
}
```

| Key | Type | Required | Description |
|---|---|---|---|
| `multiplicity` | integer | no | Number of wheels at this station. Default `1` (today's behavior, unchanged). |
| `dual_spacing` | number | no | Convenience field: center-to-center lateral distance between wheels (m), when they're symmetric about the corner's nominal Y. |
| `positions` | array | no | Explicit per-wheel lateral offset + tire reference. When present, takes precedence over `dual_spacing` (same "explicit overrides derived" precedent as motion ratio and other fields already in the spec). Length must equal `multiplicity`. |

When `multiplicity` is absent or `1`, the existing single-tire model (`corner.tire.set_ref`, §9.10) applies unchanged — nothing about the current 9 examples needs to change. When `multiplicity > 1`, `positions[].tire` (or a shared `corner.tire` applied to all positions if `positions[].tire` is absent) supplies the tire set per wheel — inner and outer duals sometimes run different pressures/wear states, hence per-position override rather than forcing them identical.

### 4.2 Consequences elsewhere

- **Unsprung mass**: `mass_unsprung_per_corner` stays a single scalar per corner (it already represents "everything unsprung at this station," which now includes 2 tires + 2 rims instead of 1 — no schema change, just a documentation note).
- **Brakes** (§12/9.9): unaffected — one brake assembly per hub regardless of wheel count.
- **Half-shafts** (§10.9): unaffected — one CV joint / shaft per driven hub; dual wheels don't imply two shafts.
- **Contact patch / force summation**: out of scope for SVJ itself (that's a solver concern — how a consuming tool sums two contact patches into one hub load is up to the physics engine), but worth one sentence in the spec so implementers aren't surprised that `multiplicity: 2` means the solver needs to run two tire models per corner, not one.

## 5. Example vehicles worth building once schema lands

- **3-axle rigid truck** (e.g. 6x2 or 6x4 box truck): A1 steered/undriven, A2 driven single wheels, A3 driven with `multiplicity: 2` dual wheels. Exercises axle metadata, generalized corner naming, and dual wheels together.
- **Tyrrell P34** (already promised by the stale changelog entry): A1 + A2 both steered, both narrow single wheels, A3 driven rear — good stress test for `additional_axles` steering linkage with two steered axles and no rear steering at all.
- **Tandem-axle trailer** (no engine): A2/A3 sharing a `bogie`, all wheels dual, none driven, none steered — exercises §3.4 and the dual-wheel work with nothing else in the way.

## 6. Scope and rollout recommendation

This is materially bigger than the v0.98 changes:

- Touches **required** fields on 3 schema objects (`suspension`, `mass_unsprung_per_corner`, `half_shafts`) — those need `patternProperties` instead of a closed enum, which is a more invasive schema edit than adding an optional block.
- Needs new top-level sections (`axles`, `bogies`) and a `steering` extension.
- Needs at least 2-3 new example files to prove it out (§5), including one truck someone should sanity-check against real published dimensions rather than estimates.
- The walking-beam bogie kinematics (§3.4) need more reference research before the field list is trustworthy — I'd treat that as a separate, later addendum rather than blocking the rest of this on it.

Given PROJECT_BRIEF's own framing ("Multi-axle is an addendum, not a replacement" — design decision #1), I'd suggest landing this in stages rather than one big version bump:

1. **Stage A**: `axles` metadata array + generalized `A{n}{L|R}` corner naming with FL/FR/RL/RR aliases (§3.1–3.2). Lowest risk, unlocks straight 3+ axle trucks with single wheels immediately.
2. **Stage B**: `wheel.multiplicity`/`positions` for dual wheels (§4). Independent of Stage A — could ship first if dual-wheel pickups are the more urgent case.
3. **Stage C**: multi-axle steering linkage (§3.3).
4. **Stage D**: bogies/walking-beam (§3.4) — needs more research, do last.

I haven't touched schema or spec files for this yet — this document is the research/proposal pass. Let me know which stage(s) you want implemented and I'll do the same spec → schema → example → validate sequence used for v0.98.
