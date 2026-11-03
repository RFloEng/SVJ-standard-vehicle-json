# Study: glTF or OpenUSD as the appearance file of SVJ

**Status:** feasibility study, revised. **Decision (project owner): a USD workflow around SVJ is only prospective, so option B stays a documented possibility and is not built.** Nothing implemented · **Question:** may the shape-and-appearance file bound to an SVJ vehicle (spec §22) be OpenUSD as well as glTF, one or the other per vehicle? · **Builds on:** spec §22, `proposals/svj_step_visual_binding_proposal.md`

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

- ~~Is a USD workflow already in use around SVJ?~~ Answered: prospective only. Revisit option B when a real USD user (a configurator, a digital twin) appears.
- Should appearance variants (paint, wheels) be part of the standard at all, or left to the asset?
- Which USD materials may a conforming SVJ viewer be expected to show (`UsdPreviewSurface` only, or MaterialX)?
- Who maintains the optional USD checks as the USD libraries and Python versions change?

## 9. Sources and confidence

Verified: glTF 2.0 as ISO/IEC 12113:2022 ([Khronos](https://www.khronos.org/news/press/khronos-gltf-2.0-released-as-an-iso-iec-international-standard)); the scope of AOUSD Core Specification 1.0 ([Linux Foundation](https://www.linuxfoundation.org/press/alliance-for-openusd-announces-core-specification-1.0-the-universal-language-for-building-3d-worlds), [AOUSD](https://aousd.org/uncategorized/core-spec-announcement/)); clearcoat as a ratified glTF extension ([Khronos repository](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_clearcoat)); sheen and transmission announced with it ([Khronos](https://www.khronos.org/news/press/khronos-releases-wave-of-new-gltf-pbr-3d-material-capabilities)); the limits of three.js's USD loader ([forum](https://discourse.threejs.org/t/usdz-loader-for-three-js/35357), [PR 25023](https://github.com/mrdoob/three.js/pull/25023)); the experimental WebAssembly build of the USD bindings ([grill-usd-core](https://pypi.org/project/grill-usd-core/)).

From general knowledge, not checked here: the status of glTF material variants and mesh instancing extensions, OpenUSD's current licence terms, the prim-name character rules, the default `metersPerUnit`, and Blender and Unreal import and export support. Check these before a decision. The sources date from late 2025.
