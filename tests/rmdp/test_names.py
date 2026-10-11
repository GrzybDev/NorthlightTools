import pytest

from northlighttools.rmdp.names import (
    from_filesystem_name,
    name_checksum,
    to_filesystem_name,
)


@pytest.mark.parametrize(
    ("name", "escaped"),
    [
        ("font.binfnt", "font.binfnt"),
        ("d:", "d%3A"),
        ("100%", "100%25"),
        ("a<b>|c?*", "a%3Cb%3E%7Cc%3F%2A"),
        ("..", ".%2E"),
        ("trailing ", "trailing%20"),
        ("nul.txt", "%6Eul.txt"),
        ("COM1", "%43OM1"),
        ("tab\there", "tab%09here"),
    ],
)
def test_names_are_escaped_reversibly(name: str, escaped: str) -> None:
    assert to_filesystem_name(name) == escaped
    assert from_filesystem_name(escaped) == name


def test_empty_names_are_refused() -> None:
    with pytest.raises(ValueError, match="empty name"):
        to_filesystem_name("")


def test_checksum_ignores_letter_case() -> None:
    assert name_checksum("Fonts") == name_checksum("fonts") == 0x7303E8FB
