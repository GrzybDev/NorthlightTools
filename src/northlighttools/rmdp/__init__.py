from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress

from northlighttools.rmdp.helpers import get_archive_paths
from northlighttools.rmdp.package import Package

app = typer.Typer(help="Tools for Remedy Packages (.bin/.rmdp files)")


@app.command(help="Prints information about a Remedy Package")
def info(
    archive_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the input .bin/.rmdp file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    print_unknown_metadata: Annotated[
        bool,
        typer.Option(
            "--print-unknown-metadata",
            "-u",
            is_flag=True,
            help="Print unknown metadata from the package header",
        ),
    ] = False,
):
    bin_path, _ = get_archive_paths(archive_path)

    with Progress(transient=True) as progress:
        progress.add_task(
            description="Reading package metadata...",
            total=None,
        )
        package = Package(header_path=bin_path)

    typer.echo(f"Endianness: {package.endianness}")
    typer.echo(f"Version: {package.version.name} ({package.version.value})")
    typer.echo(f"Number of folders: {len(package.folders)}")
    typer.echo(f"Number of files: {len(package.files)}")

    if print_unknown_metadata:
        typer.echo("Unknown metadata:")
        for key, value in package.unknown_data.items():
            typer.echo(f"  {key}: {value}")


@app.command(name="list", help="Lists files in a Remedy Package")
def contents(
    archive_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the input .bin/.rmdp file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
):
    bin_path, _ = get_archive_paths(archive_path)

    with Progress(transient=True) as progress:
        progress.add_task(
            description="Reading package metadata...",
            total=None,
        )
        package = Package(header_path=bin_path)

    for file in package.files:
        file_path = package.get_file_path(file)
        typer.echo(f"{file_path} (Size: {file.size} bytes, Offset: {file.offset})")


if __name__ == "__main__":
    app()
