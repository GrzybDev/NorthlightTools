"""Exchanging string tables with translation tools: XLIFF 2.0, XLIFF 1.2 or PO."""

import codecs
import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from lxml import etree

from northlighttools.errors import FormatError
from northlighttools.string_table.po import export_po, import_po
from northlighttools.string_table.table import StringEntry
from northlighttools.string_table.xliff import (
    XLIFF2_ROOT,
    XLIFF12_ROOT,
    export_xliff1,
    export_xliff2,
    import_xliff1,
    import_xliff2,
)


class TranslationFormat(StrEnum):
    """A format string tables are exchanged with translation tools in."""

    XLIFF2 = "xliff-2.0"
    XLIFF1 = "xliff-1.2"
    PO = "po"

    @property
    def suffix(self) -> str:
        """The usual extension of the format's files."""
        return _CODECS[self].suffix

    @classmethod
    def of_suffix(cls, suffix: str) -> "TranslationFormat":
        """Return the format whose files have this extension, XLIFF 2.0 for others."""
        return next((f for f in cls if f.suffix == suffix.lower()), cls.XLIFF2)


@dataclass(frozen=True)
class _Codec:
    suffix: str
    export: Callable[[Iterable[StringEntry], str, str], bytes]
    """Takes the entries, the table's file name and its language."""
    import_: Callable[[bytes], list[StringEntry]]


_CODECS = {
    TranslationFormat.XLIFF2: _Codec(".xlf", export_xliff2, import_xliff2),
    TranslationFormat.XLIFF1: _Codec(".xliff", export_xliff1, import_xliff1),
    # PO records no source language: its Language header is the translation's.
    TranslationFormat.PO: _Codec(
        ".po", lambda entries, filename, _: export_po(entries, filename), import_po
    ),
}
_XLIFF_ROOTS = {
    XLIFF2_ROOT: TranslationFormat.XLIFF2,
    XLIFF12_ROOT: TranslationFormat.XLIFF1,
}


def export_translation(
    entries: Iterable[StringEntry],
    translation_format: TranslationFormat = TranslationFormat.XLIFF2,
    filename: str = "string_table.bin",
    source_language: str = "en",
) -> bytes:
    """Return a document with the entries' texts, in source_language, untranslated."""
    return _CODECS[translation_format].export(entries, filename, source_language)


def import_translation(data: bytes) -> tuple[TranslationFormat, list[StringEntry]]:
    """Build string table entries from a document of any of the formats."""
    translation_format = detect_format(data)
    return translation_format, _CODECS[translation_format].import_(data)


def detect_format(data: bytes) -> TranslationFormat:
    """Tell an XLIFF document's version by its root element; anything else is PO."""
    if not _is_xml(data):
        return TranslationFormat.PO
    try:
        events = etree.iterparse(
            io.BytesIO(data), events=("start",), resolve_entities=False, no_network=True
        )
        _, root = next(events)
    except (etree.XMLSyntaxError, StopIteration) as error:
        msg = f"Cannot read the XML document: {error}"
        raise FormatError(msg) from error
    tag = etree.QName(root).text
    if (found := _XLIFF_ROOTS.get(tag)) is None:
        msg = f"Not an XLIFF 2.0 or 1.2 document: its root element is {tag}"
        raise FormatError(msg)
    return found


def _is_xml(data: bytes) -> bool:
    # XML may come in UTF-16, which gettext does not support.
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return True
    return data.removeprefix(codecs.BOM_UTF8).lstrip().startswith(b"<")
