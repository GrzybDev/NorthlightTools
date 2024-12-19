from pathlib import Path
from typing import Annotated, Optional

import typer

from northlighttools.string_table.dataclasses.String import String
from northlighttools.string_table.enums.DataFormat import DataFormat
from northlighttools.string_table.enums.MissingString import MissingStringBehaviour
from northlighttools.string_table.readers import read_csv, read_json, read_po, read_xml
from northlighttools.string_table.writers import (
    write_csv,
    write_json,
    write_po,
    write_xml,
)

app = typer.Typer()


@app.command(name="export")
def cmd_export(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_file: Annotated[Path, typer.Argument(writable=True)] = None,
    output_type: Optional[DataFormat] = DataFormat.XML,
):
    strings = []

    with open(input_file, "rb") as f:
        strings_count = int.from_bytes(f.read(4), "little", signed=False)

        for _ in range(strings_count):
            key_len = int.from_bytes(f.read(4), "little", signed=False)
            key = f.read(key_len).decode("ascii")

            str_len = int.from_bytes(f.read(4), "little", signed=False)
            value = f.read(str_len * 2).decode("utf-16le")

            strings.append(String(key, value))

    if output_file:
        output_path = output_file
    else:
        output_path = input_file.with_suffix(f".{output_type.value.lower()}")

    match output_type:
        case DataFormat.XML:
            write_xml(strings, output_path)
        case DataFormat.JSON:
            write_json(strings, output_path)
        case DataFormat.CSV:
            write_csv(strings, output_path)
        case DataFormat.PO:
            write_po(strings, output_path)


@app.command(name="import")
def cmd_import(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_file: Annotated[Path, typer.Argument(writable=True)] = None,
    missing_strings: Optional[
        MissingStringBehaviour
    ] = MissingStringBehaviour.KeyAndOriginal,
):
    # Determine the file format based on the file extension
    match input_file.suffix.lower():
        case ".xml":
            strings = read_xml(input_file)
        case ".json":
            strings = read_json(input_file)
        case ".csv":
            strings = read_csv(input_file, missing_strings)
        case ".po":
            strings = read_po(input_file, missing_strings)
        case _:
            raise typer.BadParameter(f"{input_file} is not a supported file format!")

    if output_file:
        output_path = output_file
    else:
        output_path = input_file.with_suffix(".bin")

    with open(output_path, "wb") as f:
        f.write(len(strings).to_bytes(4, "little", signed=False))

        for string in strings:
            f.write(len(string.key).to_bytes(4, "little", signed=False))
            f.write(string.key.encode("ascii"))

            f.write(len(string.value).to_bytes(4, "little", signed=False))
            f.write(string.value.encode("utf-16le"))


if __name__ == "__main__":
    app()
