from dataclasses import dataclass


@dataclass
class CharacterEntry:
    idx: None
    x: int
    y: int
    width: int
    height: int
    xoffset: float
    yoffset: float
    xadvance: float
    page: int
    chnl: int
