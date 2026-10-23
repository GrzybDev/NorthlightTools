"""Exchanging string tables with translation tools through Gettext PO.

Each paragraph of a text (see Layout) becomes a unit, in table order. Its
context names the entry: the key, with %, # and / escaped as %25, %23 and %2F,
then #N for the second and later entries with that key (#1 too for the empty
key, since a context cannot be empty) and /N for the N-th paragraph of a text
with more than one. Extracted comments, quoted as PO strings, hold the layout
runs around a paragraph and how many paragraphs its text has:

    #. layout before: "..."    (first paragraph only)
    #. paragraphs: N           (first paragraph of a text with more than one)
    #. layout after: "..."

Untranslated and fuzzy units keep their source text.
"""

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from translate.storage import pypo
from translate.storage.pypo import pofile, pounit

from northlighttools.errors import FormatError
from northlighttools.string_table.characters import checked
from northlighttools.string_table.layout import Layout
from northlighttools.string_table.table import StringEntry

_ESCAPED = re.compile("[%#/]")
_UNESCAPED = re.compile("%(25|23|2F)")
_CONTEXT = re.compile(r"([^#/]*)(?:#([1-9]\d*))?(?:/([1-9]\d*))?")
_BEFORE = "layout before: "
_AFTER = "layout after: "
_PARAGRAPHS = re.compile(r"paragraphs: ([1-9]\d*)")


def export_po(entries: Iterable[StringEntry], filename: str = "string_table.bin") -> bytes:
    """Return a PO document with the entries' paragraphs as untranslated units."""
    store = pofile(noheader=True, width=-1)
    store.init_headers(project_id_version=filename, pot_creation_date="", po_revision_date="")
    occurrences: Counter[str] = Counter()
    for entry in checked(entries, "PO"):
        occurrences[entry.key] += 1
        layout = Layout.of(entry.value)
        count = len(layout.paragraphs)
        for number, paragraph in enumerate(layout.paragraphs, start=1):
            context = _context(entry.key, occurrences[entry.key], number if count > 1 else None)
            if paragraph.startswith("_:"):
                msg = f"{context}: a text starting with _: would be read as a comment"
                raise ValueError(msg)
            unit = store.UnitClass(paragraph, wrapper=store.wrapper)
            unit.setcontext(context)
            comments = []
            if number == 1 and layout.runs[0]:
                comments.append(_BEFORE + _quote(layout.runs[0]))
            if number == 1 and count > 1:
                comments.append(f"paragraphs: {count}")
            if layout.runs[number]:
                comments.append(_AFTER + _quote(layout.runs[number]))
            if comments:
                unit.addnote("\n".join(comments), origin="developer")
            store.addunit(unit)
    return bytes(store)


def import_po(data: bytes) -> list[StringEntry]:
    """Build string table entries from a PO document, in its order."""
    try:
        store = pofile.parsestring(data)
    except Exception as error:
        msg = f"Cannot read the PO document: {error}"
        raise FormatError(msg) from error
    if not store.units:
        # Even an empty table exports with a header.
        msg = "The PO document holds no units, not even a header"
        raise FormatError(msg)
    return [entry.build() for entry in _entries(store.units)]


@dataclass
class _Entry:
    key: str
    paragraphs: int
    before: str
    texts: list[str] = field(default_factory=list)
    afters: list[str] = field(default_factory=list)

    def build(self) -> StringEntry:
        if len(self.texts) != self.paragraphs:
            count = len(self.texts)
            msg = f"{self.key!r} has {count} of its {self.paragraphs} paragraphs"
            raise FormatError(msg)
        if not all(self.afters[:-1]):
            msg = f"The layout comments of {self.key!r} are missing"
            raise FormatError(msg)
        layout = Layout(tuple(self.texts), (self.before, *self.afters))
        return StringEntry(self.key, layout.join(self.texts))


def _entries(units: Iterable[pounit]) -> Iterator[_Entry]:
    """Gather the units of each entry, checking they come complete and in order."""
    occurrences: Counter[str] = Counter()
    entry: _Entry | None = None
    for unit in units:
        if unit.isheader() or unit.isobsolete():
            continue
        context = unit.getpreviouscontext()
        if unit.msgidcomments and not unit.istranslated():
            msg = f"{context}: a line starting with _: was read as a comment"
            raise FormatError(msg)
        key, occurrence, number = _parse_context(context)
        before, paragraphs, after = _comments(unit)
        if number is None or number == 1:
            occurrences[key] += 1
            if occurrence != occurrences[key]:
                expected = occurrences[key]
                msg = f"{context}: entry {occurrence} of its key is where {expected} goes"
                raise FormatError(msg)
            if number == 1 and paragraphs is None:
                msg = f"{context}: the comment counting its paragraphs is missing"
                raise FormatError(msg)
            if entry is not None:
                yield entry
            entry = _Entry(key, paragraphs or 1, before)
        elif (
            entry is None
            or entry.key != key
            or occurrences[key] != occurrence
            or len(entry.texts) + 1 != number
        ):
            msg = f"{context}: paragraph {number} does not follow paragraph {number - 1}"
            raise FormatError(msg)
        entry.texts.append(str(unit.target if unit.istranslated() else unit.source))
        entry.afters.append(after)
    if entry is not None:
        yield entry


def _context(key: str, occurrence: int, paragraph: int | None) -> str:
    context = _ESCAPED.sub(lambda match: f"%{ord(match[0]):02X}", key)
    if occurrence > 1 or not key:
        context += f"#{occurrence}"
    if paragraph is not None:
        context += f"/{paragraph}"
    return context


def _parse_context(context: str) -> tuple[str, int, int | None]:
    match = _CONTEXT.fullmatch(context)
    if match is None or (not match[1] and match[2] is None):
        msg = f"The context {context!r} does not name a string table entry"
        raise FormatError(msg)
    key = _UNESCAPED.sub(lambda m: chr(int(m[1], 16)), match[1])
    return key, int(match[2] or 1), None if match[3] is None else int(match[3])


def _quote(text: str) -> str:
    return f'"{pypo.escapeforpo(text)}"'


def _comments(unit: pounit) -> tuple[str, int | None, str]:
    """Read the layout before, the paragraph count and the layout after a unit."""
    before = after = ""
    paragraphs = None
    for line in unit.getnotes("developer").splitlines():
        if line.startswith(_BEFORE + '"') and line.endswith('"'):
            before = pypo.unescape(line[len(_BEFORE) + 1 : -1])
        elif line.startswith(_AFTER + '"') and line.endswith('"'):
            after = pypo.unescape(line[len(_AFTER) + 1 : -1])
        elif match := _PARAGRAPHS.fullmatch(line):
            paragraphs = int(match[1])
    return before, paragraphs, after
