from io import BytesIO
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image

from northlighttools.binfnt.font import BinaryFont
from northlighttools.binfnt.utilities import convert_r16f_to_bgra8, convert_to_bmfont

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

    with open(input_file, "rb") as f:
        binfnt = BinaryFont(reader=f)
        characters, kernings = convert_to_bmfont(binfnt)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        fnt_file = output_dir / input_file.with_suffix(".fnt").name
    else:
        fnt_file = input_file.with_suffix(".fnt")

    with open(fnt_file, "w") as f:
        f.write(f'info face="" size={binfnt.fontSize} bold=0 italic=0\n')
        f.write(
            f"common lineHeight={binfnt.lineHeight} base=0 scaleW={binfnt.textureWidth} scaleH={binfnt.textureHeight} pages=1\n"
        )
        f.write(f'page id=0 file="{input_file.with_suffix(".png").name}"\n')
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

    if output_dir:
        bitmap_file = output_dir / input_file.with_suffix(".png").name
    else:
        bitmap_file = input_file.with_suffix(".png")

    texture = convert_r16f_to_bgra8(BytesIO(binfnt.textureBytes))
    bitmap = Image.open(BytesIO(texture))

    if separate_chars:
        char_bitmap_dir = output_dir / "chars"
        char_bitmap_dir.mkdir(parents=True, exist_ok=True)

        for char in characters:
            if char.width == 0 or char.height == 0:
                continue

            char_bitmap = bitmap.crop(
                (char.x, char.y, char.x + char.width, char.y + char.height)
            )
            char_bitmap.save(char_bitmap_dir / f"{char.idx}.png")
    else:
        with open(bitmap_file, "wb") as f:
            bitmap.save(f, "PNG")


if __name__ == "__main__":
    app()