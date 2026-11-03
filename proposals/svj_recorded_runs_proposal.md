# Proposal: recorded runs (time-varying data from simulators and tests)

**Status:** PARKED — not a priority. SVJ is a format for physics characteristics, with the JSON as its authority; time-varying recordings are outside that scope for now. Kept as a draft for later, nothing implemented · **Target:** additive, after v0.104 · **Origin:** an earlier version of `proposals/svj_openusd_vs_gltf_study.md` (what is lost today) · **Builds on:** §24.7 poses, §26 loop solver, §29 paths and setups, §11.13 tyre evaluator, `benchmarks` and `validation` (§7, §20b)

**Answer to the question that started it:** OpenUSD can store a recording (time samples on any attribute), but it is the wrong *primary* container for one. A recorded run is mostly scalar channels at a high rate; USD is good at animating a scene. Store the run in a small **companion descriptor** that binds channels to SVJ ids and units, with a pluggable data container; use USD only as an optional *export* for visual replay.

---

## 1. What is lost today

SVJ describes a vehicle in one configuration (§1) with poses (§24.7) as static snapshots. Nothing in the standard holds **what a simulator or a test produced over time**: speed, steering, slip angles, tyre forces, damper velocities, temperatures, wheel loads, joint coordinates, driver inputs. A converter that reads an Assetto Corsa or BeamNG session, or a test-rig log, has no place to put it, and the correlation fields (`validation`, `benchmarks`) can only carry summary numbers.

Uses that are blocked by the gap:

1. **Correlation**: compare a simulated run with a measured one on the same vehicle file (`validation.correlated_channels` names channels that no file contains).
2. **Model checks**: overlay a recorded `Fy` against the tyre evaluator (§11.13) at the recorded slip angle and load; check suspension travel against the solver (§26).
3. **Visual replay**: drive the viewer's poses (joint coordinates and wheel travel per frame) from a recording.
4. **Exchange**: hand a run from one tool to another without losing the vehicle it belongs to.

## 2. Requirements

- Channels **bound to SVJ ids and paths** (so a channel means a specific tyre, damper or joint of a specific file).
- **SI units and SAE axes**, declared per channel, like the rest of SVJ.
- Efficient for **long, high-rate** data (1 kHz for an hour is 3.6 million samples per channel).
- A **small reader**: someone can read a run without a large library.
- **Provenance**: which simulator and version, which vehicle file (and `setup`), which scenario, when.
- Carries **both** measured and simulated data, and says which.

## 3. Container options

| Option | For | Against | Verdict |
|---|---|---|---|
| **A. JSON arrays inside the SVJ file** | One file | Text arrays are huge and slow; mixes a vehicle description with data that changes every run | No |
| **B. OpenUSD time samples** | Typed, binary, time-sampled attributes; one stage can hold poses, forces and meshes together; native to Omniverse and Isaac-style simulators | Built for scene animation, not 1 kHz scalar channels; no telemetry schema, so it would be an SVJ-only convention; analysis tools (MoTeC, MATLAB, Python data stacks) do not read it; large dependency | Only as an **export for replay** |
| **C. ASAM MDF4** (`.mf4`) | The industry standard for recorded automotive data; ASAM lists version 4.3.0 (Sep 2025) ([ASAM](https://asam.net/standards/detail/mdf/)); channel groups, units, conversions, compression; open Python reader `asammdf` ([docs](https://asammdf.readthedocs.io/)) | Complex binary format, no 3D or vehicle semantics, channel naming is free (SVJ would still need a naming rule) | **Good data container**, selectable |
| **D. CSV** | Universal, every tool writes it | Untyped, no units in the file, large | Allowed as the simplest container |
| **E. Columnar binary** (for example Parquet) | Compact, typed, fast, wide tool support | Needs a library to read | Allowed |

No container is the answer on its own: what SVJ adds is the **binding**, and that is the same for all of them.

## 4. Recommendation: a run descriptor with a pluggable data file

A run is a small JSON file `*.svj-run.json` (like `*.svj-combination.json`) that points at the data:

```json
{
  "_metadata": { "format": "svj-run", "version": "0.105" },
  "vehicle": { "file": "mazda_mx5_nd2_2024.svj.json", "setup": "track" },
  "source": { "kind": "simulated", "tool": "assetto_corsa", "version": "1.16.4", "scenario": "skidpad_50m", "date": "2026-11-05T14:00:00Z" },
  "time": { "channel": "t", "unit": "s", "rate_hz": 1000 },
  "data": { "container": "csv", "file": "run_0042.csv" },
  "channels": [
    { "id": "t",        "unit": "s" },
    { "id": "speed",    "unit": "m/s",   "path": "chassis.velocity.x" },
    { "id": "steer",    "unit": "m",     "path": "joint[slide_rack].q" },
    { "id": "fz_fl",    "unit": "N",     "path": "wheel_stations[FL].fz" },
    { "id": "alpha_fl", "unit": "rad",   "path": "wheel_stations[FL].slip_angle" },
    { "id": "fy_fl",    "unit": "N",     "path": "wheel_stations[FL].fy" },
    { "id": "damper_fl","unit": "m/s",   "path": "constraints[damper_fl].velocity" }
  ],
  "events": [ { "t": 12.4, "label": "lap_start" } ]
}
```

- **`path`** uses the path syntax of §29.1 (ids in brackets), extended with a small **channel namespace** for derived or measured quantities that are not file values: `chassis.*` (position, velocity, acceleration, yaw rate), `wheel_stations[<id>].*` (`fz`, `fy`, `fx`, `mz`, `slip_angle`, `slip_ratio`, `camber`, `temperature`), `joint[<id>].q` (joint coordinate), `constraints[<id>].*` (element length, velocity, force), `driver.*` (steering, throttle, brake). The list is open: unknown paths are allowed and marked as such.
- **`data.container`**: `"csv"`, `"parquet"`, `"mdf4"` or `"inline"` (short runs, under a few thousand samples, as arrays in the descriptor). The descriptor is the contract; the container is a detail, the way `external_models` (§11.12) points at proprietary files.
- **`source.kind`**: `"measured"` or `"simulated"`; a correlation tool pairs one of each.
- **Units** are SI and the axes are SAE J670 as everywhere in SVJ; a converter must convert, not annotate.

## 5. What it enables in the tools

| Tool | Use |
|---|---|
| `tools/validate.py` | Check that every `path` resolves in the vehicle file (or is in the open namespace), units are SI, time is monotonic, the container file exists, channel counts match |
| `tools/tire_model.py` | `--run file` evaluates the tyre model at the recorded `Fz`, `slip_angle`, `slip_ratio`, `camber` and reports the error against recorded `Fy`, `Fx` |
| `tools/loop_solver.py` | Replays wheel travel from recorded `joint[...]` coordinates and compares camber and toe |
| `svj-py` | `Run` class: channels as arrays, resample, slice by event, `compare(measured, simulated)` |
| Viewer | **Replay**: a timeline drives the poses (joint coordinates, wheel travel) and shows channel plots next to the 3D view; overlay of two runs |
| `validation` / `benchmarks` | `validation.test_reference` may point at a run file instead of a note; benchmark values can be computed from it |

## 6. Where OpenUSD fits

An optional `tools/run2usd.py` could write the **kinematic part** of a run as a USD stage: body transforms (from the vehicle's joints and the recorded coordinates) as time samples over the vehicle's USD export (an optional external tool; USD never carries SVJ physics), for viewing in USD tools. It is a derived view, not the record: the channels stay in the run file. Reasons not to make USD the store:

- scalar channels at 1 kHz are not what USD time samples are for, and no analysis tool reads them there;
- it would add a heavy dependency to read a table;
- a USD telemetry schema would be an SVJ-only convention anyway, so it would buy no interoperability.

If a simulator ecosystem already produces USD recordings (an Omniverse replay, say), the **import** direction is worth a converter.

## 7. Risks and open questions

- **Channel namespace.** The standard names (`wheel_stations[FL].fz`) must be agreed with the people who write converters; too narrow a list makes everyone use unknown paths. Suggested rule: a short normative core list, open extension.
- **Sign and frame conventions for forces.** Tyre forces in tyre axes, vehicle axes or wheel-carrier axes? The descriptor should declare it per channel (`frame`: `"tyre"`, `"vehicle"`, `"hub"`), default `"tyre"` to match §11.13.
- **Time base.** Fixed rate or a time channel? Support both (`time.rate_hz` or `time.channel`).
- **Size limits of `inline`.** Cap it (for example 10 000 samples) so descriptors stay human-readable.
- **MDF4 mapping.** Whether to define how SVJ paths are stored in MDF channel names or comments; needs a short note with someone who uses MDF tools daily.
- **Privacy and licensing of recordings.** Recordings from commercial simulators may carry licence restrictions; `source` should allow a `licence` note.
- **Which simulators write what today** (Assetto Corsa shared memory and replays, BeamNG logs, iRacing, rFactor 2, test-rig exports): this decides the first converters and the core channel list; it is not established in this proposal.

## 8. Plan

1. **Spec §30** *Recorded runs*: descriptor format, channel namespace, containers, rules (≈ 2 pages) and a schema `svj-run.schema.json`.
2. **`tools/run_check.py`** (mirror in `svj-py`) and an example run with a small CSV for the MX-5 (a synthetic steady-state skidpad, clearly marked as such).
3. **`tools/tire_model.py --run`** correlation report.
4. **Viewer**: channel plots and a replay timeline.
5. Optional later: `run2usd.py`, MDF4 reader/writer through `asammdf`, converters from real simulators once the channel list is agreed.

Sources: [ASAM MDF](https://asam.net/standards/detail/mdf/) (version 4.3.0, Sep 2025, described as a binary format for recorded data); [asammdf](https://asammdf.readthedocs.io/) (open reader and writer). The statements about USD time samples and analysis-tool support come from general knowledge and the OpenUSD study; check them before a decision.
