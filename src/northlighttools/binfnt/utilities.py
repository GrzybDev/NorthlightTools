from io import BytesIO
from pathlib import Path
from struct import pack

import numpy as np

from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character import Character
from northlighttools.binfnt.dataclasses.character_entry import CharacterEntry
from northlighttools.binfnt.dataclasses.kernel import Kernel
from northlighttools.binfnt.dataclasses.point import Point
from northlighttools.binfnt.enums.font_version import FontVersion
from northlighttools.binfnt.headers import BGRA8_HEADER, R16F_HEADER
from northlighttools.binfnt.helpers import (
    get_kernings_for_bmfont,
    get_point_from_uv_mapping,
    get_uv_mapping_from_point,
)


def convert_binfnt_char_to_char_entry(orig_char, width, height, lineHeight, size):
    point = get_point_from_uv_mapping(orig_char, width, height)

    return CharacterEntry(
        idx=None,
        x=int(round(point.x, 2)),
        y=int(round(point.y, 2)),
        width=int(round(point.width, 2)),
        height=int(round(point.height, 2)),
        xoffset=orig_char.bearingX1_1 * size,
        yoffset=lineHeight - orig_char.bearingY2_1 * size - point.height,
        xadvance=0.0,
        page=0,
        chnl=0,
    )


def convert_to_bmfont(binfnt):
    characters = [
        convert_binfnt_char_to_char_entry(
            char,
            binfnt.textureWidth,
            binfnt.textureHeight,
            binfnt.lineHeight,
            binfnt.fontSize,
        )
        for char in binfnt.characters
    ]

    for idx, id in enumerate(binfnt.ids):
        characters[idx].idx = id

    for idx, advance in enumerate(binfnt.advance):
        characters[idx].xadvance = advance.xadvance2_1 * binfnt.fontSize
        characters[idx].chnl = {0: 4, 1: 2, 2: 1}.get(advance.chnl, 0)

    kernings = get_kernings_for_bmfont(binfnt)
    return characters, kernings


def convert_r16f_to_bgra8(r16f: BytesIO) -> bytes:
    r16f.seek(12)
    textureHeight = int.from_bytes(r16f.read(4), "little")
    textureWidth = int.from_bytes(r16f.read(4), "little")
    r16f.seek(84)

    if int.from_bytes(r16f.read(4), "little") != 111:
        raise ValueError("Texture is not in R16_FLOAT pixel format!")

    r16f.seek(128)
    bgra8 = BytesIO()
    bgra8.write(BGRA8_HEADER[:12])
    bgra8.write(textureHeight.to_bytes(4, "little"))
    bgra8.write(textureWidth.to_bytes(4, "little"))
    bgra8.write((textureWidth * 2).to_bytes(4, "little"))
    bgra8.write(BGRA8_HEADER[24:])

    for _ in range(textureWidth * textureHeight):
        hGray = np.frombuffer(r16f.read(2), dtype=np.float16)[0]
        hGray = np.nan_to_num(hGray, nan=255)
        alpha = int(np.clip(((9 - hGray) * 255) / 18, 0, 255))
        bgra8.write(
            pack("BBBB", *((255, 255, 255, alpha) if alpha > 0 else (0, 0, 0, 0)))
        )

    return bgra8.getvalue()


def apply_bmfont_to_binfnt(binfnt, bmfont):
    def parse_line_to_dict(line):
        return {x.split("=")[0]: x.split("=")[1].strip() for x in line.split()[1:]}

    def get_character(char):
        point = Point(
            x=float(char["x"]),
            y=float(char["y"]),
            width=int(char["width"]),
            height=int(char["height"]),
        )

        uv = get_uv_mapping_from_point(point, binfnt.textureWidth, binfnt.textureHeight)

        bx1 = float(char["xoffset"]) / binfnt.fontSize
        bx2 = (float(char["xoffset"]) + float(char["width"])) / binfnt.fontSize
        by1 = (binfnt.lineHeight - float(char["yoffset"])) / binfnt.fontSize
        by2 = (
            binfnt.lineHeight - float(char["yoffset"]) - int(char["height"])
        ) / binfnt.fontSize

        c = Character(
            bearingX1_1=bx1,
            bearingX1_2=bx1,
            bearingY2_1=by2,
            bearingY2_2=by2,
            xMin_1=uv.UVLeft,
            xMin_2=uv.UVLeft,
            yMin_1=uv.UVTop,
            yMin_2=uv.UVTop,
            xMax_1=uv.UVRight,
            xMax_2=uv.UVRight,
            yMax_1=uv.UVBottom,
            yMax_2=uv.UVBottom,
            bearingX2_1=bx2,
            bearingX2_2=bx2,
            bearingY1_1=by1,
            bearingY1_2=by1,
        )

        if int(char["id"]) in [9, 10, 13, 32]:
            c.bearingX1_1 = c.bearingY2_1 = c.bearingX2_1 = c.bearingY1_1 = 0

        return c

    def get_advance(char, num4, num6, i):
        chnl = {2: 1, 1: 2}.get(int(char["chnl"]), 0)
        yoffset2 = -float(char["yoffset"]) / binfnt.fontSize
        xadvance2 = float(char["xadvance"]) / binfnt.fontSize
        yoffset1 = yoffset2 - int(char["height"]) / binfnt.fontSize

        return Advance(
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

    def get_kerning(version, kerning):
        amount = (
            float(kerning["amount"]) * binfnt.fontSize
            if version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]
            else float(kerning["amount"]) / binfnt.fontSize
        )

        return Kernel(
            first=int(kerning["first"]), second=int(kerning["second"]), amount=amount
        )

    info = parse_line_to_dict(bmfont[0])
    binfnt.fontSize = float(info["size"])
    common = parse_line_to_dict(bmfont[1])
    binfnt.lineHeight = float(common["lineHeight"])
    binfnt.textureWidth = int(common["scaleW"])
    binfnt.textureHeight = int(common["scaleH"])
    page = parse_line_to_dict(bmfont[2])
    chars = parse_line_to_dict(bmfont[3])
    expected_chars = int(chars["count"])
    binfnt.characters.clear()

    num4, num6 = binfnt.advance[0].num4, binfnt.advance[0].num6
    binfnt.advance.clear()
    binfnt.ids.clear()

    for i in range(expected_chars):
        char = parse_line_to_dict(bmfont[4 + i])

        if int(char["width"]) == 0 and int(char["height"]) == 0:
            char["width"] = 6
            char["height"] = 6

        binfnt.characters.append(get_character(char))
        binfnt.advance.append(get_advance(char, num4, num6, i))
        binfnt.ids.append(int(char["id"]))

    kernings = parse_line_to_dict(bmfont[4 + expected_chars])
    expected_kernings = int(kernings["count"])
    binfnt.kerning.clear()

    for i in range(expected_kernings):
        kerning = parse_line_to_dict(bmfont[5 + expected_chars + i])
        binfnt.kerning.append(get_kerning(binfnt.version, kerning))

    return Path(page["file"].strip('"'))


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

    for _ in range(textureWidth * textureHeight):
        b, g, r, a = bgra8.read(4)
        hGray = -((18) * a / 255.0 - 9.0)
        r16f.write(
            np.float16(hGray).tobytes() if a > 0 else int.to_bytes(32767, 2, "little")
        )

    return r16f.getvalue()
