from dataclasses import dataclass


@dataclass
class Advance:
    """Advance/kerning and channel data for a font character."""

    plus4: int
    num4: int
    plus6: int
    num6: int
    chnl: int

    xadvance1_1: float
    yoffset1_1: float
    xadvance2_1: float
    yoffset1_2: float
    xadvance2_2: float
    yoffset2_1: float
    xadvance1_2: float
    yoffset2_2: float
