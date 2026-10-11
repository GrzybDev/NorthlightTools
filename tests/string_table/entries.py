"""Invented string table entries that exercise every translation format."""

from northlighttools.string_table import StringEntry
from northlighttools.string_table.layout import Layout

BREAK = "\r\n\\n"

ENTRIES = [
    StringEntry("MENU_TITLE", "Main menu"),
    StringEntry("REPEATED", "first"),
    StringEntry("REPEATED", "second"),
    StringEntry("LETTER", f"Josef,{BREAK}{BREAK}I asked. \t{BREAK}{BREAK}-Josef\r\n"),
    StringEntry("LEADING", "\nSecond line\\nThird line"),
    StringEntry("LAYOUT_ONLY", " \\n\\n "),
    StringEntry("EMPTY", ""),
    StringEntry("PADDED", '  say "hi", & <b>bye</b>\t'),
    StringEntry("SAME_TWICE", "---\n---"),
    StringEntry("CONT\u2019D 100% #1/2", "Zażółć gęślą jaźń \U0001f600"),
    StringEntry("", "-"),
    StringEntry("", "--"),
    StringEntry("A:B", "colon"),
    StringEntry("A_B", "underscore"),
    StringEntry("A B", "clashes with A_B once made fit for XML"),
]


def translate(paragraph: str) -> str:
    return f"PL[{paragraph}]"


def translated(entry: StringEntry) -> StringEntry:
    """The entry with every paragraph translated, its layout kept."""
    layout = Layout.of(entry.value)
    return StringEntry(
        entry.key, layout.join([translate(p) for p in layout.paragraphs])
    )
