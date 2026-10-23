import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from northlighttools.binfnt import encode_font
from northlighttools.cli import app
from northlighttools.rmdp import FORMATS, Game, pack_directory
from northlighttools.string_table import encode_string_table, export_translation
from tests.binfnt.fonts import SAMPLES
from tests.string_table.entries import ENTRIES, translated


@pytest.fixture(autouse=True)
def in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def run(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, list(args), catch_exceptions=False)
    # The console breaks long paths across lines at its width.
    return result.exit_code, "".join(result.output.split())


def test_translating_a_string_table_keeps_the_translation_and_the_original() -> None:
    original = encode_string_table(ENTRIES)
    Path("string_table.bin").write_bytes(original)
    translation = [translated(entry) for entry in ENTRIES]
    document = Path("string_table.xlf")

    assert run("string-table", "export", "string_table.bin")[0] == 0
    document.write_bytes(export_translation(translation))
    exported_again = run("string-table", "export", "string_table.bin")
    imported = run("string-table", "import", "string_table.xlf")
    imported_again = run("string-table", "import", "string_table.xlf")

    assert exported_again[0] == 1
    assert "string_table.xlf" in exported_again[1]
    assert document.read_bytes() == export_translation(translation)
    assert imported[0] == imported_again[0] == 0
    assert "string_table.bin.orig" in imported[1]
    assert "string_table.bin.orig" not in imported_again[1]
    assert Path("string_table.bin.orig").read_bytes() == original
    assert Path("string_table.bin").read_bytes() == encode_string_table(translation)


@pytest.fixture
def package() -> dict[str, bytes]:
    source = Path("source")
    for index, (relative, data) in enumerate(
        {"data/fonts/body.binfnt": b"glyphs" * 100, "data/strings.bin": b"\x01\x02"}.items()
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        timestamp = 1_700_000_000_000_000_000 + index * 100  # whole FILETIME ticks
        os.utime(path, ns=(timestamp, timestamp))
    pack_directory(source, Path("game.rmdp"), FORMATS[Game.QUANTUM_BREAK])
    return {name: Path(name).read_bytes() for name in ("game.bin", "game.rmdp")}


@pytest.mark.parametrize("options", [[], ["--original", "game.rmdp"]], ids=["new", "repacked"])
def test_packing_an_extracted_package_back_keeps_the_original(
    options: list[str], package: dict[str, bytes]
) -> None:
    assert run("rmdp", "extract", "game.rmdp")[0] == 0
    Path("game", "data", "strings.bin.orig").write_bytes(b"kept by an import")
    code, output = run("rmdp", "pack", "game", *options)

    assert code == 0
    for name, data in package.items():
        assert f"{name}.orig" in output
        assert Path(f"{name}.orig").read_bytes() == data
        assert Path(name).read_bytes() == data


def test_later_packs_take_the_layout_of_the_kept_original(package: dict[str, bytes]) -> None:
    assert run("rmdp", "extract", "game.rmdp")[0] == 0
    strings = Path("game", "data", "strings.bin")
    strings.write_bytes(b"translated" * 100)
    assert run("rmdp", "pack", "game", "--original", "game.rmdp")[0] == 0
    strings.write_bytes(b"\x01\x02")

    code, _ = run("rmdp", "pack", "game", "--original", "game.rmdp.orig")

    assert code == 0
    for name, data in package.items():
        assert Path(name).read_bytes() == data


def test_extracting_over_an_edited_file_writes_nothing(package: dict[str, bytes]) -> None:
    edited = Path("game", "data", "strings.bin")
    edited.parent.mkdir(parents=True)
    edited.write_bytes(b"edited")

    code, output = run("rmdp", "extract", "game.rmdp")

    assert code == 1
    assert "strings.bin" in output
    assert edited.read_bytes() == b"edited"
    assert [path for path in Path("game").rglob("*") if path.is_file()] == [edited]


def test_a_font_compiles_back_over_its_original_and_decompiling_keeps_edits() -> None:
    original = encode_font(SAMPLES["quantum break"])
    Path("font.binfnt").write_bytes(original)
    document = Path("font", "font.json")

    assert run("binfnt", "decompile", "font.binfnt")[0] == 0
    compiled = run("binfnt", "compile", str(document), "font.binfnt")
    document.write_bytes(b"edited")
    decompiled_again = run("binfnt", "decompile", "font.binfnt")

    assert compiled[0] == 0
    assert "font.binfnt.orig" in compiled[1]
    assert Path("font.binfnt.orig").read_bytes() == Path("font.binfnt").read_bytes() == original
    assert decompiled_again[0] == 1
    assert document.read_bytes() == b"edited"
