import pytest

from northlighttools.string_table.layout import Layout


@pytest.mark.parametrize(
    ("text", "paragraphs", "runs"),
    [
        ("One", ("One",), ("", "")),
        ("One\r\nTwo", ("One", "Two"), ("", "\r\n", "")),
        ("One \\n\r\n\\n  Two", ("One", "Two"), ("", " \\n\r\n\\n  ", "")),
        ("\nOne\r", ("One",), ("\n", "\r")),
        ("  One  ", ("  One  ",), ("", "")),
        ("", ("",), ("", "")),
        ("\r\n\\n ", ("",), ("", "\r\n\\n ")),
    ],
)
def test_texts_split_into_paragraphs_and_layout_runs(
    text: str, paragraphs: tuple[str, ...], runs: tuple[str, ...]
) -> None:
    layout = Layout.of(text)

    assert (layout.paragraphs, layout.runs) == (paragraphs, runs)
    assert layout.join(layout.paragraphs) == text


def test_translations_take_the_layout_of_the_source() -> None:
    layout = Layout.of("\nOne\r\n\\nTwo\\n")

    assert layout.join(["Jeden", "Dwa"]) == "\nJeden\r\n\\nDwa\\n"


def test_translations_need_as_many_paragraphs() -> None:
    with pytest.raises(ValueError, match="Expected 2 paragraphs, got 1"):
        Layout.of("One\nTwo").join(["Jeden"])


def test_layouts_need_one_run_more_than_paragraphs() -> None:
    with pytest.raises(ValueError, match="one run more"):
        Layout(("One",), ("",))
