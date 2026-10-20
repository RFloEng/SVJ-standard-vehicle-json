# Proposal: movable parts and constraints between parts

**Status:** draft for discussion — nothing implemented · **Target:** additive, after v0.99.4 · **Builds on:** §7.2 `mass_bodies` (v0.96 `parent`, `markers`), §9.2.3.2 joint types, §22 visual binding

## 1. The gap

SVJ can already split a vehicle into parts (`chassis.mass_bodies[]`: mass, CG, inertia, `parent`,
named `markers`, a `visual` binding). What it cannot say is **how a part is allowed to move**:

- `parent` records hierarchy only. There is no joint, axis, range of motion or rest state.
- Joint types exist only on suspension links (§9.2.3.2).
- `suspension_couplings` (§23.5) relate axles, not arbitrary bodies.
- The only moving-part construct is aerodynamic: `aerodynamics.components[].settings` and `active_systems.drs`.

So a door, hood, tailgate, tilt cab, tipper body, folding mirror or seat is stored as a rigid body
with a mass and a mesh, frozen in one pose. Nothing says that it swings, where its hinge is,
what stops it, what holds it, or that it rests against another panel.

## 2. Requirements

1. A movable part **has mass** (it already does: it is a `mass_body`).
2. A part **can move** relative to another part: hinge, slide, ball, planar, and so on, with limits.
3. Constraints are **between any two parts**, not only "attached to the parent": a hood rests on
   bump rubbers, a door check holds a door at a detent, two doors are linked, a latch holds a lid.
4. Additive and optional: a file without the new block is unchanged; simple readers ignore it.
5. Solver-agnostic: describe the physics (frames, limits, stiffness, friction), not a solver's syntax.

## 3. Design

### 3.1 Part = existing `mass_body`

No new "part" object. A mass body is the part; its `position` and `markers` are in the vehicle
frame **at the reference pose** (the pose the file's geometry and meshes are authored in).
Rule: a body that no constraint mentions is **welded to its `parent`** (today's behaviour). A body
named by a `joint` moves as that joint allows.

`ground` and `chassis` are the two implicit root bodies (as in the v0.96 `parent` text).

### 3.2 New top-level `constraints[]`

An array like `suspension_couplings`: each entry joins two bodies through two **markers** (named
frames from `mass_body.markers`; `chassis`/`ground` use `chassis.markers` / the vehicle origin).
Convention (ADAMS-style, stated once): a revolute or translational joint acts about / along the
**+Z axis of the marker frame**; the marker's `orientation` quaternion (§4.1 of the multibody
proposal) therefore *is* the hinge axis.

Common fields:

| Key | Type | Description |
|---|---|---|
| `id` | string | Unique id |
| `type` | string | `joint`, `spring`, `contact`, `latch`, `coupling` |
| `body_a`, `body_b` | string | Body ids (`mass_bodies[].id`, `chassis`, `ground`). `body_a` is the reference side |
| `marker_a`, `marker_b` | string | Marker names on the respective bodies. For `chassis` and `ground` an inline `frame_a` / `frame_b` `{position, orientation}` may be used instead |
| `description` | string | |

Type-specific fields:

**`joint`** — kinematic connection

| Key | Description |
|---|---|
| `joint_type` | `revolute`, `translational`, `cylindrical`, `spherical`, `universal`, `planar`, `fixed` (the §9.2.3.2 set) |
| `range` | `{min, max}` of the joint coordinate (rad for rotation, m for translation), measured from the reference pose = 0 |
| `stop` | `{stiffness, damping, restitution}` of the end stops reached at `min` / `max` (omit = rigid stop) |
| `friction` | Coulomb friction torque (N·m) or force (N) |
| `damping` | Viscous damping (N·m·s/rad or N·s/m) |
| `bushing` | Optional compliance instead of a perfect joint: a `bushing_obj` (§9.2.5), expressed in the marker frame |
| `drive` | Optional actuation: `{mode: "free"\|"position"\|"velocity"\|"force", target, max_force, rate}` — a hydraulic ram on a tipper or tilt cab, an electric window |

**`spring`** — force element between two markers (gas strut, door check spring, return spring)

| Key | Description |
|---|---|
| `rate` / `rate_curve` | Linear rate (N/m) or force–length curve (`curve2d`) |
| `free_length`, `preload` | As in §9.3 |
| `damping` | Viscous damping along the element (N·s/m) |
| `actuated` | Optional `{stroke, ...}` for a ram |

**`contact`** — one-sided contact between two bodies that are *not* jointed to each other (hood on its
bump rubbers, door against the seal, flap on its seat)

| Key | Description |
|---|---|
| `shape_a`, `shape_b` | Contact primitives attached to the markers: `{type: "point"\|"plane"\|"sphere"\|"cylinder"\|"box", size…}` |
| `gap` | Clearance at the reference pose (m); negative = pre-compressed |
| `stiffness`, `damping`, `friction`, `restitution` | Contact law |

**`latch`** — holds a joint until released

| Key | Description |
|---|---|
| `joint_ref` | `id` of a `joint` |
| `position` | Coordinate at which it latches |
| `holding_force` | Torque / force above which it lets go (N·m or N) |
| `state` | `latched` \| `released` at the reference pose |

**`coupling`** — kinematic relation between two joints (linked or mirrored doors, scissor hinge, rack and pinion)

| Key | Description |
|---|---|
| `joint_a`, `joint_b`, `ratio` | `q_b = ratio · q_a` |

### 3.3 Named poses

Optional top-level `poses[]`:

```json
"poses": [
  { "id": "closed" },
  { "id": "door_l_open", "values": { "hinge_door_l": 1.1 } },
  { "id": "hood_up",     "values": { "hinge_hood": 0.9 }, "aero_setting_ref": "hood_open" }
]
```

`closed` is the reference pose: every joint coordinate is 0. A pose assigns a coordinate to joints (rad / m). Poses let tools show and compare configurations
and compute derived data per pose (§3.4); `aero_setting_ref` may name an
`aerodynamics.components[].settings[].name` so an open panel can change Cd and Cl through the
mechanism that already exists (§13.5.1).

### 3.4 Mass and CG per pose

Mass bodies already carry mass and CG at the reference pose, so the composite fields
(`mass_total`, `center_of_gravity`) keep describing the reference pose. A tool computes the CG and
inertia for any pose by forward kinematics over the constraint graph rooted at `chassis`: each
moving body's position and inertia are carried by the rigid transform of its joint chain. Closed
loops (a four-bar) are allowed in the file but need a solver; the checker only warns.

### 3.5 Visual

`mass_body.visual` already binds a glTF node. Under a pose the node follows the body frame:
`T = FK(pose) · (authored placement)`. The motion is a rigid transform **about the joint axis in the
vehicle frame**, so it does not depend on where the node's own origin sits (a door mesh whose
origin is its centre still swings about the hinge line). This is exactly what a viewer needs to
animate a pose, and what the per-part mesh fitting in the viewer can be used to align.

## 4. Worked example (excerpt)

```json
"chassis": {
  "mass_bodies": [
    { "id": "door_l", "category": "structural", "mass": 14.5, "position": [-1.05, -0.78, -0.62],
      "parent": "chassis",
      "inertia": { "Ixx": 0.9, "Iyy": 1.1, "Izz": 0.4 },
      "markers": { "hinge": { "position": [-0.62, -0.80, -0.55], "orientation": [0, 0, 0, 1] } },
      "visual": { "node": "SVJ::body::door_l" } },
    { "id": "hood", "category": "structural", "mass": 11.0, "position": [0.55, 0.0, -0.78],
      "markers": { "hinge": { "position": [-0.05, 0.0, -0.80], "orientation": [0.7071, 0, 0, 0.7071] },
                   "strut": { "position": [0.35, -0.45, -0.82] },
                   "stop_l": { "position": [1.10, -0.40, -0.74] } } }
  ],
  "markers": { "hood_hinge": { "position": [-0.05, 0.0, -0.80], "orientation": [0.7071, 0, 0, 0.7071] },
               "hood_strut": { "position": [0.30, -0.45, -0.55] },
               "hood_stop_l": { "position": [1.10, -0.40, -0.72] } }
},
"constraints": [
  { "id": "hinge_door_l", "type": "joint", "joint_type": "revolute",
    "body_a": "chassis", "frame_a": { "position": [-0.62, -0.80, -0.55], "orientation": [0, 0, 0, 1] },
    "body_b": "door_l", "marker_b": "hinge",
    "range": { "min": 0.0, "max": 1.15 }, "stop": { "stiffness": 20000, "damping": 150 }, "friction": 0.6 },
  { "id": "door_l_check", "type": "latch", "joint_ref": "hinge_door_l",
    "position": 0.55, "holding_force": 8.0, "state": "released" },
  { "id": "hinge_hood", "type": "joint", "joint_type": "revolute",
    "body_a": "chassis", "marker_a": "hood_hinge", "body_b": "hood", "marker_b": "hinge",
    "range": { "min": 0.0, "max": 1.0 } },
  { "id": "hood_gas_strut", "type": "spring", "body_a": "chassis", "marker_a": "hood_strut",
    "body_b": "hood", "marker_b": "strut", "free_length": 0.38, "rate": 900, "preload": 180, "damping": 60 },
  { "id": "hood_on_rubber_l", "type": "contact", "body_a": "chassis", "marker_a": "hood_stop_l",
    "body_b": "hood", "marker_b": "stop_l",
    "shape_a": { "type": "plane" }, "shape_b": { "type": "point" },
    "gap": 0.0, "stiffness": 80000, "damping": 400, "friction": 0.3 }
],
"poses": [ { "id": "closed" }, { "id": "door_l_open", "values": { "hinge_door_l": 1.1 } },
           { "id": "hood_up", "values": { "hinge_hood": 0.95 } } ]
```

The example uses `chassis.markers` for the frames that sit on the chassis side; this adds a
`markers` object to `chassis` (same shape as `mass_body.markers`).

## 5. Where it matters

| Use | Needs |
|---|---|
| Doors, hood, boot, tailgate, fuel flap | `joint` + `range` + `poses`; `spring` / `latch` for stays and detents |
| Tilt cab, tipper body, crane, folding trailer | `joint` + `drive` (rams); `poses` for the CG in each state |
| Mirror, wiper, seat, window | `joint` / `translational` + `coupling` for linked motion |
| Pit stop, side load with a door open | Mass and CG per pose (§3.4) |
| Aero flaps and hood vents | `poses[].aero_setting_ref` onto the existing aero settings |
| Multibody export | The joints map to joint entities and the springs to force elements; the existing marker convention carries the axes |
| Articulated combinations (planned §23.8) | The same `joint` between two bodies is a fifth wheel or hitch; body ids would then have to be qualified per vehicle (open question 7) |

## 6. Checker rules (`tools/constraints_check.py`, mirrored in `svj-py`)

| # | Rule | Severity |
|---|---|---|
| 1 | `body_a` / `body_b` exist (`mass_bodies`, `chassis`, `ground`); `marker_*` resolve on their body | error |
| 2 | Constraint ids unique; `joint_ref`, `joint_a`, `joint_b` name a `joint`; a `coupling` joins two different joints | error |
| 3 | `range.min ≤ range.max`; `0` lies inside the range (the reference pose is legal); pose values lie inside the ranges | error |
| 4 | Marker orientation quaternions are unit length (the existing v0.96 rule) | error |
| 5 | Every body named by a `joint` has a path of joints back to `chassis` / `ground` (no floating bodies) | error |
| 6 | A body with a joint and a different explicit `parent` | warning |
| 7 | Closed kinematic loops, or more than 6 constrained DOF between two bodies | warning ("needs a solver / over-constrained") |
| 8 | `contact` shapes lack the size their type needs; `spring` with `rate` and `rate_curve` both set | error |
| 9 | A moved body has `mass` ≤ 0 or no `inertia` when a drive or spring acts on it | warning |
| 10 | Pose ids unique; `aero_setting_ref` resolves | error |

## 7. Viewer (after the schema)

- **Poses panel:** dropdown of poses and a slider per joint coordinate; the bound glTF nodes animate about the joint axes (§3.5); hinge axes and range arcs drawn as helpers.
- **CG and mass readout per pose.**
- Springs drawn as lines with the live length; contacts shown when `gap` closes.
- With the existing per-part mesh fitting (viewer v4.4), the hinge marker can be snapped onto the mesh's hinge line, then the corrected SVJ saved.

## 8. Compatibility

Everything is optional. A file without `constraints` / `poses` is unchanged, and `parent` keeps its
v0.96 meaning (hierarchy; welded unless a constraint says otherwise). `chassis.markers` is new but
has the same shape as the existing `mass_body.markers`. Readers that ignore the block still see a
valid vehicle in its reference pose.

## 9. Open questions

1. **Contact geometry.** Are primitives at markers enough for a first release, or do bodies need collision proxies (a glTF node, a convex hull)? Primitives keep it solver-neutral; proxies make exact contact possible.
2. **Closed loops.** Allow them in v1 (flagged), or restrict `joint`s to a tree and express a four-bar through a `coupling`?
3. **One list or several.** `constraints[]` with a `type` (above) versus separate `joints[]`, `force_elements[]`, `contacts[]`. A single list keeps referencing simple; several lists match how solvers group them.
4. **Chassis markers.** Add `chassis.markers`, or require a `helper` body for chassis-side frames?
5. **Poses in an override file.** Are poses part of the vehicle or a variant concern (§3.4 override files)?
6. **Time-dependent behaviour.** `latch` and `drive` imply commands over time. Keep the file to the static parameters, and leave scenarios and control to the simulator?
7. **Qualified ids across vehicles** (tractor/trailer) — shared with the articulated-combination work.
8. **Aero coupling.** Is `aero_setting_ref` enough for panels that change Cd and Cl, or do we need a continuous map from joint coordinate to coefficient?

## 10. Suggested phases

| Phase | Content | Exit criterion |
|---|---|---|
| 1 | `constraints[]` with `joint` and `spring`; `poses[]`; `chassis.markers`; checker rules 1–7 and 10; forward kinematics and CG per pose in `svj-py`; one worked example (doors and hood) | The example validates and `svj-py` returns the CG for each pose |
| 2 | Viewer poses panel and animation | Poses animate the bound meshes about the hinges |
| 3 | `latch`, `coupling`, `drive` | A tilt-cab / tipper example |
| 4 | `contact` (needs the geometry decision, question 1) | A hood-on-rubber example |
