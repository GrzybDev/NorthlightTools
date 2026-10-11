import codecs

import pytest

from northlighttools.errors import FormatError
from northlighttools.string_table import (
    StringEntry,
    TranslationFormat,
    detect_format,
    export_translation,
    import_translation,
)

from .entries import ENTRIES


@pytest.mark.parametrize("translation_format", list(TranslationFormat))
def test_every_format_is_told_apart_and_imports_back_unchanged(
    translation_format: TranslationFormat,
) -> None:
    data = export_translation(ENTRIES, translation_format)

    assert import_translation(data) == (translation_format, ENTRIES)
    assert detect_format(codecs.BOM_UTF8 + data) is translation_format


@pytest.mark.parametrize(
    "translation_format", [TranslationFormat.XLIFF2, TranslationFormat.XLIFF1]
)
def test_xliff_in_utf_16_is_read_as_xml(translation_format: TranslationFormat) -> None:
    data = export_translation(ENTRIES, translation_format).decode()
    utf16 = data.replace('encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16")

    assert import_translation(utf16) == (translation_format, ENTRIES)


def test_xliff_2_0_is_the_default() -> None:
    assert detect_format(export_translation(ENTRIES)) is TranslationFormat.XLIFF2


def test_formats_have_their_usual_extensions() -> None:
    assert [f.suffix for f in TranslationFormat] == [".xlf", ".xliff"]
    assert TranslationFormat.of_suffix(".xliff") is TranslationFormat.XLIFF1
    assert TranslationFormat.of_suffix(".txt") is TranslationFormat.XLIFF2


@pytest.mark.parametrize("translation_format", list(TranslationFormat))
@pytest.mark.parametrize(
    ("key", "text"), [("KEY", "a\x0bb"), ("K\x00", "text"), ("KEY", chr(0xD800))]
)
def test_characters_documents_cannot_carry_are_refused(
    translation_format: TranslationFormat, key: str, text: str
) -> None:
    with pytest.raises(ValueError, match=r"holds U\+\w{4}, which \S+ cannot carry"):
        export_translation([StringEntry(key, text)], translation_format)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b"<tmx version='1.4'/>", "Not an XLIFF 2.0 or 1.2 document: .* tmx"),
        (b"<xliff version='1.2'/>", "Not an XLIFF 2.0 or 1.2 document: .* xliff"),
        (
            b"<xliff xmlns='urn:oasis:names:tc:xliff:document:1.1' version='1.1'/>",
            "Not an XLIFF 2.0 or 1.2 document",
        ),
        (b"<!-- unclosed", "Cannot read the XML document"),
    ],
)
def test_other_xml_documents_are_reported(document: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        detect_format(document)


def test_empty_files_are_not_taken_for_an_empty_table() -> None:
    with pytest.raises(FormatError, match="Cannot read the XML document"):
        import_translation(b"")
