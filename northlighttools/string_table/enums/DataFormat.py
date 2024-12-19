from enum import Enum


class DataFormat(str, Enum):
    XML = "xml"
    JSON = "json"
    CSV = "csv"
    PO = "po"
