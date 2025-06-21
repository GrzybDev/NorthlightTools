import os
from struct import pack, unpack

import numpy as np

from northlighttools.binfnt.dataclasses.advance import Advance
from northlighttools.binfnt.dataclasses.character import Character
from northlighttools.binfnt.dataclasses.kernel import Kernel
from northlighttools.binfnt.dataclasses.unknown import Unknown
from northlighttools.binfnt.enums.font_version import FontVersion
from northlighttools.binfnt.utilities import get_point_from_uv_mapping


class BinaryFont:
    """Binary font reader/writer for .binfnt files."""

    def __init__(self, reader):
        self.reader = reader
        self.characters = []
        self.unknown = []
        self.advance = []
        self.ids = []
        self.kerning = []
        self.parse()

    def parse(self):
        self.version = FontVersion(int.from_bytes(self.reader.read(4), "little"))
        self._read_char_block()
        self._read_unknown_block()
        self._read_advance_block()
        self._read_id_block()
        self._read_kernel_block()
        self._read_texture()

    def _read_char_block(self):
        count = int.from_bytes(self.reader.read(4), "little") // 4

        for _ in range(count):
            self.characters.append(Character(*unpack("16f", self.reader.read(64))))

    def _read_unknown_block(self):
        self.reader.read(4)  # skip count

        for _ in range(len(self.characters)):
            self.unknown.append(Unknown(*unpack("6H", self.reader.read(12))))

    def _read_advance_block(self):
        self.reader.read(4)

        for _ in range(len(self.characters)):
            self.advance.append(Advance(*unpack("4HI8f", self.reader.read(44))))

    def _read_id_block(self):
        start = self.reader.tell()
        baseId = 0

        while (self.reader.tell() - start) / 2 <= 0xFFFF:
            idx = int.from_bytes(self.reader.read(2), "little")
            if idx != 0:
                self.ids.append(baseId)
            baseId += 1

        if self.ids:
            self.ids.insert(0, self.ids[0] - 1)

    def _read_kernel_block(self):
        kerns_count = int.from_bytes(self.reader.read(4), "little")

        if self.version == FontVersion.QUANTUM_BREAK:
            fmt, size = "2Hf", 8
        elif self.version == FontVersion.ALAN_WAKE_REMASTERED:
            fmt, size = "2If", 12
        else:
            raise ValueError("Unsupported font version")

        for _ in range(kerns_count):
            self.kerning.append(Kernel(*unpack(fmt, self.reader.read(size))))

    def _read_texture(self):
        if self.version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            self.reader.read(4)
        elif self.version == FontVersion.QUANTUM_BREAK:
            self.textureUnknownVal = self.reader.read(8)

        pos = self.reader.tell()
        self.reader.seek(12, os.SEEK_CUR)
        self.textureHeight = int.from_bytes(self.reader.read(4), "little")
        self.textureWidth = int.from_bytes(self.reader.read(4), "little")
        self.reader.seek(pos)
        self.textureBytes = self.reader.read()
        self._calculate_font_metrics()

    def _calculate_font_metrics(self):
        sizes, lineHeights = [], []

        for idx, char in enumerate(self.characters):
            point = get_point_from_uv_mapping(
                char, self.textureWidth, self.textureHeight
            )

            try:
                size = point.height / (char.bearingY1_1 - char.bearingY2_1)
            except ZeroDivisionError:
                size = 0

            lineHeight = (
                -self.advance[idx].yoffset2_1 * size
                + point.height
                + char.bearingY2_1 * size
            )

            sizes.append(size)
            lineHeights.append(lineHeight)

        self.fontSize = max(set(sizes), key=sizes.count) if sizes else 0
        self.lineHeight = (
            max(set(lineHeights), key=lineHeights.count) if lineHeights else 0
        )

    def write(self, writer):
        writer.write(self.version.value.to_bytes(4, "little"))
        self._write_char_block(writer)
        self._write_unknown_block(writer)
        self._write_advance_block(writer)
        self._write_id_block(writer)
        self._write_kernel_block(writer)
        self._write_texture(writer)

    def _write_char_block(self, writer):
        writer.write((len(self.characters) * 4).to_bytes(4, "little"))
        for char in self.characters:
            writer.write(pack("16f", *char.__dict__.values()))

    def _write_unknown_block(self, writer):
        writer.write((len(self.unknown) * 6).to_bytes(4, "little"))
        for i in range(len(self.characters)):
            u = self.unknown[min(i, len(self.unknown) - 1)]
            writer.write(pack("6H", u.n1, u.n2, u.n3, u.n4, u.n5, u.n6))

    def _write_advance_block(self, writer):
        writer.write(len(self.advance).to_bytes(4, "little"))
        for adv in self.advance:
            writer.write(
                pack(
                    "4HI8f",
                    adv.plus4,
                    adv.num4,
                    adv.plus6,
                    adv.num6,
                    adv.chnl,
                    adv.xadvance1_1,
                    adv.yoffset1_1,
                    adv.xadvance2_1,
                    adv.yoffset1_2,
                    adv.xadvance2_2,
                    adv.yoffset2_1,
                    adv.xadvance1_2,
                    adv.yoffset2_2,
                )
            )

    def _write_id_block(self, writer):
        id_table = np.zeros(0xFFFF + 1, dtype=np.uint16)
        base_id = 0
        for idx in self.ids:
            id_table[idx] = base_id
            base_id += 1
        for idx in id_table.tolist():
            writer.write(idx.to_bytes(2, "little"))

    def _write_kernel_block(self, writer):
        writer.write(len(self.kerning).to_bytes(4, "little"))
        for kerning in self.kerning:
            writer.write(pack("2Hf", kerning.first, kerning.second, kerning.amount))

    def _write_texture(self, writer):
        if self.version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            writer.write(len(self.textureBytes).to_bytes(4, "little"))
        elif self.version == FontVersion.QUANTUM_BREAK:
            writer.write(self.textureUnknownVal)
        writer.write(self.textureBytes)
