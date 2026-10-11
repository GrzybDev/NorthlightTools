import os
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from northlighttools.binary import packer
from northlighttools.rmdp import (
    FORMATS,
    Game,
    decode_index,
    extract_package,
    pack_directory,
    patch_index,
    read_package,
    repack_directory,
)

CONTENTS = {
    "data/fonts/body.binfnt": b"glyphs" * 100,
    "data/fonts/title.binfnt": b"letters" * 50,
    "data/locale/en/strings.bin": b"\x01\x02\x03",
}


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    for index, (relative, data) in enumerate(CONTENTS.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.utime(path, ns=(1_700_000_000_000_000_000 + index,) * 2)
    return root


def header_size(game: Game) -> int:
    return 17 + 128 + (8 if FORMATS[game].has_header_value else 0)


def make_game_package(source: Path, folder: Path, game: Game) -> Path:
    """Pack source, then give the package what the games' own packers leave:
    data in another order than the index, an outdated checksum and garbage in
    the header and in the folders' unknown field."""
    package_format = FORMATS[game]
    package = pack_directory(source, folder / "plain.rmdp", package_format)
    plain = (folder / "plain.rmdp").read_bytes()
    data = bytearray()
    moved = {}
    for file in reversed(package.files):
        data += bytes(-len(data) % package_format.data_alignment)
        moved[file.path] = replace(file, offset=len(data))
        data += plain[file.offset : file.offset + file.size]
    files = [moved[file.path] for file in package.files]
    files[0] = replace(files[0], checksum=0xBAD)
    index = bytearray(patch_index((folder / "plain.bin").read_bytes(), files))

    path_start = header_size(game) - 128
    path_end = index.index(b"\0", path_start)
    index[path_end + 1 : path_start + 128] = b"\xcd" * (path_start + 127 - path_end)
    folder_layout = packer(package.byte_order, package_format.folder_fields)
    unknown_at = folder_layout.pack(*[0] * 3, 0xFFFFFFFF, *[0] * 3).index(b"\xff" * 4)
    for number in range(len(package.folders) + 1):
        position = header_size(game) + number * folder_layout.size + unknown_at
        index[position : position + 4] = struct.pack("<I", 0xCACACACA)

    (folder / "game.bin").write_bytes(index)
    (folder / "game.rmdp").write_bytes(data)
    return folder / "game.rmdp"


def extract(package_path: Path, output_dir: Path) -> None:
    extract_package(read_package(package_path), package_path, output_dir)
    for path in output_dir.rglob("*"):
        os.utime(path, ns=(1_800_000_000_000_000_000,) * 2)


@pytest.mark.parametrize("game", list(Game))
def test_an_unchanged_directory_repacks_into_the_same_package(
    game: Game, source: Path, tmp_path: Path
) -> None:
    original = make_game_package(source, tmp_path, game)
    extract(original, tmp_path / "extracted")

    repack_directory(tmp_path / "extracted", tmp_path / "again.rmdp", original)

    assert (tmp_path / "again.bin").read_bytes() == original.with_suffix(
        ".bin"
    ).read_bytes()
    assert (tmp_path / "again.rmdp").read_bytes() == original.read_bytes()


@pytest.mark.parametrize("game", [Game.ALAN_WAKE_REMASTERED, Game.CONTROL])
def test_a_changed_file_changes_only_its_own_record(
    game: Game, source: Path, tmp_path: Path
) -> None:
    original = make_game_package(source, tmp_path, game)
    extract(original, tmp_path / "extracted")
    changed = tmp_path / "extracted" / "data" / "fonts" / "title.binfnt"
    changed.write_bytes(b"LETTERS" * 50)

    package = repack_directory(
        tmp_path / "extracted", tmp_path / "again.rmdp", original
    )

    before = read_package(original)
    after = decode_index((tmp_path / "again.bin").read_bytes())
    assert [file.offset for file in after.files] == [
        file.offset for file in before.files
    ]
    for old, new in zip(before.files, after.files, strict=True):
        assert (new.checksum == old.checksum) == (new.name != "title.binfnt")
    assert package.files == after.files
    original_header = original.with_suffix(".bin").read_bytes()[: header_size(game)]
    assert (tmp_path / "again.bin").read_bytes()[: header_size(game)] == original_header


def test_a_package_can_be_repacked_over_itself(source: Path, tmp_path: Path) -> None:
    original = make_game_package(source, tmp_path, Game.CONTROL)
    expected = original.read_bytes(), original.with_suffix(".bin").read_bytes()
    extract(original, tmp_path / "extracted")

    repack_directory(tmp_path / "extracted", original, original)

    assert (
        original.read_bytes(),
        original.with_suffix(".bin").read_bytes(),
    ) == expected


def test_new_files_go_after_the_original_data(source: Path, tmp_path: Path) -> None:
    original = make_game_package(source, tmp_path, Game.QUANTUM_BREAK)
    extract(original, tmp_path / "extracted")
    (tmp_path / "extracted" / "data" / "added.txt").write_bytes(b"new")

    package = repack_directory(
        tmp_path / "extracted", tmp_path / "again.rmdp", original
    )

    before = {file.path: file.offset for file in read_package(original).files}
    offsets = {file.path: file.offset for file in package.files}
    assert {path: offsets[path] for path in before} == before
    assert offsets[("data", "added.txt")] > max(before.values())
    assert read_package(tmp_path / "again.bin").files == package.files
