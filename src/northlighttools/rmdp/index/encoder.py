"""Building a package index as the games do, or patching the file records of one."""

import struct

from northlighttools.binary import BinaryWriter, ByteOrder, packer
from northlighttools.rmdp.index.decoder import decode_index
from northlighttools.rmdp.index.records import (
    BASE_PATH_SIZE,
    FileRecord,
    FolderRecord,
    stored_checksum,
)
from northlighttools.rmdp.model import Package, PackageFile
from northlighttools.rmdp.names import (
    PackagePath,
    format_path,
    name_checksum,
    sort_key,
)

# Positions of the fields patch_index rewrites among those of a file record.
_FILE_FLAGS, _FILE_OFFSET, _FILE_SIZE, _FILE_CHECKSUM, _FILE_TIMESTAMP = 3, 5, 6, 7, 8


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
    header_size = 17 + BASE_PATH_SIZE + (8 if package_format.has_header_value else 0)
    folder_size = packer(byte_order, package_format.folder_fields).size
    file_size = packer(byte_order, package_format.file_fields).size
    first_file = header_size + (len(package.folders) + 1) * folder_size

    patched = bytearray(original)
    for number, file in enumerate(files):
        values = {
            _FILE_FLAGS: file.flags,
            _FILE_OFFSET: file.offset,
            _FILE_SIZE: file.size,
            _FILE_CHECKSUM: stored_checksum(file.checksum, byte_order),
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
    if len(base_path) >= BASE_PATH_SIZE:
        msg = f"The base path is longer than {BASE_PATH_SIZE - 1} bytes"
        raise ValueError(msg)
    writer.write(base_path.ljust(BASE_PATH_SIZE, b"\0"))
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
            stored_checksum(file.data_checksum, package.byte_order),
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


class _TreeBuilder:
    """Creates entries and their names in the order paths are added."""

    def __init__(self, null: int) -> None:
        self.null = null
        self.folders = [FolderRecord(name_checksum(""), null, null, null, null, null)]
        self.files: list[FileRecord] = []
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
        self.folders.append(FolderRecord(checksum, self.null, parent, offset, self.null, self.null))
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
            FileRecord(
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
