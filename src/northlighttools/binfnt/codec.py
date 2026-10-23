"""Reading and writing binary fonts (.binfnt).

A font is a little-endian file holding, in order: its version; a vertex buffer
(position and texture coordinates of each glyph corner); an index buffer of
triangles; for each glyph, the ranges of both buffers it uses, its texture
channel and its layout box; a table giving the glyph of each of the 65536 BMP
character codes (0 for none); kerning pairs (versions 4 and 7); values of
unknown meaning (versions 6 and 7); and a DDS texture, preceded by its size in
versions 3 and 4.
"""

from northlighttools.binary import BinaryReader, BinaryWriter
from northlighttools.binfnt.model import (
    BinaryFont,
    FontVersion,
    Glyph,
    KerningPair,
    Vertex,
)
from northlighttools.errors import FormatError

CHARMAP_SIZE = 0x10000
_GLYPH_FIELDS = "4HI8f"
_KERNING_FIELDS = {FontVersion.V4: "IIi", FontVersion.V7: "HHf"}
_UNKNOWN_COUNTS = {FontVersion.V6: 2, FontVersion.V7: 2}
_SIZED_TEXTURE = {FontVersion.V3, FontVersion.V4}


def decode_font(data: bytes) -> BinaryFont:
    """Parse a binary font.

    Args:
        data: Contents of a .binfnt file.
    """
    reader = BinaryReader(data)
    raw_version = reader.u32()
    try:
        version = FontVersion(raw_version)
    except ValueError:
        msg = f"Unsupported font version {raw_version}"
        raise FormatError(msg) from None

    vertices = [Vertex(*values) for values in reader.iter_unpack("4f", reader.u32())]
    indices = [index for (index,) in reader.iter_unpack("H", reader.u32())]
    records = list(reader.iter_unpack(_GLYPH_FIELDS, reader.u32()))
    charmap_table = reader.unpack(f"{CHARMAP_SIZE}H")
    kerning = []
    if version in _KERNING_FIELDS:
        kerning = [
            KerningPair(*pair)
            for pair in reader.iter_unpack(_KERNING_FIELDS[version], reader.u32())
        ]
    unknown = reader.unpack("I" * _UNKNOWN_COUNTS.get(version, 0))
    texture_size = reader.u32() if version in _SIZED_TEXTURE else reader.remaining
    texture = reader.read(texture_size)
    if reader.remaining:
        msg = f"{reader.remaining} unexpected bytes after the texture"
        raise FormatError(msg)

    glyphs = _split_glyphs(records, vertices, indices)
    charmap = {}
    for code, glyph in enumerate(charmap_table):
        if glyph >= len(glyphs):
            msg = f"Character {code} maps to missing glyph {glyph}"
            raise FormatError(msg)
        if glyph:
            charmap[code] = glyph
    return BinaryFont(version, glyphs, charmap, kerning, tuple(unknown), texture)


def encode_font(font: BinaryFont) -> bytes:
    """Build the .binfnt file of a font.

    Args:
        font: The font to encode.
    """
    version = font.version
    if version not in _KERNING_FIELDS and font.kerning:
        msg = f"Fonts of version {version} have no kerning"
        raise ValueError(msg)
    expected_unknown = _UNKNOWN_COUNTS.get(version, 0)
    if len(font.unknown) != expected_unknown:
        msg = f"Fonts of version {version} need {expected_unknown} unknown values"
        raise ValueError(msg)

    writer = BinaryWriter()
    writer.u32(version)
    vertex_count = sum(len(glyph.vertices) for glyph in font.glyphs)
    writer.u32(vertex_count)
    for glyph in font.glyphs:
        for vertex in glyph.vertices:
            writer.pack("4f", vertex.x, vertex.y, vertex.u, vertex.v)
    writer.u32(sum(len(glyph.indices) for glyph in font.glyphs))
    for glyph in font.glyphs:
        writer.pack(f"{len(glyph.indices)}H", *glyph.indices)
    writer.u32(len(font.glyphs))
    first_vertex = first_index = 0
    for glyph in font.glyphs:
        writer.pack(
            _GLYPH_FIELDS,
            first_vertex,
            len(glyph.vertices),
            first_index,
            len(glyph.indices),
            glyph.channel,
            *glyph.box,
        )
        first_vertex += len(glyph.vertices)
        first_index += len(glyph.indices)

    table = [0] * CHARMAP_SIZE
    for code, glyph_index in font.charmap.items():
        if not 0 <= code < CHARMAP_SIZE or not 0 < glyph_index < len(font.glyphs):
            msg = f"Cannot map character {code} to glyph {glyph_index}"
            raise ValueError(msg)
        table[code] = glyph_index
    writer.pack(f"{CHARMAP_SIZE}H", *table)

    if version in _KERNING_FIELDS:
        writer.u32(len(font.kerning))
        for pair in font.kerning:
            amount = pair.amount
            if version is FontVersion.V4:
                if not float(amount).is_integer():
                    msg = f"Version 4 kerning amounts are integers, not {amount}"
                    raise ValueError(msg)
                amount = int(amount)
            writer.pack(_KERNING_FIELDS[version], pair.first, pair.second, amount)
    writer.pack("I" * len(font.unknown), *font.unknown)
    if version in _SIZED_TEXTURE:
        writer.u32(len(font.texture))
    writer.write(font.texture)
    return writer.getvalue()


def _split_glyphs(
    records: list[tuple[float, ...]], vertices: list[Vertex], indices: list[int]
) -> list[Glyph]:
    """Give each glyph its own part of the vertex and index buffers."""
    glyphs = []
    next_vertex = next_index = 0
    for number, record in enumerate(records):
        first_vertex, vertex_count, first_index, index_count, channel = map(int, record[:5])
        # Every known font stores the glyphs' parts one after another, which is
        # what lets a glyph own its vertices and indices.
        if (first_vertex, first_index) != (next_vertex, next_index):
            msg = f"Glyph {number} does not follow the previous glyph in the buffers"
            raise FormatError(msg)
        glyph_vertices = tuple(vertices[first_vertex : first_vertex + vertex_count])
        glyph_indices = tuple(indices[first_index : first_index + index_count])
        if len(glyph_vertices) != vertex_count or len(glyph_indices) != index_count:
            msg = f"Glyph {number} reaches past the end of the buffers"
            raise FormatError(msg)
        if any(index >= vertex_count for index in glyph_indices):
            msg = f"Glyph {number} has a triangle outside its own vertices"
            raise FormatError(msg)
        box = tuple(record[5:])
        glyphs.append(Glyph(glyph_vertices, glyph_indices, channel, box))  # type: ignore[arg-type]
        next_vertex += vertex_count
        next_index += index_count
    if (next_vertex, next_index) != (len(vertices), len(indices)):
        msg = "Some vertices or indices belong to no glyph"
        raise FormatError(msg)
    return glyphs
