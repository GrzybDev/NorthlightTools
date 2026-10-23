"""Converting font textures between DDS pixel data and images.

Images keep the stored values exactly: 4-bit channels widen to 8 bits, and the
half floats of distance fields become 16-bit gray levels through a mapping that
keeps their order: the glyph edge is mid-gray, the inside lighter and texels
beyond the field (stored as not-a-number) black.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from northlighttools.binfnt.dds import DdsTexture, PixelFormat

Pixels = NDArray[np.uint8] | NDArray[np.uint16]
"""RGBA bytes (height, width, 4), or half float bits (height, width) for R16F."""

_SIGN = 0x8000
_GRAY_EDGE = 0x7FFF
# The games' distance fields mark texels beyond their range with this
# not-a-number, which is not the one numpy writes.
_BEYOND_FIELD = 0x7FFF


def can_convert(pixel_format: PixelFormat) -> bool:
    """Return whether textures of a pixel format convert to and from images.

    Args:
        pixel_format: Pixel format of the texture.
    """
    return pixel_format is not PixelFormat.DXT5


def decode_pixels(texture: DdsTexture) -> Pixels:
    """Return the full-size image of an uncompressed texture.

    Args:
        texture: A texture in a pixel format that can_convert accepts.
    """
    width, height, data = texture.width, texture.height, texture.levels[0]
    match texture.pixel_format:
        case PixelFormat.A4R4G4B4:
            packed = np.frombuffer(data, "<u2").reshape(height, width)
            nibbles = [(packed >> shift) & 0xF for shift in (8, 4, 0, 12)]
            return (np.stack(nibbles, axis=-1) * 17).astype(np.uint8)
        case PixelFormat.A8R8G8B8:
            bgra = np.frombuffer(data, np.uint8).reshape(height, width, 4)
            return bgra[..., [2, 1, 0, 3]].copy()
        case PixelFormat.R16F:
            return np.frombuffer(data, "<u2").reshape(height, width).copy()
        case PixelFormat.DXT5:
            msg = "DXT5 textures are kept as DDS files"
            raise ValueError(msg)


def encode_pixels(pixels: Pixels, pixel_format: PixelFormat, mipmap_count: int) -> DdsTexture:
    """Build a texture and its mipmaps from a full-size image.

    Mipmaps average 2x2 blocks of the stored values, rounding to nearest, which
    reproduces those of the games' own fonts.

    Args:
        pixels: The full-size image.
        pixel_format: Pixel format to store.
        mipmap_count: Number of levels, the full-size image included.
    """
    height, width = pixels.shape[:2]
    values = _stored_values(pixels, pixel_format)
    levels = []
    for level in range(mipmap_count):
        if level:
            values = (
                _halve_half_floats(values) if pixel_format is PixelFormat.R16F else _halve(values)
            )
        levels.append(_pack(values, pixel_format))
    return DdsTexture(width, height, pixel_format, tuple(levels))


def to_image(pixels: Pixels, pixel_format: PixelFormat) -> Image.Image:
    """Return an image that keeps the stored values of the pixels exactly.

    Args:
        pixels: Pixels as decode_pixels returns them.
        pixel_format: Pixel format the pixels come from.
    """
    if pixel_format is PixelFormat.R16F:
        bits = pixels.astype(np.int32)
        gray = np.where(bits & _SIGN, bits, _GRAY_EDGE - bits)
        return Image.fromarray(gray.astype("<u2"))
    return Image.fromarray(np.asarray(pixels, dtype=np.uint8))


def from_image(image: Image.Image, pixel_format: PixelFormat) -> Pixels:
    """Undo to_image.

    Args:
        image: An image made by to_image or edited from one.
        pixel_format: Pixel format to store.
    """
    if pixel_format is PixelFormat.R16F:
        if image.mode not in ("I;16", "I;16B", "I"):
            msg = f"A distance field needs a 16-bit grayscale image, not {image.mode}"
            raise ValueError(msg)
        gray = np.asarray(image).astype(np.int32)
        bits = np.where(gray & _SIGN, gray, _GRAY_EDGE - gray)
        return bits.astype(np.uint16)
    return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def _stored_values(pixels: Pixels, pixel_format: PixelFormat) -> NDArray[Any]:
    match pixel_format:
        case PixelFormat.A4R4G4B4:
            return np.clip(np.rint(pixels / 17), 0, 15).astype(np.int32)
        case PixelFormat.A8R8G8B8:
            return pixels.astype(np.int32)
        case PixelFormat.R16F:
            return pixels.astype(np.uint16)
        case PixelFormat.DXT5:
            msg = "DXT5 textures are kept as DDS files"
            raise ValueError(msg)


def _halve(values: NDArray[Any]) -> NDArray[Any]:
    """Average blocks of up to 2x2 values, dropping a last odd row or column."""
    for axis in (0, 1):
        if values.shape[axis] > 1:
            count = values.shape[axis] // 2 * 2
            values = values.take(range(0, count, 2), axis=axis) + values.take(
                range(1, count, 2), axis=axis
            )
        else:
            values = values * 2
    if np.issubdtype(values.dtype, np.floating):
        return values / 4
    return (values + 2) // 4


def _halve_half_floats(bits: NDArray[Any]) -> NDArray[Any]:
    averaged = _halve(bits.astype("<u2").view("<f2").astype(np.float32))
    halved = averaged.astype("<f2").view("<u2").copy()
    halved[np.isnan(averaged)] = _BEYOND_FIELD
    return halved


def _pack(values: NDArray[Any], pixel_format: PixelFormat) -> bytes:
    match pixel_format:
        case PixelFormat.A4R4G4B4:
            red, green, blue, alpha = np.moveaxis(values, -1, 0)
            packed = alpha << 12 | red << 8 | green << 4 | blue
            return bytes(packed.astype("<u2").tobytes())
        case PixelFormat.A8R8G8B8:
            return bytes(values[..., [2, 1, 0, 3]].astype(np.uint8).tobytes())
        case _:
            return bytes(values.astype("<u2").tobytes())
