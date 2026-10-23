"""The string table format (string_table.bin): localized texts by key.

The table is little-endian in every game, Alan Wake's big-endian packages
included: a count of entries, then for each entry a UTF-8 key and a UTF-16
value, both prefixed with their length (in bytes for keys, in UTF-16 code units
for values). Keys may repeat, with the same or a different value.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from northlighttools.binary import BinaryReader, BinaryWriter
from northlighttools.errors import FormatError


@dataclass(frozen=True, slots=True)
class StringEntry:
    key: str
    value: str


def decode_string_table(data: bytes) -> list[StringEntry]:
    """Parse a string table, keeping its order and repeated keys.

    Args:
        data: Contents of a string_table.bin file.
    """
    reader = BinaryReader(data)
    entries = []
    for _ in range(reader.u32()):
        key = _decode(reader.read(reader.u32()), "utf-8")
        value = _decode(reader.read(2 * reader.u32()), "utf-16-le")
        entries.append(StringEntry(key, value))
    if reader.remaining:
        msg = f"{reader.remaining} unexpected bytes after the last string"
        raise FormatError(msg)
    return entries


def encode_string_table(entries: Iterable[StringEntry]) -> bytes:
    """Build a string table from its entries.

    Args:
        entries: The entries, in table order.
    """
    entries = list(entries)
    writer = BinaryWriter()
    writer.u32(len(entries))
    for entry in entries:
        key = entry.key.encode("utf-8", "surrogatepass")
        value = entry.value.encode("utf-16-le", "surrogatepass")
        writer.u32(len(key))
        writer.write(key)
        writer.u32(len(value) // 2)
        writer.write(value)
    return writer.getvalue()


def _decode(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding, "surrogatepass")
    except UnicodeDecodeError as error:
        msg = f"Text that is not valid {encoding}: {raw[:40]!r}"
        raise FormatError(msg) from error
