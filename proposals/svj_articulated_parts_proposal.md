# Proposal: movable parts, constraints between parts, and attachments

**Status:** phase 1 implemented in v0.99.5 (spec §24); later phases open · **Target:** additive, after v0.99.4 · **Builds on:** §7.2 `mass_bodies` (v0.96 `parent`, `markers`), §9.2.3.2 joint types, §22 visual binding, `proposals/trailer_coupling_research.md`

> Revision notes: generalised after the observation that movable parts are also the way to add
> **attachments** to a vehicle (a tractor's front loader, three-point hitch and implements, an
> excavator arm, a crane, a tipper body). Added: joints of every type with vector coordinates,
> a linear `actuator` element (hydraulic ram) with stroke-feasibility checks, element lengths per pose,
> and a path to attachments defined in their own files that reuses the planned combination file.

## 1. The gap

SVJ can already split a vehicle into parts (`chassis.mass_bodies[]`: mass, CG, inertia, `parent`,
named `markers`, a `visual` binding). What it cannot say is **how a part is allowed to move**:

- `parent` records hierarchy only. There is no joint, axis, range of motion or rest state.
- Joint types exist only on suspension links (§9.2.3.2).
- `suspension_couplings` (§23.5) relate axles, not arbitrary bodies.
- The only moving-part construct is aerodynamic: `aerodynamics.components[].settings` and `active_systems.drs`.

So a door, hood, tilt cab, tipper body, loader arm or implement is stored as a rigid body with a
mass and a mesh, frozen in one pose. Nothing says that it swings, where its hinge is, what drives
it, what stops it, or that it hangs from another moving part.

## 2. Requirements

1. A movable part **has mass** (it already does: it is a `mass_body`).
2. A part **can move** relative to another part with any joint (hinge, slide, ball, universal, planar, …) and limits.
3. Constraints are **between any two parts**, not only "attached to the parent": a hood rests on bump rubbers, a gas strut pushes a lid, a cylinder drives a boom, two doors are linked.
4. **General kinematic trees**, not a fixed list of parts: a loader is chassis → boom → bucket, a hitch is chassis → lift arm → lower link → implement; the same mechanism describes a door, an excavator, a crane or a forklift mast.
5. **Attachments**: an implement or body that can be fitted to different vehicles is its own SVJ file, mounted on a vehicle interface (§3.6). One joint definition serves both the articulations inside a file and the connections between files.
6. Additive and optional: a file without the new blocks is unchanged; simple readers ignore them.
7. Solver-agnostic: describe the physics (frames, limits, stiffness, friction, stroke), not a solver's syntax.

## 3. Design

### 3.1 Part = existing `mass_body`

No new "part" object. A mass body is the part; its `position` and `markers` are in the vehicle
frame **at the reference pose** (the pose the file's geometry and meshes are authored in).
Rule: a body that no constraint mentions is **welded to its `parent`** (today's behaviour); a body
named by a `joint` moves as that joint allows, carrying everything welded to it.

The part is a full physical rigid body: `mass`, `position` (CG), and an **inertia tensor** that may be given as the §7.1 object or as the full symmetric 3×3 matrix, optionally in a rotated frame (`inertia_orientation`, e.g. the principal axes), as in multibody tools. A moving body without inertia is treated as a point mass and the checker warns.

`ground` and `chassis` are the two implicit root bodies. `category` gains the recommended value
`attachment` for loaders, implements and bodies that are not part of the base vehicle. Body ids must
not contain `.`: the dot is reserved for qualifying a body of an attached unit (`loader.boom`, §3.6).

### 3.2 New top-level `constraints[]`

An array like `suspension_couplings`: each entry connects two bodies through two **frames**, given as
**markers** (named frames from `mass_body.markers` or `chassis.markers`) or inline `frame_a` /
`frame_b` `{position, orientation}`. Convention (ADAMS-style, stated once): a joint's axis is the
**+Z axis of the marker frame**; the marker's `orientation` quaternion therefore *is* the hinge axis.
At the reference pose the two frames of a joint **coincide**.

Common fields:

| Key | Type | Description |
|---|---|---|
| `id` | string | Unique id |
| `type` | string | Phase 1: `joint`, `spring`, `actuator`. Later: `latch`, `contact`, `coupling` |
| `body_a`, `body_b` | string | Body ids (`mass_bodies[].id`, `chassis`, `ground`). `body_a` is the reference (parent) side |
| `marker_a`, `marker_b` / `frame_a`, `frame_b` | | One of each pair per side |
| `description` | string | |

**`joint`** — kinematic connection. The joint coordinate is a vector whose length depends on the type;
it is measured in the `body_a` marker frame from the reference pose (all zero):

| `joint_type` | Coordinate | Motion of `body_b` relative to `body_a` |
|---|---|---|
| `revolute` | `[θ]` | rotation about marker Z |
| `translational` | `[d]` | translation along marker Z |
| `cylindrical` | `[θ, d]` | rotation about and translation along marker Z |
| `spherical` | `[rx, ry, rz]` | rotation vector (axis × angle) about the marker origin |
| `universal` | `[θx, θy]` | rotation about marker X, then about marker Y |
| `planar` | `[x, y, θ]` | translation in the marker XY plane and rotation about Z |
| `fixed` | `[]` | none (a rigid attachment that is still a separate body) |

| Key | Description |
|---|---|
| `range` | `{min, max}`: numbers for a one-coordinate joint, arrays (one entry per coordinate, `null` = free) otherwise. Rad / m. The reference pose (0) must lie inside |
| `stop` | `{stiffness, damping, restitution}` of the end stops (omit = rigid stop) |
| `friction` | Coulomb friction torque (N·m) or force (N) |
| `damping` | Viscous damping (N·m·s/rad or N·s/m) |
| `bushing` | Optional compliance instead of a perfect joint: a `bushing_obj` (§9.2.5) in the marker frame |

**`spring`** — passive force element between two markers (gas strut, return spring, door check)

| Key | Description |
|---|---|
| `rate` / `rate_curve` | Linear rate (N/m) or force–length curve (`curve2d`); exactly one |
| `free_length`, `preload` | As in §9.3 |
| `damping` | Viscous damping along the element (N·s/m) |

**`actuator`** — linear drive between two markers (hydraulic or electric ram: loader, tipper, tilt cab, hitch lift)

| Key | Description |
|---|---|
| `retracted_length` | Length between the two markers fully retracted (m) |
| `stroke` | `{min, max}` extension from the retracted length (m); the working length is `retracted_length + stroke` |
| `bore_diameter`, `rod_diameter` | m, optional (with a supply pressure they give the force limits) |
| `max_pressure` / `max_force` | Pa / N, optional |
| `damping` | N·s/m, optional |

An actuator is a force-producing element, not a kinematic constraint. The poses (§3.3) set the joint
coordinates; each element's length in a pose is derived from the geometry, and the checker confirms an
actuator can physically reach it. This is the quick, solver-free test that a loader's cylinder
really lifts the boom to the stated height.

### 3.3 Named poses

Optional top-level `poses[]`:

```json
"poses": [
  { "id": "closed" },
  { "id": "door_open",  "values": { "hinge_door_fl": 1.1 } },
  { "id": "loader_up",  "values": { "hinge_loader_boom": 0.85, "hinge_loader_bucket": -0.4 } },
  { "id": "hood_up",    "values": { "hinge_hood": 0.95 }, "aero_setting_ref": "hood_open" }
]
```

`closed` (or any pose with no `values`) is the reference pose: every joint coordinate is 0. `values`
maps a joint id to its coordinate: a number for one-coordinate joints, an array for the others. A pose
may also name an `aerodynamics.components[].settings[].name` (`aero_setting_ref`) so an open panel
changes Cd and Cl through the mechanism that already exists (§13.5.1).

### 3.4 Mass, CG and element lengths per pose

Mass bodies carry mass and CG at the reference pose, so the composite fields (`mass_total`,
`center_of_gravity`) keep describing the reference pose. For any pose a tool computes

- the **CG**: `CG(pose) = CG_ref + Σ mᵢ (Xᵢ(pᵢ) − pᵢ) / M`, where `Xᵢ` is the rigid transform the joint chain gives body *i*;
- the **length of every `spring` / `actuator`** from its two marker positions after transformation.

Closed kinematic loops (a four-bar linkage) are allowed in a file but are not solved by phase 1: the
poses give the independent coordinates.

### 3.5 Visual

`mass_body.visual` already binds a glTF node. Under a pose the node follows the body frame:
`T = FK(pose) · (authored placement)`. The motion is a rigid transform **about the joint axis in the
vehicle frame**, so it does not depend on where the node's own origin sits (a door mesh whose origin is
its centre still swings about the hinge line).

### 3.6 Attachments (phase 4; design constraints for phases 1–3)

An attachment is a normal SVJ file (an "implement" or "body": loader, mower, plough, crane, tipper body)
that declares the **interfaces** it can be fitted with. The vehicle declares matching interfaces. This is
the same mechanism as `coupling_points` and the combination file in `proposals/trailer_coupling_research.md`;
this proposal supplies the missing piece, the **joint object**, so one definition serves both uses:

- inside a file: `constraints[]` entry of type `joint`;
- between files: a combination `connections[].joint` (the object listed in §3.2 minus the body/frame fields).

Interfaces are named frames with a role and a size, e.g. `three_point_lower_link` (category and pin
diameters), `three_point_top_link`, `loader_mount`, `pto_shaft`, `fifth_wheel`; compatible roles and
sizes are checked as in the trailer research (rules C2/C3). A fitted attachment appears in the
combination file as a unit; its bodies and joints are addressed with qualified ids
(`loader.boom`, `loader.hinge_boom`), which is why `.` is reserved in ids (§3.1). Mass and CG of the
whole combination, and the pose, are then computed over the union of the units' bodies.

Phases 1–3 therefore keep every id file-local and every joint self-contained, so nothing has to change
when attachments arrive.

## 4. Worked examples (excerpts)

Hood with a gas strut (positive rotation opens it: marker +Z points along +Y, so a positive angle raises
the front edge):

```json
"chassis": {
  "markers": { "hood_hinge":  { "position": [-0.30, 0.0, -0.80], "orientation": [-0.7071, 0, 0, 0.7071] },
               "hood_strut_base": { "position": [-0.05, -0.55, -0.56] } },
  "mass_bodies": [
    { "id": "hood", "category": "structural", "mass": 10.0, "position": [0.55, 0.0, -0.80],
      "markers": { "hinge": { "position": [-0.30, 0.0, -0.80], "orientation": [-0.7071, 0, 0, 0.7071] },
                   "strut": { "position": [0.25, -0.55, -0.82] } } }
  ]
},
"constraints": [
  { "id": "hinge_hood", "type": "joint", "joint_type": "revolute",
    "body_a": "chassis", "marker_a": "hood_hinge", "body_b": "hood", "marker_b": "hinge",
    "range": { "min": 0.0, "max": 1.0 } },
  { "id": "hood_gas_strut", "type": "spring", "body_a": "chassis", "marker_a": "hood_strut_base",
    "body_b": "hood", "marker_b": "strut", "free_length": 0.34, "rate": 900, "preload": 180, "damping": 60 }
]
```

Tractor front loader (a chain; the boom cylinder is checked against its stroke in every pose):

```json
"constraints": [
  { "id": "hinge_loader_boom",   "type": "joint", "joint_type": "revolute", "body_a": "chassis", "marker_a": "loader_boom_hinge",
    "body_b": "loader_boom", "marker_b": "hinge", "range": { "min": -0.15, "max": 0.95 } },
  { "id": "hinge_loader_bucket", "type": "joint", "joint_type": "revolute", "body_a": "loader_boom", "marker_a": "loader_bucket_hinge",
    "body_b": "loader_bucket", "marker_b": "hinge", "range": { "min": -0.9, "max": 0.7 } },
  { "id": "loader_boom_cylinder", "type": "actuator", "body_a": "chassis", "marker_a": "loader_boom_cylinder_base",
    "body_b": "loader_boom", "marker_b": "loader_boom_cylinder_rod", "retracted_length": 0.62, "stroke": { "min": 0.0, "max": 0.46 } },
  { "id": "loader_bucket_cylinder", "type": "actuator", "body_a": "loader_boom", "marker_a": "loader_bucket_cylinder_base",
    "body_b": "loader_bucket", "marker_b": "loader_bucket_cylinder_rod", "retracted_length": 0.48, "stroke": { "min": 0.0, "max": 0.36 } }
]
```

## 5. Where it matters

| Use | Needs |
|---|---|
| Doors, hood, boot, tailgate, fuel flap | `joint` + `range` + `poses`; `spring` for stays |
| Tractor front loader, excavator arm, crane, forklift mast | Joint chains, `actuator` with stroke check, `poses` for transport / dig / dump |
| Three-point hitch, implements, mowers, ploughs | Lift arm and links as joints, the implement as a `fixed`/hinged body; attachment files in phase 4 |
| Tilt cab, tipper body, folding trailer | `joint` + `actuator`; CG in each state |
| Mirror, wiper, seat, window | one-coordinate joints; `coupling` for linked motion (phase 3) |
| Pit stop, side load with a door open | Mass and CG per pose (§3.4) |
| Aero flaps and hood vents | `poses[].aero_setting_ref` onto the existing aero settings |
| Multibody export | Joints map to joint entities, springs and actuators to force elements; the marker convention carries the axes |
| Articulated combinations (§23.8) | The same joint object in a combination `connections[].joint` |

## 6. Checker rules (`tools/constraints_check.py`, mirrored in `svj-py`)

| # | Rule | Severity |
|---|---|---|
| 1 | `body_a` / `body_b` exist (`mass_bodies`, `chassis`, `ground`) and differ; `marker_*` resolve; each side has a marker or an inline frame | error |
| 2 | Constraint ids unique; body ids contain no `.` | error / warning |
| 3 | `range.min ≤ range.max` per coordinate and its length matches the joint type; 0 lies inside; pose values have the right length and lie inside the range; pose ids unique; pose value ids name joints | error |
| 4 | Frame orientation quaternions are unit length | error |
| 5 | Every body named by a `joint` is connected to `chassis` / `ground` through joints (no floating bodies) | error |
| 6 | A body with a joint and a different explicit `parent` | warning |
| 7 | A body that is `body_b` of more than one joint, or two joints between the same pair (closed loop / over-constraint) | warning |
| 8 | `spring` with both `rate` and `rate_curve`; `actuator` with `stroke.min > stroke.max` | error |
| 9 | The two frames of a joint coincide at the reference pose (1 mm) and their Z axes are parallel (axis-bearing joint types) | error |
| 10 | `aero_setting_ref` resolves | error |
| 11 | For each pose, each `actuator`'s derived length lies inside `[retracted_length + stroke.min, retracted_length + stroke.max]` | error |
| 12 | A `spring` / `actuator` whose two end frames coincide (zero length) in the reference pose | warning |

## 7. Viewer (after the schema)

- **Poses panel:** dropdown of poses and a slider per joint coordinate; the bound glTF nodes animate about the joint axes (§3.5); hinge axes and range arcs drawn as helpers.
- **CG and mass readout per pose**; actuators and springs drawn as lines with the live length and a stroke bar (red outside the stroke).
- With the per-part mesh fitting (viewer v4.4), a hinge marker can be snapped onto the mesh's hinge line, then the corrected SVJ saved.

## 8. Compatibility

Everything is optional. A file without `constraints` / `poses` is unchanged, and `parent` keeps its
v0.96 meaning (hierarchy; welded unless a constraint says otherwise). `chassis.markers` is new but has the
same shape as the existing `mass_body.markers`; `category` gains the value `attachment`. Readers that
ignore the blocks still see a valid vehicle in its reference pose.

## 9. Open questions

1. **Contact geometry** (phase 5): primitives at markers, or collision proxies (a glTF node, a hull)?
2. **Closed loops:** solve them (loader linkages, four-bar hitches) or keep poses as independent coordinates plus the stroke check?
3. **One list or several:** a single `constraints[]` with `type`, or separate `joints[]`, `force_elements[]`?
4. **Poses in an override file:** are poses part of the vehicle or of a variant?
5. **Time-dependent behaviour:** `latch` / commands over time stay out of the file; leave scenarios and control to the simulator?
6. **Attachments in the same file or separate:** allow both (a small implement can be `category: "attachment"` bodies inside the host), with the separate file as the interchangeable form?
7. **Interface vocabulary:** roles and sizes for agricultural interfaces (ISO 730 three-point, loader mounts, PTO) alongside the trailer roles.
8. **Loads in tools:** model a carried load (bucket, bale) as a `payload` body joined with a `fixed` joint that poses can attach and detach?
9. **Rotary drives** (slew rings, hydraulic motors, electric hinges) on a joint (`joint.drive`), phase 3.

## 10. Phases

| Phase | Content | Exit criterion |
|---|---|---|
| 1 | `constraints[]` with `joint` (all types, vector coordinates), `spring`, `actuator`; `poses[]`; `chassis.markers`; checker rules 1–12 (except `latch`/`contact`); forward kinematics, CG and element lengths per pose in `svj-py`; two examples (car panels; tractor with front loader and hitch) | Both examples validate, FK reproduces the expected poses and the stroke checks pass |
| 2 | Viewer poses panel and animation | Poses animate the bound meshes about the hinges |
| 3 | `latch`, `coupling`, rotary `joint.drive` — **implemented in v0.99.6** | A tilt-cab / tipper example (`skeleton_dump_truck_tipper_cab`) |
| 4 | Attachments: interfaces, qualified ids, joint object in the combination file | A loader file fitted to a tractor file |
| 5 | `contact` — **implemented in v0.99.8** (primitives at markers) | A hood-on-rubber example (`skeleton_ff_articulated_panels`) |
