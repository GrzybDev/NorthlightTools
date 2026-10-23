from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from northlighttools.binary import ByteOrder
from northlighttools.rmdp.formats import PackageFormat
from northlighttools.rmdp.names import PackagePath

_FILETIME_UNIX_EPOCH = 116_444_736_000_000_000
_FILETIME_ORIGIN = datetime(1601, 1, 1, tzinfo=UTC)


def filetime_from_ns(nanoseconds: int) -> int:
    """Convert nanoseconds since the Unix epoch to a Windows FILETIME.

    Args:
        nanoseconds: Time since the Unix epoch, in nanoseconds.
    """
    return nanoseconds // 100 + _FILETIME_UNIX_EPOCH


def filetime_to_ns(filetime: int) -> int:
    """Convert a Windows FILETIME to nanoseconds since the Unix epoch.

    Args:
        filetime: Time since 1601 in 100-nanosecond units.
    """
    return (filetime - _FILETIME_UNIX_EPOCH) * 100


def filetime_to_datetime(filetime: int) -> datetime | None:
    """Return the moment a Windows FILETIME stands for, or None past the year 9999.

    Args:
        filetime: Time since 1601 in 100-nanosecond units.
    """
    try:
        return _FILETIME_ORIGIN + timedelta(microseconds=filetime // 10)
    except OverflowError:
        return None


@dataclass(frozen=True, slots=True)
class PackageFile:
    """A file stored in a package."""

    path: PackagePath
    offset: int
    size: int
    checksum: int
    """CRC-32 of the file's data."""
    timestamp: int | None = None
    """Last write time as a Windows FILETIME, in formats that store one."""
    flags: int = 0
    """Stored as found; zero in every package of the supported games."""

    @property
    def name(self) -> str:
        """The file's own name, the last part of its path."""
        return self.path[-1]


@dataclass
class Package:
    """The index of a package: where each file lies in its data (.rmdp) file."""

    format: PackageFormat
    byte_order: ByteOrder
    base_path: str
    folders: list[PackagePath]
    """Every folder but the unnamed root, including empty ones."""
    files: list[PackageFile]
    extra_paths: list[str] = field(default_factory=list)
    """Paths listed after the names, found only in one Alan Wake Remastered package;
    what the game does with them is unknown."""
    header_value: int = 1
    """Unknown header value of formats with timestamps; 1 in every known package."""

    @property
    def data_size(self) -> int:
        """Total size of the files' data in bytes."""
        return sum(file.size for file in self.files)
