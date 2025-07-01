import os
from io import BytesIO
from pathlib import Path
from struct import unpack

from PIL import Image

from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character_rmd import RemedyCharacter
from northlighttools.binfnt.dataclasses.kerning import Kerning
from northlighttools.binfnt.dataclasses.unknown import Unknown
from northlighttools.binfnt.dds import DDS
from northlighttools.binfnt.enumerators.font_version import FontVersion
from northlighttools.rmdp import Progress


class BinaryFont:

    __version: FontVersion = FontVersion.QUANTUM_BREAK

    __texture: Image.Image | None = None
    __texture_size: int | None = None
    __unknown_dds_header: int | None = None

    def __init__(self, progress: Progress, file_path: Path | None = None):
        self.__progress = progress

        self.__characters: list[RemedyCharacter] = []
        self.__unknowns: list[Unknown] = []
        self.__advances: list[Advance] = []
        self.__id_table: list[int] = []
        self.__kernings: list[Kerning] = []

        if file_path is not None:
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
