"""Fonts as msdf-atlas-gen JSON documents with their texture beside them.

The document follows the layout msdf-atlas-gen writes: glyph metrics in em
units (planeBounds, advance, kerning advance), which are the font's own units,
and atlas rectangles in texture pixels counted from the top (atlasBounds).
Every value is the shortest number that gives back the font's exact value.

What msdf-atlas-gen has no field for lives in fields of its own: the layout
box of each glyph (layoutBounds, from 0 to the advance; layoutCorners when it
is not such a box), its texture channel, the vertices of glyphs that are not
textured rectangles, and the "northlight" object with the font's version,
texture format and texture file. The first glyph, which has an index instead
of a unicode, is drawn for characters the font lacks.

The texture is a PNG image (16-bit grayscale for distance fields) when that
converts back to the very same texture, otherwise the font's DDS file. Glyphs
can also be cut into one image each when that loses nothing.
"""

import json
import math
import statistics
import struct
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from northlighttools.binfnt.codec import CHARMAP_SIZE
from northlighttools.binfnt.dds import DdsTexture, PixelFormat, decode_dds, encode_dds
from northlighttools.binfnt.model import (
    BinaryFont,
    FontVersion,
    Glyph,
    KerningPair,
    Vertex,
)
from northlighttools.binfnt.texture import (
    Pixels,
    can_convert,
    decode_pixels,
    encode_pixels,
    from_image,
    to_image,
)
from northlighttools.errors import FormatError
from northlighttools.fileio import write_atomically

_QUAD_TRIANGLES = (0, 1, 2, 0, 2, 3)
_KERNED_VERSIONS = (FontVersion.V4, FontVersion.V7)
_EDGES = ("left", "bottom", "right", "top")


def _float32(value: float) -> float:
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


def _same_floats(first: Iterable[float], second: Iterable[float]) -> bool:
    first, second = tuple(first), tuple(second)
    return len(first) == len(second) and all(
        struct.pack("<f", a) == struct.pack("<f", b)
        for a, b in zip(first, second, strict=True)
    )


def _clean(value: float) -> float | int:
    """Return a whole number as an int, so that JSON writes it without a fraction."""
    if value.is_integer() and math.copysign(1, value) > 0:
        return int(value)
    return value


def _em(value: float) -> float | int:
    """Return the shortest number that a float32 font value reads back as."""
    for digits in range(1, 10):
        candidate = float(f"{value:.{digits}g}")
        if _same_floats([candidate], [value]):
            return _clean(candidate)
    return value


def _pixels(coordinate: float, length: int) -> float | int:
    """Return the shortest texel position whose share of length is coordinate."""
    exact = coordinate * length
    for digits in range(10):
        candidate = round(exact, digits)
        if _same_floats([candidate / length], [coordinate]):
            return _clean(candidate)
    return exact


def _coordinate(pixels: float, length: int) -> float:
    return _float32(pixels / length)


@dataclass(frozen=True)
class _Rectangle:
    """A glyph drawn as a textured rectangle."""

    plane: tuple[float, float, float, float]
    """Left, bottom, right and top in em units, up from the baseline."""
    atlas: tuple[float, float, float, float]
    """Left, bottom, right and top in texture pixels, down from the top."""

    @classmethod
    def of(cls, glyph: Glyph, width: int, height: int) -> "_Rectangle | None":
        if len(glyph.vertices) != 4 or glyph.indices != _QUAD_TRIANGLES:
            return None
        bottom_left, bottom_right, top_right, top_left = glyph.vertices
        corners_share_edges = _same_floats(
            [bottom_left.y, top_left.x, top_left.y, bottom_right.x],
            [bottom_right.y, bottom_left.x, top_right.y, top_right.x],
        ) and _same_floats(
            [top_left.u, bottom_right.u, bottom_right.v, top_left.v],
            [bottom_left.u, top_right.u, bottom_left.v, top_right.v],
        )
        if not corners_share_edges:
            return None
        return cls(
            plane=(bottom_left.x, bottom_left.y, top_right.x, top_right.y),
            atlas=(
                _pixels(bottom_left.u, width),
                _pixels(bottom_left.v, height),
                _pixels(top_right.u, width),
                _pixels(top_right.v, height),
            ),
        )

    def vertices(self, width: int, height: int) -> tuple[Vertex, ...]:
        left, bottom, right, top = (_float32(edge) for edge in self.plane)
        u0, u1 = _coordinate(self.atlas[0], width), _coordinate(self.atlas[2], width)
        v1, v0 = _coordinate(self.atlas[1], height), _coordinate(self.atlas[3], height)
        return (
            Vertex(left, bottom, u0, v1),
            Vertex(right, bottom, u1, v1),
            Vertex(right, top, u1, v0),
            Vertex(left, top, u0, v0),
        )


def _glyph_codes(font: BinaryFont) -> list[int | None]:
    codes: list[int | None] = [None] * len(font.glyphs)
    for code, index in sorted(font.charmap.items()):
        if codes[index] is not None:
            msg = f"Glyph {index} serves several characters, which the JSON cannot hold"
            raise ValueError(msg)
        codes[index] = code
    if None in codes[1:]:
        msg = (
            f"Glyph {codes.index(None, 1)} serves no character; the JSON cannot hold it"
        )
        raise ValueError(msg)
    return codes


def _atlas_size(font: BinaryFont, width: int) -> float:
    """Estimate the texture pixels per em, rounded to 1/16 as in the games."""
    ratios = []
    for glyph in font.glyphs:
        xs = [vertex.x for vertex in glyph.vertices]
        us = [vertex.u for vertex in glyph.vertices]
        if len(xs) == 4 and max(xs) > min(xs) and max(us) > min(us):
            ratios.append((max(us) - min(us)) * width / (max(xs) - min(xs)))
    return round(statistics.median(ratios) * 16) / 16 if ratios else 0.0


def decompile_font(
    font: BinaryFont, json_path: Path, *, separate_glyphs: bool = False
) -> None:
    """Write a font as a JSON document at json_path, with its texture beside it."""
    texture = decode_dds(font.texture)
    width, height = texture.width, texture.height
    codes = _glyph_codes(font)
    rectangles = [_Rectangle.of(glyph, width, height) for glyph in font.glyphs]
    packed = any(glyph.channel for glyph in font.glyphs)

    glyphs = [
        _glyph_entry(glyph, index, code, rectangle, texture, packed)
        for index, (glyph, code, rectangle) in enumerate(
            zip(font.glyphs, codes, rectangles, strict=True)
        )
    ]
    pixels = _exact_pixels(font, texture)
    output_dir, stem = json_path.parent, json_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    northlight: dict[str, Any] = {
        "version": int(font.version),
        "format": texture.pixel_format.value,
        "mipmaps": len(texture.levels),
    }
    if font.unknown:
        northlight["unknown"] = list(font.unknown)
    document = {
        "atlas": _atlas_entry(font, texture, pixels),
        "metrics": _metrics_entry(font),
        "glyphs": glyphs,
    }
    if font.version in _KERNED_VERSIONS:
        document["kerning"] = [
            {
                "unicode1": pair.first,
                "unicode2": pair.second,
                "advance": int(pair.amount)
                if font.version is FontVersion.V4
                else _em(pair.amount),
            }
            for pair in font.kerning
        ]
    document["northlight"] = northlight

    if separate_glyphs:
        if pixels is None:
            msg = "This font's texture can only be kept as a DDS file"
            raise ValueError(msg)
        background = _background(pixels)
        cuts = _cut_glyphs(font, texture, pixels, rectangles, background)
        folder = output_dir / f"{stem}_glyphs"
        folder.mkdir(parents=True, exist_ok=True)
        northlight["glyphs"] = folder.name
        northlight["background"] = background
        for index, region in cuts:
            code = codes[index]
            name = f"U+{code:04X}.png" if code is not None else "fallback.png"
            glyphs[index]["image"] = name
            image = (
                Image.fromarray(region)
                if packed
                else to_image(region, texture.pixel_format)
            )
            image.save(folder / name)
    elif pixels is not None:
        northlight["texture"] = f"{stem}.png"
        to_image(pixels, texture.pixel_format).save(output_dir / f"{stem}.png")
    else:
        northlight["texture"] = f"{stem}.dds"
        write_atomically(output_dir / f"{stem}.dds", font.texture)
    write_atomically(json_path, _dump(document))


def _atlas_entry(
    font: BinaryFont, texture: DdsTexture, pixels: Pixels | None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "sdf" if texture.pixel_format is PixelFormat.R16F else "softmask"
    }
    if texture.pixel_format is PixelFormat.R16F and pixels is not None:
        distances = pixels.astype("<u2").view("<f2")
        finite = distances[np.isfinite(distances)]
        if finite.size:
            # The games' fields reach this far outside a glyph; msdf-atlas-gen
            # counts the range across both sides of the edge.
            entry["distanceRange"] = 2 * max(1, math.ceil(float(finite.max())))
    entry["size"] = _clean(_atlas_size(font, texture.width))
    entry["width"] = texture.width
    entry["height"] = texture.height
    entry["yOrigin"] = "top"
    return entry


def _metrics_entry(font: BinaryFont) -> dict[str, Any]:
    """Derive line metrics from the layout boxes; reading ignores them."""
    descender = min((glyph.box[1] for glyph in font.glyphs), default=0.0)
    ascender = max((glyph.box[5] for glyph in font.glyphs), default=0.0)
    return {
        "emSize": 1,
        "lineHeight": _em(_float32(ascender - descender)),
        "ascender": _em(ascender),
        "descender": _em(descender),
    }


def _glyph_entry(
    glyph: Glyph,
    index: int,
    code: int | None,
    rectangle: _Rectangle | None,
    texture: DdsTexture,
    packed: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"index": index} if code is None else {"unicode": code}
    box = glyph.box
    entry["advance"] = _em(box[2])
    if rectangle is not None:
        entry["planeBounds"] = dict(zip(_EDGES, map(_em, rectangle.plane), strict=True))
        entry["atlasBounds"] = dict(zip(_EDGES, rectangle.atlas, strict=True))
    standard_box = [0.0, box[1], box[2], box[1], box[2], box[5], 0.0, box[5]]
    if _same_floats(standard_box, box):
        entry["layoutBounds"] = {"bottom": _em(box[1]), "top": _em(box[5])}
    else:
        entry["layoutCorners"] = [_em(value) for value in box]
    if packed or glyph.channel:
        entry["channel"] = glyph.channel
    if rectangle is None:
        entry["vertices"] = [
            [
                _em(vertex.x),
                _em(vertex.y),
                _pixels(vertex.u, texture.width),
                _pixels(vertex.v, texture.height),
            ]
            for vertex in glyph.vertices
        ]
        entry["triangles"] = list(glyph.indices)
    return entry


def _exact_pixels(font: BinaryFont, texture: DdsTexture) -> Pixels | None:
    """Return the texture's pixels if an image of them rebuilds it exactly."""
    if not can_convert(texture.pixel_format):
        return None
    pixels = decode_pixels(texture)
    image = to_image(pixels, texture.pixel_format)
    rebuilt = encode_pixels(
        from_image(image, texture.pixel_format),
        texture.pixel_format,
        len(texture.levels),
    )
    exact = encode_dds(rebuilt, legacy_header=font.version is FontVersion.V3)
    return pixels if exact == font.texture else None


def _background(pixels: Pixels) -> str:
    """Return the most common pixel as hex: RGBA bytes, or half float bits."""
    flat = pixels.reshape(pixels.shape[0] * pixels.shape[1], -1)
    if flat.dtype == np.uint16:
        flat = flat.astype(">u2")
    return Counter(map(bytes, flat)).most_common(1)[0][0].hex()


def _whole_bounds(
    atlas: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """Return left, top, right, bottom texture pixels of an atlas rectangle."""
    left, bottom, right, top = (round(edge) for edge in atlas)
    return left, top, right, bottom


def _check_inside(
    bounds: tuple[int, int, int, int], size: tuple[int, int], what: str
) -> None:
    """Refuse a rectangle reaching past the texture, which numpy would clip."""
    left, top, right, bottom = bounds
    width, height = size
    if left < 0 or top < 0 or right > width or bottom > height:
        msg = f"{what} reaches outside the {width}x{height} texture"
        raise ValueError(msg)


def _blank_canvas(
    pixel_format: PixelFormat, size: tuple[int, int], background: str
) -> Pixels:
    width, height = size
    value = bytes.fromhex(background)
    if pixel_format is PixelFormat.R16F:
        return np.full((height, width), int.from_bytes(value, "big"), np.uint16)
    canvas = np.empty((height, width, 4), dtype=np.uint8)
    canvas[...] = np.frombuffer(value, dtype=np.uint8)
    return canvas


def _region(
    bounds: tuple[int, int, int, int], channel: int | None
) -> tuple[slice | int, ...]:
    left, top, right, bottom = bounds
    rows, columns = slice(top, bottom), slice(left, right)
    return (rows, columns) if channel is None else (rows, columns, channel)


def _cut_glyphs(
    font: BinaryFont,
    texture: DdsTexture,
    pixels: Pixels,
    rectangles: list[_Rectangle | None],
    background: str,
) -> list[tuple[int, NDArray[Any]]]:
    """Cut out the pixels of each glyph, checking that they rebuild the texture."""
    packed = any(glyph.channel for glyph in font.glyphs)
    canvas = _blank_canvas(texture.pixel_format, pixels.shape[1::-1], background)
    cuts = []
    for index, (glyph, rectangle) in enumerate(
        zip(font.glyphs, rectangles, strict=True)
    ):
        if rectangle is None:
            msg = f"Glyph {index} is not a textured rectangle and cannot be cut out"
            raise ValueError(msg)
        left, top, right, bottom = bounds = _whole_bounds(rectangle.atlas)
        if right <= left or bottom <= top:
            continue
        _check_inside(bounds, (texture.width, texture.height), f"Glyph {index}")
        region = _region(bounds, glyph.channel if packed else None)
        canvas[region] = pixels[region]
        cuts.append((index, np.ascontiguousarray(pixels[region])))
    rebuilt = encode_pixels(canvas, texture.pixel_format, len(texture.levels))
    if encode_dds(rebuilt, font.version is FontVersion.V3) != font.texture:
        msg = "Cutting this font into glyph images would lose texture data"
        raise ValueError(msg)
    return cuts


def _dump(document: dict[str, Any]) -> bytes:
    """Write one glyph or kerning pair per line, which keeps diffs readable."""
    fields = []
    for key, value in document.items():
        if isinstance(value, list) and value:
            items = ",\n".join(f"    {_compact(item)}" for item in value)
            fields.append(f"  {_compact(key)}: [\n{items}\n  ]")
        else:
            fields.append(f"  {_compact(key)}: {_compact(value)}")
    return ("{\n" + ",\n".join(fields) + "\n}\n").encode()


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


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
    """Build a binary font from a JSON document written by decompile_font."""
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
                msg = (
                    "The first glyph is drawn for missing characters and has no unicode"
                )
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
            pair["advance"] if version is FontVersion.V4 else _float32(pair["advance"]),
        )
        for pair in document.get("kerning", [])
    ]
    unknown = tuple(northlight.get("unknown", []))
    texture = _read_texture(document, folder)
    return BinaryFont(version, glyphs, charmap, kerning, unknown, texture)


def _read_glyph(entry: dict[str, Any], width: int, height: int) -> Glyph:
    if "vertices" in entry:
        vertices = tuple(
            Vertex(
                _float32(x), _float32(y), _coordinate(u, width), _coordinate(v, height)
            )
            for x, y, u, v in entry["vertices"]
        )
        indices = tuple(entry["triangles"])
        if len(indices) % 3 or any(not 0 <= i < len(vertices) for i in indices):
            msg = f"Glyph {_describe(entry)} has invalid triangles"
            raise FormatError(msg)
    else:
        rectangle = _Rectangle(
            plane=_edges(entry["planeBounds"]),
            atlas=_edges(entry["atlasBounds"]),
        )
        vertices, indices = rectangle.vertices(width, height), _QUAD_TRIANGLES
    if "layoutCorners" in entry:
        box = [_float32(value) for value in entry["layoutCorners"]]
        if len(box) != 8:
            msg = f"Glyph {_describe(entry)} needs 8 layoutCorners values"
            raise FormatError(msg)
    else:
        advance = _float32(entry["advance"])
        bottom = _float32(entry["layoutBounds"]["bottom"])
        top = _float32(entry["layoutBounds"]["top"])
        box = [0.0, bottom, advance, bottom, advance, top, 0.0, top]
    channel = entry.get("channel", 0)
    if channel not in (0, 1, 2, 3):
        msg = f"Glyph {_describe(entry)} has channel {channel}, not 0 to 3"
        raise FormatError(msg)
    return Glyph(vertices, indices, channel, tuple(box))  # type: ignore[arg-type]


def _edges(bounds: dict[str, float]) -> tuple[float, float, float, float]:
    left, bottom, right, top = (bounds[edge] for edge in _EDGES)
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
    canvas = _blank_canvas(pixel_format, size, document["northlight"]["background"])
    for entry in glyphs:
        if (name := entry.get("image")) is None:
            continue
        left, top, right, bottom = bounds = _whole_bounds(_edges(entry["atlasBounds"]))
        _check_inside(bounds, size, name)
        with Image.open(folder / name) as image:
            if image.size != (right - left, bottom - top):
                msg = f"{name} is {image.size}, not {(right - left, bottom - top)}"
                raise FormatError(msg)
            if packed:
                pixels = np.asarray(image.convert("L"))
            else:
                pixels = from_image(image, pixel_format)
        canvas[_region(bounds, entry["channel"] if packed else None)] = pixels
    return canvas
