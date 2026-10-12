# Northlight Tools

Collection of various tools for Northlight Engine used for Polish fan translation of Quantum Break!

Every tool is lossless: packages, string tables and fonts unpacked from a game build back into the very same bytes.

Table of Contents
-----------------
- [Supported games](#supported-games)
- [Features](#features)
- [Requirements](#requirements)
- [Installing](#installing)
- [Usage](#usage)
- [File formats](#file-formats)
- [Development](#development)
- [Credits](#credits)

Supported games
---------------

All games on the original Northlight engine, before its rework for Alan Wake 2:

| Game                           | Packages        | Fonts                      |
|--------------------------------|-----------------|----------------------------|
| Alan Wake                      | version 2       | version 3                  |
| Alan Wake's American Nightmare | version 7       | version 3                  |
| Alan Wake Remastered           | version 2       | version 4                  |
| Quantum Break                  | version 8       | version 7 (6 for fixedsys) |
| Control                        | version 9       | version 7                  |

String tables share one format in every game.

Features
--------

- **Remedy packages (`rmdp`)**: inspect, list, extract and pack `.bin`/`.rmdp` packages. Extraction checks each file
  against its CRC-32 and keeps its timestamp; packing orders entries, names and data like the games' own
  packages.
- **String tables (`string-table`)**: export `string_table.bin` to XLIFF 2.0, XLIFF 1.2 or Gettext PO for translation
  and build it back from the translated file. Translators get each paragraph of a text as its own segment; repeated
  keys, empty keys, line breaks and escape sequences survive unchanged.
- **Binary fonts (`binfnt`)**: decompile `.binfnt` fonts to an [msdf-atlas-gen](https://github.com/Chlumsky/msdf-atlas-gen)
  JSON document with the texture as an image, edit them, add glyphs and compile them back.

Requirements
------------

- Python 3.14+

Installing
----------

Either use compiled portable build for Windows or Linux from [Releases](https://github.com/GrzybDev/NorthlightTools/releases) page or use your python package management system (like `pipx` or `uv`)

Example:
`pipx install git+https://github.com/GrzybDev/NorthlightTools.git`

Usage
-----

After installing the package, you can use the tools via the `northlighttools` command (or `python -m northlighttools`
for local installs). Every command has its own help, e.g. `northlighttools rmdp pack --help`.

### Remedy packages

```sh
northlighttools rmdp info path/to/ep999-000-pl.rmdp
northlighttools rmdp list path/to/ep999-000-pl.rmdp
northlighttools rmdp extract path/to/ep999-000-pl.rmdp [output_dir]
northlighttools rmdp pack path/to/input_dir [path/to/output.rmdp] --game quantum-break
northlighttools rmdp pack path/to/input_dir [path/to/output.rmdp] --original path/to/ep999-000-pl.rmdp
```

A package is a pair of files: the index (`.bin`) and the data (`.rmdp`); either can be given. `--game` picks the
package format: `alan-wake`, `american-nightmare`, `alan-wake-remastered`, `quantum-break` (default) or `control`.

`--original` packs a directory in the layout of the package it was extracted from: unchanged files keep their place,
timestamp and stored checksum, new files go last, and the original index is only patched while no file or folder is
added or removed. A directory extracted and packed back unchanged gives the very same package, byte for byte.

Names that file systems cannot hold are escaped on extraction and unescaped on packing: `:` becomes `%3A`, so Quantum
Break's `d:` folder is extracted as `d%3A`. Some files in Alan Wake's own packages do not match their stored CRC-32;
extraction warns about them and keeps going.

### String tables

```sh
northlighttools string-table export path/to/string_table.bin [path/to/string_table.xlf] [--format xliff-2.0] [--source-language en]
northlighttools string-table import path/to/string_table.xlf [path/to/string_table.bin]
```

`--format` picks `xliff-2.0` (`.xlf`), `xliff-1.2` (`.xliff`) or `po`; without it, the output's extension decides,
and XLIFF 2.0 is the default. `--source-language` names the language of the table's texts in XLIFF documents. Import
tells the formats apart by their content.

Texts are laid out with line breaks and `\n` escape sequences: translators get the paragraphs between them, and the
layout comes back exactly as it was. Untranslated paragraphs keep their original text when imported; import expects
every unit the export wrote.

- **XLIFF 2.0**: a unit per entry, named after its key (`name`), with a segment per paragraph and an `ignorable` per
  stretch of layout.
- **XLIFF 1.2**: a `trans-unit` per entry (`resname` is the key), or a `group` of them for texts with layout, the
  layout in `translate="no"` units.
- **PO**: a unit per paragraph. The context is the key, then `#N` for the second and later entries with that key
  (`#1` too for the empty key) and `/N` for the N-th paragraph of a text with more than one; `%`, `#` and `/` in keys
  are escaped as `%25`, `%23` and `%2F`. The layout and the number of paragraphs are kept in `#.` comments, which
  translation tools carry over.

In XLIFF a non-empty target is used whatever its state, since OmegaT marks none in XLIFF 2.0; in PO fuzzy
translations are not used.

OmegaT 6.1 hands every `.xlf` and `.xliff` file to its legacy XLIFF filter, which only translates existing targets
and drops carriage returns. In *Project > Properties... > Local File Filters...*, tick *Use local file filter
settings* and untick *XLIFF (legacy filter)*, or untick it for every project in *Options > Global File Filters...*.
Its PO filter cannot read texts holding U+0085, U+2028 or U+2029; use XLIFF for those.

### Binary fonts

```sh
northlighttools binfnt info path/to/customer_facing.binfnt
northlighttools binfnt decompile path/to/customer_facing.binfnt [output_dir] [--separate-glyphs]
northlighttools binfnt compile path/to/customer_facing.json [path/to/customer_facing.binfnt]
```

`decompile` writes `customer_facing.json` and the texture next to it; `--separate-glyphs` saves one image per glyph
instead of the whole texture, when that loses nothing.

File formats
------------

### Font documents

The JSON follows the layout msdf-atlas-gen writes, so glyphs it generates can be moved into a game's font:

- `glyphs`: in the font's order. The first one has an `index` instead of a `unicode`: it is drawn for characters the
  font lacks. `planeBounds` and `advance` are in em units (the font's own units), `atlasBounds` in texture pixels from
  the top. Changing a glyph's `unicode` gives it to another character; a new entry adds a glyph.
- `layoutBounds`: what msdf-atlas-gen has no field for, the bottom and top of the glyph's layout box, which spans from
  0 to its advance. Glyphs whose box is not such a rectangle list its corners in `layoutCorners`.
- `channel`: the texture channel holding the glyph (0 red, 1 green, 2 blue, 3 alpha) in Alan Wake's fonts, which pack
  several glyphs into one texel.
- `vertices` and `triangles`: glyphs that are not textured rectangles (fixedsys, buttons and Alan Wake's Arial).
- `kerning`: `advance` in em units; in Alan Wake Remastered an integer of unknown unit, as stored.
- `northlight`: the font's version, texture format, mipmap count, values of unknown meaning and the texture file.

Every value is written as the shortest number that converts back to the font's exact value.

### Font textures

- Alan Wake's 4-bit and 8-bit RGBA textures become RGBA PNG images; their mipmaps are rebuilt exactly when compiling.
- Quantum Break's and Control's distance fields (half floats, `"type": "sdf"`) become 16-bit grayscale PNG images that
  hold every value exactly: the glyph edge is mid-gray, the inside lighter and texels beyond the field black. The
  scale is not linear, so distance field glyphs from other tools need converting before they are pasted in.
- Textures that no image rebuilds exactly (the DXT5 textures of Alan Wake's debug fonts) are kept as DDS files.

Development
-----------

```sh
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

Credits
-------

- [GrzybDev](https://grzyb.dev)

Thanks to:
- [Nostritius](https://github.com/Nostritius) who created [AWTools](https://github.com/Nostritius/AWTools) which helped with understanding rmdp and string table formats
- [eprilx](https://github.com/eprilx) who created [NorthlightFontMaker](https://github.com/eprilx/NorthlightFontMaker) which helped with understanding binfnt format!

Special thanks to:
- Remedy Entertainment (for making Northlight Engine)
