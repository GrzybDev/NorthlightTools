import pytest
from translate.storage.pypo import pofile

from northlighttools.errors import FormatError
from northlighttools.string_table import StringEntry
from northlighttools.string_table.po import export_po, import_po

from .entries import ENTRIES, translate, translated


def units(data: bytes) -> list[tuple[str, str, str]]:
    return [
        (unit.getcontext(), unit.source, unit.getnotes("developer"))
        for unit in pofile.parsestring(data).units
        if not unit.isheader()
    ]


def test_untranslated_export_imports_back_unchanged() -> None:
    assert import_po(export_po(ENTRIES)) == ENTRIES


def test_translated_paragraphs_keep_the_layout() -> None:
    store = pofile.parsestring(export_po(ENTRIES))
    for unit in store.units:
        if not unit.isheader():
            unit.target = translate(unit.source)

    assert import_po(bytes(store)) == [translated(entry) for entry in ENTRIES]


def test_fuzzy_translations_are_not_used() -> None:
    store = pofile.parsestring(export_po([StringEntry("KEY", "Hello")]))
    unit = store.units[1]
    unit.target = "Cześć"
    unit.markfuzzy()

    assert import_po(bytes(store)) == [StringEntry("KEY", "Hello")]


def test_paragraphs_become_units_with_their_layout_in_comments() -> None:
    entries = [StringEntry("LETTER", "\nJosef,\r\n\\n\r\n\\nI asked.\\n")]

    assert units(export_po(entries)) == [
        (
            "LETTER/1",
            "Josef,",
            'layout before: "\\n"\nparagraphs: 2\n'
            'layout after: "\\r\\n\\\\n\\r\\n\\\\n"',
        ),
        ("LETTER/2", "I asked.", 'layout after: "\\\\n"'),
    ]


def test_contexts_name_keys_repeats_and_paragraphs_unambiguously() -> None:
    entries = [
        StringEntry("KEY", "a"),
        StringEntry("KEY", "b\nc"),
        StringEntry("", ""),
        StringEntry("", "d"),
        StringEntry("100% #1/2", "e"),
    ]

    contexts = [context for context, _, _ in units(export_po(entries))]

    assert contexts == ["KEY", "KEY#2/1", "KEY#2/2", "#1", "#2", "100%25 %231%2F2"]


def test_lost_layout_comments_are_reported() -> None:
    data = export_po([StringEntry("KEY", "One\nTwo")]).replace(
        b'#. layout after: "\\n"\n', b""
    )

    with pytest.raises(FormatError, match="layout comments of 'KEY' are missing"):
        import_po(data)


def test_paragraphs_out_of_order_are_reported() -> None:
    store = pofile.parsestring(export_po([StringEntry("KEY", "One\nTwo\nThree")]))
    store.units[2], store.units[3] = store.units[3], store.units[2]

    with pytest.raises(FormatError, match="paragraph 3 does not follow paragraph 2"):
        import_po(bytes(store))


@pytest.mark.parametrize(("text", "lost", "left"), [("A\nB", 2, 1), ("A\nB\nC", 3, 2)])
def test_lost_paragraphs_are_reported(text: str, lost: int, left: int) -> None:
    store = pofile.parsestring(export_po([StringEntry("KEY", text), ENTRIES[0]]))
    del store.units[lost]

    with pytest.raises(FormatError, match=f"has {left} of its {left + 1} paragraphs"):
        import_po(bytes(store))


def test_lost_paragraph_counts_are_reported() -> None:
    data = export_po([StringEntry("KEY", "One\nTwo")]).replace(
        b"#. paragraphs: 2\n", b""
    )

    with pytest.raises(FormatError, match="comment counting its paragraphs"):
        import_po(data)


def test_repeated_keys_out_of_order_are_reported() -> None:
    store = pofile.parsestring(
        export_po([StringEntry("KEY", "first"), StringEntry("KEY", "second")])
    )
    store.units[1], store.units[2] = store.units[2], store.units[1]

    with pytest.raises(FormatError, match="entry 2 of its key is where 1 goes"):
        import_po(bytes(store))


def test_texts_read_as_kde_comments_are_refused() -> None:
    with pytest.raises(ValueError, match="starting with _:"):
        export_po([StringEntry("KEY", "_: not a comment")])


@pytest.mark.parametrize(
    ("msgstr", "imported"), [("Przytrzymaj", "Przytrzymaj"), ("", None)]
)
def test_rewrapped_kde_like_lines_only_matter_untranslated(
    msgstr: str, imported: str | None
) -> None:
    data = (
        f'msgctxt "HINT"\nmsgid ""\n"Hold to save "\n"_:1 slot"\nmsgstr "{msgstr}"\n'
    ).encode()

    if imported is None:
        with pytest.raises(FormatError, match="read as a comment"):
            import_po(data)
    else:
        assert import_po(data) == [StringEntry("HINT", imported)]


@pytest.mark.parametrize("data", [b"", b" \r\n", b"\xef\xbb\xbf"])
def test_documents_without_units_are_refused(data: bytes) -> None:
    with pytest.raises(FormatError, match="holds no units"):
        import_po(data)


def test_an_empty_table_comes_back_empty() -> None:
    assert import_po(export_po([])) == []


@pytest.mark.parametrize("context", ["#", "a#b#2", "KEY/0"])
def test_contexts_that_name_no_entry_are_reported(context: str) -> None:
    data = f'msgctxt "{context}"\nmsgid "x"\nmsgstr ""\n'.encode()

    with pytest.raises(FormatError, match="does not name a string table entry"):
        import_po(data)
