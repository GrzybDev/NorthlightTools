import os
from pathlib import Path

import pytest

from northlighttools.errors import FormatError
from northlighttools.rmdp import (
    FORMATS,
    Game,
    extract_package,
    pack_directory,
    read_package,
)

CONTENTS = {
    "d%3A/data/fonts/body.binfnt": b"glyphs" * 100,
    "d%3A/data/locale/en/strings.bin": b"\x01\x02\x03",
    "d%3A/data/empty.txt": b"",
}


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    for index, (relative, data) in enumerate(CONTENTS.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        timestamp = 1_700_000_000_123_456_700 + index * 100  # whole FILETIME ticks
        os.utime(path, ns=(timestamp, timestamp))
    (root / "d%3A" / "data" / "unused").mkdir()
    return root


@pytest.mark.parametrize("game", list(Game))
def test_a_packed_directory_extracts_unchanged(game: Game, source: Path, tmp_path: Path) -> None:
    pack_directory(source, tmp_path / "out.rmdp", FORMATS[game])

    package = read_package(tmp_path / "out.bin")
    extract_package(package, tmp_path / "out.rmdp", tmp_path / "extracted")

    extracted = tmp_path / "extracted"
    for relative, data in CONTENTS.items():
        assert (extracted / relative).read_bytes() == data
    assert (extracted / "d%3A" / "data" / "unused").is_dir()
    assert ("d:", "data", "unused") in package.folders


@pytest.mark.parametrize("game", [Game.AMERICAN_NIGHTMARE, Game.CONTROL])
def test_timestamps_survive_packing_and_extraction(
    game: Game, source: Path, tmp_path: Path
) -> None:
    pack_directory(source, tmp_path / "out.rmdp", FORMATS[game])
    package = read_package(tmp_path / "out.bin")

    extract_package(package, tmp_path / "out.rmdp", tmp_path / "extracted")

    for relative in CONTENTS:
        original = (source / relative).stat().st_mtime_ns
        assert (tmp_path / "extracted" / relative).stat().st_mtime_ns == original


@pytest.mark.parametrize("game", [Game.ALAN_WAKE, Game.ALAN_WAKE_REMASTERED])
def test_formats_without_timestamps_pack_none(game: Game, source: Path, tmp_path: Path) -> None:
    package = pack_directory(source, tmp_path / "out.rmdp", FORMATS[game])

    assert all(file.timestamp is None for file in package.files)
    assert read_package(tmp_path / "out.bin").files == package.files


@pytest.mark.parametrize("game", list(Game))
def test_file_data_is_aligned_as_in_the_games(game: Game, source: Path, tmp_path: Path) -> None:
    alignment = FORMATS[game].data_alignment

    package = pack_directory(source, tmp_path / "out.rmdp", FORMATS[game])

    assert all(file.offset % alignment == 0 for file in package.files)
    assert (tmp_path / "out.rmdp").stat().st_size % alignment == 0


def test_data_not_matching_its_checksum_is_reported(source: Path, tmp_path: Path) -> None:
    package = pack_directory(source, tmp_path / "out.rmdp", FORMATS[Game.CONTROL])
    body = next(file for file in package.files if file.name == "body.binfnt")
    data = bytearray((tmp_path / "out.rmdp").read_bytes())
    data[body.offset] ^= 0xFF
    (tmp_path / "out.rmdp").write_bytes(data)

    mismatched = extract_package(package, tmp_path / "out.rmdp", tmp_path / "extracted")

    assert mismatched == [body]
    extracted = tmp_path / "extracted" / "d%3A" / "data" / "fonts" / "body.binfnt"
    assert extracted.read_bytes() == bytes(data[body.offset : body.offset + body.size])


def test_data_cut_short_fails_extraction_and_leaves_no_files(source: Path, tmp_path: Path) -> None:
    package = pack_directory(source, tmp_path / "out.rmdp", FORMATS[Game.CONTROL])
    last = max(package.files, key=lambda file: file.offset)
    with (tmp_path / "out.rmdp").open("r+b") as data:
        data.truncate(last.offset + 1)

    with pytest.raises(FormatError, match="cut short"):
        extract_package(package, tmp_path / "out.rmdp", tmp_path / "extracted")

    assert not [path for path in (tmp_path / "extracted").rglob("*") if path.is_file()]


def test_failed_packing_leaves_no_package(source: Path, tmp_path: Path) -> None:
    (source / "d%3A" / "data" / "empty%2Etxt").write_bytes(b"")

    with pytest.raises(ValueError, match="listed twice"):
        pack_directory(source, tmp_path / "out.rmdp", FORMATS[Game.CONTROL])

    assert list(tmp_path.glob("out*")) == []
