import zlib
from datetime import datetime
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, track

from northlighttools.rmdp.dataclasses.Archive import Archive
from northlighttools.rmdp.dataclasses.FileEntry import FileEntry
from northlighttools.rmdp.dataclasses.FolderEntry import FolderEntry
from northlighttools.rmdp.enums.ArchiveEndianness import ArchiveEndianness
from northlighttools.rmdp.enums.ArchiveVersion import ArchiveVersion
from northlighttools.rmdp.helpers import get_parent_folder_path, read_name


def read_metadata(bin_file: Path) -> Archive:
    result = Archive()

    with bin_file.open("rb") as f:
        result.endianness = ArchiveEndianness(int.from_bytes(f.read(1)))
        byteorder = "little" if result.endianness == ArchiveEndianness.LITTLE else "big"

        result.version = ArchiveVersion(
            int.from_bytes(f.read(4), byteorder=byteorder, signed=False)
        )

        num_folders = int.from_bytes(f.read(4), byteorder=byteorder, signed=False)
        num_files = int.from_bytes(f.read(4), byteorder=byteorder, signed=False)

        match result.version:
            case ArchiveVersion.ALAN_WAKE:
                name_size = int.from_bytes(f.read(4), byteorder="big", signed=False)
                f.seek(128, 1)
            case _:
                f.seek(8, 1)
                name_size = int.from_bytes(f.read(4), byteorder="little", signed=False)
                f.seek(128, 1)

        folders = []

        for _ in range(num_folders):
            expected_checksum = int.from_bytes(
                f.read(4), byteorder=byteorder, signed=False
            )

            if result.version.value >= ArchiveVersion.QUANTUM_BREAK.value:
                next_file_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
                parent_folder_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
            else:
                next_file_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                parent_folder_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )

            f.seek(4, 1)

            if result.version.value >= ArchiveVersion.QUANTUM_BREAK.value:
                name_offset = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
                next_parent_folder_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
                next_file_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
            else:
                name_offset = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                next_parent_folder_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                next_file_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )

            if name_offset != 0xFFFFFFFF and name_offset != 0xFFFFFFFFFFFFFFFF:
                folder_name = read_name(f, name_size, name_offset)
            else:
                # Root folder
                folder_name = ""

            # Verify checksum before continuing
            actual_checksum = zlib.crc32(folder_name.lower().encode())

            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"Invalid checksum for folder name! Archive may be corrupted. (Expected: {expected_checksum}, Got: {actual_checksum})"
                )

            entry = FolderEntry(
                name=folder_name,
                checksum=expected_checksum,
                name_offset=name_offset,
                next_file_id=next_file_id,
                next_folder_id=next_file_id,
                next_parent_folder_id=next_parent_folder_id,
                prev_folder_id=parent_folder_id,
            )

            folders.append(entry)

        result.folders = folders
        files = []

        for _ in range(num_files):
            expected_checksum = int.from_bytes(
                f.read(4), byteorder=byteorder, signed=False
            )

            if result.version.value >= ArchiveVersion.QUANTUM_BREAK.value:
                next_file_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
                parent_folder_id = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )

                file_flags = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                name_offset = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
            else:
                next_file_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                parent_folder_id = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                file_flags = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )
                name_offset = int.from_bytes(
                    f.read(4), byteorder=byteorder, signed=False
                )

            file_offset = int.from_bytes(f.read(8), byteorder=byteorder, signed=False)
            file_size = int.from_bytes(f.read(8), byteorder=byteorder, signed=False)
            file_checksum = int.from_bytes(f.read(4), byteorder="little", signed=False)
            file_name = read_name(f, name_size, name_offset)

            if (
                result.version.value
                >= ArchiveVersion.ALAN_WAKE_AMERICAN_NIGHTMARE.value
            ):
                writetime_bytes = int.from_bytes(
                    f.read(8), byteorder=byteorder, signed=False
                )
                writetime = datetime.fromtimestamp(
                    (writetime_bytes - 116444736000000000) / 10000000
                )

            actual_checksum = zlib.crc32(file_name.lower().encode())
            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"Invalid checksum for file name! Archive may be corrupted. (Expected: {expected_checksum}, Got: {actual_checksum})"
                )

            entry = FileEntry(
                name=file_name,
                parent_folder_id=parent_folder_id,
                next_file_id=next_file_id,
                name_checksum=expected_checksum,
                data_checksum=file_checksum,
                name_offset=name_offset,
                flags=file_flags,
                size=file_size,
                offset=file_offset,
                writetime=(
                    writetime
                    if result.version.value
                    >= ArchiveVersion.ALAN_WAKE_AMERICAN_NIGHTMARE.value
                    else None
                ),
            )

            files.append(entry)

        result.files = files

    return result


def extract_rmdp(bin_file: Path, rmdp_file: Path, output_folder: Path | None = None):
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        progress.add_task("Parsing archive metadata...")
        archive = read_metadata(bin_file)

    with open(rmdp_file, "rb") as rmdp:
        for file in track(archive.files, description="Extracting files..."):
            file_path = get_parent_folder_path(
                archive.folders, file.parent_folder_id
            ) + [file.name]

            file_path[0] = file_path[0].replace(":", "_")
            file_path = Path(*file_path)

            if output_folder:
                file_path = output_folder / file_path
            else:
                file_path = rmdp_file.parent / rmdp_file.stem / file_path

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as output:
                rmdp.seek(file.offset)

                actual_checksum = 0
                remaining_bytes = file.size

                while remaining_bytes > 0:
                    # Read max. 4MB chunks
                    chunk_size = min(4 * 1024 * 1024, remaining_bytes)
                    chunk = rmdp.read(chunk_size)
                    actual_checksum = zlib.crc32(chunk, actual_checksum)
                    output.write(chunk)
                    remaining_bytes -= chunk_size

                if actual_checksum != file.data_checksum:
                    raise ValueError(
                        f"Invalid checksum for file data! Archive may be corrupted. (Expected: {file.data_checksum}, Got: {actual_checksum})"
                    )
