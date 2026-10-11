from pathlib import Path
from typing import Annotated

import typer
from rich.filesize import decimal
from rich.markup import escape
from rich.table import Table

from northlighttools.cli.console import (
    SPINNER,
    console,
    done,
    progress_bar,
    reports_errors,
    warn,
)
from northlighttools.rmdp import (
    FORMATS,
    Game,
    Package,
    extract_package,
    filetime_to_datetime,
    format_path,
    pack_directory,
    package_paths,
    read_package,
    repack_directory,
)

app = typer.Typer(
    help="Remedy packages: a .bin index with a .rmdp data file.",
    no_args_is_help=True,
)

PackageArgument = Annotated[
    Path,
    typer.Argument(
        help="The package's .bin or .rmdp file (both must exist)",
        exists=True,
        dir_okay=False,
    ),
]


def _open(path: Path) -> tuple[Package, Path]:
    index_path, data_path = package_paths(path)
    missing = [str(p) for p in (index_path, data_path) if not p.is_file()]
    if missing:
        msg = f"The package is incomplete, missing: {', '.join(missing)}"
        raise FileNotFoundError(msg)
    with console.status("Reading the package index...", spinner=SPINNER):
        return read_package(index_path), data_path


@app.command(help="Show what a package is made for and what it holds.")
@reports_errors
def info(package_path: PackageArgument) -> None:
    package, _ = _open(package_path)
    table = Table(show_header=False, box=None)
    table.add_row("Game", f"{package.format.title} (version {package.format.version})")
    table.add_row("Byte order", package.byte_order.name.lower())
    table.add_row("Base path", escape(package.base_path) or "(none)")
    table.add_row("Folders", str(len(package.folders)))
    table.add_row("Files", str(len(package.files)))
    table.add_row("Data size", decimal(package.data_size))
    if package.extra_paths:
        table.add_row("Extra paths", "\n".join(map(escape, package.extra_paths)))
    console.print(table)


@app.command(name="list", help="List the files of a package.")
@reports_errors
def list_files(package_path: PackageArgument) -> None:
    package, _ = _open(package_path)
    table = Table("Path", "Size", "Offset", "Modified (UTC)")
    for file in package.files:
        table.add_row(
            escape(format_path(file.path)),
            decimal(file.size),
            hex(file.offset),
            _modified(file.timestamp),
        )
    console.print(table)


def _modified(timestamp: int | None) -> str:
    if timestamp is None:
        return ""
    moment = filetime_to_datetime(timestamp)
    if moment is None:
        return f"{timestamp:#x} (not a date)"
    return moment.strftime("%Y-%m-%d %H:%M:%S")


@app.command(help="Extract every file of a package.")
@reports_errors
def extract(
    package_path: PackageArgument,
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Where to extract (default: next to the package, named after it)",
            file_okay=False,
        ),
    ] = None,
) -> None:
    package, data_path = _open(package_path)
    output_dir = output_dir or data_path.with_suffix("")
    with progress_bar() as progress:
        task = progress.add_task("Extracting", total=len(package.files))
        mismatched = extract_package(
            package, data_path, output_dir, lambda _: progress.advance(task)
        )
    for file in mismatched:
        warn(f"{format_path(file.path)} does not match its stored CRC-32")
    done(f"Extracted {len(package.files)} files to {output_dir}")


@app.command(help="Pack a directory into a package.")
@reports_errors
def pack(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory to pack", exists=True, file_okay=False, dir_okay=True
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            help="The .bin or .rmdp file to create, with its pair "
            "(default: next to the directory, named after it)",
            dir_okay=False,
        ),
    ] = None,
    game: Annotated[
        Game | None,
        typer.Option(
            "--game",
            "-g",
            help="Game whose package format to use [default: quantum-break]",
        ),
    ] = None,
    original: Annotated[
        Path | None,
        typer.Option(
            "--original",
            help="The package the directory was extracted from: unchanged files keep "
            "their exact place, so an unchanged directory packs into the same package",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
) -> None:
    if game and original:
        msg = "--original sets the package format; leave out --game"
        raise ValueError(msg)
    input_dir = input_dir.resolve()  # "." has no name to call the package after
    output_path = output_path or input_dir.parent / f"{input_dir.name}.rmdp"
    with progress_bar() as progress:
        task = progress.add_task("Packing", total=None)

        def advance(_: object) -> None:
            progress.advance(task)

        if original:
            package = repack_directory(input_dir, output_path, original, advance)
        else:
            package_format = FORMATS[game or Game.QUANTUM_BREAK]
            package = pack_directory(
                input_dir, output_path, package_format, on_file=advance
            )
    index_path, data_path = package_paths(output_path)
    done(f"Packed {len(package.files)} files into {index_path} and {data_path}")
