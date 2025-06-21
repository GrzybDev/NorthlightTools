from io import BytesIO
from struct import pack

import numpy as np

from northlighttools.binfnt.dataclasses.character_entry import CharacterEntry
from northlighttools.binfnt.headers import BGRA8_HEADER
from northlighttools.binfnt.helpers import (
    get_kernings_for_bmfont,
    get_point_from_uv_mapping,
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
