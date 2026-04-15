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

## CLI

```bash
svj info templates/mazda_mx5_nd2_2024.svj.json
svj validate templates/mazda_mx5_nd2_2024.svj.json
svj query templates/mazda_mx5_nd2_2024.svj.json chassis.mass_total
```
