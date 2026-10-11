from dataclasses import dataclass
from enum import IntEnum


class FontVersion(IntEnum):
    V3 = 3
    """Alan Wake and Alan Wake's American Nightmare."""
    V4 = 4
    """Alan Wake Remastered."""
    V6 = 6
    """Quantum Break, only in its fixedsys font."""
    V7 = 7
    """Quantum Break and Control."""


@dataclass(frozen=True, slots=True)
class Vertex:
    """A corner of a glyph: its position and its texture coordinates."""

    x: float
    y: float
    """Position in font units from the pen on the baseline, upwards."""
    u: float
    v: float
    """Texture coordinates, from the top left corner of the texture."""


@dataclass(frozen=True, slots=True)
class Glyph:
    vertices: tuple[Vertex, ...]
    indices: tuple[int, ...]
    """Triangles over the glyph's own vertices."""
    channel: int
    """Texture channel holding the glyph: 0 red, 1 green, 2 blue, 3 alpha."""
    box: tuple[float, float, float, float, float, float, float, float]
    """Corners (x, y) of the glyph's layout box in font units; the games' own
    fonts span it from 0 to the glyph's advance."""


@dataclass(frozen=True, slots=True)
class KerningPair:
    first: int
    second: int
    """Character codes."""
    amount: float
    """In font units in version 7; an integer of unknown unit in version 4."""


@dataclass
class BinaryFont:
    """A font as stored in a .binfnt file."""

    version: FontVersion
    glyphs: list[Glyph]
    """Glyph 0 is drawn for characters the font lacks."""
    charmap: dict[int, int]
    """Glyph index of each character code the font has."""
    kerning: list[KerningPair]
    unknown: tuple[int, ...]
    """Values of unknown meaning ending versions 6 and 7."""
    texture: bytes
    """The texture atlas, a DDS file."""
