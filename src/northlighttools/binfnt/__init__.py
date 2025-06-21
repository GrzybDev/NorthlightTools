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
from northlighttools.binfnt.utilities import (
    apply_bmfont_to_binfnt,
    convert_bgra8_to_r16f,
    convert_binfnt_char_to_char_entry,
    convert_r16f_to_bgra8,
    convert_to_bmfont,
)

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


@app.command(name="compile", help="Compile BMFont text and bitmap(s) to .binfnt file")
def cmd_compile(
    original_file: Annotated[
        Path,
        typer.Argument(
            help="Path to original .binfnt file",
            exists=True,
            readable=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    modified_file: Annotated[
        Path,
        typer.Argument(
            help="Path to modified .fnt file",
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
            exists=False,
        ),
    ] = None,
):
    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Compiling...", total=1)
        progress.console.log(f"Loading original font from {original_file}...")

        with open(original_file, "rb") as f:
            binfnt = BinaryFont(f)

        with open(modified_file, "r") as f:
            bitmap_file_path = apply_bmfont_to_binfnt(binfnt, f.readlines())

        bitmap_file_path = modified_file.parent / bitmap_file_path
        compiled_bitmap = None

        if not bitmap_file_path.exists():
            if binfnt.version in [
                FontVersion.ALAN_WAKE,
                FontVersion.ALAN_WAKE_REMASTERED,
            ]:
                raise typer.BadParameter(f"{bitmap_file_path} does not exist!")

            progress.console.log(f"Compiling bitmap from character bitmaps...")

            if binfnt.version == FontVersion.QUANTUM_BREAK:
                char_dir = modified_file.parent / CHARS_FOLDER

                if not char_dir.exists():
                    raise typer.BadParameter(
                        f"Neither {char_dir} or {bitmap_file_path} exist! Please ensure that the character bitmaps are in a directory named '{CHARS_FOLDER}' in the same directory as the .fnt file."
                    )

                compiled_bitmap = Image.new(
                    "RGBA",
                    (binfnt.textureWidth, binfnt.textureHeight),
                    (255, 255, 255, 127),
                )

                for i, char in enumerate(binfnt.characters):
                    idx = binfnt.ids[i]
                    char_path = char_dir / f"{idx}.png"

                    if char_path.exists():
                        point = convert_binfnt_char_to_char_entry(
                            char,
                            binfnt.textureWidth,
                            binfnt.textureHeight,
                            binfnt.lineHeight,
                            binfnt.fontSize,
                        )

                        compiled_bitmap.paste(Image.open(char_path), (point.x, point.y))
        else:
            progress.console.log(f"Loading bitmap from {bitmap_file_path}...")
            compiled_bitmap = Image.open(bitmap_file_path)

        if compiled_bitmap is None:
            raise typer.BadParameter("No bitmap could be compiled or loaded.")

        progress.console.log("Converting bitmap to RGBA format...")
        rgba_texture = BytesIO()
        compiled_bitmap.save(rgba_texture, "DDS")
        rgba_texture.seek(0)

        if binfnt.version == FontVersion.QUANTUM_BREAK:
            binfnt.textureBytes = convert_bgra8_to_r16f(rgba_texture)
        else:
            binfnt.textureBytes = rgba_texture.getvalue()

        progress.console.log("Writing compiled font to .binfnt file...")

        output_file = (
            Path(output_file) if output_file else modified_file.with_suffix(".binfnt")
        )

        with open(output_file, "wb") as f:
            binfnt.write(f)

        progress.console.log("Font compiled successfully!")
        progress.update(task, advance=1)


if __name__ == "__main__":
    app()
