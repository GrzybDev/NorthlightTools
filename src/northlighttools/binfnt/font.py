import os
import xml.etree.ElementTree as ET
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from struct import pack, unpack

import numpy as np
from PIL import Image

from northlighttools.binfnt.constants import ATLAS_NULL_COLOR, CHARS_FOLDER
from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character import Character
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

    def __get_character_by_id(self, char_id: int) -> str:
        return repr(str(chr(self.__id_table[char_id])))[1:-1]

    def decompile(self, output_path: Path, separate_characters: bool = False):
        if not self.__texture:
            self.__progress.console.log("No texture data available, cannot save font.")
            return

        self.__progress.console.log("Saving font data...")

        # Dump the font data to a xml file
        font_path = output_path / f"{self.__font_name}.xml"

        root = ET.Element(
            "BinaryFont",
            version=str(self.__version.value),
            line_height=str(self.__line_height),
            font_size=str(self.__font_size),
        )

        # Characters
        chars_elem = ET.SubElement(root, "Characters")
        for char_id, char in enumerate(self.__characters):
            char_data = char.to_character(
                texture_width=self.__texture.width,
                texture_height=self.__texture.height,
                advance=self.__advances[char_id],
                line_height=self.__line_height,
                font_size=self.__font_size,
            )

            ET.SubElement(
                chars_elem,
                "Character",
                index=str(self.__id_table[char_id]),
                char=self.__get_character_by_id(char_id),
                x=str(char_data.x),
                y=str(char_data.y),
                width=str(char_data.width),
                height=str(char_data.height),
                xoffset=str(char_data.xoffset),
                yoffset=str(char_data.yoffset),
                xadvance=str(char_data.xadvance),
                chnl=str(char_data.chnl),
            )

        # Kernings
        kerns_elem = ET.SubElement(root, "Kernings")
        for kern in self.__kernings:
            ET.SubElement(
                kerns_elem,
                "Kerning",
                first=str(kern.first),
                second=str(kern.second),
                amount=str(kern.amount),
            )

        # Unknowns
        unks_elem = ET.SubElement(root, "Unknowns")
        for unk in self.__unknowns:
            ET.SubElement(
                unks_elem,
                "Unknown",
                n1=str(unk.n1),
                n2=str(unk.n2),
                n3=str(unk.n3),
                n4=str(unk.n4),
                n5=str(unk.n5),
                n6=str(unk.n6),
            )

        # Texture
        texture_elem = ET.SubElement(root, "Texture")
        if self.__texture_size is not None:
            ET.SubElement(texture_elem, "Size").text = str(self.__texture_size)

        if separate_characters:
            ET.SubElement(texture_elem, "Width").text = str(self.__texture.width)
            ET.SubElement(texture_elem, "Height").text = str(self.__texture.height)

        # Unknown DDS Header
        if self.__unknown_dds_header is not None:
            ET.SubElement(
                root,
                "UnknownDDSHeader",
            ).text = str(self.__unknown_dds_header)

        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(font_path, encoding="utf-8", xml_declaration=True)

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

    def __char_to_id(self, char_id: str) -> int:
        try:
            return ord(char_id.encode("utf-8").decode("unicode_escape"))
        except:
            return ord(char_id)

    def compile(self, meta_path: Path, separate_characters: bool = False):
        self.__progress.console.log("Loading font data...")

        with meta_path.open("r", encoding="utf-8") as f:
            font_data = ET.parse(f).getroot()

        if not separate_characters:
            texture_width, texture_height = Image.open(
                meta_path.with_suffix(".png")
            ).size
        else:
            __texture_width = font_data.find("Texture/Width")
            __texture_height = font_data.find("Texture/Height")

            if (__texture_width is None or __texture_width.text is None) or (
                __texture_height is None or __texture_height.text is None
            ):
                raise ValueError(
                    "Texture width and height elements must be provided for separate characters."
                )

            texture_width = int(__texture_width.text)
            texture_height = int(__texture_height.text)

        self.__version = FontVersion(
            int(font_data.attrib.get("version", str(FontVersion.QUANTUM_BREAK.value)))
        )
        self.__line_height = float(font_data.attrib.get("line_height", "0"))
        self.__font_size = float(font_data.attrib.get("font_size", "0"))

        characters_elem = font_data.find("Characters")
        if characters_elem is None:
            raise ValueError("Characters element not found in metadata file.")

        chars = {}
        char_index_map = {}

        for char_elem in characters_elem.findall("Character"):
            char_id = char_elem.attrib.get("char")

            if char_id is None:
                raise ValueError("Character ID (char attribute) is missing in XML.")

            char_id = self.__char_to_id(char_id)

            char_data = {
                "x": int(char_elem.attrib.get("x", "0")),
                "y": int(char_elem.attrib.get("y", "0")),
                "width": int(char_elem.attrib.get("width", "0")),
                "height": int(char_elem.attrib.get("height", "0")),
                "xoffset": float(char_elem.attrib.get("xoffset", "0")),
                "yoffset": float(char_elem.attrib.get("yoffset", "0")),
                "xadvance": float(char_elem.attrib.get("xadvance", "0")),
                "chnl": int(char_elem.attrib.get("chnl", "0")),
            }

            chars[char_id] = Character(**char_data)
            char_index_map[char_id] = int(char_elem.attrib.get("index", "0"))

        self.__characters = [
            chars[char_id].to_remedy_character(
                char_id,
                texture_width,
                texture_height,
                self.__line_height,
                self.__font_size,
            )
            for char_id in chars.keys()
        ]

        self.__advances = [
            Advance.calculate_values(
                char,
                idx,
                self.__font_size,
            )
            for idx, char in enumerate(chars.values())
        ]

        kernings_elem = font_data.find("Kernings")

        if kernings_elem is None:
            raise ValueError("Kernings element not found in metadata file.")

        self.__kernings = [
            Kerning(
                first=int(kerning_elem.attrib.get("first", "0")),
                second=int(kerning_elem.attrib.get("second", "0")),
                amount=float(kerning_elem.attrib.get("amount", "0")),
            ).with_font_size(self.__font_size, self.__version)
            for kerning_elem in kernings_elem.findall("Kerning")
        ]

        unknowns_elem = font_data.find("Unknowns")
        if unknowns_elem is None:
            raise ValueError("Unknowns element not found in metadata file.")

        self.__unknowns = [
            Unknown(
                n1=int(unknown_elem.attrib.get("n1", "0")),
                n2=int(unknown_elem.attrib.get("n2", "0")),
                n3=int(unknown_elem.attrib.get("n3", "0")),
                n4=int(unknown_elem.attrib.get("n4", "0")),
                n5=int(unknown_elem.attrib.get("n5", "0")),
                n6=int(unknown_elem.attrib.get("n6", "0")),
            )
            for unknown_elem in unknowns_elem.findall("Unknown")
        ]

        self.__id_table = list(chars.keys())
        __texture_size = font_data.find("Texture/Size")

        if __texture_size is not None and __texture_size.text is not None:
            self.__texture_size = int(__texture_size.text)

        unknown_dds_header_elem = font_data.find("UnknownDDSHeader")
        if (
            unknown_dds_header_elem is not None
            and unknown_dds_header_elem.text is not None
        ):
            self.__unknown_dds_header = int(unknown_dds_header_elem.text)

        # Load the texture if it exists
        texture_path = meta_path.with_suffix(".png")

        if texture_path.exists():
            self.__progress.console.log("Loading texture from PNG file...")
            self.__texture = Image.open(texture_path)
        else:
            self.__progress.console.log("Creating empty texture atlas...")
            self.__texture = Image.new(
                "RGBA", (texture_width, texture_height), ATLAS_NULL_COLOR
            )

            if not self.__texture:
                raise ValueError("Failed to create empty texture atlas.")

            chars_path = meta_path.parent / CHARS_FOLDER

            self.__progress.console.log(
                "Creating texture atlas from character files..."
            )
            for idx, char_data in enumerate(chars.values()):
                # Use index from XML to get character to load
                char_idx = char_index_map[self.__id_table[idx]]
                char_path = chars_path / f"{char_idx}.png"

                if char_data.width == 0 or char_data.height == 0:
                    continue

                if char_path.exists():
                    char_texture = Image.open(char_path)
                    self.__texture.paste(
                        char_texture,
                        (
                            char_data.x,
                            char_data.y,
                            char_data.x + char_data.width,
                            char_data.y + char_data.height,
                        ),
                    )
                else:
                    self.__progress.console.log(
                        f"Warning: Character texture file not found: {char_path}"
                    )

    def save(self, output_path: Path):
        if not self.__texture:
            raise ValueError("Texture is not loaded. Cannot compile.")

        self.__progress.console.log("Converting texture to DDS format...")

        texture_data = BytesIO()
        self.__texture.save(texture_data, format="DDS")
        texture_bytes = texture_data.getvalue()

        if self.__version == FontVersion.QUANTUM_BREAK:
            self.__progress.console.log("Converting texture to R16_FLOAT format...")
            texture_bytes = DDS.convert_to_r16f(texture_bytes)

        self.__progress.console.log("Writing font to file...")
        with output_path.open("wb") as writer:
            writer.write(self.__version.value.to_bytes(4, "little"))

            self.__write_character_block(writer)
            self.__write_unknown_block(writer)
            self.__write_advance_block(writer)
            self.__write_id_table(writer)
            self.__write_kerning_block(writer)
            self.__write_texture(writer, texture_bytes)

    def __write_character_block(self, writer):
        writer.write((len(self.__characters) * 4).to_bytes(4, "little"))

        for char in self.__characters:
            writer.write(pack("16f", *asdict(char).values()))

    def __write_unknown_block(self, writer):
        writer.write((len(self.__unknowns) * 6).to_bytes(4, "little"))

        for unk in self.__unknowns:
            writer.write(pack("6H", *asdict(unk).values()))

    def __write_advance_block(self, writer):
        writer.write((len(self.__advances)).to_bytes(4, "little"))

        for adv in self.__advances:
            writer.write(pack("4HI8f", *asdict(adv).values()))

    def __write_id_table(self, writer):
        id_table = np.zeros(0xFFFF + 1, dtype=np.uint16)
        base_id = 0

        for idx in self.__id_table:
            id_table[int(idx)] = base_id
            base_id += 1

        for idx in id_table.tolist():
            writer.write(idx.to_bytes(2, "little"))

    def __write_kerning_block(self, writer):
        writer.write(len(self.__kernings).to_bytes(4, "little"))

        match self.__version:
            case FontVersion.ALAN_WAKE_REMASTERED:
                fmt = "2Ii"
            case FontVersion.QUANTUM_BREAK:
                fmt = "2Hf"
            case _:
                return

        for ker in self.__kernings:
            writer.write(pack(fmt, *asdict(ker).values()))

    def __write_texture(self, writer, texture_bytes):
        if self.__version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            writer.write(len(texture_bytes).to_bytes(4, "little"))
        elif self.__version == FontVersion.QUANTUM_BREAK:
            writer.write((self.__unknown_dds_header or 0).to_bytes(8, "little"))

        writer.write(texture_bytes)
