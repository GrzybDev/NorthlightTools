import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from northlighttools.binfnt import (
    BinaryFont,
    compile_font,
    decompile_font,
    encode_font,
)
from northlighttools.errors import FormatError
from tests.binfnt.fonts import SAMPLES, rectangle


def read(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("font", SAMPLES.values(), ids=SAMPLES.keys())
@pytest.mark.parametrize("separate_glyphs", [False, True])
def test_decompiled_fonts_compile_back_unchanged(
    font: BinaryFont, separate_glyphs: bool, tmp_path: Path
) -> None:
    font = BinaryFont(**{**vars(font), "glyphs": font.glyphs[:2], "charmap": {65: 1}})

    decompile_font(font, tmp_path / "font.json", separate_glyphs=separate_glyphs)

    assert encode_font(compile_font(tmp_path / "font.json")) == encode_font(font)


@pytest.mark.parametrize("font", SAMPLES.values(), ids=SAMPLES.keys())
def test_glyphs_that_are_not_rectangles_keep_their_vertices(
    font: BinaryFont, tmp_path: Path
) -> None:
    decompile_font(font, tmp_path / "font.json")

    glyphs = read(tmp_path / "font.json")["glyphs"]
    assert encode_font(compile_font(tmp_path / "font.json")) == encode_font(font)
    assert glyphs[2]["triangles"] == [0, 1, 2, 2, 3, 0]
    assert "planeBounds" not in glyphs[2]
    assert len(glyphs[2]["layoutCorners"]) == 8


def test_documents_follow_the_msdf_atlas_gen_layout(tmp_path: Path) -> None:
    decompile_font(SAMPLES["quantum break"], tmp_path / "font.json")

    document = read(tmp_path / "font.json")

    assert document["atlas"]["type"] == "sdf"
    assert document["atlas"]["yOrigin"] == "top"
    assert document["glyphs"][0]["index"] == 0
    assert document["glyphs"][1] == {
        "unicode": 65,
        "advance": 0.625,
        "planeBounds": {"left": 0.0625, "bottom": 0, "right": 0.5625, "top": 0.75},
        "atlasBounds": {"left": 4, "bottom": 8, "right": 12, "top": 0},
        "layoutBounds": {"bottom": -0.25, "top": 1},
    }
    assert document["kerning"][0] == {
        "unicode1": 65,
        "unicode2": 66,
        "advance": -0.0625,
    }
    assert document["northlight"] == {
        "version": 7,
        "format": "r16f",
        "mipmaps": 1,
        "unknown": [4, 128],
        "texture": "font.png",
    }


def test_packed_fonts_name_each_glyphs_channel(tmp_path: Path) -> None:
    decompile_font(SAMPLES["alan wake packed"], tmp_path / "font.json")

    glyphs = read(tmp_path / "font.json")["glyphs"]

    assert [glyph["channel"] for glyph in glyphs] == [0, 1, 2]


def test_glyph_images_are_named_after_their_characters(tmp_path: Path) -> None:
    font = SAMPLES["alan wake packed"]
    font = BinaryFont(**{**vars(font), "glyphs": font.glyphs[:2], "charmap": {65: 1}})

    decompile_font(font, tmp_path / "font.json", separate_glyphs=True)

    images = sorted(path.name for path in (tmp_path / "font_glyphs").iterdir())
    assert images == ["U+0041.png", "fallback.png"]


def test_a_glyph_can_take_another_character(tmp_path: Path) -> None:
    decompile_font(SAMPLES["quantum break"], tmp_path / "font.json")
    document = read(tmp_path / "font.json")
    document["glyphs"][1]["unicode"] = 0x105
    write(tmp_path / "font.json", document)

    font = compile_font(tmp_path / "font.json")

    assert font.charmap == {0x105: 1, 66: 2}


def test_glyphs_can_be_added(tmp_path: Path) -> None:
    decompile_font(SAMPLES["quantum break"], tmp_path / "font.json")
    document = read(tmp_path / "font.json")
    document["glyphs"].append({**document["glyphs"][1], "unicode": 0x119})
    write(tmp_path / "font.json", document)

    font = compile_font(tmp_path / "font.json")

    assert font.charmap[0x119] == 3
    assert font.glyphs[3] == font.glyphs[1]


def test_the_first_glyph_cannot_have_a_character(tmp_path: Path) -> None:
    decompile_font(SAMPLES["quantum break"], tmp_path / "font.json")
    document = read(tmp_path / "font.json")
    document["glyphs"][0] = {**document["glyphs"][0], "unicode": 32}
    write(tmp_path / "font.json", document)

    with pytest.raises(FormatError, match="missing characters"):
        compile_font(tmp_path / "font.json")


def test_characters_cannot_be_given_to_two_glyphs(tmp_path: Path) -> None:
    decompile_font(SAMPLES["quantum break"], tmp_path / "font.json")
    document = read(tmp_path / "font.json")
    document["glyphs"][2]["unicode"] = 65
    write(tmp_path / "font.json", document)

    with pytest.raises(FormatError, match="given to two glyphs"):
        compile_font(tmp_path / "font.json")


def test_documents_without_northlight_data_are_refused(tmp_path: Path) -> None:
    write(tmp_path / "font.json", {"atlas": {}, "glyphs": []})

    with pytest.raises(FormatError, match="lacks the northlight object"):
        compile_font(tmp_path / "font.json")


def test_cutting_glyphs_that_would_lose_texture_data_is_refused(tmp_path: Path) -> None:
    font = SAMPLES["quantum break"]
    font = BinaryFont(**{**vars(font), "glyphs": font.glyphs[:1], "charmap": {}})

    with pytest.raises(ValueError, match="would lose texture data"):
        decompile_font(font, tmp_path / "font.json", separate_glyphs=True)

    assert list(tmp_path.iterdir()) == []


def test_glyphs_reaching_past_the_texture_are_not_cut_out(tmp_path: Path) -> None:
    font = SAMPLES["alan wake remastered"]
    outside = replace(
        font.glyphs[1], vertices=rectangle((0.0625, 0.0, 0.5625, 0.75), (12, 0, 17, 8))
    )
    font = BinaryFont(**{**vars(font), "glyphs": [font.glyphs[0], outside], "charmap": {65: 1}})

    with pytest.raises(ValueError, match="Glyph 1 reaches outside the 16x16 texture"):
        decompile_font(font, tmp_path / "font.json", separate_glyphs=True)
