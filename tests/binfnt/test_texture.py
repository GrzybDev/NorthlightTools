import numpy as np
import pytest

from northlighttools.binfnt.dds import (
    DdsTexture,
    PixelFormat,
    decode_dds,
    encode_dds,
)
from northlighttools.binfnt.texture import (
    decode_pixels,
    encode_pixels,
    from_image,
    to_image,
)
from northlighttools.errors import FormatError
from tests.binfnt.fonts import pixels_for

CONVERTIBLE = [PixelFormat.A4R4G4B4, PixelFormat.A8R8G8B8, PixelFormat.R16F]


@pytest.mark.parametrize("pixel_format", CONVERTIBLE)
@pytest.mark.parametrize("legacy_header", [True, False])
def test_textures_survive_a_round_trip(
    pixel_format: PixelFormat, legacy_header: bool
) -> None:
    texture = encode_pixels(pixels_for(pixel_format), pixel_format, 3)

    data = encode_dds(texture, legacy_header)

    assert decode_dds(data) == texture
    assert np.array_equal(decode_pixels(texture), pixels_for(pixel_format))


@pytest.mark.parametrize(
    ("legacy_header", "flags", "pitch", "depth", "mipmaps", "caps"),
    [
        (True, 0x21007, 0, 0, 3, 0x40100A),
        (False, 0x2100F, 64, 1, 3, 0x401008),
    ],
)
def test_headers_follow_the_games_conventions(
    legacy_header: bool, flags: int, pitch: int, depth: int, mipmaps: int, caps: int
) -> None:
    texture = encode_pixels(pixels_for(PixelFormat.A8R8G8B8), PixelFormat.A8R8G8B8, 3)

    data = encode_dds(texture, legacy_header)

    header = np.frombuffer(data[:128], "<u4")
    assert (header[2], header[5], header[6], header[7], header[27]) == (
        flags,
        pitch,
        depth,
        mipmaps,
        caps,
    )


def test_mipmaps_average_blocks_rounding_to_nearest() -> None:
    pixels = np.zeros((2, 3, 4), dtype=np.uint8)
    pixels[..., 0] = [[0, 1, 9], [1, 1, 9]]

    texture = encode_pixels(pixels, PixelFormat.A8R8G8B8, 2)

    assert texture.levels[1][2] == 1
    assert len(texture.levels[1]) == 4


def test_every_half_float_survives_the_grayscale_image() -> None:
    bits = np.arange(0x10000, dtype=np.uint16).reshape(256, 256)

    image = to_image(bits, PixelFormat.R16F)

    assert np.array_equal(from_image(image, PixelFormat.R16F), bits)


def test_distance_field_images_show_the_glyph_lighter_than_its_surroundings() -> None:
    distances = np.array([[-4.0, -0.0, 0.0, 4.0]], dtype="<f2").view("<u2")
    empty = np.array([[0x7FFF]], dtype=np.uint16)

    gray = np.asarray(to_image(distances, PixelFormat.R16F)).astype(int)[0]

    assert gray[0] > gray[1] > gray[2] > gray[3]
    assert (gray[1], gray[2]) == (0x8000, 0x7FFF)
    assert np.asarray(to_image(empty, PixelFormat.R16F))[0, 0] == 0


def test_distance_fields_need_a_16_bit_image() -> None:
    image = to_image(pixels_for(PixelFormat.A8R8G8B8), PixelFormat.A8R8G8B8)

    with pytest.raises(ValueError, match="16-bit grayscale"):
        from_image(image, PixelFormat.R16F)


def test_unsupported_pixel_formats_are_rejected() -> None:
    texture = DdsTexture(4, 4, PixelFormat.DXT5, (bytes(16),))
    data = bytearray(encode_dds(texture, legacy_header=False))
    data[84:88] = b"DXT1"

    with pytest.raises(FormatError, match="Unsupported DDS pixel format"):
        decode_dds(bytes(data))
