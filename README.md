# Northlight Tools

A command-line toolkit that unpacks and rebuilds the packages, string tables and fonts of Remedy's Northlight engine
games, from Alan Wake to Control, for translations and mods.

Every round trip is lossless: a package extracted and packed back in its original layout, a string table exported and
imported back or a font decompiled and compiled back without changes gives the very same bytes as the game's own file.
Texts go to translation tools as XLIFF 2.0, XLIFF 1.2 or Gettext PO, and fonts become
[msdf-atlas-gen](https://github.com/Chlumsky/msdf-atlas-gen) JSON documents with PNG textures.

Table of Contents
-----------------
- [Supported games](#supported-games)
- [Legal notes](#legal-notes)
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

Legal notes
-----------

This repository and its releases contain no files of the games. You need your own copy of a game, such as one from:

- Alan Wake: [Steam](https://store.steampowered.com/app/108710/), [GOG](https://www.gog.com/en/game/alan_wake)
- Alan Wake's American Nightmare: [Steam](https://store.steampowered.com/app/202750/),
  [GOG](https://www.gog.com/en/game/alan_wakes_american_nightmare)
- Alan Wake Remastered: [Epic Games Store](https://store.epicgames.com/p/alan-wake-remastered)
- Quantum Break: [Steam](https://store.steampowered.com/app/474960/)
- Control: [Steam](https://store.steampowered.com/app/870780/),
  [GOG](https://www.gog.com/en/game/control_ultimate_edition)

The tools only read and write the games' data files. They neither make piracy easier nor bypass or remove any DRM.

Features
--------

- **Remedy packages (`rmdp`)**
  - Show the game a package is made for and what it holds, and list its files with their sizes, offsets and timestamps
  - Extract every file with its stored timestamp, checking each against its stored CRC-32
  - Pack a directory into a package for any supported game, with entries, names and data ordered and aligned like the
    game's own packages
  - Repack an extracted directory in the layout of its original package, which gives back the very same package while
    nothing changed
- **String tables (`string-table`)**
  - Export `string_table.bin` to XLIFF 2.0, XLIFF 1.2 or Gettext PO, each paragraph of a text a segment of its own
  - Import the translated document back, with repeated keys, empty keys, line breaks and escape sequences unchanged and
    the original text in untranslated paragraphs
- **Binary fonts (`binfnt`)**
  - Show a font's version, its numbers of glyphs, characters and kerning pairs, and its texture
  - Decompile a font to an msdf-atlas-gen JSON document with its texture as a PNG image, or one image per glyph
  - Compile the document back with changed, moved and added glyphs and kerning pairs, rebuilding the texture's mipmaps
    the way the games' own fonts have them
- **All commands**: never replace an extracted, exported or decompiled file that may hold edits, and keep the first
  file a build replaces as `.orig`

Not covered: the other files inside packages (textures, models, audio, scripts and the rest), the executables, and the
reworked engine of Alan Wake 2 and later games.

Requirements
------------

- Python 3.14+ (the portable builds include it)

Installing
----------

Download the portable build for your system from the
[Releases](https://github.com/GrzybDev/NorthlightTools/releases) page: `NorthlightTools_v<version>_Windows.exe`
(code-signed), `NorthlightTools_v<version>_Linux` or `NorthlightTools_v<version>_macOS`. Each is a single executable
that needs no Python; run it in place of `northlighttools` in the commands below, on Linux and macOS after making it
executable with `chmod +x`. The macOS build is not notarised, so macOS keeps a copy downloaded with a browser from
running until its quarantine flag is cleared with `xattr -d com.apple.quarantine NorthlightTools_v<version>_macOS`.

To install the command with Python instead, give pipx or uv the repository's URL:

```sh
uv tool install git+https://github.com/GrzybDev/NorthlightTools.git
```

`pipx install` takes the same URL.

Usage
-----

The `northlighttools` command has a group of commands for each file type: `rmdp`, `string-table` and `binfnt`.
`--help` lists the groups, and after any group or command it shows what that takes:

```sh
northlighttools --help
northlighttools rmdp pack --help
```

`python -m northlighttools` runs the same commands in a Python environment the package is installed in, and
`uv run northlighttools` in a clone of the repository.

Every output argument is optional. Without one, a command writes next to its input, named after it: `rmdp extract` and
`binfnt decompile` create a folder, the other commands a file with the extension of what they write.

Commands that write files for editing never replace one: when a file that `rmdp extract`, `string-table export` or
`binfnt decompile` would write exists already, the command names it, writes nothing and stops. Move the file away or
choose another output. Other files in the output folder are left alone.

Commands that build game files replace their output: `rmdp pack`, `string-table import` and `binfnt compile`. The first
time one of them replaces a file, it keeps that file beside the new one as `<name>.orig`, such as
`string_table.bin.orig`, and says so. Once the `.orig` file exists, they replace the output without another copy.
Rename the `.orig` file back to restore the original.

Built files are written through a temporary file in the same folder, and a file that cannot be replaced, such as a
package a running game holds open, stays as it was. `extract` and `decompile` remove the files they wrote when they
fail. A command that fails prints the reason to the
standard error and exits with code 1, or with code 2 when an argument is missing or names no file; warnings go to the
standard error too.

### Remedy packages

```sh
northlighttools rmdp info path/to/package.rmdp
northlighttools rmdp list path/to/package.rmdp
northlighttools rmdp extract path/to/package.rmdp [path/to/output_dir]
northlighttools rmdp pack path/to/input_dir [path/to/package.rmdp] [--game quantum-break]
northlighttools rmdp pack path/to/input_dir [path/to/package.rmdp] --original path/to/original.rmdp
```

A package is a pair of files with one name: the index (`.bin`) and the data (`.rmdp`). Every command takes either file
of the pair, and both must exist; `pack` writes both.

`info` shows the game the package is made for with its format version, the byte order, the base path stored in the
index, the numbers of folders and files and the size of the data. `list` shows each file's path, size, offset in the
data and, in packages of version 7 and later, its last write time in UTC.

`extract` writes every folder and file of the package to the output folder, by default a folder next to the package
named after it. Each file gets its stored last write time and is checked against its stored CRC-32. Some files in Alan
Wake's own packages do not match their stored CRC-32; extraction warns about them and keeps going. A data file that is
cut short stops extraction with an error.

Names that file systems cannot hold are escaped on extraction and unescaped on packing: `<`, `>`, `:`, `"`, `/`, `\`,
`|`, `?`, `*`, `%`, the control characters U+0000 to U+001F, a trailing dot or space and the first letter of a Windows
device name such as
`CON` become `%` and two hex digits. Quantum Break's `d:` folder is therefore extracted as `d%3A`.

`pack` packs every folder and file under the input folder into a package, by default next to the folder and named
after it. `--game` picks the game whose package format to write: entries, names and data are ordered and aligned like
that game's own packages, with its byte order and base path. Packages of version 7 and later store each file's last
write time. Files ending in `.orig`, the originals that `import` and `compile` keep, are left out; no game's package
holds such a file.

`--original` packs a directory in the format and layout of the package it was extracted from. Files keep their order,
and their offset while the files before them have not grown; unchanged files keep their timestamp and stored checksum,
and new files go last. The original index is patched rather than rebuilt while no file or folder is added or removed,
so a directory extracted and packed back unchanged gives the very same package, byte for byte. The output may be the
original package itself, and `--original` also takes the `.orig` files of a kept original. `--original` sets the
format, so it does not take `--game`.

|         Option | Description                                                                                                                 | Default         |
|---------------:|-----------------------------------------------------------------------------------------------------------------------------|-----------------|
| `--game`, `-g` | Game whose package format to write: `alan-wake`, `american-nightmare`, `alan-wake-remastered`, `quantum-break` or `control` | `quantum-break` |
|   `--original` | The package the directory was extracted from, whose format and layout to keep                                               | none            |

```sh
northlighttools rmdp extract ep999-000-en.rmdp
northlighttools rmdp pack ep999-000-en ep999-000-en-repacked.rmdp --original ep999-000-en.rmdp
```

The first command extracts the package to `ep999-000-en/`; the second packs the folder into `ep999-000-en-repacked.bin`
and `ep999-000-en-repacked.rmdp`, identical to the original pair while nothing in the folder changed.

### String tables

```sh
northlighttools string-table export path/to/string_table.bin [path/to/string_table.xlf] [--format xliff-2.0] [--source-language en]
northlighttools string-table import path/to/string_table.xlf [path/to/string_table.bin]
```

`export` writes the table's texts to a new translation document, by default next to the table with the format's
extension. `--format` picks the format; without it, the output's extension decides (`.xlf` for XLIFF 2.0, `.xliff` for
XLIFF 1.2, `.po` for PO), and XLIFF 2.0 is used for any other. `--source-language` names the language of the table's
texts in XLIFF documents; PO has no field for it.

`import` builds a string table from a translated document in any of the three formats, which it tells apart by their
content, by default next to the document with the `.bin` extension. It expects every unit the export wrote, and
untranslated paragraphs keep their original text.

Texts are laid out with line breaks and `\n` escape sequences: translators get the paragraphs between them, and the
layout comes back exactly as it was. See [Translation documents](#translation-documents) for what each format holds.

|                    Option | Description                                                                   | Default                                     |
|--------------------------:|-------------------------------------------------------------------------------|---------------------------------------------|
|          `--format`, `-f` | The document's format: `xliff-2.0` (`.xlf`), `xliff-1.2` (`.xliff`) or `po`   | by the output's extension, else `xliff-2.0` |
| `--source-language`, `-l` | The language of the table's texts as a BCP 47 tag, written to XLIFF documents | `en`                                        |

```sh
northlighttools string-table export string_table.bin --format po
northlighttools string-table import string_table.po
```

The first command writes `string_table.po`. Once it is translated, the second builds `string_table.bin` from it and
keeps the table it replaces as `string_table.bin.orig`.

### Binary fonts

```sh
northlighttools binfnt info path/to/customer_facing.binfnt
northlighttools binfnt decompile path/to/customer_facing.binfnt [path/to/output_dir] [--separate-glyphs]
northlighttools binfnt compile path/to/customer_facing.json [path/to/customer_facing.binfnt]
```

`info` shows the font's version, its numbers of glyphs, characters and kerning pairs, and its texture's size, pixel
format and number of mipmap levels.

`decompile` writes the font as an msdf-atlas-gen JSON document, `customer_facing.json`, with its texture beside it, to
the output folder, by default a folder next to the font named after it. `--separate-glyphs` saves each glyph as its own
image in `customer_facing_glyphs/` instead of the whole texture. It refuses fonts that would lose texture data that
way: textures kept as DDS files, glyphs that are not textured rectangles and texture data outside the glyphs.

`compile` builds a font from a document and the images it names, which it reads from the document's folder, by default
next to the document with the `.binfnt` extension. A glyph, image or texture that does not fit the font's format stops
it with an error naming that glyph or file.

|                    Option | Description                                                   | Default |
|--------------------------:|---------------------------------------------------------------|---------|
| `--separate-glyphs`, `-s` | Save each glyph as its own image instead of the whole texture | off     |

```sh
northlighttools binfnt decompile customer_facing.binfnt
northlighttools binfnt compile customer_facing/customer_facing.json customer_facing.binfnt
```

The first command writes `customer_facing/customer_facing.json` and the texture,
`customer_facing/customer_facing.png`. Once they are edited, the second builds the font over the original and keeps
that as `customer_facing.binfnt.orig`.

### Translating a game

Quantum Break keeps the texts and fonts of each language in a package of its own, such as `data/ep999-000-en.rmdp` for
English. To translate them:

1. Extract the language's package to a work folder:

   ```sh
   northlighttools rmdp extract path/to/QuantumBreak/data/ep999-000-en.rmdp ep999-000-en
   ```

2. Export its string table:

   ```sh
   northlighttools string-table export ep999-000-en/d%3A/data/locale/en/string_table.bin string_table.xlf
   ```

3. Translate `string_table.xlf` in a translation tool. OmegaT needs the filter settings that
   [Translation documents](#translation-documents) gives, and writes the translated document to its project's `target`
   folder.

4. Import the translated document over the extracted table:

   ```sh
   northlighttools string-table import path/to/project/target/string_table.xlf ep999-000-en/d%3A/data/locale/en/string_table.bin
   ```

   If the translation uses letters the fonts lack, add them to the fonts in `ep999-000-en/d%3A/data/fonts/locale/en/`:
   decompile each one to a folder outside `ep999-000-en`, add the glyphs and compile it back over the extracted font.

5. With the game closed, pack the folder over the game's package in its original layout:

   ```sh
   northlighttools rmdp pack ep999-000-en path/to/QuantumBreak/data/ep999-000-en.rmdp --original path/to/QuantumBreak/data/ep999-000-en.rmdp
   ```

   The game's own package is kept as `ep999-000-en.bin.orig` and `ep999-000-en.rmdp.orig`; renaming them back restores
   it. The `.orig` files that import and compile kept in the folder are not packed. When packing again after later
   changes, give `--original` the kept `path/to/QuantumBreak/data/ep999-000-en.rmdp.orig`, so the package keeps the
   layout of the game's own one.

The other games work the same way; `rmdp list` shows which package holds a `string_table.bin` or a font.

### Known limitations

- OmegaT's PO filter cannot read texts holding U+0085, U+2028 or U+2029; use XLIFF for those tables.
- OmegaT 5.8 drops the carriage returns of the layout from XLIFF 2.0 targets, which doubles the gaps between
  paragraphs in the game; use OmegaT 6.1.
- Export refuses keys and texts holding characters that XML cannot carry: U+0000 to U+001F other than tab, line feed
  and carriage return, U+FFFE, U+FFFF and unpaired surrogates. PO is held to the same set.
- PO refuses a text with a paragraph starting with `_:`, which PO tools read as a comment; use XLIFF for that table.
- The DXT5 textures of Alan Wake's debug fonts stay DDS files (see [Font textures](#font-textures)), which only a DDS
  editor changes.
- Distance field textures map distances to gray levels on a scale that is not linear, so distance field glyphs from
  other tools need converting before they are pasted in.

File formats
------------

The games' own formats are described in [docs/rmdp.md](docs/rmdp.md) (packages),
[docs/string-table.md](docs/string-table.md) (string tables) and [docs/binfnt.md](docs/binfnt.md) (binary fonts).

### Package folders

An extracted package is a folder tree of the package's folders and files under their escaped names, each file with
its stored last write time. Packing it back unescapes the names.

### Translation documents

- **XLIFF 2.0**: a unit per entry, named after its key (`name`), with a segment per paragraph and an `ignorable` per
  stretch of layout.
- **XLIFF 1.2**: a `trans-unit` per entry (`resname` is the key), or a `group` of them for texts with layout, the
  layout in `translate="no"` units.
- **PO**: a unit per paragraph. The context is the key, then `#N` for the second and later entries with that key
  (`#1` too for the empty key) and `/N` for the N-th paragraph of a text with more than one; `%`, `#` and `/` in keys
  are escaped as `%25`, `%23` and `%2F`. The layout and the number of paragraphs are kept in `#.` comments, which
  translation tools carry over.

In XLIFF a non-empty target is used whatever its state, since OmegaT marks none in XLIFF 2.0; in PO fuzzy translations
are not used.

OmegaT 6.1 hands every `.xlf` and `.xliff` file to its legacy XLIFF filter, which only translates existing targets
and drops carriage returns. In *Project > Properties... > Local File Filters...*, tick *Use local file filter
settings* and untick *XLIFF (legacy filter)*, or untick it for every project in *Options > Global File Filters...*.

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

With `--separate-glyphs`, `northlight` names the glyph folder and the texture's background instead of the texture
file, and each glyph names its image: `U+0041.png` for the letter A, `fallback.png` for the first glyph. Texels outside
the glyphs take the background when compiling.

### Font textures

- Alan Wake's 4-bit and 8-bit RGBA textures become RGBA PNG images; their mipmaps are rebuilt exactly when compiling.
- Quantum Break's and Control's distance fields (half floats, `"type": "sdf"`) become 16-bit grayscale PNG images that
  hold every value exactly: the glyph edge is mid-gray, the inside lighter and texels beyond the field black.
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

The round trips over the games' own files run only when `NORTHLIGHT_GAME_DIRS` lists the games' install folders,
separated by `;` on Windows and `:` elsewhere. They decode and encode every package index, extract and repack the
smallest package of each game, and export and import every string table and decompile and compile every font found in
the packages, expecting the very same bytes back. They only read the game folders and write to pytest's temporary
folders:

```sh
NORTHLIGHT_GAME_DIRS="path/to/QuantumBreak:path/to/Control" uv run pytest -m games
```

Credits
-------

- [GrzybDev](https://grzyb.dev)

Thanks to:
- [Nostritius](https://github.com/Nostritius), whose [AWTools](https://github.com/Nostritius/AWTools) helped with
  understanding the package and string table formats
- [eprilx](https://github.com/eprilx), whose [NorthlightFontMaker](https://github.com/eprilx/NorthlightFontMaker)
  helped with understanding the binary font format

Special thanks to:
- Remedy Entertainment (for making the games and the Northlight engine)
- Xbox Game Studios (for publishing Quantum Break)
- Epic Games Publishing (for publishing Alan Wake Remastered)
