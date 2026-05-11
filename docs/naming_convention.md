# SVJ glTF Node Naming Convention

> **Status:** Adopted in SVJ v0.97  
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

### Categories

| Category | Meaning |
|----------|---------|
| `body`   | Primary rigid body (chassis, wheel, upright, etc.) |
| `helper` | Non-physical marker: suspension hardpoints, sensor origins, camera pivots |
| `lod`    | Level-of-Detail geometry variant of a body node |

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

For `helper` nodes the binding is looser — the name should be descriptive but does **not** need to match any SVJ id:

| Purpose | Example glTF node name |
|---------|----------------------|
| Front-left suspension hardpoint | `SVJ::helper::susp_anchor_fl` |
| Driver eye point | `SVJ::helper::driver_eyepoint` |
| Rear camera pivot | `SVJ::helper::cam_pivot_rear` |

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
1. Every `visual.node` follows the `SVJ::category::name` pattern.
2. For `body` and `lod` nodes, the `<name>` suffix matches the parent body `id`.
3. Every `visual.mesh_ref` points to an entry in `assets.meshes`.
4. No two bodies share the same `visual.node`.

---

## Rules Summary

1. Names must be unique within a glTF file.
2. Use `snake_case` — lowercase letters, digits, underscores only.
3. No spaces, hyphens, or special characters.
4. For `body` and `lod` nodes: `<name>` suffix **must** match the SVJ `body.id`.
5. For `helper` nodes: `<name>` should be descriptive; no id-matching requirement.
6. The `SVJ::` prefix is reserved — do not use it for non-SVJ nodes.

---

## Why This Matters

- **Deterministic parsing** — any tool can re-derive the binding from the name alone, no lookup table required.
- **Pipeline safety** — node re-ordering in a DCC tool cannot break the binding.
- **Multi-mesh support** — when a vehicle splits across several `.glb` files, the naming convention is the same; `mesh_ref` disambiguates the file.
- **Human-readable** — opening a glTF in any viewer instantly shows which nodes are physics-bound.
