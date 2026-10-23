"""Exchanging string tables with translation tools through XLIFF 2.0 and 1.2.

Each entry becomes a unit named after its key; its identifier is the key made
fit for XML, numbered when that clashes with another. The paragraphs of a text
(see Layout) are what translators get, its layout runs come back unchanged:

* XLIFF 2.0: the unit holds a segment per paragraph and an ignorable per run;
* XLIFF 1.2: a text with one paragraph and no layout is a trans-unit, any other
  text a group of trans-units: the paragraphs, and the runs with translate="no".

translate-toolkit has no API for these structures, so they are built with lxml
in the documents it creates and writes, and read with lxml. A paragraph takes
its target when it has a non-empty one, whatever its state: OmegaT marks no
state in XLIFF 2.0. Untranslated paragraphs keep their source text.
"""

import re
from collections.abc import Callable, Iterable, Iterator

from lxml import etree
from translate.storage.xliff import Xliff1File
from translate.storage.xliff2 import Xliff2File

from northlighttools.errors import FormatError
from northlighttools.string_table.characters import checked
from northlighttools.string_table.layout import Layout
from northlighttools.string_table.table import StringEntry

_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_XLIFF12 = "urn:oasis:names:tc:xliff:document:1.2"
# translate-toolkit writes XLIFF 1.1 unless it starts from a 1.2 document.
_XLIFF12_SKELETON = f"""<?xml version="1.0" ?>
<xliff version="1.2" xmlns="{_XLIFF12}">
<file original="NoName" source-language="en" datatype="x-northlight-string-table">
<body>
</body>
</file>
</xliff>""".encode()
_NOT_IN_IDS = re.compile(r"[^A-Za-z0-9._:-]")

type _Tag = Callable[[str], str]


def _xliff2(name: str) -> str:
    return f"{{{Xliff2File.namespace}}}{name}"


def _xliff1(name: str) -> str:
    return f"{{{_XLIFF12}}}{name}"


XLIFF2_ROOT = _xliff2("xliff")
XLIFF12_ROOT = _xliff1("xliff")


def export_xliff2(
    entries: Iterable[StringEntry],
    filename: str = "string_table.bin",
    source_language: str = "en",
) -> bytes:
    """Return an XLIFF 2.0 document with the entries' texts as untranslated sources.

    Args:
        entries: The string table's entries.
        filename: Name of the string table, recorded in the document.
        source_language: Language of the texts, as a BCP 47 tag.
    """
    store = Xliff2File()
    store.setsourcelanguage(source_language)
    file = store.document.getroot()[0]
    store.setfilename(file, _xml_id(filename))
    for unit_id, key, layout in _units(entries):
        unit = etree.SubElement(file, _xliff2("unit"), id=unit_id, name=key)
        unit.set(_XML_SPACE, "preserve")
        numbered = len(layout.paragraphs) > 1
        if numbered:
            unit.set("canResegment", "no")
        for is_paragraph, number, text in _parts(layout):
            part = etree.SubElement(unit, _xliff2("segment" if is_paragraph else "ignorable"))
            if is_paragraph and numbered:
                part.set("id", str(number))
            etree.SubElement(part, _xliff2("source")).text = text
    return bytes(store)


def import_xliff2(data: bytes) -> list[StringEntry]:
    """Build string table entries from an XLIFF 2.0 document, in its order.

    Args:
        data: Contents of the XLIFF 2.0 document.
    """
    document = _parse(data, XLIFF2_ROOT, "XLIFF 2.0")
    parts = {_xliff2("segment"), _xliff2("ignorable")}
    return [
        StringEntry(
            _key(unit, "name"),
            "".join(_text(part, _xliff2) for part in unit if part.tag in parts),
        )
        for unit in document.iter(_xliff2("unit"))
    ]


def export_xliff1(
    entries: Iterable[StringEntry],
    filename: str = "string_table.bin",
    source_language: str = "en",
) -> bytes:
    """Return an XLIFF 1.2 document with the entries' texts as untranslated sources.

    Args:
        entries: The string table's entries.
        filename: Name of the string table, recorded in the document.
        source_language: Language of the texts, as a BCP 47 tag.
    """
    store = Xliff1File.parsestring(_XLIFF12_SKELETON)
    store.setsourcelanguage(source_language)
    file = store.document.getroot()[0]
    store.setfilename(file, filename)
    body = file[0]
    for unit_id, key, layout in _units(entries):
        if len(layout.paragraphs) == 1 and not any(layout.runs):
            _trans_unit(body, unit_id, layout.paragraphs[0]).set("resname", key)
            continue
        group = etree.SubElement(body, _xliff1("group"), id=unit_id, resname=key)
        for is_paragraph, number, text in _parts(layout):
            if is_paragraph:
                _trans_unit(group, f"{unit_id}/{number}", text)
            else:
                unit = _trans_unit(group, f"{unit_id}/layout-{number}", text)
                unit.set("translate", "no")
    return bytes(store)


def import_xliff1(data: bytes) -> list[StringEntry]:
    """Build string table entries from an XLIFF 1.2 document, in its order.

    Args:
        data: Contents of the XLIFF 1.2 document.
    """
    document = _parse(data, XLIFF12_ROOT, "XLIFF 1.2")
    entries = []
    for body in document.iter(_xliff1("body")):
        for element in body:
            if element.tag == _xliff1("trans-unit"):
                text = _text(element, _xliff1)
            elif element.tag == _xliff1("group"):
                units = element.iter(_xliff1("trans-unit"))
                text = "".join(_text(unit, _xliff1) for unit in units)
            else:
                continue
            entries.append(StringEntry(_key(element, "resname"), text))
    return entries


def _units(entries: Iterable[StringEntry]) -> Iterator[tuple[str, str, Layout]]:
    """Yield each entry's unit identifier, key and layout."""
    used: set[str] = set()
    for entry in checked(entries, "XLIFF"):
        base = _xml_id(entry.key)
        unit_id, number = base, 1
        while unit_id in used:
            number += 1
            unit_id = f"{base}.{number}"
        used.add(unit_id)
        yield unit_id, entry.key, Layout.of(entry.value)


def _xml_id(name: str) -> str:
    """Make a name fit for an XLIFF 2.0 identifier (an XML name token)."""
    return _NOT_IN_IDS.sub("_", name) or "_"


def _parts(layout: Layout) -> Iterator[tuple[bool, int, str]]:
    """Yield the paragraphs and the non-empty layout runs with their numbers.

    Paragraphs are numbered from 1; a run takes the number of the paragraph it
    follows, 0 before the first paragraph.
    """
    if layout.runs[0]:
        yield False, 0, layout.runs[0]
    for number, (paragraph, run) in enumerate(
        zip(layout.paragraphs, layout.runs[1:], strict=True), start=1
    ):
        yield True, number, paragraph
        if run:
            yield False, number, run


def _trans_unit(parent: etree._Element, unit_id: str, text: str) -> etree._Element:
    unit = etree.SubElement(parent, _xliff1("trans-unit"), id=unit_id)
    unit.set(_XML_SPACE, "preserve")
    etree.SubElement(unit, _xliff1("source")).text = text
    return unit


def _parse(data: bytes, root: str, name: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    try:
        document = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as error:
        msg = f"Cannot read the XLIFF document: {error}"
        raise FormatError(msg) from error
    if (tag := etree.QName(document).text) != root:
        msg = f"Not an {name} document: its root element is {tag}"
        raise FormatError(msg)
    return document


def _key(element: etree._Element, attribute: str) -> str:
    key = element.get(attribute)
    if key is None:
        msg = f"The unit {element.get('id')!r} has no {attribute} to take its key from"
        raise FormatError(msg)
    return key


def _text(element: etree._Element, tag: _Tag) -> str:
    """Return the text of an element's target, or of its source when untranslated."""
    for name in ("target", "source"):
        child = element.find(tag(name))
        if child is not None and (text := str(child.xpath("string()"))):
            return text
    return ""
