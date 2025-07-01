import os
import zlib
from datetime import datetime, timezone
from io import BufferedReader, BufferedWriter
from pathlib import Path
from typing import Literal

from northlighttools.rmdp.constants import CHUNK_SIZE
from northlighttools.rmdp.dataclasses.entry_file import FileEntry
from northlighttools.rmdp.dataclasses.entry_folder import FolderEntry
from northlighttools.rmdp.enumerators.endianness import Endianness
from northlighttools.rmdp.enumerators.package_version import PackageVersion
from northlighttools.rmdp.helpers import filetime_to_dt


class Package:

    __endianness: Endianness = Endianness.LITTLE
    __version: PackageVersion = PackageVersion.QUANTUM_BREAK

    @property
    def endianness(self) -> Endianness:
        return self.__endianness

    @property
    def version(self) -> PackageVersion:
        return self.__version

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
    def __readsize(self) -> int:
        return 4 if self.__version.value < PackageVersion.QUANTUM_BREAK.value else 8

    @property
    def __null_id(self) -> int:
        return (
            0xFFFFFFFFFFFFFFFF
            if int(self.__version) >= int(PackageVersion.QUANTUM_BREAK)
            else 0xFFFFFFFF
        )

    def __init__(self, header_path: Path | None = None):
        self.__name_block_len = 0

        self.__folders: list[FolderEntry] = []
        self.__files: list[FileEntry] = []
        self.__unknown_data = {}

        if header_path:
            self.__read_header(header_path)

    def __read_header(self, header_path: Path):
        with header_path.open("rb") as f:
            self.__endianness = Endianness(self.__read_int(f, 1))
            self.__version = PackageVersion(self.__read_int(f, 4))

            num_folders = self.__read_int(f, 4)
            num_files = self.__read_int(f, 4)

            if self.__version == PackageVersion.ALAN_WAKE:
                self.__name_block_len = self.__read_int(f, 4, override_byteorder="big")
                self.__unknown_data["header_data"] = f.read(0x80)
            else:
                self.__unknown_data["header_value_1"] = self.__read_int(f, 8)
                self.__name_block_len = self.__read_int(
                    f, 4, override_byteorder="little"
                )
                self.__unknown_data["header_data"] = f.read(0x80)

            self.__folders = [self.__read_folder_entry(f) for _ in range(num_folders)]
            self.__files = [self.__read_file_entry(f) for _ in range(num_files)]

    def __read_int(
        self, f, size: int, override_byteorder: Literal["little", "big"] | None = None
    ) -> int:
        return int.from_bytes(
            f.read(size), byteorder=override_byteorder or self.__endianness.name.lower()  # type: ignore
        )

    def __read_string(self, f, offset: int) -> str:
        if offset == self.__null_id:
            return ""

        start_pos = f.tell()
        f.seek(-self.__name_block_len + offset, os.SEEK_END)

        # Read null-terminated string
        result = ""

        while (char := f.read(1)) != b"\x00":
            result += char.decode("utf-8")

        f.seek(start_pos)  # Reset file pointer to original position
        return result

    def __read_folder_entry(self, f) -> FolderEntry:
        expected_checksum = self.__read_int(f, 4)

        next_folder_id = self.__read_int(f, self.__readsize)
        parent_folder_id = self.__read_int(f, self.__readsize)

        flags = self.__read_int(f, 4)

        name_offset = self.__read_int(f, self.__readsize)
        next_parent_folder_id = self.__read_int(f, self.__readsize)
        next_file_id = self.__read_int(f, self.__readsize)

        folder_name = self.__read_string(f, name_offset)
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
        file_checksum = self.__read_int(f, 4, override_byteorder="little")
        file_name = self.__read_string(f, name_offset)
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

    def extract(self, reader: BufferedReader, file: FileEntry, output_path: Path):
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

    def get_folder_entry(self, path: Path) -> FolderEntry:
        if path == Path("."):
            # If the path is just a single part, return the root folder
            return self.__folders[0]

        for folder in self.__folders:
            # Iterate through folders to find the one matching the path
            folder_path = self.get_folder_path(folder)

            if folder_path == path:
                return folder
        else:
            raise ValueError(f"Folder not found for path: {path}")

    def get_child_files(self, entry: FolderEntry) -> list[FileEntry]:
        # Find all files that are children of the specified folder entry
        result = []

        for file in self.__files:
            if file.parent_folder_id == self.__folders.index(entry):
                result.append(file)

        return result

    def add_file(self, writer: BufferedWriter, real_path: Path, pkg_path: Path):
        parent_folder = self.get_folder_entry(pkg_path.parent)

        child_files = self.get_child_files(parent_folder)
        last_child_file = child_files[-1] if child_files else None

        if last_child_file:
            last_child_file.next_file_id = len(self.__files)
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
