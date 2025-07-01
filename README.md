# Northlight Tools

Collection of various tools for Northlight Engine used for Polish fan translation of Quantum Break!

Table of Contents
-----------------
- [Features](#features)
- [Requirements](#build-requirements)
- [Installing](#installing)
- [Usage](#usage)
- [Credits](#credits)

Features
--------

Northlight Tools provides the following utilities:

- **Remedy Package Tools (`rmdp`)**:  
  Allows you to extract, pack, and inspect Remedy package files (`.bin`/`.rmdp`).  
  - Export: Extract all files from a package to a directory.
  - Import: Pack a directory of files into a new Remedy package.
  - Info: Print metadata and structure of a package.
  - List-files: List all files contained in a package.

- **String Table Tools (`string-table`)**:  
  Enables conversion between `string_table.bin` and editable formats (XML, JSON, CSV, PO), and re-importing translations.  
  - Export: Convert `string_table.bin` to XML, JSON, CSV, or PO for translation.
  - Import: Generate a new `string_table.bin` from a translated file.
  - Flexible handling of missing translations with the `--missing-strings` option.

- **Binary Font Tools (`binfnt`)**:  
  Supports decompiling and compiling Northlight binary font files (`.binfnt`).  
  - Decompile: Convert `.binfnt` to BMFont text and bitmap(s), optionally extracting each character as a separate image.
  - Compile: Build a `.binfnt` from BMFont text and bitmap(s).

Requirements
------------

- Python 3.10+

Installing
----------

Either use compiled portable build for Windows or Linux from [Releases](https://github.com/GrzybDev/NorthlightTools/releases) page or use your python package management system (like `pipx` or `uv`)

Example:
`pipx install git+https://github.com/GrzybDev/NorthlightTools.git`


Usage
-----

After installing the package, you can use the tools via the `northlighttools` command (or `python -m northlighttools` for local installs).

### General

```sh
northlighttools --help
```

### String Table Tools

Export a `string_table.bin` to XML, JSON, CSV, or PO:
```sh
northlighttools string-table export path/to/string_table.bin --output-type xml
northlighttools string-table export path/to/string_table.bin --output-type json
northlighttools string-table export path/to/string_table.bin --output-type csv
northlighttools string-table export path/to/string_table.bin --output-type po
```

Import a translation file (XML, JSON, CSV, PO) and generate a new `string_table.bin`:
```sh
northlighttools string-table import path/to/translated_file.xml
northlighttools string-table import path/to/translated_file.csv --missing-strings key
```
Options for `--missing-strings`:

- `key+original` (default): Use both the key and the original string as the fallback, e.g. `(KEY) Original text`.
- `key`: Use only the key as the fallback for missing translations.
- `original`: Use only the original (source) string as the fallback.
- `empty`: Use an empty string for missing translations.
- `remove`: Remove entries with missing translations from the output file.
- `error`: Raise an error if any translation is missing (import will fail).

### Remedy Package Tools (`rmdp`)

Show info about a package:
```sh
northlighttools rmdp info path/to/archive.rmdp
```

List files in a package:
```sh
northlighttools rmdp list path/to/archive.rmdp
```

Extract all files from a package:
```sh
northlighttools rmdp extract path/to/archive.rmdp path/to/output_dir
```

Pack a directory into a Remedy package:
```sh
northlighttools rmdp pack path/to/input_dir path/to/output_archive.rmdp
```
You can customize the package creation with these options:
- `--endianness`: Set the byte order for the package files. Use `little` (default) for most cases, or `big` if required by your target game/version.
- `--version`: Specify the package format version. Supported values:
    - `2` for Alan Wake
    - `7` for Alan Wake: American Nightmare
    - `8` for Quantum Break (default)
    - `9` for Control

### Binary Font Tools (`binfnt`)

Decompile a `.binfnt` file to editable JSON and bitmap(s):
```sh
northlighttools binfnt decompile path/to/font.binfnt path/to/output_dir
```
To save each character as a separate image:
```sh
northlighttools binfnt decompile path/to/font.binfnt path/to/output_dir --separate-chars
```

Compile JSON and bitmap(s) back to `.binfnt`:
```sh
northlighttools binfnt compile path/to/modified.json path/to/output.binfnt
```

---

Each command has its own help, e.g.:
```sh
northlighttools binfnt --help
northlighttools rmdp extract --help
```

Credits
-------

- [GrzybDev](https://grzyb.dev)

Thanks to:
- [Nostritius](https://github.com/Nostritius) who created [AWTools](https://github.com/Nostritius/AWTools) which helped with understanding rmdp and string table formats
- [eprilx](https://github.com/eprilx) who created [NorthlightFontMaker](https://github.com/eprilx/NorthlightFontMaker) which helped with understanding binfnt format!

Special thanks to:
- Remedy Entertainment (for making Northlight Engine)
