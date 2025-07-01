from pathlib import Path

from northlighttools.binfnt.enumerators.font_version import FontVersion
from northlighttools.rmdp import Progress


class BinaryFont:

    __version: FontVersion = FontVersion.QUANTUM_BREAK

    def __init__(self, progress: Progress, file_path: Path | None = None):
        self.__progress = progress

        if file_path is not None:
            self.__load(file_path)

    def __load(self, file_path: Path):
        with file_path.open("rb") as reader:
            self.__version = FontVersion(int.from_bytes(reader.read(4), "little"))
