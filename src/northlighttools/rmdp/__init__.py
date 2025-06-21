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

from northlighttools.rmdp.enumerators.endianness import Endianness
from northlighttools.rmdp.enumerators.package_version import PackageVersion
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
    bin_path = archive_path.with_suffix(".bin")
    rmdp_path = archive_path.with_suffix(".rmdp")

    missing = [str(p) for p in [bin_path, rmdp_path] if not p.exists()]
    if missing:
        raise typer.BadParameter(
            f"Cannot read {archive_path} because the following required file(s) are missing: {', '.join(missing)}"
        )

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


@app.command(help="Lists files in a Remedy Package")
def list_files(
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
    bin_path = archive_path.with_suffix(".bin")
    rmdp_path = archive_path.with_suffix(".rmdp")

    missing = [str(p) for p in [bin_path, rmdp_path] if not p.exists()]
    if missing:
        raise typer.BadParameter(
            f"Cannot list files in {archive_path} because the following required file(s) are missing: {', '.join(missing)}"
        )

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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            is_flag=True,
            help="Enable verbose output",
        ),
    ] = False,
):
    bin_path = archive_path.with_suffix(".bin")
    rmdp_path = archive_path.with_suffix(".rmdp")
    output_dir = output_dir or rmdp_path.parent / rmdp_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [str(p) for p in [bin_path, rmdp_path] if not p.exists()]
    if missing:
        raise typer.BadParameter(
            f"Cannot extract {archive_path} because the following required file(s) are missing: {', '.join(missing)}"
        )

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

    with progress:
        with rmdp_path.open("rb") as f:
            for file in progress.track(
                package.files,
                description="Extracting files...",
            ):
                file_path = package.get_file_path(file)
                output_path = output_dir / file_path

                if verbose:
                    progress.console.log(f"Extracting {file_path}...")

                package.extract_file(
                    f,
                    file,
                    output_path,
                )


@app.command(help="Package files into a Remedy Package")
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
        Endianness,
        typer.Option(
            "--endianness",
            "-e",
            help="Endianness of the package (little or big)",
            case_sensitive=False,
        ),
    ] = Endianness.LITTLE,
    version: Annotated[
        PackageVersion,
        typer.Option(
            "--version",
            "-v",
            help="Version of the package",
        ),
    ] = PackageVersion.QUANTUM_BREAK,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            is_flag=True,
            help="Enable verbose output",
        ),
    ] = False,
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
    package.endianness = endianness
    package.version = version

    with progress:
        with rmdp_path.open("wb") as rmdp_file:
            for path in progress.track(
                sorted(input_dir.rglob("*")),
                description="Creating package...",
            ):
                if path.is_dir():
                    if verbose:
                        progress.console.log(
                            f"Adding folder: {path.relative_to(input_dir)}..."
                        )

                    package.add_folder(path.relative_to(input_dir))
                elif path.is_file():
                    if verbose:
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
