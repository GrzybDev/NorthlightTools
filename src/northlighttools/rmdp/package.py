import os
import zlib
from datetime import datetime, timezone
from io import BufferedReader, BufferedWriter
from pathlib import Path

from northlighttools.rmdp.constants import CHUNK_SIZE
from northlighttools.rmdp.dataclasses.entry_file import FileEntry
from northlighttools.rmdp.dataclasses.entry_folder import FolderEntry
from northlighttools.rmdp.enumerators.endianness import Endianness
from northlighttools.rmdp.enumerators.package_version import PackageVersion
from northlighttools.rmdp.helpers import (
    dt_to_filetime,
    filetime_to_dt,
    get_endianness,
    get_package_version,
    read_name,
)


class Package:

    @property
    def endianness(self) -> str:
        return self.__endianness.name.capitalize()

    @endianness.setter
    def endianness(self, value: Endianness):
        self.__endianness = value

    @property
    def version(self) -> PackageVersion:
        return self.__version

    @version.setter
    def version(self, value: PackageVersion):
        self.__version = value

    @property
    def __byteorder(self) -> str:
        return self.__endianness.value

    @property
    def __readsize(self) -> int:
        return 4 if int(self.__version) < int(PackageVersion.QUANTUM_BREAK) else 8

    @property
    def folders(self) -> list[FolderEntry]:
        return self.__folders

    @property
    def files(self) -> list[FileEntry]:
        return self.__files

    @property
    def unknown_data(self) -> dict[str, bytes | int]:
        return self.__unknown_data

    @property
    def __null_id(self) -> int:
        return (
            0xFFFFFFFFFFFFFFFF
            if int(self.__version) >= int(PackageVersion.QUANTUM_BREAK)
            else 0xFFFFFFFF
        )

    def __init__(self, header_path: Path | None = None):
        if header_path:
            self.__read_header(header_path)

    def __read_int(self, f, size: int, byteorder: str | None = None) -> int:
        return int.from_bytes(f.read(size), byteorder=byteorder or self.__byteorder)  # type: ignore

    def __write_int(self, f, value: int, size: int, byteorder: str | None = None):
        f.write(value.to_bytes(size, byteorder=byteorder or self.__byteorder))  # type: ignore

    def __read_folder_entry(self, f) -> FolderEntry:
        expected_checksum = self.__read_int(f, 4)

        next_folder_id = self.__read_int(f, self.__readsize)
        parent_folder_id = self.__read_int(f, self.__readsize)

        flags = self.__read_int(f, 4)

        name_offset = self.__read_int(f, self.__readsize)
        next_parent_folder_id = self.__read_int(f, self.__readsize)
        next_file_id = self.__read_int(f, self.__readsize)

        folder_name = read_name(f, self.__name_block_len, name_offset)
        actual_checksum = zlib.crc32(folder_name.lower().encode())

        if actual_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for folder name '{folder_name}': "
                f"expected {expected_checksum}, got {actual_checksum}. Package may be corrupted."
            )

        return FolderEntry(
            name=folder_name,
            checksum=actual_checksum,
            flags=flags,
            name_offset=name_offset,
            next_file_id=next_file_id,
            next_folder_id=next_folder_id,
            next_parent_folder_id=next_parent_folder_id,
            parent_folder_id=parent_folder_id,
        )

    def __read_file_entry(self, f):
        expected_checksum = self.__read_int(f, 4)

        next_file_id = self.__read_int(f, self.__readsize)
        parent_folder_id = self.__read_int(f, self.__readsize)
        file_flags = self.__read_int(f, 4)
        name_offset = self.__read_int(f, self.__readsize)

        file_offset = self.__read_int(f, 8)
        file_size = self.__read_int(f, 8)
        file_checksum = self.__read_int(f, 4, byteorder="little")
        file_name = read_name(f, self.__name_block_len, name_offset)
        actual_checksum = zlib.crc32(file_name.lower().encode())

        if actual_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for file name '{file_name}': "
                f"expected {expected_checksum}, got {actual_checksum}. Package may be corrupted."
            )

        write_time = None

        if self.__version.value >= PackageVersion.ALAN_WAKE_AMERICAN_NIGHTMARE.value:
            filetime = self.__read_int(f, 8)
            write_time = filetime_to_dt(filetime)

        return FileEntry(
            name=file_name,
            parent_folder_id=parent_folder_id,
            next_file_id=next_file_id,
            name_checksum=actual_checksum,
            data_checksum=file_checksum,
            name_offset=name_offset,
            flags=file_flags,
            size=file_size,
            offset=file_offset,
            write_time=write_time,
        )

    def __read_header(self, header_path: Path):
        with header_path.open("rb") as f:
            self.__endianness = get_endianness(int.from_bytes(f.read(1)))
            self.__version = get_package_version(self.__read_int(f, 4))

            num_folders = self.__read_int(f, 4)
            num_files = self.__read_int(f, 4)

            self.__unknown_data = {}

            if self.__version == PackageVersion.ALAN_WAKE:
                self.__name_block_len = self.__read_int(f, 4, byteorder="big")
                self.__unknown_data["header_data"] = f.read(0x80)
            else:
                self.__unknown_data["header_value_1"] = self.__read_int(f, 8)
                self.__name_block_len = self.__read_int(f, 4, byteorder="little")
                self.__unknown_data["header_data"] = f.read(0x80)

            self.__folders = [self.__read_folder_entry(f) for _ in range(num_folders)]
            self.__files = [self.__read_file_entry(f) for _ in range(num_files)]

    def get_folder_path(self, folder: FolderEntry) -> Path:
        # Navigate up the folder hierarchy to get the full path
        path_parts = []

        while folder.parent_folder_id != self.__null_id:
            folder_name = folder.name

            if folder.parent_folder_id == 0:
                folder_name = folder.name.replace(
                    ":", "_"
                )  # Replace ':' with '_' for compatibility

            path_parts.append(folder_name)
            folder = self.folders[folder.parent_folder_id]

        path_parts.append(folder.name)
        return Path(*reversed(path_parts))

    def get_file_path(self, file: FileEntry) -> Path:
        parent_folder = self.folders[file.parent_folder_id]
        return Path(self.get_folder_path(parent_folder), file.name)

    def extract_file(self, reader: BufferedReader, file: FileEntry, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        reader.seek(file.offset)

        with output_path.open("wb") as out_file:
            actual_checksum = 0
            remaining_bytes = file.size

            while remaining_bytes > 0:
                chunk_size = min(remaining_bytes, CHUNK_SIZE)
                chunk = reader.read(chunk_size)

                if not chunk:
                    raise ValueError(
                        f"Unexpected end of file while reading {file.name}. "
                        f"Expected {file.size} bytes, but got {file.size - remaining_bytes + chunk_size} bytes."
                    )

                out_file.write(chunk)

                actual_checksum = zlib.crc32(chunk, actual_checksum)
                remaining_bytes -= len(chunk)

        if file.write_time:
            ts = file.write_time.timestamp()
            os.utime(output_path, (ts, ts))

    def __create_root_folder(self):
        """Create a root folder entry with default values."""
        self.__folders = []
        self.__files = []

        self.__folder_path_map = {}
        self.__folder_children_map = {}
        self.__file_children_map = {}

        root_folder = FolderEntry(
            name="",
            checksum=0,
            flags=0,
            name_offset=self.__null_id,
            next_file_id=self.__null_id,
            next_folder_id=self.__null_id,
            next_parent_folder_id=self.__null_id,
            parent_folder_id=self.__null_id,
        )

        self.__folders.append(root_folder)
        self.__folder_path_map[Path(".")] = root_folder
        self.__folder_children_map[root_folder] = []

    def add_folder(self, path: Path):
        folder_name = path.name

        if path.parent == Path("."):
            # If the parent is empty, create the root folder
            self.__create_root_folder()

            folder_name = (
                folder_name.replace("_", ":")
                if len(self.__folders) == 1
                else folder_name
            )

        parent_folder = self.__folder_path_map[path.parent]
        child_folders = self.__folder_children_map.get(parent_folder, [])

        if child_folders:
            child_folders[-1].next_folder_id = len(self.__folders)
        else:
            parent_folder.next_parent_folder_id = len(self.__folders)

        entry = FolderEntry(
            name=folder_name,
            checksum=zlib.crc32(folder_name.lower().encode()),
            flags=0,
            name_offset=self.__null_id,
            next_file_id=self.__null_id,
            next_folder_id=self.__null_id,
            next_parent_folder_id=self.__null_id,
            parent_folder_id=self.__folders.index(parent_folder),
        )

        self.__folders.append(entry)
        self.__folder_path_map[path] = entry
        self.__folder_children_map.setdefault(parent_folder, []).append(entry)

    def add_file(self, writer: BufferedWriter, real_path: Path, pkg_path: Path):
        parent_folder = self.__folder_path_map[pkg_path.parent]
        child_files = self.__file_children_map.get(parent_folder, [])

        if child_files:
            child_files[-1].next_file_id = len(self.__files)
        else:
            parent_folder.next_file_id = len(self.__files)

        file_offset = writer.tell()
        file_size = real_path.stat().st_size
        file_write_time = datetime.fromtimestamp(
            real_path.stat().st_mtime, tz=timezone.utc
        )

        data_checksum = 0

        with real_path.open("rb") as f:
            remaining_bytes = file_size

            while remaining_bytes > 0:
                chunk_size = min(remaining_bytes, CHUNK_SIZE)
                chunk = f.read(chunk_size)

                if not chunk:
                    raise ValueError(
                        f"Unexpected end of file while reading {pkg_path.name}. "
                        f"Expected {file_size} bytes, but got {file_size - remaining_bytes + chunk_size} bytes."
                    )

                writer.write(chunk)

                data_checksum = zlib.crc32(chunk, data_checksum)
                remaining_bytes -= len(chunk)

        entry = FileEntry(
            name=pkg_path.name,
            parent_folder_id=self.__folders.index(parent_folder),
            next_file_id=self.__null_id,
            name_checksum=zlib.crc32(pkg_path.name.lower().encode()),
            data_checksum=data_checksum,
            name_offset=self.__null_id,
            flags=0,
            size=file_size,
            offset=file_offset,
            write_time=file_write_time,
        )

        self.__files.append(entry)
        self.__file_children_map.setdefault(parent_folder, []).append(entry)

    def __build_names_block(self) -> bytes:
        names_block = b""

        for folder in self.__folders:
            if not folder.name:
                # Skip empty folder names
                continue

            folder.name_offset = len(names_block)
            names_block += folder.name.encode() + b"\x00"

            files = self.__file_children_map.get(folder, [])
            if not files:
                # If there are no files in this folder, continue to the next folder
                continue

            for file in files:
                if not file.name:
                    # Skip empty file names
                    continue

                file.name_offset = len(names_block)
                names_block += file.name.encode() + b"\x00"

        return names_block

    def __write_folder_entry(self, writer: BufferedWriter, folder: FolderEntry):
        self.__write_int(writer, folder.checksum, 4)
        self.__write_int(writer, folder.next_folder_id, self.__readsize)
        self.__write_int(writer, folder.parent_folder_id, self.__readsize)
        self.__write_int(writer, folder.flags, 4)
        self.__write_int(writer, folder.name_offset, self.__readsize)
        self.__write_int(writer, folder.next_parent_folder_id, self.__readsize)
        self.__write_int(writer, folder.next_file_id, self.__readsize)

    def __write_file_entry(self, writer: BufferedWriter, file: FileEntry):
        self.__write_int(writer, file.name_checksum, 4)
        self.__write_int(writer, file.next_file_id, self.__readsize)
        self.__write_int(writer, file.parent_folder_id, self.__readsize)
        self.__write_int(writer, file.flags, 4)
        self.__write_int(writer, file.name_offset, self.__readsize)
        self.__write_int(writer, file.offset, 8)
        self.__write_int(writer, file.size, 8)
        self.__write_int(writer, file.data_checksum, 4)

        if self.__version.value >= PackageVersion.ALAN_WAKE_AMERICAN_NIGHTMARE.value:
            ts = file.write_time if file.write_time else datetime.now()
            filetime = dt_to_filetime(ts)

            self.__write_int(writer, filetime, 8)

    def build_header(self, writer: BufferedWriter):
        names_block = self.__build_names_block()

        writer.write(list(Endianness).index(self.__endianness).to_bytes(1))
        self.__write_int(writer, int(self.__version), 4)
        self.__write_int(writer, len(self.__folders), 4)
        self.__write_int(writer, len(self.__files), 4)

        if self.__version != PackageVersion.ALAN_WAKE:
            self.__write_int(writer, 1, 8)

        self.__write_int(writer, len(names_block), 4)

        writer.write(b"d:\\data")
        writer.write(b"\0" * 121)

        for folder in self.__folders:
            self.__write_folder_entry(writer, folder)

        for file in self.__files:
            self.__write_file_entry(writer, file)

        self.__write_int(writer, 0, 4)
        writer.write(b"\xff" * (self.__readsize * 2))
        writer.write(b"ctor")
        writer.write(b"\xff" * (self.__readsize * 3))
        writer.write(names_block)
