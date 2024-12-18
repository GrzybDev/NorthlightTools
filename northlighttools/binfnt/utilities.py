from io import BytesIO
from struct import pack, unpack

import numpy as np

from northlighttools.binfnt.dataclasses.Character import Character
from northlighttools.binfnt.dataclasses.CharacterEntry import CharacterEntry
from northlighttools.binfnt.dataclasses.Point import Point
from northlighttools.binfnt.enums.FontVersion import FontVersion
from northlighttools.binfnt.headers import BGRA8_HEADER


def get_point_from_uv_mapping(char: Character, width: int, height: int) -> Point:
    x = char.xMin_1 * width
    y = char.yMin_1 * height

    return Point(
        x=x,
        y=y,
        width=(char.xMax_1 * width) - x,
        height=(char.yMax_1 * height) - y,
    )


def convert_binfnt_char_to_char_entry(
    orig_char: Character, width: int, height: int, lineHeight: float, size: float
) -> CharacterEntry:
    point = get_point_from_uv_mapping(orig_char, width, height)

    return CharacterEntry(
        idx=None,
        x=point.x,
        y=point.y,
        width=point.width,
        height=point.height,
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


def convert_r16f_to_bgra8(texture: BytesIO) -> bytes:
    texture.seek(12)

    textureHeight = int.from_bytes(texture.read(4), "little")
    textureWidth = int.from_bytes(texture.read(4), "little")

    texture.seek(84)

    fourcc = int.from_bytes(texture.read(4), "little")

    if fourcc != 111:
        raise ValueError(
            f"Texture is not in R16_FLOAT pixel format! (Texture pixel format is: {fourcc})"
        )

    texture.seek(128)

    # Write new header
    converted = BytesIO()
    converted.write(BGRA8_HEADER[:12])
    converted.write(textureHeight.to_bytes(4, "little"))
    converted.write(textureWidth.to_bytes(4, "little"))
    converted.write((textureWidth * 2).to_bytes(4, "little"))
    converted.write(BGRA8_HEADER[24:])

    # Convert R16F to BGRA8
    for _ in range(textureWidth * textureHeight):
        hGray = np.frombuffer(texture.read(2), dtype=np.float16)[0]
        hGray = np.nan_to_num(hGray, nan=255)

        # normalize alpha to [-9,9]
        normalized_value = ((9 - hGray) * 255) / 18
        alpha = int(np.clip(normalized_value, 0, 255))

        if alpha > 0:
            converted.write(pack("BBBB", 255, 255, 255, alpha))
        else:
            converted.write(pack("BBBB", 0, 0, 0, 0))

    return converted.getvalue()
