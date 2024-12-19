import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import polib

from northlighttools.string_table.dataclasses.String import String
from northlighttools.string_table.enums.MissingString import MissingStringBehaviour
from northlighttools.string_table.helpers import get_translated_string


def read_xml(input_path: Path) -> list[String]:
    strings = []

    tree = ET.parse(input_path)
    root = tree.getroot()

    for string in root:
        strings.append(String(string.attrib["key"], string.attrib["value"]))

    return strings


def read_json(input_path: Path) -> list[String]:
    strings = []

    with open(input_path, "r", encoding="utf-16le") as f:
        data = json.load(f)

        for key, value in data.items():
            strings.append(String(key, value))

    return strings


def read_csv(input_path: Path, missing_strings: MissingStringBehaviour) -> list[String]:
    strings = []

    with open(input_path, "r", encoding="utf-16le") as f:
        reader = csv.DictReader(f)

        for row in reader:
            translated_string = get_translated_string(
                row["Key"],
                row["SourceString"],
                row["TranslatedString"],
                missing_strings,
            )

            if translated_string is None:
                continue

            strings.append(String(row["Key"], translated_string))

    return strings


def read_po(input_path: Path, missing_strings: MissingStringBehaviour) -> list[String]:
    strings = []
    po = polib.pofile(input_path)

    for entry in po:
        translated_string = get_translated_string(
            entry.msgctxt, entry.msgid, entry.msgstr, missing_strings
        )

        strings.append(String(entry.msgctxt, translated_string))

    return strings
