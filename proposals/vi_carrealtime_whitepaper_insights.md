# Insights from VI-Grade "VI-CarRealTime" White Paper — Applicability to SVJ

## Document Information
- **Date:** 2026-09-16
- **Source:** VI-Grade white paper, "The Central Role of Real-Time Vehicle Models in Digital Engineering" (VI-CarRealTime)
- **Target Specification:** SVJ v0.97 → v0.98
- **Proposal Type:** Review + 3 schema-extension proposals (backward compatible)
- **Status:** Implemented in v0.98 (spec, schema, tools, examples)

---

## 1. Context

The source document is a marketing white paper for VI-CarRealTime, a commercial **real-time simulation environment** (a running tool: solvers, HiL, cloud campaigns, optimization studios). SVJ is a different kind of thing — a **static data interchange format** for describing a vehicle. Most of the white paper's claimed strengths (solver speed, cloud scaling, driving-simulator integration, DOE campaign orchestration) are tooling/workflow concerns that sit *outside* a file format and don't map onto SVJ at all. No attempt is made here to import those.

That said, three of the white paper's five "strengths" describe *data-modeling* problems that SVJ, as a format, legitimately has a stake in — because they're about what has to be encoded in the exchanged file for the workflow to work, not about the solver. Those are the actionable items below.

## 2. What doesn't transfer (and why)

- **Solver performance / fast prediction** — an implementation property of a real-time engine, not something a JSON description can provide.
- **Cloud scaling / parallel DOE campaigns, HiL/DiL, driving simulators** — deployment/runtime concerns. SVJ already supports this indirectly: a validated SVJ file is the thing you'd feed into such a pipeline, nothing to add.
- **K&C Wizard / VI-Animator-style benchmarking tools** — these are applications that would *consume* SVJ data; not a schema concern.

## 3. What does transfer — three proposals

### 3.1 `validation` block — correlation status against physical test

The white paper repeatedly frames "virtual sign-off" as trust built on **model-to-test correlation** ("Models are validated against real-world data, ensuring correlation with physical tests"). SVJ already has provenance at the field level (`_est: true`, `_source` strings — see PROJECT_BRIEF "Design Decisions") but has **no vehicle-level record of whether/how the assembled model was correlated against a physical car**. Two SVJ files with identical topology are currently indistinguishable in terms of trustworthiness.

Proposed addition, optional, at top level (sibling of `_metadata`):

```json
"validation": {
  "status": "correlated",
  "method": "physical_test",
  "test_reference": "Skidpad 2026-03, Jerez, run log SK-0417",
  "correlated_channels": ["lateral_accel", "yaw_rate", "roll_angle"],
  "correlation_quality": "good",
  "date": "2026-03-12",
  "notes": "Correlated at 0.85g steady-state; not validated for transient >0.9g"
}
```

`status` enum: `"unvalidated"`, `"simulation_only"`, `"correlated"`, `"partially_correlated"`. Everything else free-text/optional — this is a record, not a computation. Backward compatible (whole block optional); costs nothing for simple consumers, gives professional pipelines (which is the audience that cares about virtual sign-off) something to gate on.

### 3.2 `overrides` — lightweight variant/delta files for design exploration

The white paper's "override file system simplifies model variations, allows suppliers to work on encrypted versions, and prevents unnecessary duplication" describes a real gap. SVJ today has two file mechanisms:
- Full inline file (everything)
- `$ref` to a **complete** external module (§3.2)

There's no way to say "take `baseline.svj.json` and change just `suspension.FL.spring.rate` and three damper curves" without either duplicating the whole corner object or hand-rolling a merge script. This is exactly the workflow DOE/optimization studies and supplier hand-offs need (vary one subsystem, keep everything else pinned, keep the diff reviewable).

Proposed addition — a sibling file type, `*.svj-override.json`, applied with JSON-Merge-Patch (RFC 7396) semantics on top of a base file:

```json
{
  "_metadata": {
    "specification": "SVJ-OVERRIDE",
    "version": "0.97",
    "base": "./mazda_mx5_nd2_2024.svj.json",
    "description": "Stiffer front spring, DOE variant 3"
  },
  "patch": {
    "suspension": {
      "FL": { "spring": { "rate": 32000 } },
      "FR": { "spring": { "rate": 32000 } }
    }
  }
}
```

A conforming tool resolves `base` (same relative-path rule as `$ref`), then applies `patch` as a merge-patch over the resolved document. This is additive (new file type, doesn't touch `svj.schema.json` for the core vehicle) and directly supports parameter-study workflows without inventing a new diff format — RFC 7396 is a formal standard, which fits SVJ's "validatable" principle.

*(Out of scope: the white paper's "encrypted versions" for IP protection. SVJ is plaintext JSON by design — see naming/design principles: "no binary blobs, no encoded arrays." Encryption belongs at the transport/storage layer, not the schema. Worth a one-line note in the spec that an `overrides` file lets a supplier ship *only the delta* they're allowed to disclose, which already solves most of the practical IP-sharing problem without touching encryption.)*

### 3.3 `benchmarks` — standardized KPI targets on the vehicle

"Performance is measured with consistent KPIs, standardized benchmarks, and automatic reporting" — again a tooling feature, but it implies the KPI *targets/results* need to travel with the vehicle model to be useful across a distributed team. SVJ has no place to record e.g. "target skidpad 0.95g" or "measured 0–100 km/h: 6.2 s" alongside the model that's supposed to reproduce them.

Proposed addition, optional, top-level:

```json
"benchmarks": [
  { "id": "skidpad_lateral_g", "value": 0.95, "unit": "g", "type": "target" },
  { "id": "accel_0_100kph", "value": 6.2, "unit": "s", "type": "measured", "source": "factory spec sheet" }
]
```

Free-form `id` (not an enum — this deliberately mirrors `x_` extension philosophy of "explicit over implicit, but don't over-constrain"), each entry tagged `target` vs `measured` vs `simulated`. This gives downstream tools (including a real-time environment like the one in the white paper) a standard place to check simulation output against, instead of every team inventing its own side-channel spreadsheet.

## 4. Recommendation

All three are additive, optional, and don't touch existing required fields or the 10 load-bearing design decisions in `SVJ_PROJECT_BRIEF.md`. Suggested order if accepted: `benchmarks` and `validation` are trivial schema adds (a few lines in `svj.schema.json`, one section each in `SVJ_Spec.md`); `overrides` is a new file-type convention and needs its own short spec section (§3.4) plus a small example under `examples/` or `proposals/` and a mention in `tools/validate.py` (validate the patch target separately from the base).

## 5. Implementation notes (v0.98)

All three landed as described in §3, with one refinement: `overrides` became a formal file type with its own tiny schema and validator rather than just a spec note, since "validate the patch target separately from the base" (§4) turned out to be a two-step job worth automating:

- `spec/SVJ_Spec.md` §3.4 (override files), §20a (`validation`), §20b (`benchmarks`)
- `schema/svj.schema.json` — `validation` and `benchmarks` properties; `_metadata.version` enum extended to `0.98`
- `schema/svj-override.schema.json` — new, structural schema for `*.svj-override.json`
- `tools/validate_override.py` — new, resolves `base` + RFC 7396 merge `patch` and validates the result against the standard schema
- `tools/validate.py` — version-advisory bumped to `0.98`
- `examples/bmw_e30_325i_semi_trailing.svj.json` — bumped to v0.98, now carries `validation` (status `partially_correlated`) and `benchmarks` (skidpad target, 0–100 measured)
- `examples/bmw_e30_325i_stiffer_front.svj-override.json` — new, +20% front spring rate as an override of the above

All example files re-validated clean (`tools/validate.py`, `tools/validate_override.py`).

## 6. Explicitly not recommended

- FMI/FMU export — belongs in a converter/tool repo, not the data spec.
- MiL/SiL/HiL/DiL "single model across stages" — SVJ already *is* that single source; no schema change implied.
- Cloud/parallel campaign scaling — deployment concern, zero schema surface.
