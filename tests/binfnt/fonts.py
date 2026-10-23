"""Small invented fonts covering every version and texture format."""

import struct

import numpy as np

from northlighttools.binfnt import BinaryFont, FontVersion, Glyph, KerningPair, Vertex
from northlighttools.binfnt.dds import PixelFormat, encode_dds
from northlighttools.binfnt.texture import encode_pixels

WIDTH = HEIGHT = 16
QUAD = (0, 1, 2, 0, 2, 3)


def f32(value: float) -> float:
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


def rectangle(
    plane: tuple[float, float, float, float], atlas: tuple[int, int, int, int]
) -> tuple[Vertex, ...]:
    """Build the vertices of a textured rectangle the way the games' fonts do."""
    left, bottom, right, top = map(f32, plane)
    u0, v0, u1, v1 = (
        f32(atlas[0] / WIDTH),
        f32(atlas[1] / HEIGHT),
        f32(atlas[2] / WIDTH),
        f32(atlas[3] / HEIGHT),
    )
    return (
        Vertex(left, bottom, u0, v1),
        Vertex(right, bottom, u1, v1),
        Vertex(right, top, u1, v0),
        Vertex(left, top, u0, v0),
    )


def box(
    advance: float, bottom: float, top: float
) -> tuple[float, float, float, float, float, float, float, float]:
    a, b, t = f32(advance), f32(bottom), f32(top)
    return (0.0, b, a, b, a, t, 0.0, t)


GLYPH_AREAS = ((slice(8, 16), slice(0, 4)), (slice(0, 8), slice(4, 12)))


def pixels_for(pixel_format: PixelFormat, packed: bool = False) -> np.ndarray:
    """Return a texture with patterns in the glyphs' areas and blank elsewhere.

    A packed texture keeps each glyph in its own channel: red, then green.
    """
    rows = np.arange(HEIGHT, dtype=np.int64)[:, None]
    columns = np.arange(WIDTH, dtype=np.int64)[None, :]
    inside = np.zeros((HEIGHT, WIDTH), dtype=bool)
    for area in GLYPH_AREAS:
        inside[area] = True
    if pixel_format is PixelFormat.R16F:
        distances = ((rows - 8) ** 2 + (columns - 4) ** 2) ** 0.5 - 4
        bits = distances.astype("<f2").view("<u2").copy()
        bits[~inside] = 0x7FFF
        return bits
    values = (rows * 16 + columns) % 256
    rgba = np.stack([values, 255 - values, (values * 7) % 256, values // 2], axis=-1)
    if pixel_format is PixelFormat.A4R4G4B4:
        rgba = rgba // 17 * 17
    rgba[~inside] = 0
    if packed:
        for channel, area in enumerate(GLYPH_AREAS):
            kept = rgba[area][..., channel].copy()
            rgba[area] = 0
            rgba[(*area, channel)] = kept
    return rgba.astype(np.uint8)


def make_font(
    version: FontVersion,
    pixel_format: PixelFormat = PixelFormat.A8R8G8B8,
    mipmaps: int = 1,
    channels: tuple[int, int, int] = (0, 0, 0),
) -> BinaryFont:
    glyphs = [
        Glyph(
            rectangle((-0.25, -0.125, 1.0, 1.5), (0, 8, 4, 16)),
            QUAD,
            channels[0],
            box(0.875, 0.0625, 1.25),
        ),
        Glyph(
            rectangle((0.0625, 0.0, 0.5625, 0.75), (4, 0, 12, 8)),
            QUAD,
            channels[1],
            box(0.625, -0.25, 1.0),
        ),
        Glyph(
            (
                Vertex(0.5, 1.0, f32(0.75), 0.0),
                Vertex(0.5, 0.0, f32(0.75), 0.5),
                Vertex(0.0, 0.0, 0.5, 0.5),
                Vertex(0.0, 1.0, 0.5, 0.0),
            ),
            (0, 1, 2, 2, 3, 0),
            channels[2],
            (0.0, -0.25, 0.5, -0.2421875, 0.5, 1.0, 0.0, 1.0),
        ),
    ]
    kerning = []
    if version is FontVersion.V4:
        kerning = [KerningPair(65, 66, -40), KerningPair(66, 65, 12)]
    elif version is FontVersion.V7:
        kerning = [KerningPair(65, 66, f32(-0.0625)), KerningPair(66, 65, f32(0.1))]
    unknown = {FontVersion.V6: (0, 0), FontVersion.V7: (4, 128)}.get(version, ())
    pixels = pixels_for(pixel_format, packed=any(channels))
    texture = encode_pixels(pixels, pixel_format, mipmaps)
    return BinaryFont(
        version=version,
        glyphs=glyphs,
        charmap={65: 1, 66: 2},
        kerning=kerning,
        unknown=unknown,
        texture=encode_dds(texture, legacy_header=version is FontVersion.V3),
    )


SAMPLES = {
    "alan wake": make_font(FontVersion.V3, PixelFormat.A4R4G4B4, mipmaps=4),
    "alan wake packed": make_font(FontVersion.V3, PixelFormat.A4R4G4B4, channels=(0, 1, 2)),
    "alan wake remastered": make_font(FontVersion.V4, PixelFormat.A8R8G8B8, mipmaps=2),
    "quantum break fixedsys": make_font(FontVersion.V6, PixelFormat.A8R8G8B8),
    "quantum break": make_font(FontVersion.V7, PixelFormat.R16F),
}
