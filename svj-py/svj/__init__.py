"""
SVJ — Standard Vehicle JSON parser and toolkit.

Load, validate, query, and export SVJ vehicle dynamics files.
"""

__version__ = "0.1.0"

from svj.vehicle import Vehicle
from svj.loader import load, loads
from svj.validator import validate

__all__ = ["Vehicle", "load", "loads", "validate", "__version__"]
