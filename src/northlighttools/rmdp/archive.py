"""Extracting packages to directories and packing directories into packages."""

import os
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from northlighttools.binary import ByteOrder
from northlighttools.errors import FormatError
from northlighttools.fileio import atomic_writer
from northlighttools.rmdp.formats import PackageFormat
from northlighttools.rmdp.index import decode_index, encode_index
from northlighttools.rmdp.model import (
    Package,
    PackageFile,
    filetime_from_ns,
    filetime_to_ns,
)
from northlighttools.rmdp.names import (
    PackagePath,
    format_path,
    from_filesystem_name,
    sort_key,
    to_filesystem_name,
)

_CHUNK_SIZE = 1024 * 1024

FileCallback = Callable[[PackageFile], None]


def package_paths(path: Path) -> tuple[Path, Path]:
    """Return the index (.bin) and data (.rmdp) paths of the package at path."""
    return path.with_suffix(".bin"), path.with_suffix(".rmdp")


def read_package(path: Path) -> Package:
    """Read the index of the package at path (its .bin or .rmdp file)."""
    index_path, _ = package_paths(path)
    return decode_index(index_path.read_bytes())


def filesystem_path(root: Path, path: PackagePath) -> Path:
    """Return where a package entry is extracted under root."""
    return root.joinpath(*map(to_filesystem_name, path))


def extract_package(
    package: Package,
    data_path: Path,
    output_dir: Path,
    on_file: FileCallback | None = None,
) -> list[PackageFile]:
    """Write every folder and file of a package under output_dir.

    Return the files whose data does not match their stored CRC-32.
    """
    for folder in package.folders:
        filesystem_path(output_dir, folder).mkdir(parents=True, exist_ok=True)
    mismatched = []
    with data_path.open("rb") as source:
        for file in sorted(package.files, key=lambda file: file.offset):
            if not extract_file(source, file, filesystem_path(output_dir, file.path)):
                mismatched.append(file)
            if on_file:
                on_file(file)
    return mismatched


def extract_file(source: BinaryIO, file: PackageFile, target: Path) -> bool:
    """Copy one file out of a package's data.

    Return whether its data matches the stored CRC-32. Alan Wake's own packages
    hold some files that do not, so a mismatch alone does not stop extraction.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    source.seek(file.offset)
    checksum = 0
    with target.open("wb") as output:
        remaining = file.size
        while remaining:
            chunk = source.read(min(remaining, _CHUNK_SIZE))
            if not chunk:
                break
            output.write(chunk)
            checksum = zlib.crc32(chunk, checksum)
            remaining -= len(chunk)
    if remaining:
        target.unlink()
        msg = f"{format_path(file.path)} is cut short; the package data is corrupted"
        raise FormatError(msg)
    if file.timestamp is not None:
        timestamp = filetime_to_ns(file.timestamp)
        os.utime(target, ns=(timestamp, timestamp))
    return checksum == file.checksum


def pack_directory(
    source_dir: Path,
    output_path: Path,
    package_format: PackageFormat,
    byte_order: ByteOrder | None = None,
    on_file: FileCallback | None = None,
) -> Package:
    """Pack every folder and file under source_dir into a package at output_path."""
    folders, sources = _collect(source_dir)
    index_path, data_path = package_paths(output_path)
    files = []
    with atomic_writer(data_path) as data, atomic_writer(index_path) as index:
        for package_path in sorted(sources, key=sort_key):
            _align(data, package_format.data_alignment)
            file = _pack_file(data, package_path, sources[package_path], package_format)
            files.append(file)
            if on_file:
                on_file(file)
        _align(data, package_format.data_alignment)
        package = Package(
            format=package_format,
            byte_order=byte_order or package_format.byte_order,
            base_path=package_format.base_path,
            folders=folders,
            files=files,
        )
        index.write(encode_index(package))
    return package


def _collect(source_dir: Path) -> tuple[list[PackagePath], dict[PackagePath, Path]]:
    """Return the folders and files under source_dir by their package paths."""
    folders: list[PackagePath] = []
    sources: dict[PackagePath, Path] = {}
    for path in source_dir.rglob("*"):
        parts = path.relative_to(source_dir).parts
        package_path = tuple(from_filesystem_name(part) for part in parts)
        if path.is_dir():
            folders.append(package_path)
        elif sources.setdefault(package_path, path) != path:
            msg = f"{format_path(package_path)} is listed twice"
            raise ValueError(msg)
    return folders, sources


def _align(data: BinaryIO, alignment: int) -> None:
    data.write(bytes(-data.tell() % alignment))


def _pack_file(
    data: BinaryIO, package_path: PackagePath, path: Path, package_format: PackageFormat
) -> PackageFile:
    offset = data.tell()
    size, checksum = _copy(path, data)
    timestamp = None
    if package_format.has_timestamps:
        timestamp = filetime_from_ns(path.stat().st_mtime_ns)
    return PackageFile(package_path, offset, size, checksum, timestamp)


def _copy(path: Path, output: BinaryIO) -> tuple[int, int]:
    size = checksum = 0
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK_SIZE):
            output.write(chunk)
            checksum = zlib.crc32(chunk, checksum)
            size += len(chunk)
    return size, checksum
