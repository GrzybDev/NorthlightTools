from dataclasses import dataclass


@dataclass
class Character:
    """Raw font character data from binfnt file."""

    bearingX1_1: float
    bearingY2_1: float
    xMin_1: float
    yMax_1: float
    bearingX2_1: float
    bearingY2_2: float
    xMax_1: float
    yMax_2: float
    bearingX2_2: float
    bearingY1_1: float
    xMax_2: float
    yMin_1: float
    bearingX1_2: float
    bearingY1_2: float
    xMin_2: float
    yMin_2: float
