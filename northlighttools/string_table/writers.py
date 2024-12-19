import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from polib import POEntry, POFile

from northlighttools.string_table.dataclasses.String import String


def write_xml(strings: list[String], output_path: Path):
    root_node = ET.Element("string_table")

    for string in strings:
        ET.SubElement(root_node, "string", {"key": string.key, "value": string.value})

    final_xml = ET.tostring(root_node, encoding="utf-16le", method="xml").decode(
        "utf-16le"
    )

    with open(output_path, "w", encoding="utf-16le") as f:
        f.write(minidom.parseString(final_xml).toprettyxml(indent="\t"))


def write_json(strings: list[String], output_path: Path):
    data = {}

    for string in strings:
        if string.key in data and data[string.key] != string.value:
            raise ValueError(f"Duplicate key: {string.key}")

        data[string.key] = string.value

    with open(output_path, "w", encoding="utf-16le") as f:
        json.dump(data, f, indent=4)


def write_csv(strings: list[String], output_path: Path):
    with open(output_path, "w", encoding="utf-16le", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Key", "SourceString", "TranslatedString"]
        )
        writer.writeheader()

        for string in strings:
            writer.writerow(
                {
                    "Key": string.key,
                    "SourceString": string.value,
                    "TranslatedString": "",
                }
            )


def write_po(strings: list[String], output_path: Path):
    po = POFile()

    for string in strings:
        po.append(POEntry(msgctxt=string.key, msgid=string.value))

    po.save(output_path)
