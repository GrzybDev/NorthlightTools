"""String tables (string_table.bin): the localized texts of a game."""

from northlighttools.string_table.table import (
    StringEntry,
    decode_string_table,
    encode_string_table,
)
from northlighttools.string_table.translation import (
    TranslationFormat,
    detect_format,
    export_translation,
    import_translation,
)

__all__ = [
    "StringEntry",
    "TranslationFormat",
    "decode_string_table",
    "detect_format",
    "encode_string_table",
    "export_translation",
    "import_translation",
]
