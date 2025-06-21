import os
from datetime import datetime, timezone

from northlighttools.rmdp.constants import EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS
from northlighttools.rmdp.enumerators.endianness import Endianness
from northlighttools.rmdp.enumerators.package_version import PackageVersion


def get_endianness(endianness_id: int) -> Endianness:
    match endianness_id:
        case 0:
            return Endianness.LITTLE
        case 1:
            return Endianness.BIG
        case _:
            raise ValueError(
                f"Unknown endianness: {endianness_id}. Expected 0 (little) or 1 (big)."
            )


def get_package_version(version_id: int) -> PackageVersion:
    return PackageVersion(str(version_id))


def read_name(f, name_block_length: int, name_offset: int) -> str:
    if name_offset in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return ""

    start_pos = f.tell()
    f.seek(-name_block_length + name_offset, os.SEEK_END)

    # Read null-terminated string
    result = ""

    while (char := f.read(1)) != b"\x00":
        result += char.decode("utf-8")

    f.seek(start_pos)  # Reset file pointer to original position
    return result


def filetime_to_dt(ft: int) -> datetime:
    # Get seconds and remainder in terms of Unix epoch
    s, ns100 = divmod(ft - EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
    # Convert to datetime object, with remainder as microseconds.
    return datetime.fromtimestamp(s, tz=timezone.utc).replace(microsecond=(ns100 // 10))
