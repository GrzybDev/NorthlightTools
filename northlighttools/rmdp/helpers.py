from calendar import timegm
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from northlighttools.rmdp.dataclasses.FolderEntry import FolderEntry

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS = 10000000


def filetime_to_dt(ft: int) -> datetime:
    # Get seconds and remainder in terms of Unix epoch
    s, ns100 = divmod(ft - EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
    # Convert to datetime object, with remainder as microseconds.
    return datetime.fromtimestamp(s, tz=timezone.utc).replace(microsecond=(ns100 // 10))


def dt_to_filetime(dt: datetime) -> int:
    filetime = EPOCH_AS_FILETIME + (timegm(dt.timetuple()) * HUNDREDS_OF_NANOSECONDS)
    return filetime + (dt.microsecond * 10)


def read_name(f: BinaryIO, size: int, offset: int) -> str:
    start_pos = f.tell()
    f.seek(-size + offset, 2)

    result = ""

    while (char := f.read(1)) != b"\0":
        result += char.decode("utf-8")

    f.seek(start_pos)
    return result


def get_parent_folder(folders: list[FolderEntry], relative_path: Path) -> FolderEntry:
    parent_folder = None

    for folder in reversed(folders):
        folder_id = folders.index(folder)
        folder_path = get_parent_folder_path(folders, folder_id)

        if folder_path:
            folder_path[0] = folder_path[0].replace(":", "_")

        if folder_path == list(relative_path.parts[:-1]):
            parent_folder = folder
            break

    return parent_folder


def get_parent_folder_path(folders: list[FolderEntry], folder_id: int) -> list[str]:
    entry = folders[folder_id]
    path = [entry.name]

    while (
        entry.parent_folder_id != 0xFFFFFFFF
        and entry.parent_folder_id != 0xFFFFFFFFFFFFFFFF
    ):
        entry = folders[entry.parent_folder_id]
        path.insert(0, entry.name)

    return path[1:]
