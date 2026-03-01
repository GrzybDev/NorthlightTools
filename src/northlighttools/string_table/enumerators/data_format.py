from enum import Enum


class DataFormat(str, Enum):
    XLIFF = "xliff"
    XLF = "xliff2"
    PO = "po"
    CSV = "csv"
