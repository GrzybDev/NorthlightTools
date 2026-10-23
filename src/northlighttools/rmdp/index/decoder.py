"""Reading a package index, checking its names and the links of its tree."""

from typing import cast

from northlighttools.binary import BinaryReader, ByteOrder, packer
from northlighttools.errors import FormatError
from northlighttools.rmdp.formats import FORMATS, PackageFormat
from northlighttools.rmdp.index.records import (
    BASE_PATH_SIZE,
    FileRecord,
    FolderRecord,
    stored_checksum,
)
from northlighttools.rmdp.model import Package, PackageFile
from northlighttools.rmdp.names import PackagePath, name_checksum

_BYTE_ORDER_FLAGS = {0: ByteOrder.LITTLE, 1: ByteOrder.BIG}


def decode_index(data: bytes) -> Package:
    """Parse a package index, checking its names and the links of its tree.

    Args:
        data: Contents of the index (.bin) file.
    """
    reader = BinaryReader(data)
    flag = reader.u8()
    if flag not in _BYTE_ORDER_FLAGS:
        msg = f"Not a package index: unknown byte order flag {flag}"
        raise FormatError(msg)
    reader.byte_order = byte_order = _BYTE_ORDER_FLAGS[flag]

    version, folder_count, file_count = reader.unpack("III")
    candidates = [f for f in FORMATS.values() if f.version == version]
    if not candidates:
        msg = f"Unsupported package version {version}"
        raise FormatError(msg)
    header_value = reader.u64() if candidates[0].has_header_value else 1
    names_size = reader.u32()
    base_path = _c_string(reader.read(BASE_PATH_SIZE))

    package_format = _detect_format(candidates, data, reader.position, byte_order)
    null = package_format.null_link
    folders = [
        FolderRecord(checksum, sibling, parent, name, child, file)
        for checksum, sibling, parent, _, name, child, file in reader.iter_unpack(
            package_format.folder_fields, folder_count
        )
    ]
    files = [
        FileRecord(*record, *(() if package_format.has_timestamps else (0,)))
        for record in reader.iter_unpack(package_format.file_fields, file_count)
    ]
    if package_format.has_closing_entry:
        _, *links = reader.unpack(package_format.folder_fields)
        if any(link != null for i, link in enumerate(links) if i != 2):
            msg = "The entry closing the tables is not empty"
            raise FormatError(msg)
    names = reader.read(names_size)
    extra_paths = _read_extra_paths(reader)

    folder_paths, file_paths = _resolve_tree(folders, files, names, null)
    return Package(
        format=package_format,
        byte_order=byte_order,
        base_path=base_path,
        folders=folder_paths[1:],
        files=[
            PackageFile(
                path=path,
                offset=file.offset,
                size=file.size,
                checksum=stored_checksum(file.data_checksum, byte_order),
                timestamp=file.timestamp if package_format.has_timestamps else None,
                flags=file.flags,
            )
            for path, file in zip(file_paths, files, strict=True)
        ],
        extra_paths=extra_paths,
        header_value=header_value,
    )


def _decode(raw: bytes) -> str:
    try:
        return raw.decode()
    except UnicodeDecodeError as error:
        msg = f"{raw!r} is not a valid name"
        raise FormatError(msg) from error


def _c_string(raw: bytes) -> str:
    return _decode(raw.split(b"\0", 1)[0])


def _detect_format(
    candidates: list[PackageFormat], data: bytes, tables: int, byte_order: ByteOrder
) -> PackageFormat:
    """Pick the layout under which the first folder reads as the root."""
    # Versions alone do not tell Alan Wake and its remaster apart, but only the
    # right layout reads the root folder with neither siblings nor a parent.
    matches = []
    for candidate in candidates:
        layout = packer(byte_order, candidate.folder_fields)
        if len(data) < tables + layout.size:
            continue
        _, sibling, parent, *_ = layout.unpack_from(data, tables)
        if sibling == parent == candidate.null_link:
            matches.append(candidate)
    if len(matches) != 1:
        msg = f"Unrecognised layout of a version {candidates[0].version} package"
        raise FormatError(msg)
    return matches[0]


def _read_extra_paths(reader: BinaryReader) -> list[str]:
    if not reader.remaining:
        return []
    paths = []
    for _ in range(reader.u32()):
        paths.append(_decode(reader.read(reader.u32())))
    if reader.remaining:
        msg = f"{reader.remaining} unexpected bytes at the end of the index"
        raise FormatError(msg)
    return paths


def _resolve_tree(
    folders: list[FolderRecord], files: list[FileRecord], names: bytes, null: int
) -> tuple[list[PackagePath], list[PackagePath]]:
    """Walk the tree from the root as the engine does and return entry paths."""

    def name_of(offset: int, checksum: int) -> str:
        end = names.find(b"\0", offset)
        if offset >= len(names) or end < 0:
            msg = f"Name offset {offset} is outside the names block"
            raise FormatError(msg)
        name = _decode(names[offset:end])
        if name_checksum(name) != checksum:
            msg = f"Checksum mismatch for the name {name!r}; the package is corrupted"
            raise FormatError(msg)
        return name

    if not folders or folders[0].name_offset != null:
        msg = "The package has no root folder"
        raise FormatError(msg)
    folder_paths: list[PackagePath | None] = [None] * len(folders)
    file_paths: list[PackagePath | None] = [None] * len(files)
    folder_paths[0] = ()
    pending = [0]
    while pending:
        parent = pending.pop()
        parent_path = folder_paths[parent]
        assert parent_path is not None
        child = folders[parent].first_child
        while child != null:
            entry = _linked(folders, child, parent, folder_paths)
            folder_paths[child] = (
                *parent_path,
                name_of(entry.name_offset, entry.checksum),
            )
            pending.append(child)
            child = entry.next_sibling
        index = folders[parent].first_file
        while index != null:
            file = _linked(files, index, parent, file_paths)
            file_paths[index] = (*parent_path, name_of(file.name_offset, file.checksum))
            index = file.next_sibling

    if None in folder_paths or None in file_paths:
        msg = "Some entries cannot be reached from the root folder"
        raise FormatError(msg)
    return cast(list[PackagePath], folder_paths), cast(list[PackagePath], file_paths)


def _linked[Entry: (FolderRecord, FileRecord)](
    entries: list[Entry], index: int, parent: int, paths: list[PackagePath | None]
) -> Entry:
    if index >= len(entries) or paths[index] is not None:
        msg = f"Broken link to entry {index}"
        raise FormatError(msg)
    entry = entries[index]
    if entry.parent != parent:
        msg = f"Entry {index} is linked from folder {parent}, not from {entry.parent}"
        raise FormatError(msg)
    return entry
