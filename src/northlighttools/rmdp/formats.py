"""Index layouts of Remedy packages, as found in the files of each game."""

import struct
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from northlighttools.binary import ByteOrder


class Game(StrEnum):
    """Games whose package format is known."""

    ALAN_WAKE = "alan-wake"
    ALAN_WAKE_REMASTERED = "alan-wake-remastered"
    AMERICAN_NIGHTMARE = "american-nightmare"
    QUANTUM_BREAK = "quantum-break"
    CONTROL = "control"


def _naturally_aligned(fields: str) -> str:
    """Pad struct fields the way a C compiler aligns them."""
    layout, offset, widest = [], 0, 1
    for code in fields:
        size = struct.calcsize(code)
        padding = -offset % size
        layout.append("x" * padding + code)
        offset += padding + size
        widest = max(widest, size)
    layout.append("x" * (-offset % widest))
    return "".join(layout)


@dataclass(frozen=True)
class PackageFormat:
    """How one game lays out the index (.bin) of its packages."""

    game: Game
    title: str
    version: int
    link: str
    """Struct code of entry indices and name offsets: I (32-bit) or Q (64-bit)."""
    aligned: bool
    """Whether entries carry the padding of naturally aligned C structs."""
    byte_order: ByteOrder
    """Byte order the game's own packages use, given to new packages."""
    data_alignment: int
    """Alignment the game's own packages give to file data in the .rmdp."""
    base_path: str
    """Path the game's own packages store in the index header."""

    @property
    def has_timestamps(self) -> bool:
        return self.version >= 7

    @property
    def has_header_value(self) -> bool:
        return self.version >= 7

    @property
    def has_closing_entry(self) -> bool:
        return self.version >= 7

    @property
    def null_link(self) -> int:
        return (1 << (8 * struct.calcsize(self.link))) - 1

    @cached_property
    def folder_fields(self) -> str:
        """Checksum, next sibling, parent, unknown, name, first child and first file."""
        fields = f"I{self.link}{self.link}I{self.link}{self.link}{self.link}"
        return _naturally_aligned(fields) if self.aligned else fields

    @cached_property
    def file_fields(self) -> str:
        """Checksum, next sibling, parent, flags, name, offset, size, data checksum and,
        in formats that have one, timestamp."""
        fields = f"I{self.link}{self.link}I{self.link}QQI"
        if self.has_timestamps:
            fields += "Q"
        return _naturally_aligned(fields) if self.aligned else fields


FORMATS: dict[Game, PackageFormat] = {
    package_format.game: package_format
    for package_format in (
        PackageFormat(Game.ALAN_WAKE, "Alan Wake", 2, "I", False, ByteOrder.BIG, 8, "d:\\data"),
        PackageFormat(
            Game.ALAN_WAKE_REMASTERED,
            "Alan Wake Remastered",
            2,
            "Q",
            True,
            ByteOrder.BIG,
            8,
            "d:\\data",
        ),
        PackageFormat(
            Game.AMERICAN_NIGHTMARE,
            "Alan Wake's American Nightmare",
            7,
            "I",
            False,
            ByteOrder.LITTLE,
            8,
            "d:\\data",
        ),
        PackageFormat(
            Game.QUANTUM_BREAK,
            "Quantum Break",
            8,
            "Q",
            False,
            ByteOrder.LITTLE,
            32,
            "d:\\data",
        ),
        PackageFormat(Game.CONTROL, "Control", 9, "Q", False, ByteOrder.LITTLE, 32, ""),
    )
}
