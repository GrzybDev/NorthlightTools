from pathlib import Path
from typing import Annotated

import typer

from northlighttools.rmdp.dataclasses.Archive import Archive
from northlighttools.rmdp.enums.ArchiveEndianness import (
    ArchiveEndianness,
    ArchiveEndiannessChoice,
)
from northlighttools.rmdp.enums.ArchiveVersion import (
    ArchiveVersion,
    ArchiveVersionChoice,
)
from northlighttools.rmdp.pack import rmdp_pack
from northlighttools.rmdp.unpack import rmdp_unpack

app = typer.Typer()


@app.command()
def unpack(
    rmdp_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[Path, typer.Argument(writable=True)] = None,
):
    if rmdp_file.suffix != ".rmdp":
        raise typer.BadParameter(f"{rmdp_file} is not a .rmdp file!")

    # Check if the file have paired .bin file
    bin_file = rmdp_file.with_suffix(".bin")

    if not bin_file.exists():
        raise typer.BadParameter(
            f"Cannot extract {rmdp_file} without paired {bin_file} file!"
        )

    rmdp_unpack(bin_file, rmdp_file, output_dir)


@app.command()
def pack(
    input_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, readable=True)
    ],
    output_file: Annotated[Path, typer.Argument(writable=True)],
    archive_endianness: Annotated[
        ArchiveEndiannessChoice, typer.Option(case_sensitive=False)
    ] = None,
    archive_version: Annotated[
        ArchiveVersionChoice, typer.Option()
    ] = ArchiveVersionChoice.QUANTUM_BREAK,
):
    archive = Archive()

    if not archive_endianness:
        archive_endianness = (
            ArchiveEndiannessChoice.LITTLE
            if archive_version != ArchiveVersionChoice.ALAN_WAKE
            else ArchiveEndiannessChoice.BIG
        )

    archive.endianness = (
        ArchiveEndianness.LITTLE
        if archive_endianness == ArchiveEndiannessChoice.LITTLE
        else ArchiveEndianness.BIG
    )
    archive.version = ArchiveVersion(int(archive_version))

    rmdp_pack(archive, input_dir, output_file)


if __name__ == "__main__":
    app()
