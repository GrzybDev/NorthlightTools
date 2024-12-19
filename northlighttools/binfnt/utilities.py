from io import BytesIO
from struct import pack

import numpy as np
import typer

from northlighttools.binfnt.dataclasses.Advance import Advance
from northlighttools.binfnt.dataclasses.Character import Character
from northlighttools.binfnt.dataclasses.CharacterEntry import CharacterEntry
from northlighttools.binfnt.dataclasses.Kernel import Kernel
from northlighttools.binfnt.dataclasses.Point import Point
from northlighttools.binfnt.dataclasses.UVMapping import UVMapping
from northlighttools.binfnt.enums.FontVersion import FontVersion
from northlighttools.binfnt.headers import BGRA8_HEADER, R16F_HEADER


def get_point_from_uv_mapping(char: Character, width: int, height: int) -> Point:
    x = char.xMin_1 * width
    y = char.yMin_1 * height

    return Point(
        x=x,
        y=y,
        width=(char.xMax_1 * width) - x,
        height=(char.yMax_1 * height) - y,
    )


def get_uv_mapping_from_point(point: Point, width: int, height: int) -> UVMapping:
    return UVMapping(
        UVLeft=point.x / width,
        UVTop=point.y / height,
        UVRight=(point.x + point.width) / width,
        UVBottom=(point.y + point.height) / height,
    )


def convert_binfnt_char_to_char_entry(
    orig_char: Character, width: int, height: int, lineHeight: float, size: float
) -> CharacterEntry:
    point = get_point_from_uv_mapping(orig_char, width, height)

    return CharacterEntry(
        idx=None,
        x=int(round(point.x, 2)),
        y=int(round(point.y, 2)),
        width=int(round(point.width, 2)),
        height=int(round(point.height, 2)),
        xoffset=orig_char.bearingX1_1 * size,
        yoffset=lineHeight - orig_char.bearingY2_1 * size - point.height,
        xadvance=None,
        page=0,
        chnl=None,
    )


def convert_to_bmfont(binfnt):
    characters = []
    kernings = []

    for char in binfnt.characters:
        characters.append(
            convert_binfnt_char_to_char_entry(
                char,
                binfnt.textureWidth,
                binfnt.textureHeight,
                binfnt.lineHeight,
                binfnt.fontSize,
            )
        )

    for idx, id in enumerate(binfnt.ids):
        characters[idx].idx = id

    for idx, advance in enumerate(binfnt.advance):
        characters[idx].xadvance = advance.xadvance2_1 * binfnt.fontSize

        if advance.chnl == 0:
            characters[idx].chnl = 4
        elif advance.chnl == 1:
            characters[idx].chnl = 2
        elif advance.chnl == 2:
            characters[idx].chnl = 1

    if binfnt.version == FontVersion.QUANTUM_BREAK:
        for kerning in binfnt.kerning:
            kerning.amount = kerning.amount * binfnt.fontSize
            kernings.append(kerning)
    elif binfnt.version == FontVersion.ALAN_WAKE_REMASTERED:
        for kerning in binfnt.kerning:
            kerning.amount = kerning.amount / binfnt.fontSize
            kernings.append(kerning)

    return characters, kernings


def apply_bmfont_to_binfnt(binfnt, bmfont):
    def __get_character(char):
        point = Point(
            x=float(char["x"]),
            y=float(char["y"]),
            width=int(char["width"]),
            height=int(char["height"]),
        )
        uv_mapping = get_uv_mapping_from_point(
            point, binfnt.textureWidth, binfnt.textureHeight
        )

        bearingX1 = float(char["xoffset"]) / binfnt.fontSize
        bearingX2 = (float(char["xoffset"]) + float(char["width"])) / binfnt.fontSize
        bearingY1 = (binfnt.lineHeight - float(char["yoffset"])) / binfnt.fontSize
        bearingY2 = (
            binfnt.lineHeight - float(char["yoffset"]) - int(char["height"])
        ) / binfnt.fontSize

        binfntChar = Character(
            bearingX1_1=bearingX1,
            bearingX1_2=bearingX1,
            bearingY2_1=bearingY2,
            bearingY2_2=bearingY2,
            xMin_1=uv_mapping.UVLeft,
            xMin_2=uv_mapping.UVLeft,
            yMin_1=uv_mapping.UVTop,
            yMin_2=uv_mapping.UVTop,
            xMax_1=uv_mapping.UVRight,
            xMax_2=uv_mapping.UVRight,
            yMax_1=uv_mapping.UVBottom,
            yMax_2=uv_mapping.UVBottom,
            bearingX2_1=bearingX2,
            bearingX2_2=bearingX2,
            bearingY1_1=bearingY1,
            bearingY1_2=bearingY1,
        )

        if int(char["id"]) in [9, 10, 13, 32]:
            binfntChar.bearingX1_1 = 0
            binfntChar.bearingY2_1 = 0
            binfntChar.bearingX2_1 = 0
            binfntChar.bearingY1_1 = 0

        return binfntChar

    def __get_advance(char):
        match int(char["chnl"]):
            case 2:
                chnl = 1
            case 1:
                chnl = 2
            case _:
                chnl = 0

        yoffset2 = -float(char["yoffset"]) / binfnt.fontSize
        xadvance2 = float(char["xadvance"]) / binfnt.fontSize
        yoffset1 = yoffset2 - int(char["height"]) / binfnt.fontSize

        advance = Advance(
            plus4=num4 * i,
            num4=num4,
            plus6=num6 * i,
            num6=num6,
            chnl=chnl,
            xadvance1_1=0,
            xadvance1_2=0,
            yoffset2_1=yoffset2,
            yoffset2_2=yoffset2,
            xadvance2_1=xadvance2,
            xadvance2_2=xadvance2,
            yoffset1_1=yoffset1,
            yoffset1_2=yoffset1,
        )

        return advance

    def __get_kerning(version, kerning):
        if version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            amount = float(kerning["amount"]) * binfnt.fontSize
        elif version == FontVersion.QUANTUM_BREAK:
            amount = float(kerning["amount"]) / binfnt.fontSize

        kerning = Kernel(
            first=int(kerning["first"]),
            second=int(kerning["second"]),
            amount=amount,
        )

        return kerning

    info_line = bmfont[0].split(" ")
    info = {x.split("=")[0]: x.split("=")[1].strip() for x in info_line[1:]}
    binfnt.fontSize = float(info["size"])

    common_line = bmfont[1].split(" ")
    common = {x.split("=")[0]: x.split("=")[1].strip() for x in common_line[1:]}
    binfnt.lineHeight = float(common["lineHeight"])
    binfnt.textureWidth = int(common["scaleW"])
    binfnt.textureHeight = int(common["scaleH"])

    page_line = bmfont[2].split(" ")
    page = {x.split("=")[0]: x.split("=")[1].strip() for x in page_line[1:]}

    chars_line = bmfont[3].split(" ")
    chars = {x.split("=")[0]: x.split("=")[1].strip() for x in chars_line[1:]}

    expected_chars = int(chars["count"])

    binfnt.characters.clear()

    num4 = binfnt.advance[0].num4
    num6 = binfnt.advance[0].num6

    binfnt.advance.clear()
    binfnt.ids.clear()

    for i in range(expected_chars):
        char_line = bmfont[4 + i].split(" ")
        char = {x.split("=")[0]: x.split("=")[1].strip() for x in char_line[1:]}

        if int(char["width"]) == 0 and int(char["height"]) == 0:
            char["width"] = 6
            char["height"] = 6

        binfnt.characters.append(__get_character(char))
        binfnt.advance.append(__get_advance(char))
        binfnt.ids.append(int(char["id"]))

    kernings_line = bmfont[4 + expected_chars].split(" ")
    kernings = {x.split("=")[0]: x.split("=")[1].strip() for x in kernings_line[1:]}
    expected_kernings = int(kernings["count"])

    binfnt.kerning.clear()

    for i in range(expected_kernings):
        kerning_line = bmfont[5 + expected_chars + i].split(" ")
        kerning = {x.split("=")[0]: x.split("=")[1].strip() for x in kerning_line[1:]}
        binfnt.kerning.append(__get_kerning(binfnt.version, kerning))

    return page["file"].strip('"')


def convert_r16f_to_bgra8(r16f: BytesIO) -> bytes:
    r16f.seek(12)

    textureHeight = int.from_bytes(r16f.read(4), "little")
    textureWidth = int.from_bytes(r16f.read(4), "little")

    r16f.seek(84)

    fourcc = int.from_bytes(r16f.read(4), "little")

    if fourcc != 111:
        raise ValueError(
            f"Texture is not in R16_FLOAT pixel format! (Texture pixel format is: {fourcc})"
        )

    r16f.seek(128)

    # Write new header
    bgra8 = BytesIO()
    bgra8.write(BGRA8_HEADER[:12])
    bgra8.write(textureHeight.to_bytes(4, "little"))
    bgra8.write(textureWidth.to_bytes(4, "little"))
    bgra8.write((textureWidth * 2).to_bytes(4, "little"))
    bgra8.write(BGRA8_HEADER[24:])

    # Convert R16F to BGRA8
    for _ in range(textureWidth * textureHeight):
        hGray = np.frombuffer(r16f.read(2), dtype=np.float16)[0]
        hGray = np.nan_to_num(hGray, nan=255)

        # normalize alpha to [-9,9]
        normalized_value = ((9 - hGray) * 255) / 18
        alpha = int(np.clip(normalized_value, 0, 255))

        if alpha > 0:
            bgra8.write(pack("BBBB", 255, 255, 255, alpha))
        else:
            bgra8.write(pack("BBBB", 0, 0, 0, 0))

    return bgra8.getvalue()


def convert_bgra8_to_r16f(bgra8: BytesIO) -> bytes:
    bgra8.seek(12)

    textureHeight = int.from_bytes(bgra8.read(4), "little")
    textureWidth = int.from_bytes(bgra8.read(4), "little")

    bgra8.seek(128)

    r16f = BytesIO()
    r16f.write(R16F_HEADER[:12])
    r16f.write(textureHeight.to_bytes(4, "little"))
    r16f.write(textureWidth.to_bytes(4, "little"))
    r16f.write((textureWidth * 2).to_bytes(4, "little"))
    r16f.write(R16F_HEADER[24:])

    # Read BGRA8 and convert to grayscale R16F
    for _ in range(textureWidth * textureHeight):
        b, g, r, a = bgra8.read(4)

        # Normalize alpha to [-9,9]
        hGray = -((18) * a / 255.0 - 9.0)

        if a > 0:
            # Convert hGray to float16
            r16f.write(np.float16(hGray).tobytes())
        else:
            r16f.write(int.to_bytes(32767, 2, "little"))

    return r16f.getvalue()
