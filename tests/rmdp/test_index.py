import dataclasses
from typing import Any

import pytest

from northlighttools.binary import ByteOrder, packer
from northlighttools.errors import FormatError
from northlighttools.rmdp import (
    FORMATS,
    Game,
    Package,
    PackageFile,
    decode_index,
    encode_index,
)


def make_package(game: Game, paths: list[str], **changes: Any) -> Package:
    package_format = FORMATS[game]
    timestamp = 133_000_000_000_000_000 if package_format.has_timestamps else None
    files = [
        PackageFile(tuple(path.split("/")), 16 * i, i + 1, 0xC0FFEE + i, timestamp)
        for i, path in enumerate(paths)
    ]
    package = Package(
        package_format,
        package_format.byte_order,
        package_format.base_path,
        folders=[],
        files=files,
    )
    return dataclasses.replace(package, **changes)


def file_order(data: bytes) -> list[str]:
    return ["/".join(file.path) for file in decode_index(data).files]


SAMPLE_PATHS = ["d:/data/fonts/body.binfnt", "d:/data/locale/en/strings.bin"]


@pytest.mark.parametrize("game", list(Game))
def test_index_survives_a_round_trip(game: Game) -> None:
    package = make_package(
        game, SAMPLE_PATHS, folders=[("d:", "data", "fonts"), ("d:", "data", "empty")]
    )

    decoded = decode_index(encode_index(package))

    assert decoded.files == package.files
    assert decoded.format == package.format
    assert decoded.byte_order == package.byte_order
    assert decoded.base_path == package.base_path
    assert set(decoded.folders) == {
        ("d:",),
        ("d:", "data"),
        ("d:", "data", "fonts"),
        ("d:", "data", "empty"),
        ("d:", "data", "locale"),
        ("d:", "data", "locale", "en"),
    }


@pytest.mark.parametrize(
    ("game", "folder_size", "file_size"),
    [
        (Game.ALAN_WAKE, 28, 40),
        (Game.ALAN_WAKE_REMASTERED, 56, 64),
        (Game.AMERICAN_NIGHTMARE, 28, 48),
        (Game.QUANTUM_BREAK, 48, 60),
        (Game.CONTROL, 48, 60),
    ],
)
def test_entries_have_the_sizes_the_games_use(game: Game, folder_size: int, file_size: int) -> None:
    package_format = FORMATS[game]

    assert packer(ByteOrder.LITTLE, package_format.folder_fields).size == folder_size
    assert packer(ByteOrder.LITTLE, package_format.file_fields).size == file_size


@pytest.mark.parametrize("game", list(Game))
def test_index_size_matches_its_layout(game: Game) -> None:
    package_format = FORMATS[game]
    package = make_package(game, ["a/b.txt"], base_path="")
    folder_size = packer(ByteOrder.LITTLE, package_format.folder_fields).size
    file_size = packer(ByteOrder.LITTLE, package_format.file_fields).size
    header_size = 1 + 12 + (8 if package_format.has_header_value else 0) + 4 + 128
    closing = folder_size if package_format.has_closing_entry else 0

    data = encode_index(package)

    assert len(data) == header_size + 2 * folder_size + file_size + closing + 8


def test_entries_follow_the_case_insensitive_order_of_backslashed_paths() -> None:
    paths = [
        "lib/junction/b.txt",
        "lib/Junction1/a.txt",
        "lib/zeta.txt",
        "lib/Alpha.txt",
        "lib/_under.txt",
    ]

    order = file_order(encode_index(make_package(Game.CONTROL, paths)))

    assert order == [
        "lib/_under.txt",
        "lib/Alpha.txt",
        "lib/Junction1/a.txt",
        "lib/junction/b.txt",
        "lib/zeta.txt",
    ]


def test_names_are_stored_in_the_order_entries_are_created() -> None:
    package = make_package(Game.CONTROL, ["a/b/c.txt", "a/d.txt"])

    data = encode_index(package)

    assert data.endswith(b"a\0b\0c.txt\0d.txt\0")


@pytest.mark.parametrize("game", [Game.ALAN_WAKE, Game.ALAN_WAKE_REMASTERED])
def test_layout_of_version_2_is_told_apart(game: Game) -> None:
    data = encode_index(make_package(game, SAMPLE_PATHS))

    assert decode_index(data).format.game is game


def test_byte_order_flag_leads_the_index() -> None:
    big = encode_index(make_package(Game.ALAN_WAKE, SAMPLE_PATHS))
    little = encode_index(make_package(Game.ALAN_WAKE, SAMPLE_PATHS, byte_order=ByteOrder.LITTLE))

    assert big[:5] == b"\x01\x00\x00\x00\x02"
    assert little[:5] == b"\x00\x02\x00\x00\x00"
    assert decode_index(little).byte_order is ByteOrder.LITTLE


@pytest.mark.parametrize("game", [Game.ALAN_WAKE, Game.QUANTUM_BREAK])
def test_data_checksums_are_stored_little_endian(game: Game) -> None:
    package = make_package(game, ["a.txt"])

    data = encode_index(package)

    assert (0xC0FFEE).to_bytes(4, "little") in data
    assert decode_index(data).files[0].checksum == 0xC0FFEE


def test_extra_paths_survive_a_round_trip() -> None:
    package = make_package(
        Game.ALAN_WAKE_REMASTERED,
        SAMPLE_PATHS,
        extra_paths=["d:\\data\\levels\\one.bin", "d:\\data\\levels\\two.resources"],
    )

    data = encode_index(package)

    assert data.endswith(b"\x00\x00\x00\x1cd:\\data\\levels\\two.resources")
    assert decode_index(data).extra_paths == package.extra_paths


def test_a_corrupted_name_is_detected() -> None:
    data = bytearray(encode_index(make_package(Game.QUANTUM_BREAK, SAMPLE_PATHS)))
    data[data.rindex(b"strings")] = ord("x")

    with pytest.raises(FormatError, match="Checksum mismatch"):
        decode_index(bytes(data))


def test_a_truncated_index_is_rejected() -> None:
    data = encode_index(make_package(Game.QUANTUM_BREAK, SAMPLE_PATHS))

    with pytest.raises(FormatError):
        decode_index(data[:-20])


def test_an_unknown_version_is_rejected() -> None:
    data = bytearray(encode_index(make_package(Game.QUANTUM_BREAK, SAMPLE_PATHS)))
    data[1] = 5

    with pytest.raises(FormatError, match="Unsupported package version 5"):
        decode_index(bytes(data))


@pytest.mark.parametrize(
    "paths",
    [["a/File.txt", "a/file.txt"], ["Data/a.txt", "data/b.txt"], ["a/x", "a/x"]],
)
def test_names_the_engine_cannot_tell_apart_are_refused(paths: list[str]) -> None:
    with pytest.raises(ValueError, match=r"letter case|listed twice"):
        encode_index(make_package(Game.CONTROL, paths))
