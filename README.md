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

| File Type				| Export	| Import	|
|:---------------------:|:---------:|:---------:|
| rmdp (Remedy Package)	| ✅		| ✅		|
| string_table.bin		| ✅		| ✅		|
| binfnt (Binary Font)  | ✅		| ✅		|

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
northlighttools rmdp list-files path/to/archive.rmdp
```

Extract all files from a package:
```sh
northlighttools rmdp extract path/to/archive.rmdp path/to/output_dir
```

Pack a directory into a Remedy package:
```sh
northlighttools rmdp pack path/to/input_dir path/to/output_archive.rmdp
```
Options:
- `--endianness little|big`
- `--version 2|7|8|9`

### Binary Font Tools (`binfnt`)

Decompile a `.binfnt` file to BMFont text and bitmap(s):
```sh
northlighttools binfnt decompile path/to/font.binfnt path/to/output_dir
```
To save each character as a separate image:
```sh
northlighttools binfnt decompile path/to/font.binfnt path/to/output_dir --separate-chars
```

Compile a BMFont `.fnt` and bitmap(s) back to `.binfnt`:
```sh
northlighttools binfnt compile path/to/original.binfnt path/to/modified.fnt path/to/output.binfnt
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
