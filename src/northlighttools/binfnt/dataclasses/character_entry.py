from dataclasses import dataclass


@dataclass
class CharacterEntry:
    """Single character entry for BMFont export/import."""

    idx: int | None = None
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    xoffset: float = 0.0
    yoffset: float = 0.0
    xadvance: float = 0.0
    page: int = 0
    chnl: int = 0
