from pathlib import Path

from northlighttools.binfnt.enumerators.font_version import FontVersion


class BinaryFont:

    __version: FontVersion = FontVersion.QUANTUM_BREAK

    def __init__(self, file_path: Path | None = None):
        if file_path is not None:
            self.__load(file_path)

    def __load(self, file_path: Path):
        with file_path.open("rb") as reader:
            self.__version = FontVersion(int.from_bytes(reader.read(4), "little"))
