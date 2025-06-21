from dataclasses import dataclass


@dataclass
class Point:
    """Rectangle/point in texture space."""

    x: float
    y: float
    width: float
    height: float
