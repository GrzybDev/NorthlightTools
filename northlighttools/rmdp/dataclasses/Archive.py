from dataclasses import dataclass

from northlighttools.rmdp.dataclasses.FileEntry import FileEntry
from northlighttools.rmdp.dataclasses.FolderEntry import FolderEntry
from northlighttools.rmdp.enums.ArchiveEndianness import ArchiveEndianness
from northlighttools.rmdp.enums.ArchiveVersion import ArchiveVersion


@dataclass
class Archive:
    endianness: ArchiveEndianness = None
    version: ArchiveVersion = None

    folders: list[FolderEntry] = None
    files: list[FileEntry] = None
