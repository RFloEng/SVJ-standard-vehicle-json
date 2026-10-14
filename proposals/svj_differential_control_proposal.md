# Proposal: differential control and centre couplings

**Status:** revised, being implemented · **Target:** v0.99.3 (additive; same patch-level policy as v0.99.2) · **Origin:** AC → SVJ converter audit

> Revision notes (vs. the first draft): `coupling.type` removed (it duplicated
> `transfer_case.type`) and replaced by an optional `mechanism`; `primary_axle` deferred;
> `filter` replaced by a time constant in seconds; separate power/coast chains are allowed
> (`lock_control` may be an array); units of every input and of `min`/`max` are now stated;
> the checker rules are split into what the schema enforces and what only a script can.

## 1. Why

Auditing the Assetto Corsa → SVJ converter against the 1,398 AC cars installed on the
reference machine showed that the SVJ powertrain schema covers the *static* description
of a differential well (`type`, `preload`, `lock_power`, `lock_coast`, `ramp_angle_*`,
`transfer_case.torque_split`, `transfer_case.center_diff`) but has no way to express two
things that real and simulated AWD drivelines use:

1. a **dynamic lock** — the lock of a (centre) differential that is *modulated* by the
   driving state (gear, brake, axle speed ratio, …) instead of being a constant;
2. a **torque-limited centre coupling** — AWD systems with no fixed split, where the
   centre transmits torque up to a limit (Haldex-style / on-demand couplings).

Both were found in AC data and had to be parked under the converter's extension block.
This proposal gives them a standard home so the information survives a conversion and
other tools (simulators, viewers) can use it.

## 2. What already maps (no change needed)

| AC (`drivetrain.ini`) | SVJ | Notes |
|---|---|---|
| `[TRACTION] TYPE` RWD / FWD / AWD / AWD2 | `powertrain.layout`, `vehicle_info.drive_type` | AWD2 → `AWD` |
| `[GEARS] GEAR_n`, `FINAL`, `GEAR_R` | `gearbox.ratios`, `differentials[].final_drive`, `gearbox.reverse_ratios` | AC writes the reverse ratio negative; SVJ stores its magnitude |
| `[CLUTCH] MAX_TORQUE` | `clutch.max_torque` | |
| `[DIFFERENTIAL] POWER / COAST / PRELOAD` | `differentials[].lock_power / lock_coast / preload` | single diff (RWD/FWD) |
| `[AWD] FRONT_DIFF_* / REAR_DIFF_*` | `differentials[]` with `location: front / rear` | one entry per axle |
| `[AWD] FRONT_SHARE` | `transfer_case.torque_split = [front, 1 - front]` | AC writes a percentage (47) in 471 of 505 cars, a fraction in the rest |
| `[AWD] CENTRE_DIFF_*` | `transfer_case.center_diff` | |

## 3. Gaps and proposed additions

### 3.1 `lock_control` — a dynamic differential lock

**Evidence.** 102 AC cars ship `ctr_awd_center_lock.ini`, a list of controllers that
modulate the centre-diff lock. Each controller reads an `INPUT` (`GEAR`, `BRAKE`,
`REAR_SPEED_RATIO`; the file's comments also list `OVERSTEER_FACTOR` and
`SLIPANGLE_FRONT/REAR_AVERAGE/MAX`), maps it through a LUT, and combines the result with
`MULT` or `ADD`, with a `FILTER` and `UP_LIMIT` / `DOWN_LIMIT`. Example (Subaru Impreza GrA):
gear → multiplier curve (12.8 at 1st … 4.2 at 6th, i.e. the overall ratio), brake → multiplier
(1 → 0, the lock opens under braking), gear → additive start lock, rear/front speed ratio →
additive lock.

**Proposal.** An optional `lock_control` on `differential_full` and `differential_obj`
(therefore also on `transfer_case.center_diff`). It is either one **chain** or an **array of
chains** with different targets (this answers the "separate power and coast chains" question:
use two chains, one with `target: "lock_power"` and one with `target: "lock_coast"`).

```json
"lock_control": {
  "target": "lock",
  "stages": [
    { "input": "gear",  "combine": "multiply", "curve": [[1,12.81],[2,9.91],[3,7.20]],
      "filter_time_constant": 0.0, "min": 0.0, "max": 1000.0 },
    { "input": "brake", "combine": "multiply", "curve": [[0,1],[1,0]],
      "filter_time_constant": 0.1 }
  ]
}
```

| Key | Type | Description |
|---|---|---|
| `target` | string | What is modulated: `"lock"` (shorthand: the same chain drives both `lock_power` and `lock_coast`), `"lock_power"`, `"lock_coast"`, `"preload"` |
| `stages[]` | array (≥ 1) | Applied in order. The running value starts at the static value of the target (0 if absent) |
| `stages[].input` | string | Controller input, see the table below; other names allowed with an `x_` prefix |
| `stages[].combine` | string | `"multiply"` (`v = v · y`) or `"add"` (`v = v + y`) |
| `stages[].curve` | `curve2d` | Input value → stage output `y`; reuses the existing `curve2d` definition. Evaluated by linear interpolation, clamped at both ends |
| `stages[].filter_time_constant` | number (s) | First-order low-pass time constant applied to the stage output `y`; 0 or absent = no filtering |
| `stages[].min`, `max` | number | Clamp of the running value after the stage, **in the unit of the target** |

**Units.** `lock_power`/`lock_coast` are dimensionless fractions 0–1 and `preload` is in Nm
(as today). The running value may leave that range between stages (a gear multiplier of 12.8
is legal); the **final** value is clamped to the target's valid range (0–1 for the locks,
≥ 0 for the preload) before it is used. `min`/`max` are in the same unit as the running value.

**Inputs.**

| `input` | Unit | Meaning |
|---|---|---|
| `gear` | index | Engaged gear, 1-based; reverse is `-1`, neutral `0` |
| `brake` | 0–1 | Brake pedal position |
| `throttle` | 0–1 | Throttle pedal position |
| `speed` | m/s | Vehicle speed |
| `rear_speed_ratio` | – | Rear axle speed ÷ front axle speed |
| `oversteer_factor` | – | Simulator-defined oversteer indicator (dimensionless) |
| `slip_angle_front`, `slip_angle_rear` | rad | Axle-average slip angle |

`lock_control` is only meaningful with `type` `lsd_clutch`, `lsd_torsen`, `lsd_viscous` or
`active`. A differential without it keeps today's constant lock.

*To confirm against AC before the converter promotes `x_lock_control` to `lock_control`:* the
evaluation order, the meaning and units of AC's `FILTER` coefficient (it is converted to
`filter_time_constant` only once known; until then the raw value stays in the extension
block), and the units of `UP_LIMIT` / `DOWN_LIMIT` and of AC's slip-angle inputs.

### 3.2 `transfer_case.coupling` — torque-limited centre coupling

**Evidence.** 35 AC cars use `TYPE=AWD2` (95 carry an `[AWD2]` section); their centre is
described by `CENTRE_RAMP_TORQUE` and `CENTRE_MAX_TORQUE` (e.g. Porsche 993 C4: 40.9 / 816.6 Nm,
Lamborghini Diablo VT: 103 / 610.7 Nm) instead of a fixed `FRONT_SHARE`. These are
rear-biased cars with a coupling feeding the front axle.

**Proposal.** An optional `coupling` object on `transfer_case`. Its presence means the centre
is an on-demand coupling, so it is used together with `transfer_case.type: "on_demand"`
(that field stays the single place that says *what kind of transfer case this is*).

```json
"transfer_case": {
  "type": "on_demand",
  "coupling": { "mechanism": "clutch_pack", "ramp_torque": 40.9, "max_torque": 816.6 }
}
```

| Key | Type | Description |
|---|---|---|
| `max_torque` | number (Nm) | **Required.** Maximum torque the coupling transmits |
| `ramp_torque` | number (Nm) | Torque at which the coupling starts to engage; must not exceed `max_torque` |
| `mechanism` | string | Optional: `"viscous"`, `"clutch_pack"`, `"electronic"`. Omitted when unknown (AC does not state it) |

`torque_split` stays the nominal split and may be omitted when `coupling` is present.

### 3.3 Rarer parameters — deferred

AC also has `[DIFFERENTIAL] RAMP_POWER / RAMP_COAST / RAMP_LOCK_LUT` (4 cars) and
`VISCOUS_FACTOR_1 / _2 / _EXP / _EXP_K` (1 car). Their semantics are not documented and the
population is tiny, so they remain in the converter's extension block
(`x_assettocorsa.drivetrain.differential_extra`). Revisit if more sources need them.

Also deferred: `coupling.primary_axle` (which axle is driven directly). AC does not provide
it, so nothing would populate it; add it when a source does.

## 4. Validation

**Enforced by the JSON Schema** (no script needed): `target`, `combine` and `mechanism`
enums; `input` is a known name or starts with `x_`; `stages` has at least one entry; `curve`
is a `curve2d` (at least two points); `filter_time_constant ≥ 0`; `coupling.max_torque > 0`.

**Checked by `tools/drivetrain_check.py`** (run by `tools/validate.py`; mirrored in
`svj-py/svj/drivetrain.py`):

| # | Rule | Severity |
|---|---|---|
| 1 | `stages[].curve` x values strictly increasing | error |
| 2 | In a `lock_control` array, targets are unique and `lock` is not combined with `lock_power`/`lock_coast` | error |
| 3 | `stages[].min` ≤ `stages[].max` when both are present | error |
| 4 | `lock_control` on a differential of `type` `open`, `locked` or `spool` | warning |
| 5 | `coupling.ramp_torque` ≤ `coupling.max_torque` | error |
| 6 | `transfer_case.type: "on_demand"` with neither `torque_split` nor `coupling` | warning |
| 7 | `coupling` on a `transfer_case.type` of `full_time` or `part_time` | warning |

## 5. Migration

Everything is additive; existing files stay valid. Until the standard adopts it, the AC → SVJ
converter writes the proposed shapes under extension keys, so promoting them is a rename
(plus the `FILTER` → `filter_time_constant` conversion once AC's semantics are confirmed):

| Now (converter output) | After adoption |
|---|---|
| `…center_diff.x_lock_control` | `…center_diff.lock_control` |
| `transfer_case.x_coupling` | `transfer_case.coupling` |

The raw AC values stay in `x_assettocorsa.drivetrain` either way.

## 6. Open questions

1. Is a flat list of stages enough, or do some simulators need branching (one stage reading
   the output of another)? Parallel power/coast chains are covered by the array form.
2. AC's `FILTER` semantics (decides whether a lossless conversion to a time constant exists).
3. Slip-angle input units in AC's controllers (rad assumed here).
