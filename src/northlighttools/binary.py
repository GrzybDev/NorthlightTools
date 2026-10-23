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
    """Return a cached struct for a format given without its byte order prefix.

    Args:
        byte_order: Byte order to prefix the format with.
        fmt: Struct format without a byte order prefix.
    """
    return struct.Struct(byte_order + fmt)


class BinaryReader:
    """Reads values from a buffer, raising FormatError when reading past its end."""

    def __init__(self, data: bytes, byte_order: ByteOrder = ByteOrder.LITTLE) -> None:
        """Start reading at the beginning of a buffer.

        Args:
            data: Buffer to read from.
            byte_order: Byte order of multi-byte values.
        """
        self._data = memoryview(data)
        self._position = 0
        self.byte_order = byte_order

    @property
    def position(self) -> int:
        """Offset of the next byte to read."""
        return self._position

    @property
    def remaining(self) -> int:
        """Number of bytes left to read."""
        return len(self._data) - self._position

    def read(self, size: int) -> bytes:
        """Read exactly size bytes.

        Args:
            size: Number of bytes to read.
        """
        return bytes(self._take(size))

    def unpack(self, fmt: str) -> tuple[Any, ...]:
        """Read the values of a struct format given without its byte order prefix.

        Args:
            fmt: Struct format without a byte order prefix.
        """
        layout = packer(self.byte_order, fmt)
        return layout.unpack(self._take(layout.size))

    def iter_unpack(self, fmt: str, count: int) -> Iterator[tuple[Any, ...]]:
        """Read count consecutive records of a struct format.

        Args:
            fmt: Struct format of one record, without a byte order prefix.
            count: Number of records to read.
        """
        layout = packer(self.byte_order, fmt)
        return layout.iter_unpack(self._take(layout.size * count))

    def u8(self) -> int:
        """Read an unsigned 8-bit integer."""
        return int(self.unpack("B")[0])

    def u16(self) -> int:
        """Read an unsigned 16-bit integer."""
        return int(self.unpack("H")[0])

    def u32(self) -> int:
        """Read an unsigned 32-bit integer."""
        return int(self.unpack("I")[0])

    def u64(self) -> int:
        """Read an unsigned 64-bit integer."""
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
        """Start an empty buffer.

        Args:
            byte_order: Byte order of multi-byte values.
        """
        self._buffer = bytearray()
        self.byte_order = byte_order

    def __len__(self) -> int:
        return len(self._buffer)

    def write(self, data: bytes | bytearray) -> None:
        """Append raw bytes.

        Args:
            data: Bytes to append.
        """
        self._buffer += data

    def pack(self, fmt: str, *values: Any) -> None:
        """Write values with a struct format given without its byte order prefix.

        Args:
            fmt: Struct format without a byte order prefix.
            *values: One value per field of the format.
        """
        try:
            self._buffer += packer(self.byte_order, fmt).pack(*values)
        except struct.error as error:
            msg = f"Cannot write {values} as {fmt!r}: {error}"
            raise ValueError(msg) from error

    def u8(self, value: int) -> None:
        """Write an unsigned 8-bit integer.

        Args:
            value: Integer to write.
        """
        self.pack("B", value)

    def u16(self, value: int) -> None:
        """Write an unsigned 16-bit integer.

        Args:
            value: Integer to write.
        """
        self.pack("H", value)

    def u32(self, value: int) -> None:
        """Write an unsigned 32-bit integer.

        Args:
            value: Integer to write.
        """
        self.pack("I", value)

    def u64(self, value: int) -> None:
        """Write an unsigned 64-bit integer.

        Args:
            value: Integer to write.
        """
        self.pack("Q", value)

    def getvalue(self) -> bytes:
        """Return the bytes written so far."""
        return bytes(self._buffer)
