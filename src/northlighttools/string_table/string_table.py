from io import BufferedReader
from pathlib import Path


class StringTable:

    def __init__(self, input_file: Path | None = None):
        if input_file is not None:
            with input_file.open("rb") as file:
                self.__load(file)

    def __load(self, reader: BufferedReader):
        self.__entries = {}

        strings_count = int.from_bytes(reader.read(4), "little")

        for _ in range(strings_count):
            key_len = int.from_bytes(reader.read(4), "little")
            key = reader.read(key_len).decode("utf-8")
            value_len = int.from_bytes(reader.read(4), "little")
            value = reader.read(value_len * 2).decode("utf-16le")
            self.__entries[key] = value.replace("\r\n", "").replace("\\n", "\n")
