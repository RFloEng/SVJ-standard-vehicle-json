"""
SVJ-specific exceptions.
"""


class SVJError(Exception):
    """Base class for all SVJ errors."""


class SVJValidationError(SVJError):
    """Raised when an SVJ file fails schema or consistency validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        msg = f"{len(errors)} validation error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)


class SVJRefError(SVJError):
    """Raised when a $ref cannot be resolved (missing file, circular reference)."""
