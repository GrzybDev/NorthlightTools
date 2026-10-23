"""The DDS textures of fonts, limited to the pixel formats the games use."""

from dataclasses import dataclass
from enum import StrEnum

from northlighttools.binary import BinaryReader, BinaryWriter
from northlighttools.errors import FormatError

_MAGIC = b"DDS "
_HEADER_SIZE = 124
_PIXEL_FORMAT_SIZE = 32

_CAPS, _HEIGHT, _WIDTH, _PITCH = 0x1, 0x2, 0x4, 0x8
_PIXEL_FORMAT, _MIPMAP_COUNT, _LINEAR_SIZE = 0x1000, 0x20000, 0x80000
_ALPHA_PIXELS, _FOURCC, _RGB = 0x1, 0x4, 0x40
_CAPS_ALPHA, _CAPS_COMPLEX, _CAPS_TEXTURE, _CAPS_MIPMAP = 0x2, 0x8, 0x1000, 0x400000

_D3DFMT_R16F = (111).to_bytes(4, "little")


class PixelFormat(StrEnum):
    A4R4G4B4 = "a4r4g4b4"
    A8R8G8B8 = "a8r8g8b8"
    DXT5 = "dxt5"
    R16F = "r16f"
    """One 16-bit float channel, holding signed distances in the games' fonts."""

    @property
    def compressed(self) -> bool:
        """Whether the format stores pixels in compressed 4x4 blocks."""
        return self is PixelFormat.DXT5


_FOURCCS = {PixelFormat.DXT5: b"DXT5", PixelFormat.R16F: _D3DFMT_R16F}
_RGB_MASKS = {
    PixelFormat.A4R4G4B4: (16, 0x0F00, 0x00F0, 0x000F, 0xF000),
    PixelFormat.A8R8G8B8: (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000),
}
_BYTES_PER_PIXEL = {
    PixelFormat.A4R4G4B4: 2,
    PixelFormat.A8R8G8B8: 4,
    PixelFormat.R16F: 2,
}


def level_size(pixel_format: PixelFormat, width: int, height: int) -> int:
    """Return the byte size of an image of the given size.

    Args:
        pixel_format: Pixel format of the image.
        width: Width in pixels.
        height: Height in pixels.
    """
    if pixel_format.compressed:
        return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 16
    return width * height * _BYTES_PER_PIXEL[pixel_format]


def level_dimensions(width: int, height: int, level: int) -> tuple[int, int]:
    """Return the width and height of a mipmap level.

    Args:
        width: Width of the full-size image.
        height: Height of the full-size image.
        level: Mipmap level, 0 for the full-size image.
    """
    return max(1, width >> level), max(1, height >> level)


@dataclass(frozen=True)
class DdsTexture:
    width: int
    height: int
    pixel_format: PixelFormat
    levels: tuple[bytes, ...]
    """Pixel data of each mipmap level, the full-size image first."""


def decode_dds(data: bytes) -> DdsTexture:
    """Parse a DDS texture in one of the pixel formats the games' fonts use.

    Args:
        data: Contents of a DDS file.
    """
    reader = BinaryReader(data)
    if reader.read(4) != _MAGIC or reader.u32() != _HEADER_SIZE:
        msg = "Not a DDS texture"
        raise FormatError(msg)
    flags, height, width, _, _, mipmap_count = reader.unpack("6I")
    reader.read(44)
    if reader.u32() != _PIXEL_FORMAT_SIZE:
        msg = "The DDS pixel format block is malformed"
        raise FormatError(msg)
    format_flags = reader.u32()
    fourcc = reader.read(4)
    masks = reader.unpack("5I")
    reader.read(20)

    pixel_format = next(
        (f for f, code in _FOURCCS.items() if format_flags & _FOURCC and fourcc == code),
        None,
    ) or next((f for f, m in _RGB_MASKS.items() if format_flags & _RGB and masks == m), None)
    if pixel_format is None:
        msg = f"Unsupported DDS pixel format (flags {format_flags:#x}, {fourcc!r})"
        raise FormatError(msg)
    count = mipmap_count if flags & _MIPMAP_COUNT and mipmap_count else 1
    levels = tuple(
        reader.read(level_size(pixel_format, *level_dimensions(width, height, level)))
        for level in range(count)
    )
    if reader.remaining:
        msg = f"{reader.remaining} unexpected bytes after the DDS mipmaps"
        raise FormatError(msg)
    return DdsTexture(width, height, pixel_format, levels)


def encode_dds(texture: DdsTexture, legacy_header: bool) -> bytes:
    """Build a DDS file with the header conventions of the games' fonts.

    Version 3 fonts carry the header D3DX writes; later ones the header of
    DirectXTex, which also fills the pitch and the depth.

    Args:
        texture: The texture to write.
        legacy_header: Whether to write the D3DX header of version 3 fonts.
    """
    pixel_format = texture.pixel_format
    count = len(texture.levels)
    mipmapped = count > 1
    flags = _CAPS | _HEIGHT | _WIDTH | _PIXEL_FORMAT
    caps = _CAPS_TEXTURE | (_CAPS_COMPLEX | _CAPS_MIPMAP if mipmapped else 0)
    if legacy_header:
        flags |= _MIPMAP_COUNT if mipmapped else 0
        pitch = depth = 0
        mipmap_count = count if mipmapped else 0
        caps |= 0 if pixel_format.compressed else _CAPS_ALPHA
    else:
        flags |= _MIPMAP_COUNT | (_LINEAR_SIZE if pixel_format.compressed else _PITCH)
        pitch = (
            level_size(pixel_format, texture.width, texture.height)
            if pixel_format.compressed
            else texture.width * _BYTES_PER_PIXEL[pixel_format]
        )
        depth = 1
        mipmap_count = count

    writer = BinaryWriter()
    writer.write(_MAGIC)
    writer.pack(
        "7I",
        _HEADER_SIZE,
        flags,
        texture.height,
        texture.width,
        pitch,
        depth,
        mipmap_count,
    )
    writer.write(bytes(44))
    if pixel_format in _FOURCCS:
        writer.pack("2I", _PIXEL_FORMAT_SIZE, _FOURCC)
        writer.write(_FOURCCS[pixel_format])
        writer.write(bytes(20))
    else:
        writer.pack("2I", _PIXEL_FORMAT_SIZE, _RGB | _ALPHA_PIXELS)
        writer.write(bytes(4))
        writer.pack("5I", *_RGB_MASKS[pixel_format])
    writer.pack("4I", caps, 0, 0, 0)
    writer.write(bytes(4))
    for level in texture.levels:
        writer.write(level)
    return writer.getvalue()
