# SVJ glTF Node Naming Convention

> **Status:** Adopted in SVJ v0.97; wheel-station names extended in v0.99; category set and link/steering bindings extended in v0.99.2  
> **Scope:** Applies to all glTF (`.glb` / `.gltf`) assets referenced from an SVJ file via the `assets.meshes` block.

---

## Problem

Before this convention, connecting an SVJ body to its visual representation in a glTF file required either:

- **Index-based mapping** — fragile, breaks whenever artists re-order nodes in their DCC tool.
- **Name guessing** — tools matched node names by substring, leading to silent failures when naming drifted.

Neither approach survives a round-trip through Blender, Maya, or any automated pipeline.

---

## The Convention

Every glTF node that corresponds to an SVJ body or helper must be named according to this format:

```
SVJ::<category>::<name>
```

### Categories *(v0.99.2)*

| Category | Meaning |
|----------|---------|
| `body` | Chassis, decomposed mass bodies, and any rigid body with no better category. Also the v0.97 category for uprights (`SVJ::body::upright_fl`) — still valid, kept for existing assets. |
| `suspension` | Uprights, links (wishbones, arms, rods, tie rods), springs, dampers, anti-roll bars, axle beams |
| `steering` | Rack / gear housing, column, steering wheel |
| `wheel` | Rims and wheels, including each wheel of a dual set |
| `brake` | Discs, drums, calipers |
| `powertrain` | Engine, gearbox, clutch, transfer case, differentials, propshafts |
| `aero` | Wings, splitters, diffusers |
| `helper` | Non-physical marker: suspension hardpoints, sensor origins, camera pivots |
| `lod` | Level-of-Detail geometry variant of a body node |

Before v0.99.2 the schema accepted only `body`, `helper` and `lod`, while the spec text listed `body`, `wheel`, `suspension`, `aero` and `powertrain`. The list above is the union of both and is now the single source of truth; nothing that validated before stops validating.

### Name

The `<name>` segment must be a `snake_case` identifier composed of lowercase letters, digits, and underscores only (`[a-z0-9_]+`). No spaces, no hyphens, no uppercase.

---

## The Binding Rule

For every `body` or `lod` node, the `<name>` suffix **must exactly equal** the `id` of the corresponding SVJ body:

```
svj_body.id  ==  glTF_node_name.split("::")[-1]
```

### Example

| SVJ body id | Required glTF node name |
|-------------|------------------------|
| `chassis` | `SVJ::body::chassis` |
| `wheel_fl` | `SVJ::body::wheel_fl` |
| `wheel_fr` | `SVJ::body::wheel_fr` |
| `wheel_rl` | `SVJ::body::wheel_rl` |
| `wheel_rr` | `SVJ::body::wheel_rr` |

### Wheel stations on multi-axle vehicles *(SVJ v0.99)*

Two-axle vehicles keep the `_fl` / `_fr` / `_rl` / `_rr` suffixes. Vehicles written with A-notation stations (§23.1 of the spec) use the lowercase station name, and dual wheels append their `positions[].label`:

| SVJ body id | Required glTF node name |
|-------------|------------------------|
| `upright_a1l` | `SVJ::body::upright_a1l` |
| `wheel_a3r` | `SVJ::body::wheel_a3r` |
| `wheel_a3r_inner` | `SVJ::body::wheel_a3r_inner` |
| `wheel_a3r_outer` | `SVJ::body::wheel_a3r_outer` |
| `wheel_a2c` (centreline wheel) | `SVJ::body::wheel_a2c` |
| `rear_bogie_l` (walking beam) | `SVJ::body::rear_bogie_l` |

### Links, steering and other non-body parts *(SVJ v0.99.2)*

Every binding except `helper` takes its `<name>` from the id of the part that carries it, lowercased, with anything outside `[a-z0-9_]` replaced by `_`. Corner parts carry the station suffix (`_fl`, `_fr`, `_rl`, `_rr`, or `_a{n}l` / `_a{n}r` / `_a{n}c`), and the suffix is not repeated if the part id already ends with it.

| SVJ part | Id source | Required glTF node name |
|----------|-----------|------------------------|
| Upright on `FL` | `topology.upright.id` | `SVJ::suspension::upright_fl` |
| Link `upper_wishbone` on `FL` | link `name` + station | `SVJ::suspension::upper_wishbone_fl` |
| Link `lower_wishbone` on `FL` | link `name` + station | `SVJ::suspension::lower_wishbone_fl` |
| Link `tie_rod` on `FL` | link `name` + station | `SVJ::suspension::tie_rod_fl` |
| Spring / damper / ARB on `FL` | part + station | `SVJ::suspension::spring_fl`, `damper_fl`, `arb_fl` |
| Brake disc / caliper on `FL` | part + station | `SVJ::brake::disc_fl`, `SVJ::brake::caliper_fl` |
| Wheel on `A3R`, outer of a dual | station + `positions[].label` | `SVJ::wheel::wheel_a3r_outer` |
| Steering wheel | fixed | `SVJ::steering::wheel` |
| Steering rack | fixed | `SVJ::steering::rack` |
| Steering column | fixed | `SVJ::steering::column` |
| Engine | fixed | `SVJ::powertrain::engine` |
| Differential `diff_rear` | differential `id` | `SVJ::powertrain::diff_rear` |
| Aero component `front_wing` | component `id` | `SVJ::aero::front_wing` |

For `helper` nodes the binding is looser — the name should be descriptive but does **not** need to match any SVJ id:

| Purpose | Example glTF node name |
|---------|----------------------|
| Front-left suspension hardpoint | `SVJ::helper::susp_anchor_fl` |
| Driver eye point | `SVJ::helper::driver_eyepoint` |
| Rear camera pivot | `SVJ::helper::cam_pivot_rear` |

---

## Canonical part names *(SVJ v0.99.2)*

The pattern alone does not stop two exporters calling the same part `wishbone_upper_fl` and `fl_upper_arm`. This table is the **recommended vocabulary**: use the canonical name as the SVJ part id (`links[].name`, `upright.id`, aero `id`…), and the node name then follows from the rules above. Converters should map the aliases they meet onto the canonical name; `tools/integrity_check.py` warns (never errors) when a link name is outside this list, so house names stay legal.

**Order is part first, corner last** — `upper_wishbone_fl`, not `fl_upper_wishbone`. One rule covers two-axle cars (`_fl`/`_fr`/`_rl`/`_rr`), multi-axle vehicles (`_a3r`) and dual wheels (`_a3r_outer`), and nodes sort by part rather than by corner.

| Canonical name | Part | Common aliases in other tools |
|----------------|------|-------------------------------|
| `upright` | Upright / knuckle / hub carrier | `knuckle`, `hub_carrier`, `spindle`, `stub_axle` |
| `hub` | Rotating hub, if modelled apart from the wheel | `hub_flange`, `wheel_hub` |
| `upper_wishbone` | Upper A-arm | `upper_arm`, `uca`, `wishbone_upper`, `a_arm_top` |
| `lower_wishbone` | Lower A-arm | `lower_arm`, `lca`, `wishbone_lower`, `a_arm_bottom` |
| `upper_link_front` / `upper_link_rear` | Split upper multi-link arms | `upper_fore`, `upper_aft` |
| `lower_link_front` / `lower_link_rear` | Split lower multi-link arms | `lower_fore`, `lower_aft` |
| `trailing_arm` | Trailing arm | `longitudinal_arm`, `radius_arm` |
| `semi_trailing_arm` | Semi-trailing arm | `sta`, `diagonal_arm` |
| `leading_arm` | Leading arm (2CV-style front) | `front_trailing_arm` |
| `tie_rod` | Steering tie rod / track rod | `track_rod`, `steering_rod`, `steering_link` |
| `toe_link` | Non-steered toe control link | `toe_rod`, `toe_control_arm` |
| `camber_link` | Camber control link | `camber_rod` |
| `drag_link` | Steering drag link (beam axles) | `relay_rod`, `centre_link` |
| `pushrod` / `pullrod` | Inboard-suspension actuation rod | `push_rod`, `pull_rod` |
| `rocker` | Bellcrank | `bellcrank`, `rocker_arm` |
| `strut` | MacPherson / Chapman strut body | `macpherson_strut`, `damper_strut` |
| `torque_rod` | Torque rod on a beam axle | `radius_rod`, `torque_arm` |
| `panhard_rod` | Panhard bar | `track_bar`, `lateral_rod` |
| `watts_link_rod` / `watts_pivot` | Watt's linkage parts | `watts_arm`, `watts_centre` |
| `axle_body` | Beam axle, housing or de Dion tube | `axle_housing`, `de_dion_tube`, `beam_axle` |
| `spring` | Spring of any type | `coil`, `leaf_spring`, `air_spring` |
| `damper` | Damper body | `shock`, `shock_absorber` |
| `arb` | Anti-roll bar | `sway_bar`, `stabiliser_bar`, `torsion_bar_arb` |
| `drop_link` | ARB drop link | `arb_link`, `end_link` |
| `wheel` | Rim + tyre | `rim`, `tire`, `tyre` |
| `disc` | Brake disc or drum | `rotor`, `brake_disc`, `drum` |
| `caliper` | Caliper or backplate | `brake_caliper`, `brake_cylinder` |
| `rack` | Steering rack / gear housing | `steering_gear`, `steering_box` |
| `column` | Steering column | `steering_shaft` |
| `wheel` *(steering category)* | Steering wheel | `steering_wheel`, `handwheel` |
| `engine` / `gearbox` / `clutch` / `transfer_case` | Driveline units | `motor`, `transmission`, `gearbox_case`, `t_case` |
| `propshaft_front` / `propshaft_rear` | Propshafts | `driveshaft`, `prop_shaft` |
| `half_shaft` | Drive shaft to one wheel | `axle_shaft`, `cv_shaft` |
| `front_wing` / `rear_wing` / `splitter` / `diffuser` / `floor` | Aero devices | `front_aero`, `rear_aero`, `undertray` |

Corner parts take the station suffix, so a full front-left double wishbone corner reads:

```
SVJ::suspension::upright_fl
SVJ::suspension::upper_wishbone_fl
SVJ::suspension::lower_wishbone_fl
SVJ::suspension::tie_rod_fl
SVJ::suspension::spring_fl
SVJ::suspension::damper_fl
SVJ::wheel::wheel_fl
SVJ::brake::disc_fl
SVJ::brake::caliper_fl
```

---

## Parts with no body frame: `placement` *(SVJ v0.99.2)*

A wishbone or tie rod is geometry between two hardpoints, not a body with a frame. Its `visual` block says so:

```json
"visual": {
  "mesh_ref": "suspension_set",
  "node": "SVJ::suspension::lower_wishbone_fl",
  "placement": "link_between_points",
  "mesh_axis": "+y",
  "scale_to_length": false
}
```

| Field | Default | Meaning |
|-------|---------|---------|
| `placement` | `rigid` | `rigid`: the node follows the part's own frame (v0.97 behaviour). `link_between_points`: the node is placed from the link's hardpoints. |
| `mesh_axis` | `+x` | Which axis of the **mesh's own local frame** runs from the inboard end to the outboard end. Model a wishbone pointing along its own +X (or declare the axis you used). |
| `from_point` | centroid | Index into the link's `inboard_points` to use as the inboard end. Omitted = centroid of all of them, so a two-point wishbone pivots about the centre of its axis. |
| `scale_to_length` | `false` | `false`: the mesh keeps its authored size and is only translated and rotated. `true`: it is stretched along `mesh_axis` only (never the other two axes) to span the hardpoint distance exactly. |

The outboard end is the upright hardpoint named by the link's `outboard_ref`. Roll about the link axis is not defined by the binding — author it into the mesh.

---

## In the SVJ File

Reference the glTF node from the body's `visual` field:

```json
{
  "assets": {
    "meshes": [
      { "id": "main_body", "uri": "meshes/car_body.glb" }
    ]
  },
  "chassis": {
    "mass_total": 1077,
    "...": "...",
    "visual": {
      "mesh_ref": "main_body",
      "node": "SVJ::body::chassis"
    }
  }
}
```

`mesh_ref` must reference a valid `id` from `assets.meshes`. When there is only one mesh in the file, `mesh_ref` may be omitted and tools will resolve it implicitly.

---

## Validation

Use `tools/integrity_check.py` to verify all visual bindings in an SVJ file before committing:

```bash
python tools/integrity_check.py path/to/vehicle.svj.json
```

The tool checks:
1. Every `visual.node` follows the `SVJ::category::name` pattern with a category from the table above.
2. The `<name>` suffix matches the id of the part that carries the binding (uprights, links, wheels, springs, dampers, brakes, steering, powertrain, aero). `helper` nodes are exempt.
3. Every `visual.mesh_ref` points to an entry in `assets.meshes`.
4. No two parts share the same `visual.node` — except a part shared by both stations of an axle (beam axle, de Dion tube, torsion beam), which is bound from each station with the same node.
5. `placement: "link_between_points"` is only used where two ends exist, and `mesh_axis` / `from_point` / `scale_to_length` only appear with it.
6. The category suits the part, and the link name is in the canonical vocabulary (advisory warnings). Using `body` on a non-body part is valid and only reported as a NOTE.

---

## Rules Summary

1. Names must be unique within a glTF file.
2. Use `snake_case` — lowercase letters, digits, underscores only.
3. No spaces, hyphens, or special characters.
4. For every category except `helper`: the `<name>` suffix **must** match the id of the SVJ part carrying the binding.
5. For `helper` nodes: `<name>` should be descriptive; no id-matching requirement.
6. The `SVJ::` prefix is reserved — do not use it for non-SVJ nodes.
7. Parts defined by hardpoints (links, propshafts) use `placement: "link_between_points"`; everything else uses the default `rigid`.

---

## Why This Matters

- **Deterministic parsing** — any tool can re-derive the binding from the name alone, no lookup table required.
- **Pipeline safety** — node re-ordering in a DCC tool cannot break the binding.
- **Multi-mesh support** — when a vehicle splits across several `.glb` files, the naming convention is the same; `mesh_ref` disambiguates the file.
- **Human-readable** — opening a glTF in any viewer instantly shows which nodes are physics-bound.
