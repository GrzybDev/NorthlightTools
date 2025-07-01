from dataclasses import dataclass


@dataclass
class RemedyCharacter:
    bearingX1_1: float  # xoffset
    bearingY2_1: float  # line_height - y_offset - char_height
    xMin_1: float
    yMax_1: float
    bearingX2_1: float  # xoffset + char_width
    bearingY2_2: float  # line_height - y_offset - char_height
    xMax_1: float
    yMax_2: float
    bearingX2_2: float  # xoffset + char_width
    bearingY1_1: float  # bearing_y2 + char_height = line_height - y_offset
    xMax_2: float
    yMin_1: float
    bearingX1_2: float  # xoffset
    bearingY1_2: float  # bearing_y2 + char_height = line_height - y_offset
    xMin_2: float
    yMin_2: float
