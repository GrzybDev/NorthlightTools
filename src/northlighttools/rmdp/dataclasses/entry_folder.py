from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class FolderEntry:
    name: str
    checksum: int
    flags: int
    name_offset: int
    next_file_id: int
    next_folder_id: int
    next_parent_folder_id: int
    parent_folder_id: int
