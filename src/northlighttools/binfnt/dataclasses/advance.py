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

    @staticmethod
    def calculate_values(char, i, font_size):
        num4 = 4
        num6 = 6

        chnl = {2: 1, 1: 2}.get(char.chnl, 0)
        yoffset2 = -char.yoffset / font_size
        xadvance2 = char.xadvance / font_size
        yoffset1 = yoffset2 - char.height / font_size

        return Advance(
            plus4=num4 * i,
            num4=num4,
            plus6=num6 * i,
            num6=num6,
            chnl=chnl,
            xadvance1_1=0,
            xadvance1_2=0,
            yoffset1_1=yoffset1,
            yoffset1_2=yoffset1,
            yoffset2_1=yoffset2,
            yoffset2_2=yoffset2,
            xadvance2_1=xadvance2,
            xadvance2_2=xadvance2,
        )
