import json
import os
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from struct import unpack

from PIL import Image

from northlighttools.binfnt.constants import CHARS_FOLDER
from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character_rmd import RemedyCharacter
from northlighttools.binfnt.dataclasses.kerning import Kerning
from northlighttools.binfnt.dataclasses.unknown import Unknown
from northlighttools.binfnt.dds import DDS
from northlighttools.binfnt.enumerators.font_version import FontVersion
from northlighttools.rmdp import Progress


class BinaryFont:

    __version: FontVersion = FontVersion.QUANTUM_BREAK
    __font_name: str = ""

    __texture: Image.Image | None = None
    __texture_size: int | None = None
    __unknown_dds_header: int | None = None

    __line_height: float = 0
    __font_size: float = 0

    def __init__(self, progress: Progress, file_path: Path | None = None):
        self.__progress = progress

        self.__characters: list[RemedyCharacter] = []
        self.__unknowns: list[Unknown] = []
        self.__advances: list[Advance] = []
        self.__id_table: list[int] = []
        self.__kernings: list[Kerning] = []

        if file_path is not None:
            self.__font_name = file_path.stem
            self.__load(file_path)

    def __load(self, file_path: Path):
        with file_path.open("rb") as reader:
            self.__version = FontVersion(int.from_bytes(reader.read(4), "little"))

            self.__read_character_block(reader)
            self.__read_unknown_block(reader)
            self.__read_advance_block(reader)
            self.__read_id_table(reader)
            self.__read_kerning_block(reader)
            self.__read_texture(reader)

            self.__calculate_font_properties()

    def __read_character_block(self, reader):
        self.__progress.console.log("Reading character block...")

        char_count = int.from_bytes(reader.read(4), "little") // 4
        self.__characters = []

        for _ in range(char_count):
            self.__characters.append(RemedyCharacter(*unpack("16f", reader.read(64))))

    def __read_unknown_block(self, reader):
        self.__progress.console.log("Reading unknown block...")

        reader.seek(4, os.SEEK_CUR)  # Skip 4 bytes (integer // 6 = character count)
        self.__unknowns = []

        for _ in range(len(self.__characters)):
            self.__unknowns.append(Unknown(*unpack("6H", reader.read(12))))

    def __read_advance_block(self, reader):
        self.__progress.console.log("Reading advance block...")

        reader.seek(4, os.SEEK_CUR)  # Skip 4 bytes (integer = character count)
        self.__advances = []

        for _ in range(len(self.__characters)):
            self.__advances.append(Advance(*unpack("4HI8f", reader.read(44))))

    def __read_id_table(self, reader):
        self.__progress.console.log("Reading ID table...")

        start_pos = reader.tell()
        current_id = 0

        self.__id_table = []

        while ((reader.tell() - start_pos) / 2) <= 0xFFFF:
            idx = int.from_bytes(reader.read(2), "little")

            if idx != 0:
                self.__id_table.append(current_id)

            current_id += 1

        self.__id_table.insert(0, self.__id_table[0] - 1)

    def __read_kerning_block(self, reader):
        self.__progress.console.log("Reading kerning block...")

        kerning_count = int.from_bytes(reader.read(4), "little")
        self.__kernings = []

        match self.__version:
            case FontVersion.ALAN_WAKE_REMASTERED:
                fmt, size = "2Ii", 12
            case FontVersion.QUANTUM_BREAK:
                fmt, size = "2Hf", 8
            case _:
                return

        for _ in range(kerning_count):
            self.__kernings.append(Kerning(*unpack(fmt, reader.read(size))))

    def __read_texture(self, reader):
        self.__progress.console.log("Reading texture metadata...")

        if self.__version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            self.__texture_size = int.from_bytes(reader.read(4), "little")
        elif self.__version == FontVersion.QUANTUM_BREAK:
            self.__unknown_dds_header = int.from_bytes(reader.read(8), "little")

        self.__progress.console.log("Converting texture to BGRA8 format...")
        converted_texture = DDS.convert_to_bgra8(reader.read())

        self.__progress.console.log("Loading texture into memory...")
        self.__texture = Image.open(BytesIO(converted_texture))

    def __calculate_font_properties(self):
        if not self.__texture:
            self.__progress.console.log(
                "No texture loaded, cannot calculate font properties."
            )
            return

        self.__progress.console.log("Calculating font properties...")

        line_heights, sizes = [], []

        for idx, char in enumerate(self.__characters):
            point = char.to_point(
                texture_width=self.__texture.width,
                texture_height=self.__texture.height,
            )

            try:
                size = point.height / (char.bearingY1_1 - char.bearingY2_1)
            except ZeroDivisionError:
                size = 0

            line_height = (
                -self.__advances[idx].yoffset2_1 * size
                + point.height
                + char.bearingY2_1 * size
            )

            line_heights.append(line_height)
            sizes.append(size)

        self.__line_height = (
            max(set(line_heights), key=line_heights.count) if line_heights else 0
        )
        self.__font_size = max(set(sizes), key=sizes.count) if sizes else 0

    def dump(self, output_path: Path, separate_characters: bool = False):
        if not self.__texture:
            self.__progress.console.log("No texture data available, cannot save font.")
            return

        self.__progress.console.log("Saving font data...")

        # Dump the font data to a json file
        font_path = output_path / f"{self.__font_name}.json"

        with font_path.open("w", encoding="utf-8") as f:
            font_data = {
                "version": self.__version.value,
                "line_height": self.__line_height,
                "font_size": self.__font_size,
                "characters": {
                    self.__id_table[char_id]: asdict(
                        char.to_character(
                            texture_width=self.__texture.width,
                            texture_height=self.__texture.height,
                            advance=self.__advances[char_id],
                            line_height=self.__line_height,
                            font_size=self.__font_size,
                        )
                    )
                    for char_id, char in enumerate(self.__characters)
                },
                "kernings": [
                    asdict(ker.without_font_size(self.__font_size, self.__version))
                    for ker in self.__kernings
                ],
                "unknowns": [asdict(unk) for unk in self.__unknowns],
                "texture_size": self.__texture_size,
                "unknown_dds_header": self.__unknown_dds_header,
            }

            if separate_characters:
                font_data["texture_width"] = self.__texture.width
                font_data["texture_height"] = self.__texture.height

            data = json.dumps(font_data, indent=4, ensure_ascii=False)
            f.write(data)

        if not separate_characters:
            # Save the texture as a PNG file
            self.__progress.console.log("Saving texture as a PNG file...")

            texture_path = font_path.with_suffix(".png")
            self.__texture.save(texture_path, format="PNG")
            return

        # Save each character as a separate PNG file
        self.__progress.console.log("Saving each character as a separate PNG file...")
        chars_dir = output_path / CHARS_FOLDER
        chars_dir.mkdir(parents=True, exist_ok=True)

        for char_id, char in enumerate(self.__characters):
            char_data = char.to_character(
                texture_width=self.__texture.width,
                texture_height=self.__texture.height,
                advance=self.__advances[char_id],
                line_height=self.__line_height,
                font_size=self.__font_size,
            )

            if char_data.width == 0 or char_data.height == 0:
                continue

            char_texture = self.__texture.crop(
                (
                    char_data.x,
                    char_data.y,
                    char_data.x + char_data.width,
                    char_data.y + char_data.height,
                )
            )

            char_texture_path = chars_dir / f"{self.__id_table[char_id]}.png"
            char_texture.save(char_texture_path, format="PNG")
