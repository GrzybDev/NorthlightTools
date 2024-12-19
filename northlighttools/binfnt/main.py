from io import BytesIO
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image
from rich.progress import Progress, SpinnerColumn, TextColumn

from northlighttools.binfnt.enums.FontVersion import FontVersion
from northlighttools.binfnt.font import BinaryFont
from northlighttools.binfnt.utilities import (
    apply_bmfont_to_binfnt,
    convert_bgra8_to_r16f,
    convert_binfnt_char_to_char_entry,
    convert_r16f_to_bgra8,
    convert_to_bmfont,
)

app = typer.Typer()


@app.command()
def decompile(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[Path, typer.Argument(writable=True)] = None,
    separate_chars: bool = False,
):
    if input_file.suffix != ".binfnt":
        raise typer.BadParameter(f"{input_file} is not a .binfnt file!")

    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        cur_task = progress.add_task("Decompiling...")

        with open(input_file, "rb") as f:
            binfnt = BinaryFont(f)
            characters, kernings = convert_to_bmfont(binfnt)

        progress.update(cur_task, total=1, completed=True)

        fnt_suffix = ".fnt"
        bitmap_suffix = (
            ".png" if binfnt.version == FontVersion.QUANTUM_BREAK else ".dds"
        )

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            fnt_file = output_dir / input_file.with_suffix(fnt_suffix).name
            bitmap_file = output_dir / input_file.with_suffix(bitmap_suffix).name
        else:
            fnt_file = input_file.with_suffix(fnt_suffix)
            bitmap_file = input_file.with_suffix(bitmap_suffix)

        cur_task = progress.add_task("Writing BMFont file...")
        with open(fnt_file, "w") as f:
            f.write(f'info face="" size={binfnt.fontSize} bold=0 italic=0\n')
            f.write(
                f"common lineHeight={binfnt.lineHeight} base=0 scaleW={binfnt.textureWidth} scaleH={binfnt.textureHeight} pages=1\n"
            )
            f.write(f'page id=0 file="{bitmap_file.name}"\n')
            f.write(f"chars count={len(characters)}\n")

            for char in characters:
                f.write(
                    f"char id={char.idx} x={char.x} y={char.y} width={round(char.width)} height={round(char.height)} xoffset={char.xoffset} yoffset={char.yoffset} xadvance={char.xadvance} page={char.page} chnl={char.chnl}\n"
                )

            f.write(f"kernings count={len(kernings)}\n")

            for kerning in kernings:
                f.write(
                    f"kerning first={kerning.first} second={kerning.second} amount={kerning.amount}\n"
                )

        progress.update(cur_task, total=1, completed=True)

        if binfnt.version == FontVersion.QUANTUM_BREAK:
            cur_task = progress.add_task("Processing texture...")
            texture = convert_r16f_to_bgra8(BytesIO(binfnt.textureBytes))
            bitmap = Image.open(BytesIO(texture))
            progress.update(cur_task, total=1, completed=True)

            if separate_chars:
                cur_task = progress.add_task("Writing character bitmaps...")
                char_bitmap_dir = output_dir / "chars"
                char_bitmap_dir.mkdir(parents=True, exist_ok=True)

                for char in characters:
                    if char.width == 0 or char.height == 0:
                        continue

                    char_bitmap = bitmap.crop(
                        (char.x, char.y, char.x + char.width, char.y + char.height)
                    )
                    char_bitmap.save(char_bitmap_dir / f"{char.idx}.png")

                progress.update(cur_task, total=1, completed=True)
            else:
                cur_task = progress.add_task("Writing texture bitmap...")

                with open(bitmap_file, "wb") as f:
                    bitmap.save(f, "PNG")

                progress.update(cur_task, total=1, completed=True)
        else:
            cur_task = progress.add_task("Writing texture file...")

            with open(bitmap_file, "wb") as f:
                f.write(binfnt.textureBytes)


@app.command()
def compile(
    original_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    modified_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_file: Annotated[Path, typer.Argument(writable=True)] = None,
):
    if original_file.suffix != ".binfnt":
        raise typer.BadParameter(f"{original_file} is not a .binfnt file!")

    if modified_file.suffix != ".fnt":
        raise typer.BadParameter(f"{modified_file} is not a .fnt file!")

    with Progress(
        SpinnerColumn(finished_text="\u2713"),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        cur_task = progress.add_task("Decompiling original font...")

        with open(original_file, "rb") as f:
            binfnt = BinaryFont(f)

        progress.update(cur_task, total=1, completed=True)

        cur_task = progress.add_task("Reading BMFont file...")

        with open(modified_file, "r") as f:
            bitmap_file_path = apply_bmfont_to_binfnt(binfnt, f.readlines())

        if binfnt.version in [
            FontVersion.ALAN_WAKE,
            FontVersion.ALAN_WAKE_REMASTERED,
        ] and not bitmap_file_path.endswith(".dds"):
            raise typer.BadParameter(
                f"{bitmap_file_path} is not a .dds file! Alan Wake fonts require a .dds texture."
            )

        if (
            binfnt.version == FontVersion.QUANTUM_BREAK
            and not bitmap_file_path.endswith(".png")
        ):
            raise typer.BadParameter(
                f"{bitmap_file_path} is not a .png file! Quantum Break fonts require a .png bitmap."
            )

        progress.update(cur_task, total=1, completed=True)

        bitmap_file_path = modified_file.parent / bitmap_file_path

        if not bitmap_file_path.exists():
            if binfnt.version in [
                FontVersion.ALAN_WAKE,
                FontVersion.ALAN_WAKE_REMASTERED,
            ]:
                raise typer.BadParameter(f"{bitmap_file_path} does not exist!")

            if binfnt.version == FontVersion.QUANTUM_BREAK:
                # Check if the char directory exists, and if it does, compile the characters into a single bitmap
                char_dir = modified_file.parent / "chars"

                if not char_dir.exists():
                    raise typer.BadParameter(
                        f"Neither {char_dir} or {bitmap_file_path} exist! Please ensure that the character bitmaps are in a directory named 'chars' in the same directory as the .fnt file."
                    )

                cur_task = progress.add_task("Compiling character PNGs to final PNG...")
                compiled_bitmap = Image.new(
                    "RGBA",
                    (binfnt.textureWidth, binfnt.textureHeight),
                    (255, 255, 255, 255),
                )

                for i, char in enumerate(binfnt.characters):
                    idx = binfnt.ids[i]

                    if not (char_dir / f"{idx}.png").exists():
                        continue

                    point = convert_binfnt_char_to_char_entry(
                        char,
                        binfnt.textureWidth,
                        binfnt.textureHeight,
                        binfnt.lineHeight,
                        binfnt.fontSize,
                    )

                    bitmap_char = Image.open(char_dir / f"{idx}.png")
                    compiled_bitmap.paste(bitmap_char, (point.x, point.y))

                progress.update(cur_task, total=1, completed=True)
        else:
            compiled_bitmap = Image.open(bitmap_file_path)

        cur_task = progress.add_task("Converting PNG to DDS Texture...")

        rgba_texture = BytesIO()
        compiled_bitmap.save(rgba_texture, "DDS")
        rgba_texture.seek(0)

        progress.update(cur_task, total=1, completed=True)

        if binfnt.version == FontVersion.QUANTUM_BREAK:
            cur_task = progress.add_task("Processing texture...")
            binfnt.textureBytes = convert_bgra8_to_r16f(rgba_texture)
            progress.update(cur_task, total=1, completed=True)
        else:
            binfnt.textureBytes = rgba_texture.getvalue()

        if output_file:
            output_file = Path(output_file)
        else:
            output_file = modified_file.with_suffix(".binfnt")

        cur_task = progress.add_task("Writing .binfnt file...")

        with open(output_file, "wb") as f:
            binfnt.write(f)

        progress.update(cur_task, total=1, completed=True)


if __name__ == "__main__":
    app()
