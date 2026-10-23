"""Building fonts from the msdf-atlas-gen JSON documents that decompiling writes."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from northlighttools.binfnt.atlas import (
    EDGES,
    QUAD_TRIANGLES,
    Rectangle,
    blank_canvas,
    check_inside,
    float32,
    texture_region,
    to_coordinate,
    whole_bounds,
)
from northlighttools.binfnt.codec import CHARMAP_SIZE
from northlighttools.binfnt.dds import PixelFormat, decode_dds, encode_dds
from northlighttools.binfnt.model import BinaryFont, FontVersion, Glyph, KerningPair, Vertex
from northlighttools.binfnt.texture import Pixels, encode_pixels, from_image
from northlighttools.errors import FormatError


def _load(data: bytes) -> dict[str, Any]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        msg = f"Not a valid JSON document: {error}"
        raise FormatError(msg) from error
    if not isinstance(document, dict) or "northlight" not in document:
        msg = "The document lacks the northlight object that decompiling writes"
        raise FormatError(msg)
    return document


def compile_font(json_path: Path) -> BinaryFont:
    """Build a binary font from a JSON document written by decompile_font.

    Args:
        json_path: The document; the files it names are read from beside it.
    """
    document = _load(json_path.read_bytes())
    try:
        return _build_font(document, json_path.parent)
    except (KeyError, TypeError, IndexError) as error:
        msg = f"The document is missing or misusing a field: {error!r}"
        raise FormatError(msg) from error


def _build_font(document: dict[str, Any], folder: Path) -> BinaryFont:
    northlight = document["northlight"]
    version = FontVersion(northlight["version"])
    width, height = document["atlas"]["width"], document["atlas"]["height"]

    glyphs: list[Glyph] = []
    charmap: dict[int, int] = {}
    for index, entry in enumerate(document["glyphs"]):
        if index == 0:
            if "unicode" in entry:
                msg = "The first glyph is drawn for missing characters and has no unicode"
                raise FormatError(msg)
        else:
            code = entry["unicode"]
            if not 0 <= code < CHARMAP_SIZE or charmap.setdefault(code, index) != index:
                msg = f"Unicode {code} is out of range or given to two glyphs"
                raise FormatError(msg)
        glyphs.append(_read_glyph(entry, width, height))
    if not glyphs:
        msg = "The font has no glyphs"
        raise FormatError(msg)

    kerning = [
        KerningPair(
            pair["unicode1"],
            pair["unicode2"],
            pair["advance"] if version is FontVersion.V4 else float32(pair["advance"]),
        )
        for pair in document.get("kerning", [])
    ]
    unknown = tuple(northlight.get("unknown", []))
    texture = _read_texture(document, folder)
    return BinaryFont(version, glyphs, charmap, kerning, unknown, texture)


def _read_glyph(entry: dict[str, Any], width: int, height: int) -> Glyph:
    if "vertices" in entry:
        vertices = tuple(
            Vertex(float32(x), float32(y), to_coordinate(u, width), to_coordinate(v, height))
            for x, y, u, v in entry["vertices"]
        )
        indices = tuple(entry["triangles"])
        if len(indices) % 3 or any(not 0 <= i < len(vertices) for i in indices):
            msg = f"Glyph {_describe(entry)} has invalid triangles"
            raise FormatError(msg)
    else:
        rectangle = Rectangle(
            plane=_edges(entry["planeBounds"]),
            atlas=_edges(entry["atlasBounds"]),
        )
        vertices, indices = rectangle.vertices(width, height), QUAD_TRIANGLES
    if "layoutCorners" in entry:
        box = [float32(value) for value in entry["layoutCorners"]]
        if len(box) != 8:
            msg = f"Glyph {_describe(entry)} needs 8 layoutCorners values"
            raise FormatError(msg)
    else:
        advance = float32(entry["advance"])
        bottom = float32(entry["layoutBounds"]["bottom"])
        top = float32(entry["layoutBounds"]["top"])
        box = [0.0, bottom, advance, bottom, advance, top, 0.0, top]
    channel = entry.get("channel", 0)
    if channel not in (0, 1, 2, 3):
        msg = f"Glyph {_describe(entry)} has channel {channel}, not 0 to 3"
        raise FormatError(msg)
    return Glyph(vertices, indices, channel, tuple(box))  # type: ignore[arg-type]


def _edges(bounds: dict[str, float]) -> tuple[float, float, float, float]:
    left, bottom, right, top = (bounds[edge] for edge in EDGES)
    return left, bottom, right, top


def _describe(entry: dict[str, Any]) -> str:
    if "unicode" in entry:
        return f"U+{entry['unicode']:04X}"
    return str(entry.get("index", "?"))


def _read_texture(document: dict[str, Any], folder: Path) -> bytes:
    northlight = document["northlight"]
    version = FontVersion(northlight["version"])
    pixel_format = PixelFormat(northlight["format"])
    size = (document["atlas"]["width"], document["atlas"]["height"])
    if "texture" in northlight:
        path = folder / str(northlight["texture"])
        if path.suffix.lower() == ".dds":
            data = path.read_bytes()
            texture = decode_dds(data)
            if (texture.width, texture.height, texture.pixel_format) != (
                *size,
                pixel_format,
            ):
                msg = f"{path.name} is not a {size[0]}x{size[1]} {pixel_format} texture"
                raise FormatError(msg)
            return data
        with Image.open(path) as image:
            if image.size != size:
                msg = f"{path.name} is {image.size}, not {size}"
                raise FormatError(msg)
            pixels = from_image(image, pixel_format)
    elif "glyphs" in northlight:
        pixels = _compose(document, folder / northlight["glyphs"], pixel_format, size)
    else:
        msg = "The northlight object names neither a texture nor a glyph folder"
        raise FormatError(msg)
    texture = encode_pixels(pixels, pixel_format, northlight["mipmaps"])
    return encode_dds(texture, legacy_header=version is FontVersion.V3)


def _compose(
    document: dict[str, Any],
    folder: Path,
    pixel_format: PixelFormat,
    size: tuple[int, int],
) -> Pixels:
    """Assemble the texture from the image of each glyph."""
    glyphs = document["glyphs"]
    packed = any("channel" in entry for entry in glyphs)
    canvas = blank_canvas(pixel_format, size, document["northlight"]["background"])
    for entry in glyphs:
        if (name := entry.get("image")) is None:
            continue
        left, top, right, bottom = bounds = whole_bounds(_edges(entry["atlasBounds"]))
        check_inside(bounds, size, name)
        with Image.open(folder / name) as image:
            if image.size != (right - left, bottom - top):
                msg = f"{name} is {image.size}, not {(right - left, bottom - top)}"
                raise FormatError(msg)
            pixels = np.asarray(image.convert("L")) if packed else from_image(image, pixel_format)
        canvas[texture_region(bounds, entry["channel"] if packed else None)] = pixels
    return canvas
