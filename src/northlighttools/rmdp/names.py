"""Rules for the names of package entries."""

import re
import zlib

PackagePath = tuple[str, ...]
"""Names of the folders leading to an entry, ending with the entry's own name."""

_UNSAFE_CHARACTERS = frozenset('<>:"/\\|?*%')
_RESERVED_STEMS = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"{device}{number}" for device in ("COM", "LPT") for number in range(1, 10)]
)
_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")


def name_checksum(name: str) -> int:
    """Return the CRC-32 the engine computes over the lowercase form of a name."""
    return zlib.crc32(name.encode().lower())


def sort_key(path: PackagePath) -> bytes:
    """Return the key that orders entries in the games' own packages."""
    return "\\".join(path).encode().lower()


def format_path(path: PackagePath) -> str:
    return "/".join(path)


def _escape(character: str) -> str:
    return f"%{ord(character):02X}"


def to_filesystem_name(name: str) -> str:
    """Escape a package name so that any file system can hold it unchanged."""
    if not name:
        msg = "A package entry has an empty name"
        raise ValueError(msg)
    characters = [
        _escape(c) if c in _UNSAFE_CHARACTERS or ord(c) < 0x20 else c for c in name
    ]
    # Windows drops trailing dots and spaces, and reserves the names of devices.
    if name[-1] in ". ":
        characters[-1] = _escape(name[-1])
    if name.split(".")[0].upper() in _RESERVED_STEMS:
        characters[0] = _escape(name[0])
    return "".join(characters)


def from_filesystem_name(name: str) -> str:
    """Undo to_filesystem_name."""
    return _ESCAPE.sub(lambda match: chr(int(match[1], 16)), name)
