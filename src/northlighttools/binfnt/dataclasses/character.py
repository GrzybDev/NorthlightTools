from dataclasses import dataclass

from northlighttools.binfnt.dataclasses.point import Point


@dataclass
class Character(Point):
    xoffset: float
    yoffset: float
    xadvance: float
    chnl: int

    def to_uv_mapping(self, texture_width: int, texture_height: int):
        from northlighttools.binfnt.dataclasses.uv_mapping import UVMapping

        return UVMapping(
            left=self.x / texture_width,
            top=self.y / texture_height,
            right=(self.x + self.width) / texture_width,
            bottom=(self.y + self.height) / texture_height,
        )

    def to_remedy_character(
        self,
        char_id: str,
        texture_width: int,
        texture_height: int,
        line_height: float,
        font_size: float,
    ):
        from northlighttools.binfnt.dataclasses.character_rmd import RemedyCharacter

        is_null_char = int(char_id) in [9, 10, 13, 32]

        uv = self.to_uv_mapping(texture_width, texture_height)

        bx1 = self.xoffset / font_size
        bx2 = (self.xoffset + self.width) / font_size
        by1 = (line_height - self.yoffset) / font_size
        by2 = (line_height - self.yoffset - self.height) / font_size

        return RemedyCharacter(
            bearingX1_1=bx1 if not is_null_char else 0,
            bearingX1_2=bx1,
            bearingY2_1=by2 if not is_null_char else 0,
            bearingY2_2=by2,
            xMin_1=uv.left,
            xMin_2=uv.left,
            yMin_1=uv.top,
            yMin_2=uv.top,
            xMax_1=uv.right,
            xMax_2=uv.right,
            yMax_1=uv.bottom,
            yMax_2=uv.bottom,
            bearingX2_1=bx2 if not is_null_char else 0,
            bearingX2_2=bx2,
            bearingY1_1=by1 if not is_null_char else 0,
            bearingY1_2=by1,
        )
