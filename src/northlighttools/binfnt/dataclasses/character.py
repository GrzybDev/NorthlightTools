from dataclasses import dataclass

from northlighttools.binfnt.dataclasses.point import Point


@dataclass
class Character(Point):
    xoffset: float
    yoffset: float
    xadvance: float
    chnl: int
