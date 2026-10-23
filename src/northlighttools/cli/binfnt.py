from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from northlighttools.binfnt import (
    compile_font,
    decode_dds,
    decode_font,
    decompile_font,
    encode_font,
)
from northlighttools.cli.console import console, done, reporting_originals, reports_errors
from northlighttools.fileio import write_atomically

app = typer.Typer(
    help="Binary fonts (.binfnt): glyphs, kerning and a texture atlas.",
    no_args_is_help=True,
)

FontArgument = Annotated[Path, typer.Argument(help="The .binfnt file", exists=True, dir_okay=False)]


@app.command()
@reports_errors
def info(font_path: FontArgument) -> None:
    """Show what a font holds."""
    font = decode_font(font_path.read_bytes())
    texture = decode_dds(font.texture)
    table = Table(show_header=False, box=None)
    table.add_row("Version", str(int(font.version)))
    table.add_row("Glyphs", str(len(font.glyphs)))
    table.add_row("Characters", str(len(font.charmap)))
    table.add_row("Kerning pairs", str(len(font.kerning)))
    table.add_row(
        "Texture",
        f"{texture.width}x{texture.height} {texture.pixel_format.value}, "
        f"{len(texture.levels)} mipmap level(s)",
    )
    console.print(table)


@app.command()
@reports_errors
def decompile(
    font_path: FontArgument,
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Where to write (default: next to the font, named after it)",
            file_okay=False,
        ),
    ] = None,
    separate_glyphs: Annotated[
        bool,
        typer.Option(
            "--separate-glyphs",
            "-s",
            help="Save each glyph as its own image instead of the whole texture",
        ),
    ] = False,
) -> None:
    """Turn a font into an msdf-atlas-gen JSON document and its texture."""
    output_dir = output_dir or font_path.with_suffix("")
    json_path = output_dir / f"{font_path.stem}.json"
    font = decode_font(font_path.read_bytes())
    decompile_font(font, json_path, separate_glyphs=separate_glyphs)
    done(f"Decompiled {font_path.name} to {json_path}")


@app.command(name="compile")
@reports_errors
def compile_command(
    json_path: Annotated[
        Path,
        typer.Argument(help="The JSON document written by decompile", exists=True, dir_okay=False),
    ],
    output_path: Annotated[
        Path | None,
        typer.Argument(
            help="The .binfnt file to create (default: next to the document)",
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Build a font from a decompiled JSON document."""
    output_path = output_path or json_path.with_suffix(".binfnt")
    with reporting_originals(output_path):
        write_atomically(output_path, encode_font(compile_font(json_path)))
    done(f"Compiled {output_path}")
