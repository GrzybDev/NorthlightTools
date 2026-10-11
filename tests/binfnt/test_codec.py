import struct

import pytest

from northlighttools.binfnt import BinaryFont, FontVersion, decode_font, encode_font
from northlighttools.errors import FormatError
from tests.binfnt.fonts import SAMPLES


@pytest.mark.parametrize("font", SAMPLES.values(), ids=SAMPLES.keys())
def test_fonts_survive_a_round_trip(font: BinaryFont) -> None:
    data = encode_font(font)

    assert decode_font(data) == font
    assert encode_font(decode_font(data)) == data


def test_version_3_stores_the_texture_size_and_no_kerning() -> None:
    font = SAMPLES["alan wake"]

    data = encode_font(font)

    texture_size = len(font.texture).to_bytes(4, "little")
    assert data.endswith(texture_size + font.texture)
    with pytest.raises(ValueError, match="have no kerning"):
        encode_font(
            BinaryFont(
                **{**vars(font), "kerning": SAMPLES["alan wake remastered"].kerning}
            )
        )


def test_version_7_ends_with_its_unknown_values_before_the_texture() -> None:
    font = SAMPLES["quantum break"]

    data = encode_font(font)

    assert data.endswith(struct.pack("<2I", 4, 128) + font.texture)


def test_glyphs_own_consecutive_parts_of_the_buffers() -> None:
    data = encode_font(SAMPLES["alan wake"])

    first, count, first_index, index_count = struct.unpack_from(
        "<4H", data, 8 + 12 * 16 + 4 + 18 * 2 + 4 + 44
    )

    assert (first, count, first_index, index_count) == (4, 4, 6, 6)


def test_unknown_versions_are_rejected() -> None:
    data = bytearray(encode_font(SAMPLES["quantum break"]))
    data[0] = 5

    with pytest.raises(FormatError, match="Unsupported font version 5"):
        decode_font(bytes(data))


def test_trailing_data_is_rejected() -> None:
    data = encode_font(SAMPLES["alan wake"]) + b"\0"

    with pytest.raises(FormatError, match="unexpected bytes"):
        decode_font(data)


def test_characters_must_map_to_existing_glyphs() -> None:
    font = SAMPLES["quantum break"]

    with pytest.raises(ValueError, match="Cannot map character 67"):
        encode_font(BinaryFont(**{**vars(font), "charmap": {67: 9}}))


def test_version_4_kerning_amounts_must_be_whole() -> None:
    font = SAMPLES["alan wake remastered"]
    kerning = [type(pair)(pair.first, pair.second, 0.5) for pair in font.kerning]

    with pytest.raises(ValueError, match="integers"):
        encode_font(BinaryFont(**{**vars(font), "kerning": kerning}))


def test_glyph_zero_maps_to_no_character() -> None:
    font = decode_font(encode_font(SAMPLES["quantum break"]))

    assert 0 not in font.charmap.values()
    assert font.version is FontVersion.V7
