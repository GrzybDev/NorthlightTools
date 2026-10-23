"""Characters translation documents cannot carry.

XML 1.0 has no place for control characters other than tab, line feed and
carriage return, for U+FFFE and U+FFFF or for lone surrogates. Gettext tools
escape or cut the same control characters, and UTF-8 has no lone surrogates,
so PO is held to the same set.
"""

import re
from collections.abc import Iterable

from northlighttools.string_table.table import StringEntry

_NOT_CARRIED = re.compile(
    f"[^\t\n\r -{chr(0xD7FF)}{chr(0xE000)}-{chr(0xFFFD)}{chr(0x10000)}-{chr(0x10FFFF)}]"
)


def checked(entries: Iterable[StringEntry], document: str) -> list[StringEntry]:
    """Return the entries, refusing keys and texts the document could not carry.

    Args:
        entries: The entries to check.
        document: Name of the document format, for the error message.
    """
    entries = list(entries)
    for entry in entries:
        for what, text in (("key", entry.key), ("text", entry.value)):
            if match := _NOT_CARRIED.search(text):
                msg = (
                    f"The {what} of {entry.key!r} holds U+{ord(match[0]):04X}, "
                    f"which {document} cannot carry"
                )
                raise ValueError(msg)
    return entries
