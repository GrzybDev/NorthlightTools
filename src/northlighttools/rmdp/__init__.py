from pathlib import Path
from typing import Annotated

import typer
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from northlighttools.rmdp.enumerators.endianness import Endianness, EndiannessChoice
from northlighttools.rmdp.enumerators.package_version import (
    PackageVersion,
    PackageVersionChoice,
)
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


@app.command(help="Extracts a Remedy Package")
def extract(
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
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the output directory where files will be extracted",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = None,
):
    bin_path, rmdp_path = get_archive_paths(archive_path)

    output_dir = output_dir or rmdp_path.parent / rmdp_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(transient=True) as progress:
        progress.add_task(
            description="Reading package metadata...",
            total=None,
        )
        package = Package(header_path=bin_path)

    progress = Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    with progress and rmdp_path.open("rb") as f:
        for file in progress.track(
            package.files,
            description="Extracting files...",
        ):
            file_path = package.get_file_path(file)
            output_path = output_dir / file_path

            progress.console.log(f"Extracting {file_path}...")

            package.extract(f, file, output_path)


@app.command(help="Pack directory into a Remedy Package")
def pack(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help="Path to the input directory containing files to package",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to where the output .bin/.rmdp file will be created",
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ] = None,
    endianness: Annotated[
        EndiannessChoice,
        typer.Option(
            "--endianness",
            "-e",
            help="Endianness of the package (little or big)",
            case_sensitive=False,
        ),
    ] = EndiannessChoice.LITTLE,
    version: Annotated[
        PackageVersionChoice,
        typer.Option(
            "--version",
            "-v",
            help="Version of the package",
        ),
    ] = PackageVersionChoice.QUANTUM_BREAK,
):
    output_dir = output_path or input_dir.parent / f"{input_dir.name}.rmdp"
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    bin_path = output_dir.with_suffix(".bin")
    rmdp_path = output_dir.with_suffix(".rmdp")

    progress = Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    package = Package()
    package.endianness = Endianness[endianness.name.upper()]
    package.version = PackageVersion(int(version))

    with progress:
        with rmdp_path.open("wb") as rmdp_file:
            for path in progress.track(
                sorted(input_dir.rglob("*")),
                description="Creating package...",
            ):
                if path.is_dir():
                    progress.console.log(
                        f"Adding folder: {path.relative_to(input_dir)}..."
                    )

                    package.add_folder(path.relative_to(input_dir))
                elif path.is_file():
                    progress.console.log(
                        f"Adding file: {path.relative_to(input_dir)}..."
                    )

                    package.add_file(rmdp_file, path, path.relative_to(input_dir))

            rmdp_file.close()

    with Progress(transient=True) as progress:
        progress.add_task(
            description="Building package metadata...",
            total=None,
        )

        with bin_path.open("wb") as bin_file:
            package.build_header(bin_file)


if __name__ == "__main__":
    app()
