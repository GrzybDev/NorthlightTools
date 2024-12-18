import zlib
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, track

from northlighttools.rmdp.dataclasses.Archive import Archive
from northlighttools.rmdp.dataclasses.FileEntry import FileEntry
from northlighttools.rmdp.dataclasses.FolderEntry import FolderEntry
from northlighttools.rmdp.enums.ArchiveEndianness import ArchiveEndianness
from northlighttools.rmdp.enums.ArchiveVersion import ArchiveVersion
from northlighttools.rmdp.helpers import (
    CHUNK_SIZE,
    dt_to_filetime,
    get_parent_folder,
    get_parent_folder_path,
)


def index_folder(
    archive: Archive, input_dir: Path
) -> tuple[list[FolderEntry], list[FileEntry]]:
    folders = []
    files = []
    names = []
    names_size = 0

    null_id = (
        0xFFFFFFFFFFFFFFFF
        if archive.version.value >= ArchiveVersion.QUANTUM_BREAK.value
        else 0xFFFFFFFF
    )

    current_folder = FolderEntry(
        name="",
        checksum=0,
        name_offset=null_id,
        next_file_id=null_id,
        next_folder_id=null_id,
        next_parent_folder_id=1,
        parent_folder_id=null_id,
    )

    folders.append(current_folder)

    previous_folder_id = 0
    prev_folder_entry = None
    prev_file_entry = None

    for path in sorted(input_dir.rglob("*")):
        relative_path = path.relative_to(input_dir)
        parent_folder = get_parent_folder(folders, relative_path)

        if path.is_dir():
            if prev_file_entry:
                prev_file_entry.next_file_id = null_id

            if len(folders) == 1:
                folder_name = relative_path.name.replace("_", ":")
            else:
                folder_name = relative_path.name

            current_folder = FolderEntry(
                name=folder_name,
                checksum=zlib.crc32(folder_name.lower().encode()),
                name_offset=null_id,
                next_file_id=null_id,
                next_folder_id=null_id,
                next_parent_folder_id=null_id,
                parent_folder_id=null_id,
            )

            names.append(folder_name)
            current_folder.name_offset = names_size
            names_size += len(current_folder.name) + 1

            current_folder.parent_folder_id = folders.index(parent_folder)
            current_folder.next_parent_folder_id = len(folders) + 1

            if (
                prev_folder_entry
                and previous_folder_id >= current_folder.parent_folder_id
            ):
                folders[folders.index(prev_folder_entry)].next_parent_folder_id = (
                    null_id
                )

                root_folder = folders[current_folder.parent_folder_id + 1]

                while root_folder.next_folder_id != null_id:
                    root_folder = folders[root_folder.next_folder_id]

                if root_folder.next_folder_id == null_id:
                    root_folder.next_folder_id = len(folders)

            previous_folder_id = current_folder.parent_folder_id

            folders.append(current_folder)
            prev_folder_entry = current_folder
        else:
            file = FileEntry(
                name=relative_path.name,
                name_checksum=zlib.crc32(relative_path.name.lower().encode()),
                data_checksum=0,
                name_offset=null_id,
                parent_folder_id=folders.index(parent_folder),
                next_file_id=len(files) + 1,
                flags=0,
                size=path.stat().st_size,
                offset=null_id,
                writetime=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            )

            names.append(relative_path.name)
            file.name_offset = names_size
            names_size += len(file.name) + 1

            if (
                prev_file_entry
                and prev_file_entry.parent_folder_id != file.parent_folder_id
            ):
                prev_file_entry.next_file_id = null_id

            if folders[file.parent_folder_id].next_file_id == null_id:
                folders[file.parent_folder_id].next_file_id = len(files)

            files.append(file)
            prev_file_entry = file

    folders[-1].next_parent_folder_id = null_id
    files[-1].next_file_id = null_id

    archive.folders = folders
    archive.files = files

    return names


def rmdp_pack(archive: Archive, input_dir: Path, output_file: Path):
    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        progress.add_task("Indexing input folder...")

        names = index_folder(archive, input_dir)
        names_size = sum(len(name) + 1 for name in names)

    with open(output_file.with_suffix(".rmdp"), "wb") as rmdp:
        for file in track(archive.files, description="Packing files..."):
            file.offset = rmdp.tell()

            file_path = get_parent_folder_path(
                archive.folders, file.parent_folder_id
            ) + [file.name]
            file_path[0] = file_path[0].replace(":", "_")

            with open(input_dir / Path(*file_path), "rb") as input:
                data_checksum = 0

                while data := input.read(CHUNK_SIZE):
                    data_checksum = zlib.crc32(data, data_checksum)
                    rmdp.write(data)

                file.data_checksum = data_checksum

    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        progress.add_task("Finalizing...")

        with open(output_file.with_suffix(".bin"), "wb") as f:
            byteorder = (
                "little" if archive.endianness == ArchiveEndianness.LITTLE else "big"
            )
            write_size = (
                8 if archive.version.value >= ArchiveVersion.QUANTUM_BREAK.value else 4
            )

            f.write(archive.endianness.value.to_bytes(1))
            f.write(
                archive.version.value.to_bytes(4, byteorder=byteorder, signed=False)
            )
            f.write(len(archive.folders).to_bytes(4, byteorder=byteorder, signed=False))
            f.write(len(archive.files).to_bytes(4, byteorder=byteorder, signed=False))

            if archive.version.value != ArchiveVersion.ALAN_WAKE.value:
                f.write(int(1).to_bytes(8, byteorder=byteorder, signed=False))

            f.write(names_size.to_bytes(4, byteorder=byteorder, signed=False))
            f.write(b"d:\\data")
            f.write(b"\0" * 121)

            for folder in archive.folders:
                f.write(folder.checksum.to_bytes(4, byteorder=byteorder, signed=False))
                f.write(
                    folder.next_folder_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )
                f.write(
                    folder.parent_folder_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )

                f.write(b"\0" * 4)

                f.write(
                    folder.name_offset.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )

                f.write(
                    folder.next_parent_folder_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )
                f.write(
                    folder.next_file_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )

            for file in archive.files:
                f.write(
                    file.name_checksum.to_bytes(4, byteorder=byteorder, signed=False)
                )
                f.write(
                    file.next_file_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )
                f.write(
                    file.parent_folder_id.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )
                f.write(file.flags.to_bytes(4, byteorder=byteorder, signed=False))
                f.write(
                    file.name_offset.to_bytes(
                        write_size, byteorder=byteorder, signed=False
                    )
                )
                f.write(file.offset.to_bytes(8, byteorder=byteorder, signed=False))
                f.write(file.size.to_bytes(8, byteorder=byteorder, signed=False))
                f.write(
                    file.data_checksum.to_bytes(4, byteorder=byteorder, signed=False)
                )

                if (
                    archive.version.value
                    >= ArchiveVersion.ALAN_WAKE_AMERICAN_NIGHTMARE.value
                ):
                    timestamp = dt_to_filetime(file.writetime)
                    f.write(timestamp.to_bytes(8, byteorder=byteorder, signed=False))

            f.write(b"\0" * 4)
            f.write(b"\xFF" * write_size)
            f.write(b"\xFF" * write_size)
            f.write(b"ctor")
            f.write(b"\xFF" * write_size)
            f.write(b"\xFF" * write_size)
            f.write(b"\xFF" * write_size)

            for name in names:
                f.write(name.encode() + b"\0")
