"""Writing fonts as msdf-atlas-gen JSON documents with their texture beside them."""

import io
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from northlighttools.binfnt.atlas import (
    EDGES,
    Rectangle,
    blank_canvas,
    check_inside,
    float32,
    json_number,
    same_floats,
    texture_region,
    to_pixels,
    whole_bounds,
)
from northlighttools.binfnt.dds import DdsTexture, PixelFormat, decode_dds, encode_dds
from northlighttools.binfnt.model import BinaryFont, FontVersion, Glyph
from northlighttools.binfnt.texture import (
    Pixels,
    can_convert,
    decode_pixels,
    encode_pixels,
    from_image,
    to_image,
)
from northlighttools.fileio import creating_files, write_atomically

_KERNED_VERSIONS = (FontVersion.V4, FontVersion.V7)


def _em(value: float) -> float | int:
    """Return the shortest number that a float32 font value reads back as."""
    for digits in range(1, 10):
        candidate = float(f"{value:.{digits}g}")
        if same_floats([candidate], [value]):
            return json_number(candidate)
    return value


def _glyph_codes(font: BinaryFont) -> list[int | None]:
    codes: list[int | None] = [None] * len(font.glyphs)
    for code, index in sorted(font.charmap.items()):
        if codes[index] is not None:
            msg = f"Glyph {index} serves several characters, which the JSON cannot hold"
            raise ValueError(msg)
        codes[index] = code
    if None in codes[1:]:
        msg = f"Glyph {codes.index(None, 1)} serves no character; the JSON cannot hold it"
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


def decompile_font(font: BinaryFont, json_path: Path, *, separate_glyphs: bool = False) -> None:
    """Write a font as a JSON document, with its texture beside it.

    Nothing is written when any of the files exists already.

    Args:
        font: The font to write.
        json_path: Where to write the document.
        separate_glyphs: Whether to save each glyph as its own image instead of the texture.
    """
    texture = decode_dds(font.texture)
    width, height = texture.width, texture.height
    codes = _glyph_codes(font)
    rectangles = [Rectangle.of(glyph, width, height) for glyph in font.glyphs]
    packed = any(glyph.channel for glyph in font.glyphs)

    glyphs = [
        _glyph_entry(glyph, index, code, rectangle, texture, packed)
        for index, (glyph, code, rectangle) in enumerate(
            zip(font.glyphs, codes, rectangles, strict=True)
        )
    ]
    pixels = _exact_pixels(font, texture)
    output_dir, stem = json_path.parent, json_path.stem
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
                "advance": int(pair.amount) if font.version is FontVersion.V4 else _em(pair.amount),
            }
            for pair in font.kerning
        ]
    document["northlight"] = northlight

    files: dict[Path, bytes] = {}
    if separate_glyphs:
        if pixels is None:
            msg = "This font's texture can only be kept as a DDS file"
            raise ValueError(msg)
        background = _background(pixels)
        cuts = _cut_glyphs(font, texture, pixels, rectangles, background)
        folder = output_dir / f"{stem}_glyphs"
        northlight["glyphs"] = folder.name
        northlight["background"] = background
        for index, region in cuts:
            code = codes[index]
            name = f"U+{code:04X}.png" if code is not None else "fallback.png"
            glyphs[index]["image"] = name
            image = Image.fromarray(region) if packed else to_image(region, texture.pixel_format)
            files[folder / name] = _png(image)
    elif pixels is not None:
        northlight["texture"] = f"{stem}.png"
        files[output_dir / f"{stem}.png"] = _png(to_image(pixels, texture.pixel_format))
    else:
        northlight["texture"] = f"{stem}.dds"
        files[output_dir / f"{stem}.dds"] = font.texture
    files[json_path] = _dump(document)
    with creating_files(files):
        for path, data in files.items():
            write_atomically(path, data)


def _atlas_entry(font: BinaryFont, texture: DdsTexture, pixels: Pixels | None) -> dict[str, Any]:
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
    entry["size"] = json_number(_atlas_size(font, texture.width))
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
        "lineHeight": _em(float32(ascender - descender)),
        "ascender": _em(ascender),
        "descender": _em(descender),
    }


def _glyph_entry(
    glyph: Glyph,
    index: int,
    code: int | None,
    rectangle: Rectangle | None,
    texture: DdsTexture,
    packed: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"index": index} if code is None else {"unicode": code}
    box = glyph.box
    entry["advance"] = _em(box[2])
    if rectangle is not None:
        entry["planeBounds"] = dict(zip(EDGES, map(_em, rectangle.plane), strict=True))
        entry["atlasBounds"] = dict(zip(EDGES, rectangle.atlas, strict=True))
    standard_box = [0.0, box[1], box[2], box[1], box[2], box[5], 0.0, box[5]]
    if same_floats(standard_box, box):
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
                to_pixels(vertex.u, texture.width),
                to_pixels(vertex.v, texture.height),
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


def _cut_glyphs(
    font: BinaryFont,
    texture: DdsTexture,
    pixels: Pixels,
    rectangles: list[Rectangle | None],
    background: str,
) -> list[tuple[int, NDArray[Any]]]:
    """Cut out the pixels of each glyph, checking that they rebuild the texture."""
    packed = any(glyph.channel for glyph in font.glyphs)
    canvas = blank_canvas(texture.pixel_format, pixels.shape[1::-1], background)
    cuts = []
    for index, (glyph, rectangle) in enumerate(zip(font.glyphs, rectangles, strict=True)):
        if rectangle is None:
            msg = f"Glyph {index} is not a textured rectangle and cannot be cut out"
            raise ValueError(msg)
        left, top, right, bottom = bounds = whole_bounds(rectangle.atlas)
        if right <= left or bottom <= top:
            continue
        check_inside(bounds, (texture.width, texture.height), f"Glyph {index}")
        region = texture_region(bounds, glyph.channel if packed else None)
        canvas[region] = pixels[region]
        cuts.append((index, np.ascontiguousarray(pixels[region])))
    rebuilt = encode_pixels(canvas, texture.pixel_format, len(texture.levels))
    if encode_dds(rebuilt, font.version is FontVersion.V3) != font.texture:
        msg = "Cutting this font into glyph images would lose texture data"
        raise ValueError(msg)
    return cuts


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


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
