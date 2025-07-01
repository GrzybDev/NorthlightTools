from enum import Enum, IntEnum


class Endianness(IntEnum):
    LITTLE = 0
    BIG = 1


class EndiannessChoice(str, Enum):
    LITTLE = "little"
    BIG = "big"
