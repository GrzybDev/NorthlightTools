from typing import BinaryIO

from northlighttools.rmdp.dataclasses.FolderEntry import FolderEntry


def read_name(f: BinaryIO, size: int, offset: int) -> str:
    start_pos = f.tell()
    f.seek(-size + offset, 2)

    result = ""

    while (char := f.read(1)) != b"\0":
        result += char.decode("utf-8")

    f.seek(start_pos)
    return result


def get_parent_folder_path(folders: list[FolderEntry], folder_id: int) -> list[str]:
    entry = folders[folder_id]
    path = [entry.name]

    while (
        entry.prev_folder_id != 0xFFFFFFFF
        and entry.prev_folder_id != 0xFFFFFFFFFFFFFFFF
    ):
        path.insert(0, folders[entry.prev_folder_id].name)
        entry = folders[entry.prev_folder_id]

    return path[1:]
