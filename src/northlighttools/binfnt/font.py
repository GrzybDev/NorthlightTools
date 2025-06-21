import os
from struct import unpack

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
