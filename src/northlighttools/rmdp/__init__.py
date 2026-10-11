"""Remedy packages: an index (.bin) describing files stored in a data file (.rmdp)."""

from northlighttools.rmdp.archive import (
    extract_file,
    extract_package,
    filesystem_path,
    pack_directory,
    package_paths,
    read_package,
)
from northlighttools.rmdp.formats import FORMATS, Game, PackageFormat
from northlighttools.rmdp.index import decode_index, encode_index
from northlighttools.rmdp.model import Package, PackageFile, filetime_to_datetime
from northlighttools.rmdp.names import PackagePath, format_path

__all__ = [
    "FORMATS",
    "Game",
    "Package",
    "PackageFile",
    "PackageFormat",
    "PackagePath",
    "decode_index",
    "encode_index",
    "extract_file",
    "extract_package",
    "filesystem_path",
    "filetime_to_datetime",
    "format_path",
    "pack_directory",
    "package_paths",
    "read_package",
]
