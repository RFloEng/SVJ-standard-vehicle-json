# Changelog

All notable changes to the SVJ specification.

## [0.96] — 2026-05-05 — Multibody Topology Extension

Added explicit multibody topology for ADAMS/Car and Simpack compatibility. New `orientation` quaternion definition. Hardpoints now accept marker objects with position + orientation (backward-compatible with plain vec3). Links gain `joint_type`, `inboard_joint_type`, and `body_ref` fields. Bushings gain `orientation` and `preload`. Mass bodies gain `parent` and `markers`. Spring/damper mounts accept oriented marker form. All additions optional — existing v0.95 files remain structurally valid.

## [0.95] — 2026-04-19 — Aerodynamics Extension

Extended aerodynamics with 1D/2D maps, component-level modeling with cross-influences, wake/dirty air, ground effect, and active systems (DRS, PID-controlled wings). Added data_origin provenance field. Fixed example geometry (AWD EV, 2CV). Added F1 aero reference example.

## [0.94] — 2026-04-15 — Initial Public Release

First public release of the SVJ specification, schema, reference template, examples, viewer, and svj-py parser.
