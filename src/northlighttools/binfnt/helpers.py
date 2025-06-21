from northlighttools.binfnt.dataclasses.point import Point
from northlighttools.binfnt.dataclasses.uv_mapping import UVMapping
from northlighttools.binfnt.enums.font_version import FontVersion


def get_point_from_uv_mapping(char, width, height):
    x, y = char.xMin_1 * width, char.yMin_1 * height
    return Point(
        x=x, y=y, width=char.xMax_1 * width - x, height=char.yMax_1 * height - y
    )


def get_uv_mapping_from_point(point, width, height):
    return UVMapping(
        UVLeft=point.x / width,
        UVTop=point.y / height,
        UVRight=(point.x + point.width) / width,
        UVBottom=(point.y + point.height) / height,
    )


def get_kernings_for_bmfont(binfnt):
    kernings = []

    if binfnt.version == FontVersion.QUANTUM_BREAK:
        for kerning in binfnt.kerning:
            kerning.amount *= binfnt.fontSize
            kernings.append(kerning)
    elif binfnt.version == FontVersion.ALAN_WAKE_REMASTERED:
        for kerning in binfnt.kerning:
            kerning.amount /= binfnt.fontSize
            kernings.append(kerning)

    return kernings


def write_bmfont_files(binfnt, characters, kernings, out_dir, input_file):
    fnt_file = out_dir / input_file.with_suffix(".fnt").name
    bitmap_file = (
        out_dir
        / input_file.with_suffix(
            ".png" if binfnt.version == FontVersion.QUANTUM_BREAK else ".dds"
        ).name
    )

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

    return bitmap_file
