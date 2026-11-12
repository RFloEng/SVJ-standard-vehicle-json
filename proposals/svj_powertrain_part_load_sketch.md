# Sketch: part-load engine torque, engine braking, shift points and torque converter

**Status:** implemented in v0.108 (spec §10.3.6, §10.4.1, §10.5.2, `tools/powertrain_check.py`). Decisions on the open questions of §7: linear interpolation in throttle plus measured `part_throttle[]`; no pedal map; CVT left out; tools only (no viewer port); electric motors keep regen. The "note" for a missing `torque_curve_closed` was dropped, since it would warn on every existing file.

**Origin:** a review of Project Chrono's Chrono::Vehicle powertrain models ([engines and transmissions](https://api.chrono.projectchrono.org/vehicle_powertrain.html)). Chrono describes an engine by two curves (full throttle and zero throttle), a gearbox by shift-point tables and a shift latency, and a torque converter by two curves against speed ratio. SVJ has none of these: `engine.torque_curve` is one curve, `gearbox` has `shift_time` only, and `clutch.type` may be `"torque_converter"` with no converter data.

**Principle (unchanged):** the JSON is the authority for the physics. These are physical data a simulator cannot guess, not labels.

## 1. Engine: part load and engine braking (§10.3)

Today `torque_curve` is read as the full-throttle curve (the spec does not say so; this sketch makes it explicit). A simulator has no data for a lifted throttle, so coasting, downshift braking and the overrun state are guesses.

| Key | Type | Description |
|-----|------|-------------|
| `torque_curve` | `[[rpm, Nm], ...]` | **Full (wide-open) throttle**, net torque at the crankshaft. Unchanged; the spec now says so |
| `torque_curve_closed` | `[[rpm, Nm], ...]` | **Closed throttle**, net torque: negative above idle (friction plus pumping losses). Engine braking |
| `part_throttle[]` | `[{ "throttle": 0.5, "curve": [[rpm, Nm], ...] }, ...]` | Optional measured curves at intermediate throttle, `throttle` strictly between 0 and 1, ascending |
| `inertia_block` | number (kg·m²) | Optional. Inertia of the engine block on its mounts (the reaction side; `inertia` stays the crank and flywheel) |

**Evaluation** (the spec would give it, like the tyre formulas). For throttle `th` in 0 to 1 and speed `n`: let the curves be ordered by throttle, with `torque_curve_closed` at 0 and `torque_curve` at 1; `T(n, th)` is the linear interpolation in torque between the two curves that bracket `th`, each curve read by linear interpolation in `n` and held flat outside its range. Without `part_throttle[]` this is `T = Tc(n) + th * (Tw(n) - Tc(n))`. Above `max_rpm` the limiter (§10.3.2) decides.

**No separate `losses_map`.** Chrono's shafts engine has an additive losses map. Here the closed-throttle curve *is* the net loss at zero throttle, and a second loss table would double-count it.

**Absent `torque_curve_closed`:** no engine braking is declared; a simulator chooses its own. The checker notes it for vehicles that declare a `gearbox`.

**Links to what exists:** `exhaust.overrun` and the `overrun` sound trigger (§10.3.5) fire on throttle lift; the closed-throttle torque gives the game the deceleration that goes with it. Electric motors keep their own regen (§14.5).

## 2. Gearbox: shift points and shifting (§10.5)

| Key | Type | Description |
|-----|------|-------------|
| `shift_time` | number (s) | Unchanged. Duration of the shift |
| `shift_latency` | number (s) | Optional. Delay between the decision and the start of the shift (auto, DCT) |
| `shift_points` | `[[up_rpm, down_rpm], ...]` | Optional, one pair per forward gear, in `ratios` order: engine speed to shift up, and to shift down *from* that gear. The last up value is unused. For `auto`, `dct`, and `sequential` with an automatic mode |
| `shift_points_vs_throttle` | `[{ "throttle": 0.3, "points": [[up, down], ...] }, ...]` | Optional. Same table at several throttle positions; interpolated linearly. Replaces `shift_points` when both are given |

Notes: the pairs must leave hysteresis (`down_rpm` of gear `k+1`, converted through the ratio step, below `up_rpm` of gear `k`), otherwise the gearbox hunts; the checker warns.

## 3. Torque converter (§10.4)

`clutch.type = "torque_converter"` gets a data object, `clutch.torque_converter`:

| Key | Type | Description |
|-----|------|-------------|
| `capacity_factor` | `[[speed_ratio, K], ...]` | `K = n_in / sqrt(T_in)` in rev/min per sqrt(Nm), against `speed_ratio = n_out / n_in` (0 to about 1) |
| `torque_ratio` | `[[speed_ratio, TR], ...]` | `TR = T_out / T_in`; 1 at the coupling point |
| `inertia_pump`, `inertia_turbine` | number (kg·m²) | Optional |
| `lockup` | `{ "min_gear": 2, "engage_speed_ratio": 0.85 }` | Optional. The lockup clutch locks input and output above that speed ratio in or above that gear |

**Evaluation.** With `sr = n_out / n_in`: `T_in = (n_in / K(sr))^2`, `T_out = TR(sr) * T_in`, efficiency `TR * sr`. Both curves are read by linear interpolation in `sr`. At the coupling point `TR = 1`, and `lockup` bypasses the converter.

The **stall speed** is not stored: it follows from `K(0)`, the engine torque curve and this evaluation, so a stored value could only contradict them.

## 4. Tools

- `tools/powertrain_check.py` (mirrored as `svj/powertrain.py`, run by `validate.py`, like `engine_check.py`): the evaluators `engine_torque(engine, rpm, throttle)` and `converter(n_in, n_out)`, and warnings.
- Warnings: `torque_curve_closed` above `torque_curve` at any speed; positive closed-throttle torque above idle; `part_throttle[]` out of order or not between 0 and 1; curve not ascending in rpm; `shift_points` count different from `ratios`; shift hysteresis violated; `torque_converter` data without `type: "torque_converter"` or the type without data (note); `capacity_factor` or `torque_ratio` not defined from `sr = 0`; `TR` below 1 at the high end without a `lockup`.
- Schema: the new properties with minimums and array shapes; version enum gets `0.108`.

## 5. Conversions

| From / to | Mapping |
|-----------|---------|
| Chrono `EngineSimpleMap` | `Map Full Throttle` is `torque_curve`, `Map Zero Throttle` is `torque_curve_closed`; one to one |
| Chrono `EngineShafts` | the torque map is `torque_curve`; its losses map is folded into `torque_curve_closed` (closed-throttle net torque); block and shaft inertias are `inertia_block` and `inertia` |
| Chrono automatic transmission | shift-point pairs are `shift_points`; latency is `shift_latency`; capacity-factor and torque-ratio maps are `torque_converter` one to one |
| Chrono frame | ISO (X forward, Y left, Z up) to SAE J670 (Y right, Z down): a fixed 180 degree rotation about X; this belongs in the converter notes |

## 6. Compatibility

All keys optional; existing engines and gearboxes stay valid. `torque_curve` keeps its meaning (the spec only states it). No data in an asset or elsewhere duplicates these.

## 7. Open questions

1. **Part-throttle shape.** Linear interpolation between the closed and wide-open curves is the default. A real engine is not linear in throttle (manifold pressure). Keep the default plus measured `part_throttle[]`, or define a throttle-to-load map?
2. **Pedal to throttle.** Drive-by-wire cars map the pedal to throttle nonlinearly. Out of scope here (a controller property), or a `pedal_map`?
3. **CVT and DCT.** `cvt` has ratios as a range, not a list; leave shift data out for it now?
4. **Viewer.** Add a JS port of the two evaluators to the viewer like the tyre one, or tools only?
5. **Electric motors.** §14 already has `torque_curve` and regen; is a zero-throttle (coasting) curve wanted there too, or is regen enough?
