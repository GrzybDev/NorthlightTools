from pathlib import Path

from northlighttools.rmdp.enumerators.endianness import Endianness
from northlighttools.rmdp.enumerators.package_version import PackageVersion


class Package:

    __endianness: Endianness = Endianness.LITTLE
    __version: PackageVersion = PackageVersion.QUANTUM_BREAK

    @property
    def endianness(self) -> Endianness:
        return self.__endianness

    @property
    def version(self) -> PackageVersion:
        return self.__version

    @property
    def unknown_data(self) -> dict[str, bytes | int]:
        return self.__unknown_data

    def __init__(self, header_path: Path | None = None):
        self.__unknown_data = {}

        if header_path:
            self.__read_header(header_path)

    def __read_header(self, header_path: Path):
        with header_path.open("rb") as f:
            self.__endianness = Endianness(self.__read_int(f, 1))
            self.__version = PackageVersion(self.__read_int(f, 4))

            self.__unknown_data["meta_value_1"] = self.__read_int(f, 4)
            self.__unknown_data["meta_value_2"] = self.__read_int(f, 4)

            if self.__version == PackageVersion.ALAN_WAKE:
                self.__unknown_data["header_value_1"] = self.__read_int(f, 4)
                self.__unknown_data["header_data"] = f.read(0x80)
            else:
                self.__unknown_data["header_value_1"] = self.__read_int(f, 8)
                self.__unknown_data["header_value_2"] = self.__read_int(f, 4)
                self.__unknown_data["header_data"] = f.read(0x80)

    def __read_int(self, f, size: int) -> int:
        return int.from_bytes(
            f.read(size), byteorder=self.__endianness.name.lower()  # type: ignore
        )
