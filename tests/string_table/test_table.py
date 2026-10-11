import pytest

from northlighttools.errors import FormatError
from northlighttools.string_table import (
    StringEntry,
    decode_string_table,
    encode_string_table,
)

ENTRIES = [
    StringEntry("MENU_TITLE", "Main menu"),
    StringEntry("REPEATED", "first"),
    StringEntry("REPEATED", "second"),
    StringEntry("DOC_BODY", "<p>One</p>\r\n<p>Two</p>"),
    StringEntry("CAPTION", "Line\\nbreak"),
    StringEntry("EMPTY", ""),
    StringEntry("CONT\u2019D", "Zażółć gęślą jaźń"),
    StringEntry("EMOJI", "\U0001f600"),
]


def test_entries_survive_a_round_trip() -> None:
    assert decode_string_table(encode_string_table(ENTRIES)) == ENTRIES


def test_lengths_count_key_bytes_and_utf16_code_units() -> None:
    data = encode_string_table([StringEntry("K\u2019", "\U0001f600")])

    assert data == (
        b"\x01\x00\x00\x00"
        + b"\x04\x00\x00\x00K\xe2\x80\x99"
        + b"\x02\x00\x00\x00"
        + "\U0001f600".encode("utf-16-le")
    )


def test_a_truncated_table_is_rejected() -> None:
    with pytest.raises(FormatError, match="Unexpected end"):
        decode_string_table(encode_string_table(ENTRIES)[:-3])


def test_trailing_data_is_rejected() -> None:
    with pytest.raises(FormatError, match="unexpected bytes"):
        decode_string_table(encode_string_table(ENTRIES) + b"\x00")


def test_lone_surrogates_in_keys_and_texts_survive_a_round_trip() -> None:
    lone = chr(0xD800)
    entries = [StringEntry(f"KEY{lone}", f"text{lone}")]

    assert decode_string_table(encode_string_table(entries)) == entries
