import os
from pathlib import Path
from struct import unpack

from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character_rmd import RemedyCharacter
from northlighttools.binfnt.dataclasses.unknown import Unknown
from northlighttools.binfnt.enumerators.font_version import FontVersion
from northlighttools.rmdp import Progress


class BinaryFont:

    __version: FontVersion = FontVersion.QUANTUM_BREAK

    def __init__(self, progress: Progress, file_path: Path | None = None):
        self.__progress = progress

        self.__characters: list[RemedyCharacter] = []
        self.__unknowns: list[Unknown] = []
        self.__advances: list[Advance] = []

        if file_path is not None:
            self.__load(file_path)

    def __load(self, file_path: Path):
        with file_path.open("rb") as reader:
            self.__version = FontVersion(int.from_bytes(reader.read(4), "little"))

            self.__read_character_block(reader)
            self.__read_unknown_block(reader)
            self.__read_advance_block(reader)

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
