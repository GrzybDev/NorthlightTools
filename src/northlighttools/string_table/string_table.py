import csv
import json
import xml.etree.ElementTree as ET
from io import BufferedReader
from pathlib import Path
from xml.dom import minidom

from polib import POEntry, POFile

from northlighttools.string_table.enumerators.data_format import DataFormat


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

    def __to_xml(self, output_path: Path):
        root_node = ET.Element("string_table")

        for key, value in self.__entries.items():
            ET.SubElement(
                root_node,
                "string",
                {
                    "key": key,
                    "value": value,
                },
            )

        final_xml = ET.tostring(root_node, encoding="utf-16le", method="xml").decode(
            "utf-16le"
        )

        with open(output_path, "w", encoding="utf-16le") as f:
            f.write(minidom.parseString(final_xml).toprettyxml(indent="\t"))

    def __to_json(self, output_path: Path):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.__entries, f, ensure_ascii=False, indent=4)

    def __to_csv(self, output_path: Path):
        with open(output_path, "w", encoding="utf-16le", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["Key", "SourceString", "TranslatedString"]
            )
            writer.writeheader()

            for key, value in self.__entries.items():
                writer.writerow(
                    {
                        "Key": key,
                        "SourceString": value,
                        "TranslatedString": "",
                    }
                )

    def __to_po(self, output_path: Path):
        po = POFile()

        for key, value in self.__entries.items():
            po.append(
                POEntry(
                    msgctxt=key,
                    msgid=value,
                )
            )

        po.save(str(output_path))

    def export(self, output_path: Path, output_type: DataFormat):
        match output_type:
            case DataFormat.XML:
                self.__to_xml(output_path)
            case DataFormat.JSON:
                self.__to_json(output_path)
            case DataFormat.CSV:
                self.__to_csv(output_path)
            case DataFormat.PO:
                self.__to_po(output_path)
