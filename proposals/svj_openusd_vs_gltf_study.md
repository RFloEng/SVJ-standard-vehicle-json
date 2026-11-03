# Study: glTF or OpenUSD as the appearance file of SVJ

**Status:** feasibility study, revised. **Decision (project owner, later): a USD-based track format (STJ) is being created and CAD input is a goal, so USD becomes the target for shapes. Option B was started in v0.105 (spec §22.10, `tools/gltf2usd.py`, `tools/mesh_check.py`); glTF stays supported during the transition.** (The earlier decision, that USD was only prospective, is superseded.) · **Question:** may the shape-and-appearance file bound to an SVJ vehicle (spec §22) be OpenUSD as well as glTF, one or the other per vehicle? · **Builds on:** spec §22, `proposals/svj_step_visual_binding_proposal.md`

**Ground rule (from the project owner).** SVJ is a format for **physics characteristics**. The **JSON is the authority and stays the main file**; every physical fact lives there. The mesh file only stores **shapes, colours and appearance**. This study judges the two formats on that job alone.

**Result in one line:** allow either format as the appearance carrier, glTF the default, with rules that keep the JSON authoritative; use none of USD's physics, composition-as-structure or recording features.

---

## 1. What the rule excludes

An earlier draft of this study counted USD's physics schema, its layers and variants as replacements for SVJ concepts, and its time samples as a place for recordings. Those are **out of scope**:

| Idea | Why it is dropped |
|---|---|
| `UsdPhysics` rigid bodies, joints and drives as a description of the vehicle | The physics is SVJ's JSON (§7, §24, §25). A second description in a mesh file would compete with it |
| USD layers or variants replacing SVJ override files and `setups[]` (§3.4, §29) | Setups change physical values; they stay in JSON. Variants may only change *appearance* (§4) |
| An SVJ-to-USD export that carries physics | Not needed for an appearance carrier; a third-party can build one from the JSON |
| USD time samples as a store for recorded runs | Recorded runs are not a priority and are not physics characteristics |

What remains: **geometry, materials, colours, textures, instancing, levels of detail, paint and wheel variants, part names.**

## 2. What SVJ asks of an appearance file

1. **Shapes**: triangle meshes per part, instanced wheels, sensible size (a car is tens of MB of triangles).
2. **Look**: base colour, metallic and rough surfaces, **car paint** (clearcoat), glass (transmission), rubber, emissive lamps, textures.
3. **Parts with stable names** so a `visual` block can point at one (§22.3, §22.5).
4. **Appearance variants**: paint colours, wheel designs, trims, levels of detail.
5. **Fixed, checkable units and axes** (§22.4).
6. **Readable by the tools that exist**: the web viewer, Blender, game engines, the simulators' converters.

## 3. glTF and OpenUSD for that job

| Criterion | glTF 2.0 | OpenUSD |
|---|---|---|
| Standard status | ISO/IEC 12113:2022 ([Khronos](https://www.khronos.org/news/press/khronos-gltf-2.0-released-as-an-iso-iec-international-standard)) | AOUSD Core Specification 1.0, Dec 2025, which covers composition and the file formats; geometry and materials are not yet standardised ([AOUSD](https://www.linuxfoundation.org/press/alliance-for-openusd-announces-core-specification-1.0-the-universal-language-for-building-3d-worlds)) |
| Meshes | Triangle meshes; instancing and compression by extensions | Meshes, subdivision surfaces and curves; native instancing; more CAD-friendly shapes |
| Materials and paint | One portable PBR model; extensions for clearcoat (ratified, [Khronos](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_clearcoat)), sheen and transmission (announced with it, [Khronos](https://www.khronos.org/news/press/khronos-releases-wave-of-new-gltf-pbr-3d-material-capabilities)) | `UsdPreviewSurface` for portability; MaterialX and richer shading networks, which not every reader renders |
| Variants (paint, wheels, LOD) | Material variants and separate files | **Variant sets** in one stage: the best fit for a paint or wheel configurator |
| Part names | Node names, not required to be unique | Prim paths, unique by construction |
| Units and axes | Fixed: metres, Y-up, right-handed | Metadata: `upAxis`, `metersPerUnit` (default centimetres): a source of 100x errors unless SVJ pins them |
| Files | `.glb` one file; `.gltf` + resources | `.usdz` package, `.usdc`, `.usda`, plus layers that reference each other |
| Reader effort | Small; JSON plus a binary buffer | Large: a reader needs the composition engine |
| Web viewer | Native in three.js, Babylon and others | Immature: three.js's loader is limited ([forum](https://discourse.threejs.org/t/usdz-loader-for-three-js/35357)); WebAssembly builds are experimental |
| Tool dependency for SVJ tools | None | Optional large library |
| Where it is strong | Web, mobile, game engines, converters | Configurators and visualisation pipelines (for example Omniverse, Apple AR), large layered scenes |

## 4. Advantages and disadvantages, under the rule

### OpenUSD instead of, or beside, glTF

**Advantages**
- Variant sets give paint, wheel and level-of-detail choices in one asset.
- Unique prim paths remove duplicate-name binding errors.
- Richer materials (MaterialX) and CAD-friendly shapes for premium visualisation.
- A vehicle already modelled for a USD pipeline (a configurator, a digital twin) can be bound without conversion.

**Disadvantages**
- No dependable browser support, so the viewer cannot open it natively.
- A heavy library, and a larger reader, for a file that only carries appearance.
- The standard is young and its geometry and materials parts are not yet in the core specification.
- The `SVJ::category::id` node names are not legal prim names, so the convention needs a USD form.
- Units and axes depend on metadata that is easy to get wrong.

### glTF as the only format

**Advantages**: small readers, the web viewer works as is, ISO standard, stable, every converter and DCC tool exports it.
**Disadvantages**: no variant sets in one asset (separate files for LODs and paints), simpler material model, nothing for large layered scenes.

## 5. Options

| | Description | Verdict |
|---|---|---|
| A | glTF only (today) | Fine; the baseline |
| **B** | **Either format**: the manifest names the format per asset, the binding stays one string, the JSON stays the authority | **Recommended.** Small change to the standard, no change to the physics, USD users are served |
| C | USD only | No: loses the web viewer and the small reader for no gain in physics |
| D | USD as an export written by a separate tool | Possible later, outside the standard |

## 6. Rules that keep the JSON in charge (apply to both formats)

1. **No physics is read from a mesh file**: masses, joints, stiffnesses, tyre data and collision proxies come only from the SVJ JSON. A mesh that carries physics-looking data (a `UsdPhysics` prim, a glTF physics extension) is ignored for physics.
2. **Mesh transforms do not define kinematics.** Where a part sits at the reference pose may be read from the mesh for display, but SVJ's joints and poses move it (§24, §26).
3. **A missing, broken or unsupported mesh never invalidates a file.** Every `visual` binding is optional (§22.8); a validator reports a bad binding as a warning about appearance only.
4. **Variants change appearance only**: paint, wheel design, trim, level of detail. A variant that would change a mass, a size that matters to physics or a hardpoint is not allowed; the JSON `setups[]` (§29) is where physical alternatives live.
5. **One place for axes and units**: the existing `coordinate_system` block (§22.4); a USD asset MUST declare `metersPerUnit = 1`.

## 7. Sketch of option B

1. **Manifest** (§22.2): `assets.meshes[]` entries get an optional `format`: `"gltf"` (default) or `"usd"`; the `uri` extension is the fallback (`.glb` `.gltf` / `.usd` `.usda` `.usdc` `.usdz`). Relative paths only, as now.
2. **Binding**: `visual.node` stays a string: a node name in glTF, a **prim path** in USD (`/Car/Chassis/Upright_FL`).
3. **Names**: for USD the SVJ id and category are stored as attributes (`svj:id`, `svj:category`) on legal prim names; the integrity checker reads them.
4. **Appearance variants** (optional): a `visual` block may name a variant (`{"variant": {"paint": "red"}}`) which a reader applies only if it understands variants; otherwise it shows the default look.
5. **Checks**: `tools/integrity_check.py` gets a USD branch behind an optional import; without the library, USD assets are skipped with a note (rule 3).
6. **Viewer**: GLB stays native; USD is opened through an offline conversion or a WebAssembly build later; saving mesh edits for USD would write a small override layer.
7. **Effort**: the spec and schema changes are small (a field and rules), the checker small, the viewer the larger part and optional.

## 8. Open questions

- ~~Is a USD workflow already in use around SVJ?~~ Answered: the track format STJ is USD based and CAD input (NURBS) is wanted, so option B was built (v0.105).
- Should appearance variants (paint, wheels) be part of the standard at all, or left to the asset?
- Which USD materials may a conforming SVJ viewer be expected to show (`UsdPreviewSurface` only, or MaterialX)?
- Who maintains the optional USD checks as the USD libraries and Python versions change?

## 9. Sources and confidence

Verified: glTF 2.0 as ISO/IEC 12113:2022 ([Khronos](https://www.khronos.org/news/press/khronos-gltf-2.0-released-as-an-iso-iec-international-standard)); the scope of AOUSD Core Specification 1.0 ([Linux Foundation](https://www.linuxfoundation.org/press/alliance-for-openusd-announces-core-specification-1.0-the-universal-language-for-building-3d-worlds), [AOUSD](https://aousd.org/uncategorized/core-spec-announcement/)); clearcoat as a ratified glTF extension ([Khronos repository](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_clearcoat)); sheen and transmission announced with it ([Khronos](https://www.khronos.org/news/press/khronos-releases-wave-of-new-gltf-pbr-3d-material-capabilities)); the limits of three.js's USD loader ([forum](https://discourse.threejs.org/t/usdz-loader-for-three-js/35357), [PR 25023](https://github.com/mrdoob/three.js/pull/25023)); the experimental WebAssembly build of the USD bindings ([grill-usd-core](https://pypi.org/project/grill-usd-core/)).

From general knowledge, not checked here: the status of glTF material variants and mesh instancing extensions, OpenUSD's current licence terms, the prim-name character rules, the default `metersPerUnit`, and Blender and Unreal import and export support. Check these before a decision. The sources date from late 2025.


---

## 10. Note: the interface between an SVJ vehicle and a track (STJ)

**Context.** A track format based on USD is being designed (working name STJ). The ground rule of this study (top of the document) applies to **vehicles**: a car's behaviour can be simulated without its shape, so the JSON is the authority and the mesh is appearance. It does **not** apply to tracks: the shape of a road (elevation, banking, camber, curvature, surface zones) is part of its physics, so a USD track with the geometry as authority is consistent. This note lists what the two formats have to agree on so that they can be developed separately. It changes neither the SVJ standard nor the track format; it is the checklist for the contract between them.

### 10.1 Who owns what

| | SVJ vehicle | STJ track |
|---|---|---|
| Physics authority | the JSON | the USD stage (geometry and surface data) |
| Shape | appearance only (glTF, optionally USD later) | the physics |
| Needs the other side's shape? | **No**: a car can be simulated on any ground that answers the contact query | Not the vehicle's shape, only its wheel contact data |

### 10.2 The contact query (the track answers, the vehicle asks)

For each wheel and simulation step the vehicle side asks the track about the ground under the tyre. The contract is a **function**, not a file format: any implementation (mesh ray casts, a parametric road model, a heightmap) may answer it.

| Input | Unit | Source in SVJ |
|---|---|---|
| Wheel centre position `(x, y)` and heading in the track frame | m, rad | the vehicle state; SAE axes |
| Footprint: length, width | m | the tyre set: `dimensions.tread_width` for the width; the contact length from the loaded radius and the load (the evaluator knows `R0` from `dimensions.overall_diameter`) |
| Vertical load (optional) | N | only for deformable surfaces |
| Time `t` (optional) | s | only for tracks with moving or changing surfaces |

| Output | Unit | Use on the vehicle side |
|---|---|---|
| Height `z` and surface normal `n` of the footprint's mean plane | m, unit vector | wheel travel, camber relative to the ground, the tyre's slip and load geometry |
| Surface id | string | key into the surface table (§10.3) |
| High-frequency roughness (optional) | m | excitation of the suspension below the footprint scale; stored apart from the main surface so it stays a separate grid |
| Surface temperature, wetness (optional) | °C, 0–1 | tyre thermal model, friction variants |
| Depth of a soft surface (optional) | m | sinkage for gravel, sand, snow; needs the vertical load, which the vehicle passes with the query |

**Footprint, not a point.** A tyre envelopes a kerb or a bump; a single ray gives a wrong height and normal. The track side should answer for the footprint: the mean plane over a small grid of samples (3 × 3 over the contact patch is a sensible default) or an analytic average. The query includes the footprint size so that the answer is the same between implementations.

### 10.3 Surface table (the link between track and tyre)

The surface id selects a row of a table published by the track. The numbers must be meaningful for the tyre model of §11.13, which scales friction and stiffness through `pacejka.scaling`. A surface cannot give one tyre-independent friction number: friction depends on the tyre as well as on the road. A workable split:

| Side | Gives |
|---|---|
| Track surface | an intrinsic **friction level** relative to a stated reference surface (the surface the tyre data were measured on), a rolling-resistance factor, a roughness class, wet and dry variants |
| Tyre set (SVJ) | the **sensitivity** to a surface: how much a given tyre loses on gravel or wet asphalt |

Mapping onto the SVJ evaluator: `LMUX = LMUY = mu_surface / mu_reference` for a road tyre on a plain surface; a tyre-specific table would refine it. A table the track might publish (the numbers are illustrations only):

```json
{ "surfaces": {
    "asphalt_dry": { "mu_scale": 1.00, "rolling_resistance": 0.010 },
    "asphalt_wet": { "mu_scale": 0.70, "rolling_resistance": 0.012 },
    "kerb":        { "mu_scale": 0.95, "rolling_resistance": 0.015 },
    "grass":       { "mu_scale": 0.40, "rolling_resistance": 0.060 } },
  "reference_surface": "asphalt_dry" }
```

If tyre-specific behaviour on surfaces is wanted, the SVJ side would gain an optional table in the tyre set, for example `tires.sets.<id>.surface_scaling: { "gravel": { "LMUX": 0.6, "LMUY": 0.55 } }`. That is an open point (§10.6), not a decision.

### 10.4 What the vehicle passes to the track

- **Wheel contact data**: the position of the wheel centre, the loaded or unloaded radius, the tread width, and the vertical load when the surface is deformable (soft soil, snow). All of it is in the SVJ file already (`wheel_stations[]`, `tires.sets`, the evaluator's `R0`).
- **Ground reference for aerodynamics**: the aero maps are functions of ride height (§13: `Cl_front_vs_ride_height`, `Cd_vs_ride_height`). The vehicle needs the ground height at a few points under the body (front axle centre, rear axle centre, the underbody); the same query serves, with a point footprint.
- **Placement**: a start pose in the track frame (position and heading of the SVJ origin, which is the front-axle centre at ground level, §2.1).

### 10.5 Conventions to state once, in both formats

| Topic | Rule |
|---|---|
| Axes | SAE J670: x forward, y right, z down, in the vehicle frame; the track frame must declare its up axis and handedness, and the conversion is stated, not implied |
| Units | SI everywhere; a USD stage declares `metersPerUnit = 1` (the USD default is centimetres) |
| Origin of the track | one stated origin and datum for height (for example mean sea level or the start line), so that a car placed at a pose has a defined ground |
| Height | `z` of the surface in the track frame, with the declared vertical axis; the contact query returns the surface point under the wheel centre along the track's vertical |
| Surface ids | lower-case identifiers `[a-z0-9_]+`, like SVJ ids |
| Addressing | track objects are addressed by prim path; vehicle ids do not appear in the track |

### 10.6 Open points

1. **Where friction sensitivity lives**: in the track (a table per tyre class), in the tyre set (§10.3), or both. The tyre set is the physically honest place; the track would then only name surfaces and give a base level.
2. **Parametric or mesh road**: a reference line with elevation and crossfall plus a separate fine-roughness grid (the way OpenDRIVE and OpenCRG split road shape and roughness; named from general knowledge, check before relying on it), or a mesh. The contact query hides the choice from the vehicle; the track format should say which it supports.
3. **Deformable and moving surfaces** (soft soil, rain-wet changes, a moving platform): these need `t` and the load in the query and a defined update rate. Out of scope for a first version.
4. **Query rate and latency**: how often, and in which coordinate system, a simulator may call the query. For a USD stage this decides whether the road is pre-sampled into a grid.
5. **Which side holds the surface table**: it must be stable across cars and tracks. The proposal is the track, referenced by the car only through the evaluator's scaling.
6. **Vertical datum of the aero ride height**: ground height under the car versus a flat reference plane. For banked or crowned roads the two differ, and the aero maps were measured over a flat floor.

### 10.7 What this note does not do

It does not define the STJ file, add fields to SVJ, or fix the footprint algorithm. It lists the information that has to cross the boundary and the conventions both sides must state. Once the STJ authors agree with §10.2 to §10.5, the agreed parts can move into an SVJ appendix, and the open points in §10.6 into the track format's own specification.
