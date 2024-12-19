import os
from io import BufferedReader, BufferedWriter
from struct import pack, unpack

import numpy as np

from northlighttools.binfnt.dataclasses.Advance import Advance
from northlighttools.binfnt.dataclasses.Character import Character
from northlighttools.binfnt.dataclasses.Kernel import Kernel
from northlighttools.binfnt.dataclasses.Unknown import Unknown
from northlighttools.binfnt.enums.FontVersion import FontVersion
from northlighttools.binfnt.utilities import get_point_from_uv_mapping


class BinaryFont:

    version: FontVersion
    characters: list[Character] = []
    unknown: list[Unknown] = []
    advance: list[Advance] = []
    ids: list[int] = []
    kerning: list[Kernel] = []

    textureWidth: int
    textureHeight: int
    textureBytes: bytes

    fontSize: float = 0
    lineHeight: float = 0

    def __init__(self, reader):
        self.reader: BufferedReader = reader
        self.parse()

    def parse(self):
        self.version = FontVersion(
            int.from_bytes(self.reader.read(4), "little", signed=False)
        )

        self.__read_char_block()
        self.__read_unknown_block()
        self.__read_advance_block()
        self.__read_id_block()
        self.__read_kernel_block()

        self.__read_texture()

    def __read_char_block(self):
        char_count = int.from_bytes(self.reader.read(4), "little", signed=False) // 4

        for _ in range(char_count):
            char_vals = unpack("16f", self.reader.read(4 * 16))
            self.characters.append(Character(*char_vals))

    def __read_unknown_block(self):
        unknown_entries = (
            int.from_bytes(self.reader.read(4), "little", signed=False) // 6
        )

        for _ in range(len(self.characters)):
            unknown_vals = unpack("6H", self.reader.read(2 * 6))
            self.unknown.append(Unknown(*unknown_vals))

    def __read_advance_block(self):
        advance_count = int.from_bytes(self.reader.read(4), "little", signed=False)

        for _ in range(len(self.characters)):
            advance_vals = unpack("4HI8f", self.reader.read(2 * 4 + 4 + 8 * 4))
            self.advance.append(Advance(*advance_vals))

    def __read_id_block(self):
        start_pos = self.reader.tell()

        baseId = 0
        while (self.reader.tell() - start_pos) / 2 <= 0xFFFF:
            idx = int.from_bytes(self.reader.read(2), "little", signed=False)

            if idx != 0:
                self.ids.append(baseId)

            baseId += 1

        self.ids.insert(0, self.ids[0] - 1)

    def __read_kernel_block(self):
        kerns_count = int.from_bytes(self.reader.read(4), "little", signed=False)

        if self.version == FontVersion.QUANTUM_BREAK:
            format_str = "2Hf"
            read_size = 2 * 2 + 4
        elif self.version == FontVersion.ALAN_WAKE_REMASTERED:
            format_str = "2If"
            read_size = 2 * 4 + 4
        else:
            raise ValueError("Unsupported font version")

        for _ in range(kerns_count):
            kern_vals = unpack(format_str, self.reader.read(read_size))
            self.kerning.append(Kernel(*kern_vals))

    def __read_texture(self):
        if self.version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            textureSize = int.from_bytes(self.reader.read(4), "little", signed=False)
        elif self.version == FontVersion.QUANTUM_BREAK:
            self.textureUnknownVal = self.reader.read(8)

        texturePos = self.reader.tell()
        self.reader.seek(12, os.SEEK_CUR)

        self.textureHeight = int.from_bytes(self.reader.read(4), "little", signed=False)
        self.textureWidth = int.from_bytes(self.reader.read(4), "little", signed=False)

        self.reader.seek(texturePos)
        self.textureBytes = self.reader.read()

        sizes = []
        lineHeights = []

        for idx, char in enumerate(self.characters):
            point = get_point_from_uv_mapping(
                char, self.textureWidth, self.textureHeight
            )

            # Calculate size
            try:
                size = point.height / (char.bearingY1_1 - char.bearingY2_1)
            except ZeroDivisionError:
                size = 0

            # Calculate line height
            lineHeight = (
                -self.advance[idx].yoffset2_1 * size
                + point.height
                + char.bearingY2_1 * size
            )

            sizes.append(size)
            lineHeights.append(lineHeight)

        self.fontSize = max(set(sizes), key=sizes.count)
        self.lineHeight = max(set(lineHeights), key=lineHeights.count)

    def write(self, writer: BufferedWriter):
        writer.write(self.version.value.to_bytes(4, "little", signed=False))

        self.__write_char_block(writer)
        self.__write_unknown_block(writer)
        self.__write_advance_block(writer)
        self.__write_id_block(writer)
        self.__write_kernel_block(writer)

        self.__write_texture(writer)

    def __write_char_block(self, writer: BufferedWriter):
        writer.write((len(self.characters) * 4).to_bytes(4, "little", signed=False))
        for char in self.characters:
            writer.write(pack("f", char.bearingX1_1))
            writer.write(pack("f", char.bearingY2_1))
            writer.write(pack("f", char.xMin_1))
            writer.write(pack("f", char.yMax_1))
            writer.write(pack("f", char.bearingX2_1))
            writer.write(pack("f", char.bearingY2_2))
            writer.write(pack("f", char.xMax_1))
            writer.write(pack("f", char.yMax_2))
            writer.write(pack("f", char.bearingX2_2))
            writer.write(pack("f", char.bearingY1_1))
            writer.write(pack("f", char.xMax_2))
            writer.write(pack("f", char.yMin_1))
            writer.write(pack("f", char.bearingX1_2))
            writer.write(pack("f", char.bearingY1_2))
            writer.write(pack("f", char.xMin_2))
            writer.write(pack("f", char.yMin_2))

    def __write_unknown_block(self, writer: BufferedWriter):
        writer.write((len(self.unknown) * 6).to_bytes(4, "little", signed=False))

        last_entry = None

        for i in range(len(self.characters)):
            # If we reached the end of the unknown list, write the last unknown entry till the end
            if last_entry == self.unknown[-1]:
                writer.write(pack("H", self.unknown[-1].n1))
                writer.write(pack("H", self.unknown[-1].n2))
                writer.write(pack("H", self.unknown[-1].n3))
                writer.write(pack("H", self.unknown[-1].n4))
                writer.write(pack("H", self.unknown[-1].n5))
                writer.write(pack("H", self.unknown[-1].n6))
            else:
                writer.write(pack("H", self.unknown[i].n1))
                writer.write(pack("H", self.unknown[i].n2))
                writer.write(pack("H", self.unknown[i].n3))
                writer.write(pack("H", self.unknown[i].n4))
                writer.write(pack("H", self.unknown[i].n5))
                writer.write(pack("H", self.unknown[i].n6))
                last_entry = self.unknown[i]

    def __write_advance_block(self, writer: BufferedWriter):
        writer.write(len(self.advance).to_bytes(4, "little", signed=False))

        for advance in self.advance:
            writer.write(pack("H", advance.plus4))
            writer.write(pack("H", advance.num4))
            writer.write(pack("H", advance.plus6))
            writer.write(pack("H", advance.num6))
            writer.write(pack("I", advance.chnl))
            writer.write(pack("f", advance.xadvance1_1))
            writer.write(pack("f", advance.yoffset1_1))
            writer.write(pack("f", advance.xadvance2_1))
            writer.write(pack("f", advance.yoffset1_2))
            writer.write(pack("f", advance.xadvance2_2))
            writer.write(pack("f", advance.yoffset2_1))
            writer.write(pack("f", advance.xadvance1_2))
            writer.write(pack("f", advance.yoffset2_2))

    def __write_id_block(self, writer: BufferedWriter):
        id_table = np.zeros(0xFFFF + 1, dtype=np.uint16)
        base_id = 0

        for idx in self.ids:
            id_table[idx] = base_id
            base_id += 1

        for idx in id_table.tolist():
            writer.write(idx.to_bytes(2, "little", signed=False))

    def __write_kernel_block(self, writer: BufferedWriter):
        writer.write(len(self.kerning).to_bytes(4, "little", signed=False))

        for kerning in self.kerning:
            writer.write(pack("2H", kerning.first, kerning.second))
            writer.write(pack("f", kerning.amount))

    def __write_texture(self, writer: BufferedWriter):
        if self.version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            writer.write(len(self.textureBytes).to_bytes(4, "little", signed=False))
        elif self.version == FontVersion.QUANTUM_BREAK:
            writer.write(self.textureUnknownVal)

        writer.write(self.textureBytes)
