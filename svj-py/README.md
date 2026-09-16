# svj-py

Python parser and toolkit for [SVJ (Standard Vehicle JSON)](../README.md) files.

## Install

```bash
pip install .
```

## Usage

```python
import svj

# Load a vehicle
car = svj.load("templates/mazda_mx5_nd2_2024.svj.json")
print(car)  # Mazda MX-5 ND2 2024

# Access data
print(car.mass_total)          # 1077.0
print(car.topologies())        # {'FL': 'double_wishbone', ...}
print(car.gear_ratios)         # [5.087, 3.063, ...]
print(car.weight_distribution_front)  # ~0.52

# Dot-path queries
car.get("suspension.FL.topology.system_type")
car.get("powertrain.engine.max_power")

# Validate
errors = svj.validate(car.data, schema_path="schema/svj.schema.json")

# Export
car.save("my_car.svj.json")
```

### Multi-axle vehicles (SVJ v0.99)

Wheel stations can be the legacy `FL/FR/RL/RR` or `A{n}{L|R|C}` for any number of axles. `corner()` resolves the aliases both ways (`"FL"` ⇄ `"A1L"`).

```python
truck = svj.load("examples/skeleton_6x4_walking_beam_dump_truck.svj.json")

truck.stations              # ['A1L', 'A1R', 'A2L', 'A2R', 'A3L', 'A3R']
truck.axle_count            # 3
truck.axle("A1")            # {'id': 'A1', 'steered': True, ...}
truck.stations_on_axle(3)   # ['A3L', 'A3R']
truck.wheel_count("A2L")    # 2  (dual wheels)
truck.tyre_count            # 10
truck.wheel_formula         # '6x4'
truck.topology("A3R")       # 'solid_axle'
truck.suspension_couplings  # walking beams, rockers, air/hydraulic circuits
```

`svj.validate()` runs the multi-axle cross-reference rules (spec §23.7). They live in `svj/multiaxle.py`, an exact copy of `tools/multiaxle_check.py` in the spec repo — a test fails if the two drift apart.

## CLI

```bash
svj info templates/mazda_mx5_nd2_2024.svj.json
svj validate templates/mazda_mx5_nd2_2024.svj.json
svj query templates/mazda_mx5_nd2_2024.svj.json chassis.mass_total
```
