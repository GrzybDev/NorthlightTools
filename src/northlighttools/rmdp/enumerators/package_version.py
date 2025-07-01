from enum import Enum, IntEnum


class PackageVersion(IntEnum):
    ALAN_WAKE = 2
    ALAN_WAKE_AMERICAN_NIGHTMARE = 7
    QUANTUM_BREAK = 8
    CONTROL = 9


class PackageVersionChoice(str, Enum):
    ALAN_WAKE = "2"
    ALAN_WAKE_AMERICAN_NIGHTMARE = "7"
    QUANTUM_BREAK = "8"
    CONTROL = "9"
