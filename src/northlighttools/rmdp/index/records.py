"""The folder and file records of a package index, shared by decoding and encoding."""

from dataclasses import dataclass

from northlighttools.binary import ByteOrder

BASE_PATH_SIZE = 128


@dataclass(slots=True)
class FolderRecord:
    checksum: int
    next_sibling: int
    parent: int
    name_offset: int
    first_child: int
    first_file: int


@dataclass(slots=True)
class FileRecord:
    checksum: int
    next_sibling: int
    parent: int
    flags: int
    name_offset: int
    offset: int
    size: int
    data_checksum: int
    timestamp: int


def stored_checksum(value: int, byte_order: ByteOrder) -> int:
    """Swap a data checksum between the package's byte order and its stored one.

    Args:
        value: The checksum to swap.
        byte_order: Byte order of the package.
    """
    # The engine stores data checksums little-endian even in big-endian packages.
    if byte_order is ByteOrder.LITTLE:
        return value
    return int.from_bytes(value.to_bytes(4, "big"), "little")
