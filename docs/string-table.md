# String table

`string_table.bin` holds a game's localized texts, each under a key. The games keep these files in their language
packages; `northlighttools string-table export` turns one into a translation document and
`northlighttools string-table import` builds it back from the translated document.

The format is the same in Alan Wake, Alan Wake's American Nightmare, Alan Wake Remastered, Quantum Break and Control.
It has no signature, version field, compression or encryption.

## Layout

| Offset | Type          | Field       | Description                   |
|--------|---------------|-------------|-------------------------------|
| 0x00   | u32           | Entry count | Number of entries             |
| 0x04   | entry × count | Entries     | Back to back, without padding |

The file ends with the last entry. A u32 is an unsigned 32-bit integer, little-endian in every game, also in Alan Wake
and Alan Wake Remastered, whose package indexes are big-endian.

### Entry

Offsets are relative to the start of the entry; K is the key length and T the text length.

| Offset | Type        | Field           | Description                             |
|--------|-------------|-----------------|-----------------------------------------|
| 0      | u32         | Key length (K)  | Length of the key in bytes              |
| 4      | K bytes     | Key             | UTF-8, without a terminator             |
| 4 + K  | u32         | Text length (T) | Length of the text in UTF-16 code units |
| 8 + K  | T × 2 bytes | Text            | UTF-16LE, without a terminator          |

An entry takes 8 + K + 2T bytes. Neither keys nor texts end with a NUL character: the lengths alone delimit them.

The tool refuses a table that ends inside an entry, has bytes after the last entry or holds a key that is not UTF-8.

## Keys

- The key length counts bytes, not characters: `CLÉ` takes 4 bytes, since `É` takes 2 in UTF-8.
- A key may be empty (length 0).
- A key may occur in more than one entry, with the same text or a different one. The tool keeps every entry; which of
  them a game uses is unknown.
- The tool also reads the three-byte forms of surrogate code points (`ED A0 80` to `ED BF BF`), which strict UTF-8
  forbids, and writes them back as they were.
- The games' own tables list their entries in ascending key order, with letters compared as lowercase (so `MENU_B`
  comes before `MENUA`). Whether a game relies on this order is unknown. The tool does not sort: it writes the entries
  in the order it gets them, from a table or from a translation document.

## Texts

- The text length counts UTF-16 code units, not characters or bytes: a character above U+FFFF takes 2 units, a
  surrogate pair.
- An empty text has length 0 and no bytes.
- A lone surrogate (a high surrogate, D800 to DBFF, without a low one, DC00 to DFFF, after it, or a low surrogate
  without a high one before it) is read as that code point and written back unchanged. None of the games' own tables
  holds one.
- XLIFF and PO cannot carry lone surrogates, characters below U+0020 other than tab, line feed and carriage return,
  U+FFFE or U+FFFF. Exporting a table whose keys or texts hold one stops with an error naming the key and the
  character.

## Text layout

Texts are laid out with line breaks and `\n` escape sequences. For translation, the tool splits each text into
paragraphs and the layout runs around them.

In this section, `<CR>`, `<LF>`, `<TAB>` and `<SP>` stand for a carriage return, a line feed, a tab and a space; every
other character stands for itself, so `\n` is the two characters backslash and `n`.

A layout run is a stretch of one or more of these, in any mix:

- line breaks: `<CR><LF>`, and `<LF>` or `<CR>` alone;
- `\n` escape sequences: a backslash followed by a lowercase `n`, also when another backslash precedes it;

together with the spaces and tabs directly before, between and after them. The paragraphs are what lies between the
runs. A text with N paragraphs has N + 1 runs: one before the first paragraph, one between each two and one after the
last; the first and the last may be empty. A text that is empty or holds only layout is one empty paragraph followed by
its layout.

Everything else stays in the paragraphs: spaces and tabs not next to a break, other control characters, U+0085,
U+2028, U+2029 and backslash sequences other than `\n`, such as `\r`, `\"` or `\N`.

| Text                             | Paragraphs          | Layout runs                              |
|----------------------------------|---------------------|------------------------------------------|
| `One<CR><LF>Two`                 | `One`, `Two`        | empty, `<CR><LF>`, empty                 |
| `One<SP>\n<CR><LF>\n<SP><SP>Two` | `One`, `Two`        | empty, `<SP>\n<CR><LF>\n<SP><SP>`, empty |
| `<LF>One<CR>`                    | `One`               | `<LF>`, `<CR>`                           |
| `<TAB>One<TAB>`                  | `<TAB>One<TAB>`     | empty, empty                             |
| `One\r\nTwo`                     | `One\r`, `Two`      | empty, `\n`, empty                       |
| empty                            | one empty paragraph | empty, empty                             |
| `<CR><LF>\n<SP>`                 | one empty paragraph | empty, `<CR><LF>\n<SP>`                  |

Translation documents offer the paragraphs for translation and carry the layout runs unchanged. Importing puts the
translated paragraphs back between the runs, so every text keeps its layout exactly.

## Differences between games

The binary format does not change between games; the texts differ in their layout and keys. In the Steam releases'
own tables:

| Game                           | Layout                                    | Repeated keys                 | Empty key         |
|--------------------------------|-------------------------------------------|-------------------------------|-------------------|
| Alan Wake                      | `\n`; `<CR><LF>` or `<CR>` in a few texts | none                          | none              |
| Alan Wake's American Nightmare | `\n`                                      | in some languages             | none              |
| Alan Wake Remastered           | `\n`; `<CR><LF>` or `<CR>` in a few texts | none                          | none              |
| Quantum Break                  | `<CR><LF>` and `\n`                       | in every language             | none              |
| Control                        | `<CR><LF>`; `\n` in a few texts           | in every language but English | in every language |

## Worked example

This script, run with `uv run python` in a checkout of the tool, writes a table of five invented entries:

```python
from pathlib import Path

from northlighttools.string_table import StringEntry, encode_string_table

entries = [
    StringEntry("MENU_QUIT", "Quit"),
    StringEntry("HINT", "Jump \r\nRoll\\n"),
    StringEntry("HINT", ""),
    StringEntry("", "-"),
    StringEntry("CLÉ", "\U0001d11e"),
]
Path("string_table.bin").write_bytes(encode_string_table(entries))
```

The resulting 105 bytes:

```text
00000000  05 00 00 00 09 00 00 00 4d 45 4e 55 5f 51 55 49
00000010  54 04 00 00 00 51 00 75 00 69 00 74 00 04 00 00
00000020  00 48 49 4e 54 0d 00 00 00 4a 00 75 00 6d 00 70
00000030  00 20 00 0d 00 0a 00 52 00 6f 00 6c 00 6c 00 5c
00000040  00 6e 00 04 00 00 00 48 49 4e 54 00 00 00 00 00
00000050  00 00 00 01 00 00 00 2d 00 04 00 00 00 43 4c c3
00000060  89 02 00 00 00 34 d8 1e dd
```

| Offset | Bytes                         | Field       | Value                                   |
|--------|-------------------------------|-------------|-----------------------------------------|
| 0x00   | `05 00 00 00`                 | Entry count | 5                                       |
| 0x04   | `09 00 00 00`                 | Key length  | 9 bytes                                 |
| 0x08   | `4d 45 4e 55 5f 51 55 49 54`  | Key         | `MENU_QUIT`                             |
| 0x11   | `04 00 00 00`                 | Text length | 4 units                                 |
| 0x15   | `51 00 75 00 69 00 74 00`     | Text        | `Quit`                                  |
| 0x1D   | `04 00 00 00`                 | Key length  | 4 bytes                                 |
| 0x21   | `48 49 4e 54`                 | Key         | `HINT`                                  |
| 0x25   | `0d 00 00 00`                 | Text length | 13 units                                |
| 0x29   | `4a 00 75 00` … `5c 00 6e 00` | Text        | `Jump<SP><CR><LF>Roll\n`                |
| 0x43   | `04 00 00 00`                 | Key length  | 4 bytes                                 |
| 0x47   | `48 49 4e 54`                 | Key         | `HINT` again                            |
| 0x4B   | `00 00 00 00`                 | Text length | 0: an empty text                        |
| 0x4F   | `00 00 00 00`                 | Key length  | 0: the empty key                        |
| 0x53   | `01 00 00 00`                 | Text length | 1 unit                                  |
| 0x57   | `2d 00`                       | Text        | `-`                                     |
| 0x59   | `04 00 00 00`                 | Key length  | 4 bytes: `É` takes two                  |
| 0x5D   | `43 4c c3 89`                 | Key         | `CLÉ`                                   |
| 0x61   | `02 00 00 00`                 | Text length | 2 units for one character               |
| 0x65   | `34 d8 1e dd`                 | Text        | U+1D11E as the surrogate pair D834 DD1E |

The table ends at 0x69. For translation, the first `HINT` text splits into the paragraphs `Jump` and `Roll`, with the
run `<SP><CR><LF>` between them and the run `\n` after `Roll`. The second `HINT` text is one empty paragraph, and every
other text is one paragraph with empty runs.
