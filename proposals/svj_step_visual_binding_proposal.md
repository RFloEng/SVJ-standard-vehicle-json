# Proposal: STEP files as a visual source for SVJ

**Status:** feasibility study and draft proposal — nothing implemented · **Target:** additive, after v0.99.3 · **Builds on:** spec §22 (glTF visual binding layer)

## 1. Question

SVJ's visual layer (§22) binds parts to nodes of a **glTF** file. CAD teams usually hold the
vehicle as a **STEP** assembly (ISO 10303). Can a STEP file be the visual source that is
associated to an SVJ, instead of (or next to) a glTF?

**Short answer: yes, feasible — but as an authoring/source format, not as the runtime format.**
Recommended shape: the manifest entry points to the STEP file, a tool bakes a glTF cache from
it, and everything downstream keeps using §22 unchanged. A viewer that can read STEP may use
it directly.

## 2. What STEP gives, and what it does not

| Aspect | STEP | Consequence for SVJ |
|---|---|---|
| Geometry | Exact B-rep (surfaces, solids). No triangles, except in AP242 tessellated entities, which few exporters write | Needs tessellation before any renderer can draw it; the result depends on tolerances |
| Assembly structure | Product tree (`PRODUCT`, `NEXT_ASSEMBLY_USAGE_OCCURRENCE`) with a placement per instance | Maps naturally onto glTF's node tree; a part used many times (bolts, wheels) is one product with many instances |
| Names | Free text on products and instances. Not guaranteed unique; CAD tools append suffixes (`<1>`, `:2`) and encode non-ASCII as `\X2\…\X0\` | Binding by name needs a tolerant match rule or an explicit map |
| Units | Declared in the file (almost always mm) | Must be converted to metres; importers expose this |
| Axes / origin | The CAD model's own frame, unrelated to the SVJ origin | A per-asset transform is required (§5) |
| Colour | AP214/AP242 via styled items; **AP203 has none** | Colour is available only for newer application protocols |
| Materials, textures, LOD, animation | None (no PBR) | Renders as flat colour; this is a preview, not a final visual |
| Size / IP | Exact geometry, often large and sensitive | Distributing STEP leaks more than a decimated mesh (§7) |

## 3. Who can read it

| Consumer | STEP directly? | Notes |
|---|---|---|
| Viewer (browser) | Possible with **occt-import-js** (OpenCascade compiled to WebAssembly: STEP/IGES/BREP → JSON meshes, runs in the browser, `linearUnit` option) | Licence listed as LGPL-2.1 (check before bundling); the `.wasm` is a large download (size not verified here); reports of memory failures on big models in mobile webviews. Needs a network or bundled copy — the viewer is currently a single self-contained HTML file |
| Python tools (`svj-py`, checks) | Reading the **assembly tree and names** needs no CAD kernel: STEP is plain text, `PRODUCT` and `NEXT_ASSEMBLY_USAGE_OCCURRENCE` lines can be parsed with a small module | Tessellation needs OpenCascade (CadQuery / OCP / pythonocc) or FreeCAD — heavy optional dependencies, not for the core library |
| Game engines, simulators, DCC tools | No | They need glTF (or similar). STEP must be baked |

So: *names and structure* can be checked cheaply anywhere; *drawing* needs a kernel, which is
why a baked glTF cache is the practical delivery format.

## 4. Proposal

### 4.1 Manifest: one entry may describe a STEP source and its glTF cache

`assets.meshes[]` keeps its current meaning for glTF. A new optional `format` (`"gltf"`
default, or `"step"`) and a few optional fields extend it:

```json
"assets": {
  "meshes": [
    {
      "id": "car_cad",
      "uri": "cad/car_assembly.step",
      "format": "step",
      "cache": "meshes/car_assembly.glb",
      "source_sha256": "9f2c…",
      "transform": { "position": [0, 0, 0], "orientation": [0, 0, 0, 1], "scale": 1.0 },
      "node_map": {
        "SVJ::suspension::upper_wishbone_fl": "UPPER WISHBONE LH",
        "SVJ::wheel::wheel_fl": "WHEEL_ASSY<1>/RIM"
      },
      "tessellation": { "linear_deflection": 0.0002, "angular_deflection": 0.5 }
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `format` | `"step"`: `uri` is a STEP (`.step`/`.stp`) file. Default `"gltf"` (unchanged) |
| `cache` | Optional baked glTF of the same assembly, with nodes already named per §22.5. Runtimes that cannot read STEP use it. Nothing may require it to exist |
| `source_sha256` | Hash of the STEP file the cache was baked from; a checker or viewer can warn that the cache is stale |
| `transform` | Maps the STEP frame to the SVJ vehicle frame (position in metres, unit quaternion as in `orientation`, uniform `scale` applied *after* unit conversion, default 1). Units come from the STEP file itself, not from this field |
| `node_map` | Optional: SVJ node name → STEP instance label or `/`-separated path in the assembly tree. For CAD files where renaming the tree is not wanted |
| `tessellation` | Hints for baking/loading (metres and radians); never part of the physics |

`visual` blocks do **not change**: `mesh_ref` selects the entry, `node` stays the canonical
`SVJ::<category>::<id>`. For a STEP asset the node is resolved in this order:
1. `node_map[node]` if present;
2. a product or instance whose label equals `node` (CAD users can name items `SVJ::suspension::upper_wishbone_fl` directly);
3. otherwise unresolved — an error in the checker, a skipped part in a viewer.

`placement` (`rigid`, `link_between_points`) keeps its §22.6 meaning: `rigid` uses the instance
transform as authored in the assembly (the CAD design position), `link_between_points`
re-places the part's own product frame between the hardpoints.

### 4.2 Why this shape

- **No second binding system.** The binding stays `part → node name`; only the asset behind the name changes.
- **Honest about what STEP is.** The cache is the thing engines load; the STEP file is the editable source. Re-baking is a tool run, not a manual export.
- **Works without STEP support.** A consumer that ignores `format: "step"` and has a `cache` still works; one with neither skips the visuals (already the rule in §22).

### 4.3 Tooling

| Tool | Does | Needs |
|---|---|---|
| `tools/step_inspect.py` | Lists products and assembly paths of a STEP file; resolves every `visual` binding of an SVJ against it (`node_map`, label match, duplicates, un-decoded `\X2\` names) | Python only (text parser) |
| `tools/step_to_glb.py` | Tessellates the STEP, converts units, applies `transform`, renames nodes to the SVJ names, writes the glTF and updates `cache` / `source_sha256` | OpenCascade via CadQuery/OCP, or FreeCAD — optional |
| `integrity_check.py` | Extended: `format: "step"` entries validate `node_map` keys, `cache` existence and hash staleness | none |
| Viewer | Phase 1: use `cache`. Phase 2: optional direct STEP load through occt-import-js, off by default | WebAssembly build, loaded on demand |

### 4.4 Round trip with what already exists

The viewer's **Export STEP** writes the suspension geometry (hardpoints and links) as an AP203
wireframe, in mm and the SAE axes. That gives a loop: export the skeleton, model around it in
CAD, import the resulting assembly as the visual — the frame in §4.1 `transform` is then
mm + SAE, usually the identity after unit conversion. Reading hardpoints *back* out of CAD
(datum points or marker parts) is a separate idea and out of scope here.

## 5. Coordinates and units

- Unit conversion is read from the STEP file's own unit declaration (importers expose it), not guessed.
- `transform` bridges the frames. Without it a STEP model drawn with its origin elsewhere shows up displaced; a viewer should warn when the assembly's bounding box does not overlap the SVJ wheelbase envelope.
- STEP is right-handed, so no mirroring. Scale is uniform only.

## 6. Feasibility verdict

| Piece | Verdict |
|---|---|
| Binding by name through STEP product/instance labels | Feasible; needs the `node_map` escape hatch because CAD naming is messy |
| Name/structure checks without a CAD kernel | Feasible (text parsing) — unverified here, no sample STEP was available |
| Baking glTF from STEP | Feasible with OpenCascade; heavy optional dependency, tolerance tuning needed |
| Viewer reading STEP directly | Feasible via WebAssembly; costs download size, memory and a licence review. Recommended as optional, second phase |
| STEP as the only runtime visual format | Not recommended |

## 7. Risks and open questions

1. **IP.** STEP is exact production geometry. A shipped SVJ package could carry it unintentionally. Suggest the spec says that distributable files should ship the `cache`, not the STEP, and that `uri` may then be omitted when `cache` is present.
2. **Name stability.** CAD renames break `node_map`. The hash warns about a stale cache but not about renamed instances; `step_inspect.py` reports them.
3. **Colour.** Only AP214/AP242 carry it; AP203 files render in one colour. The baker should say so.
4. **Licence of occt-import-js** (listed LGPL-2.1) for a single-file viewer that would embed it — decide between embedding, loading from a URL on demand, or leaving STEP to the baker.
5. **Instance vs product.** A bolt used 40 times is one product; `node_map` needs an instance path to bind one of them. Is a path syntax (`ASSY/SUB<2>/PART`) enough?
6. **Scope.** Should `link_between_points` be supported for STEP at all in the first release, or rigid only?

## 8. Suggested phases

| Phase | Content | Exit criterion |
|---|---|---|
| 0 — spike | Get one real AP214 vehicle assembly (or generate one with FreeCAD/CadQuery); measure occt-import-js `.wasm` size, load time and memory; confirm the product-tree text parser on that file | Numbers and a parsed tree on a real file |
| 1 — schema, spec, checker | `format`, `cache`, `source_sha256`, `transform`, `node_map`, `tessellation`; `step_inspect.py`; checker rules | Examples with a hand-made STEP + glb pair validate |
| 2 — baker | `step_to_glb.py` | A STEP assembly becomes a glb that the existing viewer shows bound |
| 3 — viewer | Optional direct STEP load | Same model drawn from STEP and from cache, same placement |
