from dataclasses import dataclass


@dataclass
class Advance:
    plus4: int  # +4
    num4: int  # =4
    plus6: int  # +6
    num6: int  # =6
    chnl: int

    xadvance1_1: float
    yoffset1_1: float  # yoffset2 - height
    xadvance2_1: float  # xadvance
    yoffset1_2: float  # yoffset2 - height
    xadvance2_2: float  # xadvance
    yoffset2_1: float  # -yoffset
    xadvance1_2: float
    yoffset2_2: float  # -yoffset
