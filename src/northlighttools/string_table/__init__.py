from pathlib import Path
from typing import Annotated

import typer
from rich import print

from northlighttools.string_table.enumerators.data_format import DataFormat
from northlighttools.string_table.enumerators.missing_string_behaviour import (
    MissingStringBehaviour,
)
from northlighttools.string_table.string_table import StringTable

app = typer.Typer(
    help="Tools for string tables in Remedy games (string_table.bin files)"
)


@app.command(name="export", help="Export string_table.bin to selected format")
def cmd_export(
    input_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the input string_table.bin file",
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            writable=True,
            help="Path to the output file where the exported data will be saved",
        ),
    ] = None,
    output_type: Annotated[
        DataFormat,
        typer.Option(
            "--output-type",
            "-o",
            help="Format of the output file",
            case_sensitive=False,
        ),
    ] = DataFormat.XML,
):
    output_path = output_path or input_path.with_suffix(f".{output_type.value}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = StringTable(input_file=input_path)
    table.export(output_path, output_type)

    print(f"Successfully exported string table to {output_path}!")


@app.command(name="import", help="Generate string_table.bin from input file")
def cmd_import(
    input_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the input file to import",
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            writable=True,
            help="Path to the output string_table.bin file",
        ),
    ] = None,
    missing_strings: Annotated[
        MissingStringBehaviour,
        typer.Option(
            "--missing-strings",
            "-m",
            case_sensitive=False,
            help="What should missing translations look like in imported file",
        ),
    ] = MissingStringBehaviour.KeyAndOriginal,
):
    output_path = output_path or input_path.with_suffix(".bin")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = StringTable()
    table.load_from(input_path, missing_strings=missing_strings)
    table.save(output_path)

    print(f"Successfully imported string table to {output_path}!")


if __name__ == "__main__":
    app()
