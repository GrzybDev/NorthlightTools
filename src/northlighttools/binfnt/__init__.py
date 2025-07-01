from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from northlighttools.binfnt.font import BinaryFont
from northlighttools.rmdp import Annotated

app = typer.Typer(help="Tools for .binfnt files (Binary font files)")


@app.command(
    name="decompile", help="Decompile binary font to editable JSON and bitmap(s)"
)
def cmd_decompile(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Input .binfnt file path",
            exists=True,
            readable=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Output directory", writable=True, file_okay=False, dir_okay=True
        ),
    ] = None,
    separate_chars: Annotated[
        bool,
        typer.Option(
            "--separate-chars",
            "-s",
            help="Save each character bitmap to a separate file",
            is_flag=True,
        ),
    ] = False,
):
    output_dir = output_dir or input_file.parent / input_file.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Decompiling...", total=1)

        binfnt = BinaryFont(progress, input_file)
        binfnt.dump(output_dir, separate_chars)

        progress.update(task, advance=1, description="Decompiled successfully")


@app.command(name="compile", help="Compile JSON and bitmap(s) to binary font")
def cmd_compile(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Input JSON file path",
            exists=True,
            readable=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    output_file: Annotated[
        Path | None,
        typer.Argument(
            help="Output .binfnt file path",
            writable=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
):
    output_file = output_file or input_file.with_suffix(".binfnt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    separate_chars = not input_file.with_suffix(".png").exists()

    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Compiling...", total=1)

        binfnt = BinaryFont(progress)
        binfnt.from_json(input_file, separate_chars)
        binfnt.build(output_file)

        progress.update(task, advance=1, description="Compiled successfully")


if __name__ == "__main__":
    app()
