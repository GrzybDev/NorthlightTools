from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileEntry:
    name: str
    parent_folder_id: int
    next_file_id: int
    name_checksum: int
    data_checksum: int
    name_offset: int
    flags: int
    size: int
    offset: int
    write_time: datetime | None = None
