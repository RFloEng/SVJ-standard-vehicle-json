# SVJ Multibody Topology Extension Proposal

## Document Information
- **Date:** 2026-05-05
- **Target Specification:** SVJ v0.96
- **Proposal Type:** Schema Extension (backward compatible)
- **Status:** Draft

---

## 1. Executive Summary

This proposal adds **explicit multibody topology** to SVJ, enabling direct exchange with professional multibody dynamics tools (ADAMS/Car, Simpack, MBD for ANSYS, etc.) while preserving full backward compatibility with existing SVJ files.

Instead of adding parallel top-level arrays (which would duplicate existing SVJ concepts), this proposal **extends** the existing suspension corner structure with three new optional features:

1. **Marker orientations** on hardpoints and mount points
2. **Explicit joint types** on links and connections
3. **Body references** linking suspension parts to chassis mass bodies

This means existing SVJ files remain valid, simpler tools keep working with hardpoints as before, and ADAMS-class converters get the explicit topology they need.

---

## 2. Problem Statement

### 2.1 What SVJ has today

SVJ v0.95 describes suspension topology through:
- **`system_type`** — declares the kinematic family (double_wishbone, macpherson, etc.)
- **`upright.hardpoints`** — 3D positions of key points (ball joints, wheel center)
- **`links`** — arms/rods/struts connecting inboard mount points to upright hardpoints
- **`bushings`** — compliance elements at mount points (scalar or 6-DOF stiffness)
- **`spring` / `damper`** — force elements with mount positions

This is sufficient for most game engines and simplified simulation tools. A converter can infer that a double-wishbone upper arm connects chassis to upright via a ball joint at `hardpoints.upper_ball_joint`.

### 2.2 What ADAMS/multibody tools need

Professional multibody tools require:

1. **Explicit joint types** — spherical, revolute, cylindrical, translational, universal, fixed, planar. SVJ implies these from system_type but never states them.
2. **Marker orientations** — a revolute joint needs an axis of rotation. A bushing stiffness matrix needs oriented reference frames. SVJ hardpoints are position-only `[x, y, z]`.
3. **Body definitions** — explicit rigid body declarations with mass, CG, and full inertia tensor. SVJ has `mass_body` in chassis but doesn't connect them to suspension parts.
4. **Topology graph** — which body connects to which other body, through which joint, at which markers. SVJ implies this but never makes it explicit.

### 2.3 Gap analysis

| Concept | SVJ v0.95 | ADAMS | Gap |
|---------|-----------|-------|-----|
| Body positions | `mass_bodies`, `upright.mass` | PART | No explicit link between them |
| Reference points | `hardpoints` (position only) | MARKER | Missing orientation |
| Connections | Implied from system_type + links | JOINT | No explicit joint type |
| Compliance | `bushing_obj` (6-DOF rates) | BUSHING | Missing oriented frame |
| Force elements | `spring`, `damper` | SFORCE/SPRINGDAMPER | Adequate |

---

## 3. Design Principles

1. **Extend, don't duplicate** — add fields to existing structures, not parallel arrays
2. **All additions optional** — existing files must remain valid without changes
3. **Named objects, not ID arrays** — follow SVJ convention of named keys in objects
4. **Orientation via quaternion** — compact, singularity-free, ADAMS-native
5. **Reference by path** — joints reference existing hardpoints and links by their SVJ path
6. **Solver-agnostic** — describe physics, not solver syntax

---

## 4. Schema Changes

### 4.1 New definition: `orientation`

A unit quaternion `[qx, qy, qz, qw]` defining the orientation of a marker frame relative to the vehicle frame. Defaults to identity `[0, 0, 0, 1]` (aligned with vehicle axes).

```json
"orientation": {
  "description": "Orientation as unit quaternion [qx, qy, qz, qw]. Default: [0,0,0,1] (identity).",
  "type": "array",
  "items": { "type": "number" },
  "minItems": 4,
  "maxItems": 4,
  "default": [0, 0, 0, 1]
}
```

### 4.2 Extended hardpoints (in `upright`)

Currently hardpoints are `"name": [x, y, z]`. Extended form allows either the simple vec3 or an object with position + orientation:

```json
"hardpoints": {
  "type": "object",
  "additionalProperties": {
    "oneOf": [
      { "$ref": "#/definitions/vec3" },
      {
        "type": "object",
        "required": ["position"],
        "properties": {
          "position": { "$ref": "#/definitions/vec3" },
          "orientation": { "$ref": "#/definitions/orientation" }
        }
      }
    ]
  }
}
```

This means existing files with `"upper_ball_joint": [0.0, -0.65, -0.44]` remain valid, while new files can use:
```json
"upper_ball_joint": {
  "position": [0.0, -0.65, -0.44],
  "orientation": [0, 0.707, 0, 0.707]
}
```

### 4.3 Joint type on links

Add an optional `joint_type` to each link, specifying how it connects to the upright:

```json
"joint_type": {
  "type": "string",
  "enum": [
    "spherical",
    "revolute",
    "cylindrical",
    "translational",
    "universal",
    "fixed",
    "planar",
    "convel",
    "hooke"
  ],
  "description": "Joint type at the outboard connection. If omitted, inferred from system_type."
}
```

And an optional `inboard_joint_type` for the chassis-side connection:

```json
"inboard_joint_type": {
  "type": "string",
  "enum": [
    "revolute",
    "spherical",
    "cylindrical",
    "fixed",
    "bushing"
  ],
  "description": "Joint type at the inboard connection(s). Default: revolute for arms, spherical for rods."
}
```

### 4.4 Body reference on upright and links

Add optional `body_ref` to connect suspension parts to chassis mass bodies:

On the **upright**:
```json
"body_ref": {
  "type": "string",
  "description": "Reference to a mass_body id in chassis.mass_bodies for this upright."
}
```

On each **link**:
```json
"body_ref": {
  "type": "string",
  "description": "Reference to a mass_body id in chassis.mass_bodies for this link."
}
```

### 4.5 Oriented bushings

Extend `bushing_obj` with an optional orientation for the stiffness frame:

```json
"bushing_obj": {
  "properties": {
    "orientation": { "$ref": "#/definitions/orientation" },
    "preload": {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 3,
      "maxItems": 3,
      "description": "Bushing preload forces [Fx, Fy, Fz] in N"
    }
  }
}
```

### 4.6 Oriented spring/damper mounts

Extend spring and damper mount points to accept orientation:

```json
"inboard_mount": {
  "oneOf": [
    { "$ref": "#/definitions/vec3" },
    {
      "type": "object",
      "required": ["position"],
      "properties": {
        "position": { "$ref": "#/definitions/vec3" },
        "orientation": { "$ref": "#/definitions/orientation" }
      }
    }
  ]
}
```

### 4.7 Extended mass_body definition

Add optional fields to `mass_body` for multibody tools:

```json
"mass_body": {
  "properties": {
    "parent": {
      "type": "string",
      "description": "Parent body id. Default: ground for chassis, chassis for components.",
      "default": "chassis"
    },
    "markers": {
      "type": "object",
      "description": "Named reference frames on this body.",
      "additionalProperties": {
        "type": "object",
        "required": ["position"],
        "properties": {
          "position": { "$ref": "#/definitions/vec3" },
          "orientation": { "$ref": "#/definitions/orientation" }
        }
      }
    }
  }
}
```

---

## 5. Complete Example

### 5.1 Existing SVJ (v0.95) — unchanged, still valid

```json
{
  "suspension": {
    "FL": {
      "topology": {
        "system_type": "double_wishbone",
        "upright": {
          "id": "upright_fl",
          "hardpoints": {
            "upper_ball_joint": [0.0, -0.65, -0.44],
            "lower_ball_joint": [0.0, -0.68, -0.14],
            "wheel_center": [0.0, -0.81, -0.33]
          }
        },
        "links": [
          {
            "name": "upper_wishbone",
            "type": "arm",
            "inboard_points": [[0.14, -0.3, -0.44], [-0.14, -0.3, -0.44]],
            "outboard_ref": "hardpoints.upper_ball_joint"
          },
          {
            "name": "lower_wishbone",
            "type": "arm",
            "inboard_points": [[0.2, -0.26, -0.14], [-0.18, -0.26, -0.14]],
            "outboard_ref": "hardpoints.lower_ball_joint"
          }
        ]
      }
    }
  }
}
```

### 5.2 Extended SVJ (v0.96) — same file with multibody topology added

```json
{
  "chassis": {
    "mass_bodies": [
      {
        "id": "chassis_body",
        "description": "Main chassis/frame",
        "category": "structural",
        "mass": 285.0,
        "position": [-1.48, 0.0, -0.35]
      },
      {
        "id": "upright_fl_body",
        "description": "Front-left upright/knuckle",
        "category": "structural",
        "mass": 8.2,
        "position": [0.0, -0.72, -0.29],
        "parent": "chassis_body",
        "inertia": {
          "Ixx": 0.045, "Iyy": 0.042, "Izz": 0.038,
          "Ixy": 0.0, "Ixz": 0.0, "Iyz": 0.0
        },
        "markers": {
          "upper_ball_joint": {
            "position": [0.0, -0.65, -0.44],
            "orientation": [0, 0, 0, 1]
          },
          "lower_ball_joint": {
            "position": [0.0, -0.68, -0.14],
            "orientation": [0, 0, 0, 1]
          }
        }
      },
      {
        "id": "upper_arm_fl_body",
        "description": "Front-left upper wishbone",
        "category": "structural",
        "mass": 2.8,
        "position": [0.0, -0.475, -0.44],
        "parent": "chassis_body",
        "inertia": {
          "Ixx": 0.012, "Iyy": 0.085, "Izz": 0.082,
          "Ixy": 0.0, "Ixz": 0.0, "Iyz": 0.0
        }
      },
      {
        "id": "lower_arm_fl_body",
        "description": "Front-left lower wishbone",
        "category": "structural",
        "mass": 3.5,
        "position": [0.01, -0.47, -0.14],
        "parent": "chassis_body",
        "inertia": {
          "Ixx": 0.015, "Iyy": 0.110, "Izz": 0.105,
          "Ixy": 0.0, "Ixz": 0.0, "Iyz": 0.0
        }
      }
    ]
  },
  "suspension": {
    "FL": {
      "topology": {
        "system_type": "double_wishbone",
        "upright": {
          "id": "upright_fl",
          "body_ref": "upright_fl_body",
          "mass": 8.2,
          "cg_position": [0.0, -0.72, -0.29],
          "inertia": {
            "Ixx": 0.045, "Iyy": 0.042, "Izz": 0.038
          },
          "hardpoints": {
            "upper_ball_joint": {
              "position": [0.0, -0.65, -0.44],
              "orientation": [0, 0, 0, 1]
            },
            "lower_ball_joint": {
              "position": [0.0, -0.68, -0.14],
              "orientation": [0, 0, 0, 1]
            },
            "wheel_center": [0.0, -0.81, -0.33],
            "tie_rod_outer": {
              "position": [-0.04, -0.66, -0.20],
              "orientation": [0, 0, 0, 1]
            }
          }
        },
        "links": [
          {
            "name": "upper_wishbone",
            "type": "arm",
            "body_ref": "upper_arm_fl_body",
            "joint_type": "spherical",
            "inboard_joint_type": "revolute",
            "inboard_points": [
              [0.14, -0.3, -0.44],
              [-0.14, -0.3, -0.44]
            ],
            "outboard_ref": "hardpoints.upper_ball_joint",
            "bushings": [
              {
                "rate_x": 80000,
                "rate_y": 25000,
                "rate_z": 25000,
                "orientation": [0, 0, 0, 1]
              },
              {
                "rate_x": 80000,
                "rate_y": 25000,
                "rate_z": 25000,
                "orientation": [0, 0, 0, 1]
              }
            ],
            "mass": 2.8,
            "cg_position": [0.0, -0.475, -0.44]
          },
          {
            "name": "lower_wishbone",
            "type": "arm",
            "body_ref": "lower_arm_fl_body",
            "joint_type": "spherical",
            "inboard_joint_type": "revolute",
            "inboard_points": [
              [0.2, -0.26, -0.14],
              [-0.18, -0.26, -0.14]
            ],
            "outboard_ref": "hardpoints.lower_ball_joint",
            "bushings": [
              {
                "rate_x": 120000,
                "rate_y": 40000,
                "rate_z": 40000,
                "orientation": [0, 0, 0, 1],
                "preload": [0, 0, 0]
              },
              {
                "rate_x": 120000,
                "rate_y": 40000,
                "rate_z": 40000,
                "orientation": [0, 0, 0, 1],
                "preload": [0, 0, 0]
              }
            ],
            "mass": 3.5,
            "cg_position": [0.01, -0.47, -0.14]
          }
        ]
      },
      "spring": {
        "type": "coil",
        "rate": 35000,
        "free_length": 0.28,
        "motion_ratio": 0.65,
        "inboard_mount": {
          "position": [0.02, -0.42, -0.55],
          "orientation": [0.087, 0, 0, 0.996]
        },
        "outboard_mount": {
          "position": [0.02, -0.50, -0.18],
          "orientation": [0.087, 0, 0, 0.996]
        }
      }
    }
  }
}
```

---

## 6. Mapping to ADAMS/Car

| SVJ Path | ADAMS Entity | Notes |
|----------|-------------|-------|
| `chassis.mass_bodies[id]` | `PART` | Each mass_body becomes an ADAMS part |
| `mass_body.markers.{name}` | `MARKER` on that part | Position + orientation to ADAMS marker |
| `upright.hardpoints.{name}.orientation` | `MARKER` orientation on upright part | |
| `link.joint_type` | `JOINT` type | spherical to SPHERICAL, revolute to REVOLUTE |
| `link.inboard_joint_type` | `JOINT` at chassis mount | |
| `link.bushings[i].orientation` | `BUSHING` pre-rotation | Stiffness axes alignment |
| `link.bushings[i].rate_*` | `BUSHING` stiffness | Maps directly |
| `spring` | `SPRINGDAMPER` or `SFORCE` | |
| `damper` | `SPRINGDAMPER` or `SFORCE` | |
| `upright.body_ref` | Links upright geometry to its PART | |

### Inference rules when multibody fields are absent

When an SVJ file omits the extended fields, an ADAMS converter should apply these defaults:

| system_type | Link | Outboard joint | Inboard joint |
|-------------|------|---------------|---------------|
| double_wishbone | upper arm | spherical | revolute |
| double_wishbone | lower arm | spherical | revolute |
| double_wishbone | tie rod | spherical | spherical |
| macpherson | strut | translational | fixed |
| macpherson | lower arm | spherical | revolute |
| trailing_arm | arm | revolute | revolute |
| multi_link | any link | spherical | revolute |
| solid_axle | - | - | - (special) |

---

## 7. Backward Compatibility

**No existing file breaks.** Every addition is optional:

- Hardpoints: `[x,y,z]` still accepted (parsed as position-only, identity orientation)
- Links: `joint_type` and `inboard_joint_type` omitted means inferred from `system_type`
- Bodies: `body_ref` omitted means no explicit body association (simple tools ignore it)
- Bushings: `orientation` omitted means identity (aligned with vehicle axes)
- Mass bodies: `parent` and `markers` omitted means works exactly as today

A "simple" converter (game engine, basic sim) reads exactly what it reads today and ignores the new fields. An "advanced" converter (ADAMS, Simpack) reads the extended fields when present, falls back to inference when absent.

---

## 8. Schema impact summary

| Change | Type | Location |
|--------|------|----------|
| Add `orientation` definition | New definition | `definitions.orientation` |
| Hardpoints accept object form | Modify `oneOf` | `suspension_corner.topology.upright.hardpoints` |
| Add `joint_type` to links | New optional property | `suspension_corner.topology.links[].joint_type` |
| Add `inboard_joint_type` to links | New optional property | `suspension_corner.topology.links[].inboard_joint_type` |
| Add `body_ref` to upright | New optional property | `suspension_corner.topology.upright.body_ref` |
| Add `body_ref` to links | New optional property | `suspension_corner.topology.links[].body_ref` |
| Add `orientation` to bushing_obj | New optional property | `definitions.bushing_obj.orientation` |
| Add `preload` to bushing_obj | New optional property | `definitions.bushing_obj.preload` |
| Add `parent`, `markers` to mass_body | New optional properties | `definitions.mass_body` |
| Extend spring/damper mounts | Modify `oneOf` | `suspension_corner.spring/damper.inboard_mount` |

**Total: 10 changes, 0 breaking.**

---

## 9. What this does NOT cover

The following are explicitly out of scope for this proposal:

- **Flexible bodies** (FE meshes, modal bodies) — future extension
- **Contact geometry** (tire-road, bump stop contact) — already handled by tire models
- **Solver settings** (step size, integrator type) — not SVJ's role
- **Subsystem templates** (ADAMS .tpl files) — SVJ describes physics, not tool workflow
- **Constraints** (motion drivers, position constraints) — solver-specific
