import os
import zlib
from io import BufferedReader
from pathlib import Path

from northlighttools.rmdp.constants import CHUNK_SIZE
from northlighttools.rmdp.dataclasses.entry_file import FileEntry
from northlighttools.rmdp.dataclasses.entry_folder import FolderEntry
from northlighttools.rmdp.enumerators.package_version import PackageVersion
from northlighttools.rmdp.helpers import (
    filetime_to_dt,
    get_endianness,
    get_package_version,
    read_name,
)


class Package:

    @property
    def endianness(self) -> str:
        return self.__endianness.name.capitalize()

    @property
    def version(self) -> PackageVersion:
        return self.__version

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
