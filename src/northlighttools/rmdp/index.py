"""Reading and writing the index (.bin) of a Remedy package.

The index holds a header, a table of folders, a table of files, a block of
NUL-terminated names and, in some packages, a list of extra paths. Folders and
files form a tree through first-child and next-sibling links; the games' own
packages create entries in the order of their sorted paths, which this module
reproduces.
"""

import struct
from dataclasses import dataclass
from typing import cast

from northlighttools.binary import BinaryReader, BinaryWriter, ByteOrder, packer
from northlighttools.errors import FormatError
from northlighttools.rmdp.formats import FORMATS, PackageFormat
from northlighttools.rmdp.model import Package, PackageFile
from northlighttools.rmdp.names import (
    PackagePath,
    format_path,
    name_checksum,
    sort_key,
)

_BYTE_ORDER_FLAGS = {0: ByteOrder.LITTLE, 1: ByteOrder.BIG}
_BASE_PATH_SIZE = 128
# Positions of the fields patch_index rewrites among those of a file record.
_FILE_FLAGS, _FILE_OFFSET, _FILE_SIZE, _FILE_CHECKSUM, _FILE_TIMESTAMP = 3, 5, 6, 7, 8


@dataclass(slots=True)
class _Folder:
    checksum: int
    next_sibling: int
    parent: int
    name_offset: int
    first_child: int
    first_file: int


@dataclass(slots=True)
class _File:
    checksum: int
    next_sibling: int
    parent: int
    flags: int
    name_offset: int
    offset: int
    size: int
    data_checksum: int
    timestamp: int


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
    base_path = _c_string(reader.read(_BASE_PATH_SIZE))

    package_format = _detect_format(candidates, data, reader.position, byte_order)
    null = package_format.null_link
    folders = [
        _Folder(checksum, sibling, parent, name, child, file)
        for checksum, sibling, parent, _, name, child, file in reader.iter_unpack(
            package_format.folder_fields, folder_count
        )
    ]
    files = [
        _File(*record, *(() if package_format.has_timestamps else (0,)))
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
                checksum=_data_checksum(file.data_checksum, byte_order),
                timestamp=file.timestamp if package_format.has_timestamps else None,
                flags=file.flags,
            )
            for path, file in zip(file_paths, files, strict=True)
        ],
        extra_paths=extra_paths,
        header_value=header_value,
    )


def patch_index(original: bytes, files: list[PackageFile]) -> bytes:
    """Rewrite the file records of an index, keeping all its other bytes.

    The bytes kept include those the games' packers left uninitialized.

    Args:
        original: Contents of the index to patch.
        files: The index's own files, in its order, with their new flags, data positions,
            sizes, checksums and timestamps.
    """
    package = decode_index(original)
    if [file.path for file in files] != [file.path for file in package.files]:
        msg = "The files to patch in are not those of the index"
        raise ValueError(msg)
    package_format, byte_order = package.format, package.byte_order
    fields = [code for code in package_format.file_fields if code != "x"]
    offsets = _field_offsets(package_format.file_fields)
    header_size = 17 + _BASE_PATH_SIZE + (8 if package_format.has_header_value else 0)
    folder_size = packer(byte_order, package_format.folder_fields).size
    file_size = packer(byte_order, package_format.file_fields).size
    first_file = header_size + (len(package.folders) + 1) * folder_size

    patched = bytearray(original)
    for number, file in enumerate(files):
        values = {
            _FILE_FLAGS: file.flags,
            _FILE_OFFSET: file.offset,
            _FILE_SIZE: file.size,
            _FILE_CHECKSUM: _data_checksum(file.checksum, byte_order),
        }
        if package_format.has_timestamps:
            values[_FILE_TIMESTAMP] = file.timestamp or 0
        record = first_file + number * file_size
        for field, value in values.items():
            layout = packer(byte_order, fields[field])
            layout.pack_into(patched, record + offsets[field], value)
    return bytes(patched)


def _field_offsets(fields: str) -> list[int]:
    """Return where each field of a record starts, skipping padding."""
    offsets, position = [], 0
    for code in fields:
        if code != "x":
            offsets.append(position)
        position += struct.calcsize(code)
    return offsets


def encode_index(package: Package) -> bytes:
    """Build the index of a package, ordering its entries as the games do.

    Args:
        package: The package whose index to build.
    """
    package_format = package.format
    tree = _TreeBuilder(package_format.null_link)
    entries: list[tuple[bytes, PackagePath | PackageFile]] = [
        (sort_key(folder) + b"\\", folder) for folder in package.folders
    ]
    entries += [(sort_key(file.path), file) for file in package.files]
    entries.sort(key=lambda entry: entry[0])
    for _, entry in entries:
        if isinstance(entry, PackageFile):
            tree.add_file(entry)
        else:
            tree.add_folder(entry)

    writer = BinaryWriter(package.byte_order)
    writer.u8(0 if package.byte_order is ByteOrder.LITTLE else 1)
    writer.pack("III", package_format.version, len(tree.folders), len(tree.files))
    if package_format.has_header_value:
        writer.u64(package.header_value)
    writer.u32(len(tree.names))
    base_path = package.base_path.encode()
    if len(base_path) >= _BASE_PATH_SIZE:
        msg = f"The base path is longer than {_BASE_PATH_SIZE - 1} bytes"
        raise ValueError(msg)
    writer.write(base_path.ljust(_BASE_PATH_SIZE, b"\0"))
    for folder in tree.folders:
        writer.pack(
            package_format.folder_fields,
            folder.checksum,
            folder.next_sibling,
            folder.parent,
            0,
            folder.name_offset,
            folder.first_child,
            folder.first_file,
        )
    timestamps = package_format.has_timestamps
    for file in tree.files:
        values = [
            file.checksum,
            file.next_sibling,
            file.parent,
            file.flags,
            file.name_offset,
            file.offset,
            file.size,
            _data_checksum(file.data_checksum, package.byte_order),
        ]
        if timestamps:
            values.append(file.timestamp)
        writer.pack(package_format.file_fields, *values)
    if package_format.has_closing_entry:
        null = package_format.null_link
        writer.pack(package_format.folder_fields, 0, null, null, 0, null, null, null)
    writer.write(tree.names)
    if package.extra_paths:
        writer.u32(len(package.extra_paths))
        for path in package.extra_paths:
            raw = path.encode()
            writer.u32(len(raw))
            writer.write(raw)
    return writer.getvalue()


def _data_checksum(value: int, byte_order: ByteOrder) -> int:
    """Swap a data checksum between the package's byte order and its stored one."""
    # The engine stores data checksums little-endian even in big-endian packages.
    if byte_order is ByteOrder.LITTLE:
        return value
    return int.from_bytes(value.to_bytes(4, "big"), "little")


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
    folders: list[_Folder], files: list[_File], names: bytes, null: int
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


def _linked[Entry: (_Folder, _File)](
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


class _TreeBuilder:
    """Creates entries and their names in the order paths are added."""

    def __init__(self, null: int) -> None:
        self.null = null
        self.folders = [_Folder(name_checksum(""), null, null, null, null, null)]
        self.files: list[_File] = []
        self.names = bytearray()
        self._folder_indices: dict[PackagePath, int] = {(): 0}
        self._taken_keys: dict[bytes, PackagePath] = {}
        self._last_child: dict[int, int] = {}
        self._last_file: dict[int, int] = {}

    def add_folder(self, path: PackagePath) -> int:
        if (index := self._folder_indices.get(path)) is not None:
            return index
        self._take_key(sort_key(path) + b"\\", path)
        parent = self.add_folder(path[:-1])
        index = len(self.folders)
        offset, checksum = self._add_name(path[-1])
        self.folders.append(_Folder(checksum, self.null, parent, offset, self.null, self.null))
        if (previous := self._last_child.get(parent)) is None:
            self.folders[parent].first_child = index
        else:
            self.folders[previous].next_sibling = index
        self._last_child[parent] = index
        self._folder_indices[path] = index
        return index

    def add_file(self, file: PackageFile) -> None:
        self._take_key(sort_key(file.path), file.path)
        parent = self.add_folder(file.path[:-1])
        index = len(self.files)
        offset, checksum = self._add_name(file.name)
        self.files.append(
            _File(
                checksum,
                self.null,
                parent,
                file.flags,
                offset,
                file.offset,
                file.size,
                file.checksum,
                file.timestamp or 0,
            )
        )
        if (previous := self._last_file.get(parent)) is None:
            self.folders[parent].first_file = index
        else:
            self.files[previous].next_sibling = index
        self._last_file[parent] = index

    def _take_key(self, key: bytes, path: PackagePath) -> None:
        taken = self._taken_keys.setdefault(key, path)
        if taken is path:
            return
        # The engine finds entries by their lowercase names.
        if taken == path:
            reason = "is listed twice"
        else:
            reason = f"differs from {format_path(taken)} only in letter case"
        msg = f"{format_path(path)} {reason}"
        raise ValueError(msg)

    def _add_name(self, name: str) -> tuple[int, int]:
        if not name or "\0" in name:
            msg = f"Invalid entry name {name!r}"
            raise ValueError(msg)
        offset = len(self.names)
        self.names += name.encode() + b"\0"
        return offset, name_checksum(name)
