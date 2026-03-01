from io import BufferedReader
from pathlib import Path

from translate.storage import csvl10n, po, xliff, xliff2
from translate.storage.xliff import ID_SEPARATOR

from northlighttools.string_table.enumerators.data_format import DataFormat
from northlighttools.string_table.enumerators.missing_string_behaviour import (
    MissingStringBehaviour,
)
from northlighttools.string_table.helpers import get_translated_string


class StringTable:
    def __init__(self, input_file: Path | None = None):
        self.__input_file = input_file.name if input_file else "string_table.bin"

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

    def export(self, output_path: Path, output_type: DataFormat):
        match output_type:
            case DataFormat.XLIFF:
                storage = xliff.Xliff1File()
                unit_class = xliff.Xliff1Unit

                storage.createfilenode(self.__input_file)
            case DataFormat.XLF:
                storage = xliff2.Xliff2File()
                unit_class = xliff2.Xliff2Unit

                storage.setfilename(
                    storage.body,
                    self.__input_file,
                )
            case DataFormat.PO:
                storage = po.pofile()
                unit_class = po.pounit
            case DataFormat.CSV:
                storage = csvl10n.csvfile()
                unit_class = csvl10n.csvunit

        for key, value in self.__entries.items():
            unit = unit_class(source=value)

            if output_type == DataFormat.PO:
                unit.setcontext(key)
            else:
                unit.setid(key)

            storage.addunit(unit)  # type: ignore

        storage.savefile(str(output_path))

    def load_from(self, input_path: Path, missing_strings: MissingStringBehaviour):
        match input_path.suffix.lower():
            case ".xliff":
                data_format = DataFormat.XLIFF
                storage = xliff.Xliff1File().parsefile(str(input_path))
            case ".xlf":
                data_format = DataFormat.XLF
                storage = xliff2.Xliff2File().parsefile(str(input_path))
            case ".po":
                data_format = DataFormat.PO
                storage = po.pofile().parsefile(str(input_path))
            case ".csv":
                data_format = DataFormat.CSV
                storage = csvl10n.csvfile().parsefile(str(input_path))
            case _:
                raise ValueError(f"Unsupported file format: {input_path.suffix}")

        self.__entries = {}

        for unit in storage.units:  # type: ignore
            if unit.isheader():
                continue

            if data_format == DataFormat.PO:
                key = unit.getcontext()
            else:
                key = unit.getid()

                if data_format == DataFormat.XLIFF:
                    key = key.split(ID_SEPARATOR, 1)[-1]

            if key:
                self.__entries[key] = get_translated_string(
                    key,
                    unit.source,
                    unit.target,
                    missing_strings,
                )

    def save(self, output_path: Path):
        with output_path.open("wb") as f:
            f.write(len(self.__entries).to_bytes(4, "little"))

            for key, value in self.__entries.items():
                f.write(len(key).to_bytes(4, "little"))
                f.write(key.encode("ascii"))
                f.write(len(value).to_bytes(4, "little"))
                f.write(value.encode("utf-16le"))
