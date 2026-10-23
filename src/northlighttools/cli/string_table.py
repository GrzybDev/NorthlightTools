from pathlib import Path
from typing import Annotated

import typer

from northlighttools.cli.console import done, reports_errors
from northlighttools.fileio import write_atomically
from northlighttools.string_table import (
    TranslationFormat,
    decode_string_table,
    encode_string_table,
    export_translation,
    import_translation,
)

app = typer.Typer(
    help="String tables (string_table.bin): the localized texts of a game.",
    no_args_is_help=True,
)


@app.command(
    name="export",
    help="Export a string table for translation: XLIFF 2.0, XLIFF 1.2 or Gettext PO.",
)
@reports_errors
def export_command(
    input_path: Annotated[
        Path,
        typer.Argument(help="The string_table.bin file", exists=True, dir_okay=False),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            help="The file to create (default: next to the input, with the "
            "format's extension: .xlf, .xliff or .po)",
            dir_okay=False,
        ),
    ] = None,
    translation_format: Annotated[
        TranslationFormat | None,
        typer.Option(
            "--format",
            "-f",
            help="The translation format [default: by the output's extension, else xliff-2.0]",
            show_default=False,
        ),
    ] = None,
    source_language: Annotated[
        str,
        typer.Option(
            "--source-language",
            "-l",
            help="The language of the table's texts, as a BCP 47 tag (XLIFF only)",
        ),
    ] = "en",
) -> None:
    if translation_format is None:
        translation_format = TranslationFormat.of_suffix(output_path.suffix if output_path else "")
    output_path = output_path or input_path.with_suffix(translation_format.suffix)
    entries = decode_string_table(input_path.read_bytes())
    document = export_translation(entries, translation_format, input_path.name, source_language)
    write_atomically(output_path, document)
    done(f"Exported {len(entries)} strings to {output_path} as {translation_format}")


@app.command(
    name="import",
    help="Build a string table from a translated XLIFF 2.0, XLIFF 1.2 or PO file; "
    "untranslated strings keep their original text.",
)
@reports_errors
def import_command(
    input_path: Annotated[
        Path,
        typer.Argument(
            help="The translated file, in any of the formats export writes",
            exists=True,
            dir_okay=False,
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            help="The string table to create (default: next to the input)",
            dir_okay=False,
        ),
    ] = None,
) -> None:
    output_path = output_path or input_path.with_suffix(".bin")
    translation_format, entries = import_translation(input_path.read_bytes())
    write_atomically(output_path, encode_string_table(entries))
    done(f"Imported {len(entries)} strings from {translation_format} to {output_path}")
