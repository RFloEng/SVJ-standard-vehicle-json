"""
SVJ — Standard Vehicle JSON parser and toolkit.

Load, validate, query, and export SVJ vehicle dynamics files.
"""

__version__ = "0.2.0"

from svj.vehicle import Vehicle, canonical_station, is_station, station_axle
from svj.loader import load, loads
from svj.validator import validate

__all__ = ["Vehicle", "load", "loads", "validate", "canonical_station", "is_station", "station_axle", "__version__"]
