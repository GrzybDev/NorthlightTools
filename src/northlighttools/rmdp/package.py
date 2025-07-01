import os
import zlib
from pathlib import Path
from typing import Literal

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
