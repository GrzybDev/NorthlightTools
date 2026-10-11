import re
from collections.abc import Callable

import pytest
from lxml import etree

from northlighttools.errors import FormatError
from northlighttools.string_table import StringEntry
from northlighttools.string_table.xliff import (
    export_xliff1,
    export_xliff2,
    import_xliff1,
    import_xliff2,
)

from .entries import ENTRIES, translate, translated

XLIFF2 = "{urn:oasis:names:tc:xliff:document:2.0}"
XLIFF1 = "{urn:oasis:names:tc:xliff:document:1.2}"
NMTOKEN = re.compile(r"[A-Za-z0-9._:-]+")

type Export = Callable[[list[StringEntry], str, str], bytes]
type Import = Callable[[bytes], list[StringEntry]]

FORMATS = [
    pytest.param(export_xliff2, import_xliff2, XLIFF2, "segment", id="xliff-2.0"),
    pytest.param(export_xliff1, import_xliff1, XLIFF1, "trans-unit", id="xliff-1.2"),
]


def add_targets(
    data: bytes,
    namespace: str,
    translatable: str,
    translation: Callable[[str], str] = translate,
) -> bytes:
    """Translate every translatable element the way a translation tool would."""
    root = etree.fromstring(data)
    for element in root.iter(f"{namespace}{translatable}"):
        if element.get("translate") == "no":
            continue
        source = element.find(f"{namespace}source")
        assert source is not None
        target = etree.SubElement(element, f"{namespace}target")
        target.text = translation(source.text or "")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


@pytest.mark.parametrize(("export", "import_", "namespace", "translatable"), FORMATS)
def test_untranslated_export_imports_back_unchanged(
    export: Export, import_: Import, namespace: str, translatable: str
) -> None:
    assert import_(export(ENTRIES, "string_table.bin", "en")) == ENTRIES


@pytest.mark.parametrize(("export", "import_", "namespace", "translatable"), FORMATS)
def test_translated_paragraphs_keep_the_layout(
    export: Export, import_: Import, namespace: str, translatable: str
) -> None:
    data = add_targets(
        export(ENTRIES, "string_table.bin", "en"), namespace, translatable
    )

    assert import_(data) == [translated(entry) for entry in ENTRIES]


@pytest.mark.parametrize(("export", "import_", "namespace", "translatable"), FORMATS)
def test_empty_targets_keep_the_source(
    export: Export, import_: Import, namespace: str, translatable: str
) -> None:
    data = export(ENTRIES, "string_table.bin", "en")

    assert import_(add_targets(data, namespace, translatable, lambda _: "")) == ENTRIES


def test_xliff2_units_hold_a_segment_per_paragraph_and_an_ignorable_per_run() -> None:
    root = etree.fromstring(export_xliff2(ENTRIES))
    letter = next(u for u in root.iter(f"{XLIFF2}unit") if u.get("name") == "LETTER")

    parts = [(etree.QName(part).localname, part.get("id")) for part in letter]
    sources = [part.findtext(f"{XLIFF2}source") for part in letter]

    assert letter.get("canResegment") == "no"
    assert parts == [
        ("segment", "1"),
        ("ignorable", None),
        ("segment", "2"),
        ("ignorable", None),
        ("segment", "3"),
        ("ignorable", None),
    ]
    assert sources == [
        "Josef,",
        "\r\n\\n\r\n\\n",
        "I asked.",
        " \t\r\n\\n\r\n\\n",
        "-Josef",
        "\r\n",
    ]


def test_xliff2_identifiers_are_unique_nmtokens_and_names_hold_the_keys() -> None:
    root = etree.fromstring(export_xliff2(ENTRIES, "string table (1).bin"))
    file = root.find(f"{XLIFF2}file")
    assert file is not None
    units = list(root.iter(f"{XLIFF2}unit"))
    ids = [unit.get("id") or "" for unit in units]

    assert file.get("id") == "string_table__1_.bin"
    assert [unit.get("name") for unit in units] == [entry.key for entry in ENTRIES]
    assert all(NMTOKEN.fullmatch(unit_id) for unit_id in ids)
    assert len(set(ids)) == len(ids)
    assert ids[1:3] == ["REPEATED", "REPEATED.2"]
    assert ids[-3:] == ["A:B", "A_B", "A_B.2"]


def test_xliff1_groups_texts_with_layout_and_marks_the_layout_untranslatable() -> None:
    root = etree.fromstring(export_xliff1(ENTRIES))
    body = root.find(f"{XLIFF1}file/{XLIFF1}body")
    assert body is not None
    letter = next(
        g for g in body.iter(f"{XLIFF1}group") if g.get("resname") == "LETTER"
    )

    units = [(unit.get("id"), unit.get("translate")) for unit in letter]

    assert body[0].tag == f"{XLIFF1}trans-unit"
    assert body[0].get("resname") == "MENU_TITLE"
    assert units == [
        ("LETTER/1", None),
        ("LETTER/layout-1", "no"),
        ("LETTER/2", None),
        ("LETTER/layout-2", "no"),
        ("LETTER/3", None),
        ("LETTER/layout-3", "no"),
    ]


def test_xliff1_is_version_1_2_of_the_string_table() -> None:
    root = etree.fromstring(export_xliff1(ENTRIES, "string table (1).bin", "pl"))
    file = root.find(f"{XLIFF1}file")
    assert file is not None

    assert root.get("version") == "1.2"
    assert file.get("original") == "string table (1).bin"
    assert file.get("datatype") == "x-northlight-string-table"
    assert file.get("source-language") == "pl"


def test_xliff2_documents_say_the_source_language() -> None:
    root = etree.fromstring(export_xliff2(ENTRIES, "string_table.bin", "pl"))

    assert root.get("srcLang") == "pl"


@pytest.mark.parametrize(
    ("import_", "document"),
    [
        (
            import_xliff2,
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0">'
            b'<file id="f"><unit id="u"><segment><source>x</source></segment></unit>'
            b"</file></xliff>",
        ),
        (
            import_xliff1,
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">'
            b'<file original="f"><body><trans-unit id="u"><source>x</source>'
            b"</trans-unit></body></file></xliff>",
        ),
    ],
)
def test_units_without_a_key_are_reported(import_: Import, document: bytes) -> None:
    with pytest.raises(FormatError, match="has no"):
        import_(document)


@pytest.mark.parametrize(
    ("import_", "document"),
    [
        (import_xliff2, b'<xliff version="2.0"><file id="f"/></xliff>'),
        (import_xliff1, b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.1"/>'),
        (import_xliff1, b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0"/>'),
    ],
)
def test_other_xliff_documents_are_refused(import_: Import, document: bytes) -> None:
    with pytest.raises(FormatError, match="Not an XLIFF"):
        import_(document)


@pytest.mark.parametrize("import_", [import_xliff2, import_xliff1])
def test_unreadable_documents_are_reported(import_: Import) -> None:
    with pytest.raises(FormatError, match="Cannot read the XLIFF document"):
        import_(b"<xliff")
