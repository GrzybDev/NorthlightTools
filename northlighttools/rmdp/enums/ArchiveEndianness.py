from enum import Enum, IntEnum


class ArchiveEndianness(IntEnum):
    LITTLE = 0
    BIG = 1


class ArchiveEndiannessChoice(str, Enum):
    LITTLE = "little"
    BIG = "big"
