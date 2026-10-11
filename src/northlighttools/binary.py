"""Bounds-checked reading and writing of packed binary values."""

import struct
from collections.abc import Iterator
from enum import StrEnum
from functools import cache
from typing import Any

from northlighttools.errors import FormatError


class ByteOrder(StrEnum):
    """Byte order of multi-byte values, as a struct format prefix."""

    LITTLE = "<"
    BIG = ">"


@cache
def packer(byte_order: ByteOrder, fmt: str) -> struct.Struct:
    """Return a cached struct for a format given without its byte order prefix."""
    return struct.Struct(byte_order + fmt)


class BinaryReader:
    """Reads values from a buffer, raising FormatError when reading past its end."""

    def __init__(self, data: bytes, byte_order: ByteOrder = ByteOrder.LITTLE) -> None:
        self._data = memoryview(data)
        self._position = 0
        self.byte_order = byte_order

    @property
    def position(self) -> int:
        return self._position

    @property
    def remaining(self) -> int:
        return len(self._data) - self._position

    def read(self, size: int) -> bytes:
        """Read exactly size bytes."""
        return bytes(self._take(size))

    def unpack(self, fmt: str) -> tuple[Any, ...]:
        """Read the values of a struct format given without its byte order prefix."""
        layout = packer(self.byte_order, fmt)
        return layout.unpack(self._take(layout.size))

    def iter_unpack(self, fmt: str, count: int) -> Iterator[tuple[Any, ...]]:
        """Read count consecutive records of a struct format."""
        layout = packer(self.byte_order, fmt)
        return layout.iter_unpack(self._take(layout.size * count))

    def u8(self) -> int:
        return int(self.unpack("B")[0])

    def u16(self) -> int:
        return int(self.unpack("H")[0])

    def u32(self) -> int:
        return int(self.unpack("I")[0])

    def u64(self) -> int:
        return int(self.unpack("Q")[0])

    def _take(self, size: int) -> memoryview:
        if size < 0 or size > self.remaining:
            msg = (
                f"Unexpected end of data: needed {size} bytes at offset "
                f"{self._position}, {self.remaining} left"
            )
            raise FormatError(msg)
        chunk = self._data[self._position : self._position + size]
        self._position += size
        return chunk


class BinaryWriter:
    """Builds a buffer of packed values."""

    def __init__(self, byte_order: ByteOrder = ByteOrder.LITTLE) -> None:
        self._buffer = bytearray()
        self.byte_order = byte_order

    def __len__(self) -> int:
        return len(self._buffer)

    def write(self, data: bytes | bytearray) -> None:
        self._buffer += data

    def pack(self, fmt: str, *values: Any) -> None:
        """Write values with a struct format given without its byte order prefix."""
        try:
            self._buffer += packer(self.byte_order, fmt).pack(*values)
        except struct.error as error:
            msg = f"Cannot write {values} as {fmt!r}: {error}"
            raise ValueError(msg) from error

    def u8(self, value: int) -> None:
        self.pack("B", value)

    def u16(self, value: int) -> None:
        self.pack("H", value)

    def u32(self, value: int) -> None:
        self.pack("I", value)

    def u64(self, value: int) -> None:
        self.pack("Q", value)

    def getvalue(self) -> bytes:
        return bytes(self._buffer)
