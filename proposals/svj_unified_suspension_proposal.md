# Proposal: the suspension as bodies, joints and elements

**Status:** implemented in v0.100 (spec §25; loop solver outstanding); decisions taken (§6), implementation in phases (§7) · **Target:** a breaking release, v0.100 (the old `suspension` section is replaced; accepted but deprecated for one release) · **Builds on:** spec §24 (`mass_bodies`, `constraints`, `poses`), `tools/suspension_view.py`

## 1. Why

Today a wheel station is described by a **typed corner**: `suspension.<station>.topology.system_type`
(one of 13 values), an `upright` with `hardpoints`, `links` with `inboard_points` and an `outboard_ref`,
and a `spring`, `damper`, `arb`, `bump_stop` and `brake` beside it. Joints are *implied* by the type and
the link kind (spec §9.2.3.2). Since v0.99.5 the same file also has a general model for rigid bodies,
joints, springs and actuators (§24). The two overlap and cannot meet: a suspension cannot be posed, an
attachment cannot mount on a wishbone, and a linkage nobody put on the list of 13 types cannot be written.

The decision is to make the **components** define the mechanism, and let the type be a label at most.

## 2. What the typed corner is good at (and how that is kept)

| Typed-corner advantage | How it is kept |
|---|---|
| Compact: a few hardpoints describe a corner | **Templates**: parametric generators (double wishbone from six hardpoints, MacPherson from five, …) that *emit* the components. They live in tools, not in the standard |
| A checked list of minimum hardpoints per type | The checker verifies the **mechanism** instead: every body connected, frames coincide, joint types legal, degrees of freedom counted (a corner should leave one: wheel travel, two on a steered corner) |
| Joint types inferred | Joint types are stated, so nothing is guessed (the old `trailing_arm` outboard ambiguity disappears) |
| Rates quoted at the wheel | Element rates are stated; a converter can still receive wheel rates and convert them with the geometry |
| `system_type` for filtering and diagrams | Optional descriptive `topology_hint`; `classify_suspension()` in svj-py derives one from the joints |

## 3. The model

Nothing new is needed for the rigid parts: uprights, links, axle beams, rack, steering wheel and wheels
are `mass_bodies`; hardpoints are `markers`; the joints are `constraints` of type `joint`
(frames coincide, axis = +Z of the frame, §24.4); bushings are `joint.bushing`.

### 3.1 New element types

| Type | Use | Fields |
|---|---|---|
| `damper` | Damper between two markers | `bump_curve`, `rebound_curve` (velocity of the element → force), optional `stroke`, `preload`, `damping` for a linear one |
| `spring` with `kind: torsional` (decided: a torsion bar is a spring) | Torsional element between two bodies about the frame's Z axis: anti-roll bar halves, torsion bars, twist beams, rubber torsion, column compliance | `rate` / `rate_curve` (N·m/rad), `free_angle`, `preload`, `damping` |

Everything else already exists: a **coil / air / leaf spring** is a `spring` (element rate, force–length
`rate_curve`, `preload`, plus the optional `hysteresis_force`, `effective_area`, `nominal_pressure`
fields of today's spring); a **bump or rebound stop** is a `spring` whose `rate_curve` is zero until the
stop engages (or a `contact`); a **coilover** is a spring and a damper on the same two markers.

### 3.2 Steering

The steering wheel is a body on a `revolute` joint to the chassis; the rack is a body on a
`translational` joint (axis = lateral); a `coupling` ties them (`q_rack = ratio · q_wheel`, ratio in m/rad);
tie rods are rod bodies with spherical joints to the rack and to the upright. Power assist is a `drive`
on the rack joint. No steering section is needed to move the wheels.

### 3.3 Anti-roll bar

Two bar-half bodies, each on a `revolute` joint to the chassis (with bushings), a torsional `spring`
between the halves (`rate` in N·m/rad), and a drop link (rod body, spherical joints) from each half to the
lower arm. A one-piece bar is the same with a single body and the spring omitted.

### 3.4 The wheel station becomes thin

Per-wheel data that is *not* mechanical stays together on a small object, **`wheel_stations[]`**, whose
ids keep the established naming (`fl`, `a2r`, …, §23.1):

```json
"wheel_stations": [
  { "id": "fl", "name": "Front left", "axle": "A1", "side": "L",
    "wheel_body": "wheel_fl", "upright_body": "upright_fl",
    "wheel": { "rim_diameter": 0.4318, "rim_width": 0.1778, "rim_offset": 0.045, "set_ref": "std" },
    "tire": { "set_ref": "std", "pressure": 220000 },
    "brake": { "...": "as today" },
    "alignment": { "camber": -0.017, "toe": 0.0005, "caster": 0.07 } }
]
```

`alignment` becomes **declared reference data**: camber, toe, caster and KPI follow from the geometry, so a
tool can compute them and report a mismatch instead of storing two sources of truth. Tyre models stay in
`tires.sets`.

### 3.5 Kinematics

A suspension is a closed kinematic loop, and `poses` today follow joint chains (trees). To use the unified
model for wheel travel, camber and toe curves, svj-py needs a **loop-closure solver** (assembly equations,
Newton iteration, wheel travel as the driving coordinate). That is a separate step. Until then, a solver
such as ADAMS or Simpack receives the full body / joint graph, which is the point of the change.

### 3.6 Couplings between axles

`suspension_couplings` (walking beam, equalizer, trunnion, air and hydraulic circuits) keep their meaning but
refer to **spring and body ids** instead of stations. A walking beam is a body with a revolute joint and a
spring; a circuit lists the springs / cylinders that share pressure.

## 4. Migration

`tools/suspension_view.py` already expands a typed corner into bodies and joints. It becomes
`tools/migrate_suspension.py`, one-way and lossless where the old data allows:

| Old | New |
|---|---|
| upright, links, axle body, wheel | `mass_bodies` (existing `body_ref` bodies reused) |
| `hardpoints.*`, `inboard_points` | joint frames (markers where named) |
| implied / explicit joint types | stated `joint` constraints |
| `bushings` | `joint.bushing` |
| `spring` (wheel rate) | `spring` with the **element rate**: `rate / MR²` using `motion_ratio` when given, otherwise estimated from the mount geometry and flagged `x_converted_from_wheel_rate` |
| `damper` (wheel or damper curves) | `damper` (with the §9.4 conversion; `damper.reference: "wheel"` is converted the same way) |
| `arb`, `bump_stop`, `rebound_stop` | torsional `spring`, `spring` with a stop curve |
| `steering` rack data | rack body, joint, coupling (where geometry is given) |
| `system_type` | `topology_hint` |
| `wheel`, `tire`, `brake`, `alignment` | `wheel_stations[]` |

Converters are rewritten by their author; the migration tool is for the shipped examples and for checking a
converter's output.

## 5. Impact

Schema (new `damper`, torsional `spring`, `wheel_stations`, `topology_hint`; `suspension` removed), spec
§9 and §23 rewritten, `multiaxle_check`, `multibody_check` (its joint-inference table moves into the
migration tool), svj-py (`Vehicle.stations`, `corner()`, `topologies()`), the viewer (every suspension view
reads corners today), 12 examples and the template.

## 6. Decisions

1. **Transition:** the old `suspension` section is **accepted but deprecated for one release** (validators warn); it is removed in the next. Converters can switch one at a time while the migration tool converts the shipped files.
2. **Where bodies live:** **`chassis.mass_bodies`** keeps holding every body of the vehicle (uprights, links, wheels, rack, loader parts); the spec says so explicitly, and `mass_bodies_complete` keeps its meaning.
3. **Wheel-rate conversion:** the migration **estimates the motion ratio from the mount geometry and flags the result** (`x_converted_from_wheel_rate`, with the ratio used), so an estimate is never mistaken for measured data. A given `motion_ratio` is always used instead.
4. **Leaf springs:** a **`spring` at the axle seat plus end joints** (eye, shackle, slipper), keeping the hysteresis and end-friction fields; the leaf pack is not a flexible body.
5. **Loop solver:** **the next step**, after the model, migration, tools and viewer. Solvers such as ADAMS or Simpack already receive the full body / joint graph from the model.
6. **Names:** a body that corresponds to a well-known part **keeps that part's canonical name** (`upright_fl`, `upper_wishbone_fl`, `tie_rod_fl`, `rack`), with its meaning in `description` and a display `name` (`"Upright FL"` · *"Upright / knuckle / hub carrier"*). The migration and every template use the vocabulary of `docs/naming_convention.md`; the checker flags an alias of a known part (the advisory of v0.99.7, now covering the suspension parts too). The mechanism is defined by the components, never by the name.

## 7. Phases

| Phase | Content | Exit criterion |
|---|---|---|
| 1 | `damper`, torsional `spring`, `wheel_stations`, `topology_hint` in the schema and spec; checker rules (connectivity, DOF count, coincident frames) | A hand-written unified corner validates |
| 2 | `migrate_suspension.py`; every shipped example and the template migrated | All migrated files validate; the old section is gone or flagged deprecated |
| 3 | svj-py, `multiaxle_check`, `multibody_check` updated | Tests pass on the migrated files |
| 4 | Loop-closure solver, wheel-travel poses, alignment checks | A wheel-travel pose gives camber / toe curves |
| 5 | Viewer reads the unified model | The viewer shows and animates a migrated suspension |
