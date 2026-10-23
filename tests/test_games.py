"""Round trips over the games' own files, in the folders NORTHLIGHT_GAME_DIRS lists.

The folders are only read; everything written goes to temporary folders.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import override

import pytest

from northlighttools.binfnt import compile_font, decode_font, decompile_font, encode_font
from northlighttools.rmdp import (
    PackageFile,
    decode_index,
    encode_index,
    extract_file,
    extract_package,
    format_path,
    package_paths,
    patch_index,
    read_package,
    repack_directory,
)
from northlighttools.string_table import (
    TranslationFormat,
    decode_string_table,
    encode_string_table,
    export_translation,
    import_translation,
)

GAME_DIRS = [
    Path(entry) for entry in os.environ.get("NORTHLIGHT_GAME_DIRS", "").split(os.pathsep) if entry
]

pytestmark = [
    pytest.mark.games,
    pytest.mark.skipif(not GAME_DIRS, reason="NORTHLIGHT_GAME_DIRS lists no game folders"),
]


@dataclass(frozen=True)
class GameFile:
    game_dir: Path
    path: Path

    @override
    def __str__(self) -> str:
        return f"{self.game_dir.name}/{self.path.relative_to(self.game_dir).as_posix()}"


@dataclass(frozen=True)
class PackedFile:
    package: GameFile
    """The package's data (.rmdp) file."""
    file: PackageFile

    @override
    def __str__(self) -> str:
        return f"{self.package}/{format_path(self.file.path)}"

    def read(self, folder: Path) -> bytes:
        """Extract this file alone and return its data.

        Args:
            folder: Where to extract the file.
        """
        target = folder / self.file.name
        with self.package.path.open("rb") as source:
            extract_file(source, self.file, target)
        return target.read_bytes()


@dataclass
class Found:
    indexes: list[GameFile] = field(default_factory=list)
    smallest_packages: list[GameFile] = field(default_factory=list)
    string_tables: list[PackedFile] = field(default_factory=list)
    fonts: list[PackedFile] = field(default_factory=list)


def discover(game_dirs: list[Path]) -> Found:
    """Find the package indexes, the smallest package of each game and the packed texts and fonts.

    Args:
        game_dirs: The games' install folders.
    """
    found = Found()
    seen: set[tuple[int, int]] = set()
    for game_dir in game_dirs:
        sizes: dict[GameFile, int] = {}
        for index_path in sorted(game_dir.rglob("*.bin")):
            found.indexes.append(GameFile(game_dir, index_path))
            data_path = package_paths(index_path)[1]
            if not data_path.is_file():
                continue
            package = GameFile(game_dir, data_path)
            files = read_package(index_path).files
            if files:
                sizes[package] = data_path.stat().st_size
            for file in files:
                name = file.name.lower()
                if name == "string_table.bin":
                    group = found.string_tables
                elif name.endswith(".binfnt"):
                    group = found.fonts
                else:
                    continue
                # Packages of other languages and episodes repeat many of these files.
                if (file.size, file.checksum) not in seen:
                    seen.add((file.size, file.checksum))
                    group.append(PackedFile(package, file))
        if not sizes:
            msg = f"NORTHLIGHT_GAME_DIRS lists {game_dir}, which holds no package with files"
            raise FileNotFoundError(msg)
        found.smallest_packages.append(min(sizes, key=sizes.__getitem__))
    return found


FOUND = discover(GAME_DIRS)


@pytest.mark.parametrize("index", FOUND.indexes, ids=str)
def test_package_indexes_patch_and_encode_back_into_the_games_own(index: GameFile) -> None:
    original = index.path.read_bytes()
    package = decode_index(original)

    encoded = encode_index(package)

    assert patch_index(original, package.files) == original
    assert decode_index(encoded) == package
    assert len(encoded) == len(original)
    # Encoding zeroes what the games' packers left uninitialised and nothing else.
    assert not any(new for new, old in zip(encoded, original, strict=True) if new != old)


@pytest.mark.parametrize("package", FOUND.smallest_packages, ids=str)
def test_the_smallest_package_of_each_game_extracts_and_packs_back_identical(
    package: GameFile, tmp_path: Path
) -> None:
    index_path, data_path = package_paths(package.path)
    extracted = tmp_path / "extracted"

    extract_package(read_package(index_path), data_path, extracted)
    repack_directory(extracted, tmp_path / "packed.rmdp", data_path)

    assert (tmp_path / "packed.bin").read_bytes() == index_path.read_bytes()
    assert (tmp_path / "packed.rmdp").read_bytes() == data_path.read_bytes()


@pytest.mark.parametrize("translation_format", list(TranslationFormat))
@pytest.mark.parametrize("table", FOUND.string_tables, ids=str)
def test_string_tables_come_back_identical_from_translation_documents(
    table: PackedFile, translation_format: TranslationFormat, tmp_path: Path
) -> None:
    data = table.read(tmp_path)
    entries = decode_string_table(data)
    assert encode_string_table(entries) == data

    try:
        document = export_translation(entries, translation_format, table.file.name)
    except ValueError as refusal:
        pytest.skip(f"{translation_format} cannot carry the table: {refusal}")
    imported_format, imported = import_translation(document)

    assert imported_format is translation_format
    assert encode_string_table(imported) == data


@pytest.mark.parametrize("font", FOUND.fonts, ids=str)
def test_fonts_compile_back_identical_from_their_json_documents(
    font: PackedFile, tmp_path: Path
) -> None:
    data = font.read(tmp_path)
    decoded = decode_font(data)
    assert encode_font(decoded) == data
    document = tmp_path / "decompiled" / f"{Path(font.file.name).stem}.json"

    decompile_font(decoded, document)

    assert encode_font(compile_font(document)) == data
