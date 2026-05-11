# SVJ Changelog

---

## AC → SVJ Converter  v0.9.1  (tools/ac_converter/)

### Summary

Converter v0.9.1 targets SVJ v0.97. All physics output is fully backward-compatible with v0.96. This release consolidates six months of improvements across the KN5 mesh pipeline, tire model, and physics parsers.

### New in this release

**Ephemeral-mesh transparency** (`kn5_reader.py`)
Blur-rim discs (`RIM_BLUR_*`, `rim blur lf/rf/lr/rr`) and damage panels (`damage`, `dent`, `bent`, `crash`, `deform`) are now rendered fully transparent in the exported GLB (`baseColorFactor=[0,0,0,0]`, `alphaMode=BLEND`). Previously these meshes were visible at rest, making every car look crashed or spinning.

**Bimodal alpha detection** (`kn5_reader.py`)
Materials with `blend_mode=1` are now classified as `MASK` (alpha cutout) or `BLEND` (true transparency) by inspecting the diffuse texture: if ≥85 % of alpha pixels are near-0 or near-255, the surface is a hard-edge cutout and gets `MASK`/`alphaCutoff=0.5`. Fixes grilles, belts, and licence-plate meshes that previously rendered as semi-transparent blobs.

**Front-axle Z alignment** (`kn5_reader.py`)
The GLB exporter now locates the front-axle hub nodes (`HUB_LF`/`HUB_RF`) in the KN5 node tree, derives their world-space Z coordinate, and inserts a root wrapper node with `translation=[0, 0, front_axle_z]`. This aligns the mesh so the front axle sits at Three.js Z = 0, matching the SVJ physics skeleton without any manual offset.

**Multi-LOD GLB export** (`kn5_reader.py`, `converter.py`)
`find_car_kn5_lods()` discovers all LOD KN5 files (`<stem>_LOD_B/C/D.kn5`) alongside the primary LOD A. `kn5_all_lods_to_glbs()` exports one GLB per LOD. The SVJ `assets.meshes` array lists all LODs with `"lod"` labels. Batch and single-car modes both include LOD GLBs in their ZIP output.

**Pacejka MF 6.2 block** (`tire_lab.py`, `converter.py`)
The virtual bench now fits and emits both MF 5.2 and MF 6.2 Pacejka blocks per tire set. MF 6.2 extends MF 5.2 with: camber vertical shift (`pVy3 = −CAMBER_GAIN`), full pressure-term placeholders (`pPy*`, `pPx*`), and representative combined-slip coefficients (`rBx`, `rBy`, `rCx`, `rCy`, etc.). The SVJ schema-standard key `pacejka` now carries the MF 6.2 block; the MF 5.2 block is retained at `pacejka_mf52` for simulators that only support the older format.

**MF 6.2 plots** (`tire_lab.py`)
Two new diagnostic plots: (1) `mf62_lateral_png` — AC vs MF 6.2 overlay at all Fz / camber levels with a camber-split residual cloud; (2) `mf62_camber_png` — camber sensitivity and thrust comparison at three load levels, demonstrating that `pVy3` correctly captures AC's linear camber thrust. Both are rendered in the Tire Lab tab.

**`data_origin` provenance block** (`converter.py`)
`_metadata.data_origin` is now always emitted (`type:"simulation"`, `detail` from `open_car` source note, `confidence:"medium"` for unpacked `data/`, `"low"` otherwise). Satisfies SVJ 0.95 §1.

**Encrypted-car detection** (`acd_reader.py`, `converter.py`, batch)
When a car ships with only `data.acd` (no unpacked `data/`), the loader returns an empty ini map with a clear "needs unpack" note instead of silently producing an empty SVJ. Single-car and batch modes surface a user-readable Content Manager unpack workflow. Batch writes `skipped.txt` listing all encrypted cars.

**Batch-only UI** (`converter.py`)
The Gradio interface is now one tab (batch conversion) plus one tab (Tire Lab). The former per-file upload tab was removed to keep the workflow focused: use batch for folders, Tire Lab for single-tyre inspection.

**Degenerate-axle NaN guard** (`tire_lab.py`, `converter.py`)
When a tyre section yields a degenerate sweep (all Fy or Fx values identical — e.g. truck axles with zero lateral stiffness), the R² is reported as `NaN` rather than crashing. `_clean()` in `converter.py` converts all non-finite floats to `null` so the JSON output is always strict-spec compliant.

### Changed Files

| File | Change |
|------|--------|
| `tools/ac_converter/kn5_reader.py` | Ephemeral transparency; bimodal alpha; front-axle alignment; multi-LOD export |
| `tools/ac_converter/tire_lab.py` | MF 6.2 block + plots; NaN guard; `build_svj_pacejka_blocks()` dual-output API |
| `tools/ac_converter/converter.py` | MF 6.2 wired in; data_origin; batch-only UI; LOD GLBs in ZIP; NaN clean |
| `tools/ac_converter/ac_parsers.py` | Full engine/drivetrain/brakes/aero/suspension/electronics/setup parsers |
| `tools/ac_converter/acd_reader.py` | Encrypted-car detection and clear user guidance |

---

## v0.97 — glTF Visual Binding Layer

### Summary

v0.97 adds an optional glTF visual binding system on top of the existing physics data format. The physics schema is fully backward-compatible — all v0.96 files are valid v0.97 files without any changes.

### New Features

**Flexible coordinate system declaration** (`_metadata.coordinate_system`)  
The field now accepts either a named standard string (`"SAE_J670"`, `"ISO_8855"`, `"OpenDRIVE"`) or a custom axis-specification object:
```json
"coordinate_system": { "up": "Y", "forward": "-Z", "handedness": "right" }
```
This allows glTF assets (which default to Y-up, -Z-forward in Blender/DCC tools) to be described without ambiguity alongside the SAE physics data.

**Flexible units declaration** (`_metadata.units`)  
Now accepts `"SI"` (unchanged default), `"meters"`, or `"millimeters"`. Useful when interoperating with glTF pipelines that work in millimeters.

**Asset manifest** (`assets.meshes`)  
New optional top-level block listing the glTF mesh files a vehicle uses:
```json
"assets": {
  "meshes": [
    { "id": "chassis_body", "uri": "meshes/car.glb" }
  ]
}
```
Each entry has a stable `id` (referenced from `visual.mesh_ref`) and a relative URI.

**Visual binding** (`visual` property on body objects)  
Chassis, mass-decomposition bodies, and suspension uprights now accept a `visual` object that binds them to a specific glTF node using the `SVJ::category::name` naming convention:
```json
"visual": {
  "mesh_ref": "chassis_body",
  "node": "SVJ::body::chassis"
}
```
See `docs/naming_convention.md` for the full convention specification.

**`tools/integrity_check.py`**  
New CLI tool that validates all visual bindings in an SVJ file: pattern compliance, id-suffix matching, mesh_ref validity, and node uniqueness. Exits non-zero on errors; use `--strict` to also fail on warnings.

### Changed Files

| File | Change |
|------|--------|
| `schema/svj.schema.json` | Patched `_metadata.coordinate_system` and `_metadata.units`; added `assets` property and `visual_binding` definition; added `visual` to `chassis`, `mass_body`, and `suspension_corner` |
| `examples/formula_f1_2025_aero.svj.json` | Updated to v0.97 — adds `assets` block and `visual` bindings on chassis, uprights, and aero components |
| `docs/naming_convention.md` | New |
| `tools/integrity_check.py` | New |

### Backward Compatibility

All `_metadata.version: "0.96"` files validate against the v0.97 schema without changes. The new fields (`assets`, `visual`) are optional throughout.

To opt into the new version string, change `_metadata.version` from `"0.96"` to `"0.97"`.

---

## v0.96

Initial public release. See `README.md` for the full feature list.
