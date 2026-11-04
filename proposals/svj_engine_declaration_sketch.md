# Sketch: engine declaration for sound simulation (`powertrain.engine`, `electric.motors[]`)

**Status:** implemented in v0.107 (spec §10.3.2–§10.3.4, `tools/engine_check.py`). Decisions: audio assets later, gear-mesh teeth left out, exhaust as labels, rotary and turbine in `kind`, `exhaust.overrun` added.

**Purpose (decided with the project owner):** the torque curve stays king for the physics. This declaration exists so that a **sound simulator can build the engine's sound from the file**: what makes the sound is the firing pattern, the number of cylinders, the aspiration and the exhaust, none of which the torque curve says. It is a description layer like appearance (§22), not a second source of physics: nothing here may contradict the curve.

## 1. What exists today

`powertrain.engine` (§10.3) has `displacement`, a free-text `configuration` (`"V8"`), `compression_ratio`, `idle_rpm`, `max_rpm`, `torque_curve`, `inertia`, `mass`, `position`, `thermal`. Electric motors (§14.2) have `type`, `max_rpm`, `gear_ratio`, `placement`. There is nothing about firing, aspiration or exhaust.

## 2. What a sound simulator needs

| Sound source | Needed data |
|---|---|
| Engine note (order content) | cylinders, cycle (4-stroke fires every 720 deg, 2-stroke every 360 deg), **firing angles** (crank angle of each ignition: uneven firing gives the burble of a cross-plane V8 or a 90 deg V twin), crank type |
| Character | arrangement (inline, V, flat), bank angle, valves per cylinder, displacement, rev limiter type (hard cut, soft, none) |
| Forced induction | turbo (shaft order from blade count, whistle, wastegate flutter, blow-off valve), supercharger (kind, pulley ratio: whine order), electric compressor |
| Exhaust | header type (equal / unequal length, 4-1, 4-2-1), merge (X / H pipe), catalyst, resonator, muffler type, number of outlets |
| Intake | airbox, individual throttle bodies, plenum, intake noise level |
| Electric | pole pairs, inverter switching frequency, reduction gear ratio (whine orders); no firing |
| Drive line | gear mesh orders (teeth), only if the source has them |

## 3. Proposed fields (all optional)

```json
"powertrain": {
  "engine": {
    "kind": "ice",
    "cycle": "four_stroke",
    "fuel": "petrol",
    "layout": {
      "cylinders": 8, "arrangement": "V", "bank_angle_deg": 90, "valves_per_cylinder": 4,
      "crank": "cross_plane",
      "firing_order": [1, 8, 4, 3, 6, 5, 7, 2],
      "firing_angles_deg": [0, 90, 180, 270, 360, 450, 540, 630]
    },
    "aspiration": {
      "type": "turbo",
      "chargers": [
        { "id": "tc_l", "kind": "turbo", "bank": "left",  "blades": 11, "wastegate": "external", "blow_off": true },
        { "id": "tc_r", "kind": "turbo", "bank": "right", "blades": 11, "wastegate": "external", "blow_off": true }
      ]
    },
    "exhaust": {
      "headers": "equal_length", "merge": "x_pipe", "catalyst": true,
      "resonators": 1, "muffler": "chambered", "outlets": 4
    },
    "intake": { "type": "plenum", "airbox": true },
    "limiter": { "type": "hard_cut", "rpm": 7200 },
    "idle_rpm": 800, "max_rpm": 7200,
    "torque_curve": [[1000, 180], [3000, 480], [5500, 520], [7200, 430]]
  }
},
"electric": {
  "motors": [ { "id": "front", "type": "pmsm", "pole_pairs": 4, "inverter_switching_hz": 8000, "gear_ratio": 9.0 } ]
}
```

| Key | Values / meaning |
|---|---|
| `kind` | `ice`, `rotary`, `electric`, `fuel_cell`, `turbine`; `electric` means no `engine`, see `electric.motors[]` |
| `cycle` | `four_stroke`, `two_stroke`, `wankel` |
| `fuel` | label only (`petrol`, `diesel`, `e85`, `cng`, `hydrogen`, `methanol`): changes combustion character |
| `layout.cylinders` | integer; the structured form of the text `configuration` |
| `layout.arrangement` | `I`, `V`, `flat`, `W`, `radial`, `rotary` |
| `layout.crank` | `flat_plane`, `cross_plane`, `single_plane`, or `{ "throw_angles_deg": [...] }` |
| `layout.firing_order` | cylinder numbers in firing order (starts at 1) |
| `layout.firing_angles_deg` | crank angle of each ignition within one cycle (0 to 720 for four-stroke), in firing order; the **key datum** for the note. If absent, derived from `cylinders`, `arrangement`, `crank` (even firing) |
| `aspiration.type` | `na`, `turbo`, `supercharger`, `twin_charged`, `electric_compressor` |
| `aspiration.chargers[]` | `kind` (`turbo`, `roots`, `twin_screw`, `centrifugal`, `electric`), `bank`, `blades` (turbo, for the whistle order), `pulley_ratio` (supercharger, for the whine order), `wastegate` (`internal`, `external`, `electronic`), `blow_off` (boolean) |
| `exhaust` | `headers` (`equal_length`, `unequal_length`, `log`, `4_1`, `4_2_1`), `merge` (`none`, `x_pipe`, `h_pipe`), `catalyst`, `resonators` (count), `muffler` (`none`, `straight_through`, `chambered`, `turbo_muffler`), `outlets` |
| `intake` | `type` (`plenum`, `itb`, `carburettor`, `airbox`), `airbox` |
| `limiter` | `type` (`hard_cut`, `soft`, `none`), `rpm` |
| motor `pole_pairs`, `inverter_switching_hz` | order sources of an electric drive |

## 4. Formulas to write into the spec (like the tyre formulas, so users need not look them up)

- Firing frequency: `f_fire = (rpm / 60) * cylinders / 2` for a four-stroke, `(rpm / 60) * cylinders` for a two-stroke (Hz); engine order `= cylinders / 2` (four-stroke).
- Engine order of a harmonic: `f_k = k * rpm / 60`.
- Turbo shaft order: `f_turbo = n_turbo / 60`, blade-pass frequency `f_blade = blades * n_turbo / 60`; `n_turbo` is not in the file (it depends on boost), so only the blade count is declared.
- Supercharger whine: `f = pulley_ratio * rpm / 60 * lobes`.
- Electric: `f_motor = pole_pairs * n_motor / 60`, `n_motor = rpm_wheel * gear_ratio`.
- Firing angles when absent: even firing `720 / cylinders` for four-stroke inline and flat engines; V engines from `bank_angle_deg` and `crank`.

## 5. Integrity checks (warnings)

1. `firing_order` is a permutation of `1..cylinders`; `firing_angles_deg` has `cylinders` entries inside one cycle.
2. `aspiration.type = "na"` with `chargers`, or a boosted type without `chargers`.
3. `kind = "electric"` with ICE-only fields, or `kind = "ice"` without `torque_curve`.
4. `limiter.rpm` not above `max_rpm`; `max_rpm` not below the top of the curve.
5. `layout.cylinders` disagrees with a number in `configuration` (`"V8"` vs 6).

## 6. What it does not do

- No audio files and no sound model parameters (reverb, mic position, filters): those belong to the game. **Decision (project owner): audio will not be added to SVJ**; the file only says what to simulate, via `sound_sources()` (spec §10.3.5).
- No new physics: torque pulsation could be derived from the firing angles by a simulator, but the torque curve remains the only source of torque.

## 7. Compatibility

All keys optional; `engine` already allows extra properties, so old files stay valid and old readers ignore the new keys. `configuration` and `displacement` stay. Schema: add the structured properties with enums; the version enum gets `0.107`. Converters fill `kind`, `cycle`, `layout.cylinders`, `aspiration` where the source has them; firing angles are derived when absent.

## 8. Open questions

1. Audio samples as `assets.audio[]` (recorded loops per rpm and load), bound to `SVJ::powertrain::*`: now, or later with the sound work?
2. Gear-mesh whine: add `teeth` to the gears of §10, or leave it out?
3. Exhaust geometry (primary length, collector position) as numbers, or labels only?
4. Rotary and turbine in `kind` now (cheap) or later?
5. Does the sound need load/throttle response (burble on overrun, pops)? If so a `overrun` flag in `limiter` / `exhaust`.
