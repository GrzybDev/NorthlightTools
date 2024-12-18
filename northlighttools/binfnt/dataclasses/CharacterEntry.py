from dataclasses import dataclass


@dataclass
class CharacterEntry:
    idx: None
    x: float
    y: float
    width: float
    height: float
    xoffset: float
    yoffset: float
    xadvance: float
    page: int
    chnl: int
