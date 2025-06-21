from io import BytesIO
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image
from rich.progress import Progress, SpinnerColumn, TextColumn

from northlighttools.binfnt.constants import CHARS_FOLDER
from northlighttools.binfnt.enums.font_version import FontVersion
from northlighttools.binfnt.font import BinaryFont
from northlighttools.binfnt.helpers import write_bmfont_files
from northlighttools.binfnt.utilities import convert_to_bmfont

app = typer.Typer(help="Tools for .binfnt files (Binary font files)")


@app.command(
    name="decompile", help="Decompile .binfnt file to BMFont text and bitmap(s)"
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
    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Decompiling...", total=1)

        with open(input_file, "rb") as f:
            binfnt = BinaryFont(f)
            characters, kernings = convert_to_bmfont(binfnt)

        out_dir = Path(output_dir) if output_dir else input_file.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        progress.console.log("Writing BMFont files...")

        bitmap_file = write_bmfont_files(
            binfnt, characters, kernings, out_dir, input_file
        )

        if binfnt.version == FontVersion.QUANTUM_BREAK:
            progress.console.log("Converting texture from BGRA8 to R16F format...")
            texture = convert_r16f_to_bgra8(BytesIO(binfnt.textureBytes))
            progress.console.log("Loading texture as image...")
            bitmap = Image.open(BytesIO(texture))

            if separate_chars:
                char_bitmap_dir = out_dir / CHARS_FOLDER
                char_bitmap_dir.mkdir(parents=True, exist_ok=True)

                progress.console.log(
                    f"Saving character bitmaps to individual files in {char_bitmap_dir}..."
                )

                for char in characters:
                    if char.width and char.height:
                        bitmap.crop(
                            (char.x, char.y, char.x + char.width, char.y + char.height)
                        ).save(char_bitmap_dir / f"{char.idx}.png")
            else:
                progress.console.log(f"Saving bitmap file to {bitmap_file}...")

                with open(bitmap_file, "wb") as f:
                    bitmap.save(f, "PNG")
        else:
            with open(bitmap_file, "wb") as f:
                f.write(binfnt.textureBytes)

        progress.console.log("Font decompiled successfully!")
        progress.update(task, advance=1)


if __name__ == "__main__":
    app()
