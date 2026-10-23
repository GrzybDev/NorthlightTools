"""Fonts as msdf-atlas-gen JSON documents with their texture beside them.

The document follows the layout msdf-atlas-gen writes: glyph metrics in em
units (planeBounds, advance, kerning advance), which are the font's own units,
and atlas rectangles in texture pixels counted from the top (atlasBounds).
Every value is the shortest number that gives back the font's exact value.

What msdf-atlas-gen has no field for lives in fields of its own: the layout
box of each glyph (layoutBounds, from 0 to the advance; layoutCorners when it
is not such a box), its texture channel, the vertices of glyphs that are not
textured rectangles, and the "northlight" object with the font's version,
texture format and texture file. The first glyph, which has an index instead
of a unicode, is drawn for characters the font lacks.

The texture is a PNG image (16-bit grayscale for distance fields) when that
converts back to the very same texture, otherwise the font's DDS file. Glyphs
can also be cut into one image each when that loses nothing.

This module holds what decompiling and compiling share: the document's units
and the glyph rectangles in the texture.
"""

import math
import struct
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from northlighttools.binfnt.dds import PixelFormat
from northlighttools.binfnt.model import Glyph, Vertex
from northlighttools.binfnt.texture import Pixels

QUAD_TRIANGLES = (0, 1, 2, 0, 2, 3)
EDGES = ("left", "bottom", "right", "top")


def float32(value: float) -> float:
    """Round a value to the float32 the font stores.

    Args:
        value: The value to round.
    """
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


def same_floats(first: Iterable[float], second: Iterable[float]) -> bool:
    """Return whether two sequences hold the same float32 values.

    Args:
        first: The values of one sequence.
        second: The values of the other sequence.
    """
    first, second = tuple(first), tuple(second)
    return len(first) == len(second) and all(
        struct.pack("<f", a) == struct.pack("<f", b) for a, b in zip(first, second, strict=True)
    )


def json_number(value: float) -> float | int:
    """Return a whole number as an int, so that JSON writes it without a fraction.

    Args:
        value: The number to write.
    """
    if value.is_integer() and math.copysign(1, value) > 0:
        return int(value)
    return value


def to_pixels(coordinate: float, length: int) -> float | int:
    """Return the shortest texel position whose share of length is coordinate.

    Args:
        coordinate: A texture coordinate, from 0 to 1.
        length: The texture's width or height in pixels.
    """
    exact = coordinate * length
    for digits in range(10):
        candidate = round(exact, digits)
        if same_floats([candidate / length], [coordinate]):
            return json_number(candidate)
    return exact


def to_coordinate(pixels: float, length: int) -> float:
    """Return the texture coordinate the font stores for a texel position.

    Args:
        pixels: A texel position.
        length: The texture's width or height in pixels.
    """
    return float32(pixels / length)


@dataclass(frozen=True)
class Rectangle:
    """A glyph drawn as a textured rectangle."""

    plane: tuple[float, float, float, float]
    """Left, bottom, right and top in em units, up from the baseline."""
    atlas: tuple[float, float, float, float]
    """Left, bottom, right and top in texture pixels, down from the top."""

    @classmethod
    def of(cls, glyph: Glyph, width: int, height: int) -> Rectangle | None:
        """Return the rectangle a glyph draws, or None if it draws another shape.

        Args:
            glyph: The glyph to read.
            width: The texture's width in pixels.
            height: The texture's height in pixels.
        """
        if len(glyph.vertices) != 4 or glyph.indices != QUAD_TRIANGLES:
            return None
        bottom_left, bottom_right, top_right, top_left = glyph.vertices
        corners_share_edges = same_floats(
            [bottom_left.y, top_left.x, top_left.y, bottom_right.x],
            [bottom_right.y, bottom_left.x, top_right.y, top_right.x],
        ) and same_floats(
            [top_left.u, bottom_right.u, bottom_right.v, top_left.v],
            [bottom_left.u, top_right.u, bottom_left.v, top_right.v],
        )
        if not corners_share_edges:
            return None
        return cls(
            plane=(bottom_left.x, bottom_left.y, top_right.x, top_right.y),
            atlas=(
                to_pixels(bottom_left.u, width),
                to_pixels(bottom_left.v, height),
                to_pixels(top_right.u, width),
                to_pixels(top_right.v, height),
            ),
        )

    def vertices(self, width: int, height: int) -> tuple[Vertex, ...]:
        """Return the corners of the rectangle as the font stores them.

        Args:
            width: The texture's width in pixels.
            height: The texture's height in pixels.
        """
        left, bottom, right, top = (float32(edge) for edge in self.plane)
        u0, u1 = to_coordinate(self.atlas[0], width), to_coordinate(self.atlas[2], width)
        v1, v0 = to_coordinate(self.atlas[1], height), to_coordinate(self.atlas[3], height)
        return (
            Vertex(left, bottom, u0, v1),
            Vertex(right, bottom, u1, v1),
            Vertex(right, top, u1, v0),
            Vertex(left, top, u0, v0),
        )


def whole_bounds(atlas: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Return left, top, right, bottom texture pixels of an atlas rectangle.

    Args:
        atlas: Left, bottom, right and top in texture pixels, down from the top.
    """
    left, bottom, right, top = (round(edge) for edge in atlas)
    return left, top, right, bottom


def check_inside(bounds: tuple[int, int, int, int], size: tuple[int, int], what: str) -> None:
    """Refuse a rectangle reaching past the texture, which numpy would clip.

    Args:
        bounds: Left, top, right and bottom texture pixels.
        size: The texture's width and height in pixels.
        what: The name of the rectangle in the error.
    """
    left, top, right, bottom = bounds
    width, height = size
    if left < 0 or top < 0 or right > width or bottom > height:
        msg = f"{what} reaches outside the {width}x{height} texture"
        raise ValueError(msg)


def blank_canvas(pixel_format: PixelFormat, size: tuple[int, int], background: str) -> Pixels:
    """Return a texture's pixels filled with its background.

    Args:
        pixel_format: Pixel format of the texture.
        size: The texture's width and height in pixels.
        background: The background pixel as hex: RGBA bytes, or half float bits.
    """
    width, height = size
    value = bytes.fromhex(background)
    if pixel_format is PixelFormat.R16F:
        return np.full((height, width), int.from_bytes(value, "big"), np.uint16)
    canvas = np.empty((height, width, 4), dtype=np.uint8)
    canvas[...] = np.frombuffer(value, dtype=np.uint8)
    return canvas


def texture_region(
    bounds: tuple[int, int, int, int], channel: int | None
) -> tuple[slice | int, ...]:
    """Return the index of a rectangle's pixels in a texture's pixels.

    Args:
        bounds: Left, top, right and bottom texture pixels.
        channel: The one channel to take, or None for all of them.
    """
    left, top, right, bottom = bounds
    rows, columns = slice(top, bottom), slice(left, right)
    return (rows, columns) if channel is None else (rows, columns, channel)
