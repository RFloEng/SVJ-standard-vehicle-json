# Proposal: differential control and centre couplings

**Status:** draft for discussion · **Target:** additive minor release after v0.99.2 · **Origin:** AC → SVJ converter audit

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

**Proposal.** An optional `lock_control` object on `differential_full`, `differential_obj`
(therefore also `transfer_case.center_diff`):

```json
"lock_control": {
  "target": "lock",
  "stages": [
    { "input": "gear",  "combine": "multiply", "curve": [[0,1],[1,12.81],[2,9.91]],
      "filter": 0.9, "min": 0.0, "max": 1000.0 },
    { "input": "brake", "combine": "multiply", "curve": [[0,1],[1,0]], "filter": 0.9 }
  ]
}
```

| Key | Type | Description |
|---|---|---|
| `target` | string | What is modulated: `"lock"` (both `lock_power` and `lock_coast`), `"lock_power"`, `"lock_coast"`, `"preload"` |
| `stages[]` | array | Applied in order, starting from the static value of the target |
| `stages[].input` | string | Controller input: `gear`, `brake`, `throttle`, `speed`, `rear_speed_ratio`, `oversteer_factor`, `slip_angle_front`, `slip_angle_rear`; other names allowed with an `x_` prefix |
| `stages[].combine` | string | `"multiply"` (`v = v · y`) or `"add"` (`v = v + y`) |
| `stages[].curve` | `curve2d` | Input → output; reuses the existing `curve2d` definition |
| `stages[].filter` | number | Smoothing of the stage output (0 = none, towards 1 = slower) |
| `stages[].min`, `max` | number | Clamp of the running value after the stage |

`lock_control` is only meaningful with `type` `lsd_clutch`, `lsd_torsen`, `lsd_viscous` or
`active`. A differential without it keeps today's constant lock.

*To confirm against AC before standardising:* the exact evaluation order, the meaning of the
filter coefficient and the units of the limits. Until then the converter emits the structure
under `x_lock_control` exactly as AC wrote it.

### 3.2 `transfer_case.coupling` — torque-limited centre coupling

**Evidence.** 35 AC cars use `TYPE=AWD2` (95 carry an `[AWD2]` section); their centre is
described by `CENTRE_RAMP_TORQUE` and `CENTRE_MAX_TORQUE` (e.g. Porsche 993 C4: 40.9 / 816.6 Nm,
Lamborghini Diablo VT: 103 / 610.7 Nm) instead of a fixed `FRONT_SHARE`. These are
rear-biased cars with a coupling feeding the front axle.

**Proposal.** An optional `coupling` object on `transfer_case`:

```json
"transfer_case": {
  "type": "on_demand",
  "coupling": { "type": "torque_limited", "primary_axle": "rear",
                "ramp_torque": 40.9, "max_torque": 816.6 }
}
```

| Key | Type | Description |
|---|---|---|
| `type` | string | `"torque_limited"`, `"viscous"`, `"clutch_pack"`, `"electronic"` |
| `primary_axle` | string | `"front"` or `"rear"`: the axle driven directly; the other is fed through the coupling. AC does not state it; converters leave it out when unknown |
| `ramp_torque` | number (Nm) | Torque at which the coupling starts to engage |
| `max_torque` | number (Nm) | Maximum torque the coupling transmits |

`torque_split` stays the nominal split and may be omitted when `coupling` is present.

### 3.3 Rarer parameters — deferred

AC also has `[DIFFERENTIAL] RAMP_POWER / RAMP_COAST / RAMP_LOCK_LUT` (4 cars) and
`VISCOUS_FACTOR_1 / _2 / _EXP / _EXP_K` (1 car). Their semantics are not documented and the
population is tiny, so they remain in the converter's extension block
(`x_assettocorsa.drivetrain.differential_extra`). Revisit if more sources need them.

## 4. Checker rules (`tools/integrity_check.py`)

1. `lock_control.stages[].curve` is sorted by x and has at least two points.
2. `combine` is `multiply` or `add`; `target` is one of the listed values.
3. `stages[].input` is in the vocabulary or starts with `x_`.
4. `lock_control` on a differential of `type: open`, `locked` or `spool` is a warning.
5. `coupling.max_torque ≥ coupling.ramp_torque` when both are present.
6. `transfer_case.type: on_demand` with neither `torque_split` nor `coupling` is a warning.

## 5. Migration

Everything is additive; existing files stay valid. Until the standard adopts it, the AC → SVJ
converter writes the proposed shapes under extension keys, so promoting them is a rename:

| Now (converter output) | After adoption |
|---|---|
| `…center_diff.x_lock_control` | `…center_diff.lock_control` |
| `transfer_case.x_coupling` | `transfer_case.coupling` |

The raw AC values stay in `x_assettocorsa.drivetrain` either way.

## 6. Open questions

1. Is `stages` as a single ordered chain enough, or do some simulators need branches
   (e.g. separate power and coast chains)?
2. Should `filter` be a time constant (s) instead of a 0–1 smoothing coefficient?
3. Do we want `primary_axle` in the first release, given AC does not provide it?
