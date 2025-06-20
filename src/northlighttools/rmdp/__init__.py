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

from northlighttools.rmdp.package import Package

app = typer.Typer(help="Tools for Remedy Packages (.bin/.rmdp files)")


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


if __name__ == "__main__":
    app()
