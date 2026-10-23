# Remedy package

A Remedy package is a pair of files with the same name: an index (`.bin`) that describes a tree of folders and files,
and a data file (`.rmdp`) that holds the contents of the files. The `rmdp` commands read and write both files in every
version listed below.

## Versions

| Game                           | `--game`               | Version | Byte order    | Link size | Record fields     | Data alignment | Base path |
|--------------------------------|------------------------|---------|---------------|-----------|-------------------|----------------|-----------|
| Alan Wake                      | `alan-wake`            | 2       | big-endian    | 32-bit    | packed            | 8 bytes        | `d:\data` |
| Alan Wake Remastered           | `alan-wake-remastered` | 2       | big-endian    | 64-bit    | naturally aligned | 8 bytes        | `d:\data` |
| Alan Wake's American Nightmare | `american-nightmare`   | 7       | little-endian | 32-bit    | packed            | 8 bytes        | `d:\data` |
| Quantum Break                  | `quantum-break`        | 8       | little-endian | 64-bit    | packed            | 32 bytes       | `d:\data` |
| Control                        | `control`              | 9       | little-endian | 64-bit    | packed            | 32 bytes       | empty     |

Versions 7, 8 and 9 add an unknown header value, a timestamp in each file record and a closing entry after the
records; version 2 has none of them. Versions 8 and 9 share one layout. Alan Wake Remastered pads the fields of its
records the way a C compiler aligns them; the other games pack them without padding. The byte order, data alignment
and base path in the table are those of the games' own packages, which `rmdp pack --game` gives a new package;
reading accepts either byte order in every version.

The version alone does not tell Alan Wake from Alan Wake Remastered. Reading decodes the first folder record, the
root, in both layouts and picks the one in which its next sibling and parent links are null; an index that fits both
or neither is rejected.

## Index

| Part           | Size                                                 | Present                         |
|----------------|------------------------------------------------------|---------------------------------|
| Header         | 145 bytes (version 2) or 153 bytes (versions 7 to 9) | always                          |
| Folder records | folder count × folder record size                    | always                          |
| File records   | file count × file record size                        | always                          |
| Closing entry  | one folder record                                    | versions 7 to 9                 |
| Names block    | names size from the header                           | always                          |
| Extra paths    | the rest of the index                                | only when the package lists any |

The parts follow each other without gaps, so the folder records start at 0x91 or 0x99 and 64-bit fields need not lie
at multiples of 8 in the file. All integers are unsigned and use the byte order the flag sets, except the data
CRC-32 (see [Data checksum](#data-checksum)).

A link is an unsigned integer of the link size: 32-bit in Alan Wake and Alan Wake's American Nightmare, 64-bit in the
other games. All bits set (`0xFFFFFFFF` or `0xFFFFFFFFFFFFFFFF`) is null and points to no entry. Folder links are
indices into the folder records, file links indices into the file records, and name offsets byte offsets into the
names block.

The games' own packers leave some bytes with varying content: the base path after its terminator, the unknown field
of folder records and the padding in Alan Wake Remastered records. A new index holds zeros there. While no folder or
file is added or removed, `rmdp pack --original` patches only the flags, data offset, size, CRC-32 and timestamp of
each file record and keeps every other byte of the original index.

### Header

| Version 2 | Versions 7 to 9 | Type      | Field                                                      |
|-----------|-----------------|-----------|------------------------------------------------------------|
| 0x00      | 0x00            | u8        | Byte order flag                                            |
| 0x01      | 0x01            | u32       | Version: 2, 7, 8 or 9                                      |
| 0x05      | 0x05            | u32       | Folder count: the root included, the closing entry not     |
| 0x09      | 0x09            | u32       | File count                                                 |
|           | 0x0D            | u64       | Unknown; 1 in every known package and in new ones          |
| 0x0D      | 0x15            | u32       | Names size: bytes in the names block, terminators included |
| 0x11      | 0x19            | char[128] | Base path: UTF-8, ended by a NUL byte                      |

| Byte order flag | Byte order    |
|-----------------|---------------|
| 0               | little-endian |
| 1               | big-endian    |

Reading rejects any other flag and any other version. Writing refuses a base path of 128 bytes or more, which leaves
no room for its terminator.

### Folder record

| Field         | Type    | Alan Wake, Alan Wake's American Nightmare | Quantum Break, Control | Alan Wake Remastered |
|---------------|---------|-------------------------------------------|------------------------|----------------------|
| Name checksum | u32     | 0x00                                      | 0x00                   | 0x00                 |
| Padding       | 4 bytes |                                           |                        | 0x04                 |
| Next sibling  | link    | 0x04                                      | 0x04                   | 0x08                 |
| Parent        | link    | 0x08                                      | 0x0C                   | 0x10                 |
| Unknown       | u32     | 0x0C                                      | 0x14                   | 0x18                 |
| Padding       | 4 bytes |                                           |                        | 0x1C                 |
| Name offset   | link    | 0x10                                      | 0x18                   | 0x20                 |
| First child   | link    | 0x14                                      | 0x20                   | 0x28                 |
| First file    | link    | 0x18                                      | 0x28                   | 0x30                 |
| Record size   |         | 28                                        | 48                     | 56                   |

- Name checksum: see [Name checksum](#name-checksum).
- Next sibling: the next folder in the same parent folder.
- Parent: the folder that holds this one.
- Name offset: where the folder's name starts in the names block.
- First child, first file: the first folder and the first file this folder holds.

Folder 0 is the unnamed root: its next sibling, parent and name offset are null, and its checksum is 0, the CRC-32 of
an empty name. Reading rejects an index whose first folder has a name, a next sibling or a parent.

### File record

| Field         | Type    | Alan Wake | Alan Wake's American Nightmare | Quantum Break, Control | Alan Wake Remastered |
|---------------|---------|-----------|--------------------------------|------------------------|----------------------|
| Name checksum | u32     | 0x00      | 0x00                           | 0x00                   | 0x00                 |
| Padding       | 4 bytes |           |                                |                        | 0x04                 |
| Next sibling  | link    | 0x04      | 0x04                           | 0x04                   | 0x08                 |
| Parent        | link    | 0x08      | 0x08                           | 0x0C                   | 0x10                 |
| Flags         | u32     | 0x0C      | 0x0C                           | 0x14                   | 0x18                 |
| Padding       | 4 bytes |           |                                |                        | 0x1C                 |
| Name offset   | link    | 0x10      | 0x10                           | 0x18                   | 0x20                 |
| Data offset   | u64     | 0x14      | 0x14                           | 0x20                   | 0x28                 |
| Data size     | u64     | 0x1C      | 0x1C                           | 0x28                   | 0x30                 |
| Data CRC-32   | u32     | 0x24      | 0x24                           | 0x30                   | 0x38                 |
| Padding       | 4 bytes |           |                                |                        | 0x3C                 |
| Timestamp     | u64     |           | 0x28                           | 0x34                   |                      |
| Record size   |         | 40        | 48                             | 60                     | 64                   |

- Next sibling: the next file in the same folder.
- Parent: the folder that holds the file.
- Flags: unknown; 0 in every package of the supported games. Reading keeps the value, repacking keeps each file's
  flags and new files get 0.
- Data offset, data size: where the file's bytes lie in the data file.
- Data CRC-32: see [Data checksum](#data-checksum).
- Timestamp: see [Timestamps](#timestamps).

### Closing entry

In versions 7 to 9 one more folder record follows the file records, not counted in the header. Its checksum is 0, its
unknown field is like that of the other folder records, and its next sibling, parent, name offset, first child and
first file are null. Reading rejects a closing entry in which any of these five is not null.

### Names block

The names block holds the name of every folder and file but the root, each as UTF-8 ended by a NUL byte. Every entry
has its own copy of its name, stored in the order the entries are created (see [Entry order](#entry-order)), so the
names of folders and files are interleaved. Names keep their letter case. Writing refuses an empty name and a name
holding a NUL byte.

Reading rejects a name offset outside the block, a name that is not valid UTF-8 and a name that does not match its
checksum.

### Extra paths

| Type  | Field                                         |
|-------|-----------------------------------------------|
| u32   | Number of paths                               |
| u32   | Length of the path in bytes, before each path |
| bytes | The path in UTF-8, without a terminator       |

The list follows the names block only in one Alan Wake Remastered package; what the game does with these paths is
unknown. Any byte after the list is rejected. A new index holds the list only when the package has extra paths, and
repacking keeps the original's list.

## Checksums

Both checksums are the standard CRC-32 of zlib, ZIP and PNG.

### Name checksum

The name checksum of a folder or file is the CRC-32 of its own name (not its path) in UTF-8, with the ASCII letters
A to Z turned lowercase and every other byte as it is. `Readme.txt` and `readme.txt` both give `0x22598B08`. It is
stored like any other integer, in the byte order of the index. Reading checks every name against its checksum.

The engine finds entries by their lowercase names, so writing refuses two paths that differ only in the letter case
of ASCII letters, and a path listed twice.

### Data checksum

The data CRC-32 is that of the file's bytes in the data file. It is stored little-endian in every package, also in
the big-endian ones of Alan Wake and Alan Wake Remastered: the CRC-32 `0xD98C24E6` is stored as `e6 24 8c d9` in
both byte orders.

Extraction compares every file with its CRC-32 and reports each mismatch, but still extracts the file: some files in
Alan Wake's own packages do not match their stored CRC-32. Repacking keeps the stored CRC-32 of a file whose data has
not changed, an outdated one included.

## Tree

Folders and files form a tree through first-child and next-sibling links:

- A folder's first child links to its first subfolder; each subfolder links to the next through its next sibling, and
  the last one holds null.
- A folder's first file links to its first file; each file links to the next file of the folder in the same way.
- Every folder but the root and every file names its folder in its parent field.

The path of an entry is the names of the folders from the root down to it, then its own name. Empty folders are kept.
Reading walks the tree from the root and rejects a link to a missing entry, an entry linked twice, an entry whose
parent field names another folder than the one linking to it, and an entry that cannot be reached from the root.

## Entry order

The games' own packages create their entries in the order of their sorted paths, and a new index does the same:

1. Each folder and file gets a key: the names of its path joined by `\`, in UTF-8 with the ASCII letters lowercase.
   The key of a folder ends with `\`.
2. The keys are sorted byte by byte.
3. The entries are created in that order. A new folder or file takes the next record of its kind, appends its name to
   the names block and is linked after the entries of its kind created before it in the same folder.

The separator `\` (0x5C) sorts after `.`, `-` and digits but before `_` and letters, so `maps.txt` and the folder
`maps1` come before the folder `maps` and its contents, and `maps_old` after them. The folder records, file records
and names all follow this order, and the file records list the files in the order of their keys.

## Data file

The data file holds the bytes of the files and nothing else: no header, names or index. Only the data offset and size
in a file record locate a file. The package format has no compression or encryption of its own; each file is stored
as it is, and its size is that of the extracted file.

A new package stores the files in the order of their file records. Each file starts at a multiple of the data
alignment of the game (8 or 32 bytes), zero bytes fill the gaps, and the data file ends padded with zeros to a
multiple of the alignment. Some of the games' own packages store the data in another order than the file records;
extraction reads the files in the order of their offsets.

## Timestamps

In versions 7 to 9 each file record holds the file's last write time as a Windows FILETIME: the number of
100-nanosecond intervals since 1601-01-01 00:00 UTC. Packing stores the modification time of each file, cut to whole
100-nanosecond intervals, and extraction sets the access and modification times of the extracted file to the stored
value. Repacking keeps the stored time of a file whose data has not changed. `rmdp list` shows the times in UTC and
marks a value past the year 9999 as not a date. Version 2 stores no times, and files extracted from it keep the time of
extraction.

## Names on extraction

A folder or file is extracted under its name in the package, with the characters that file systems cannot hold
replaced by `%` and two uppercase hexadecimal digits of the character's code:

| Escaped                                              | Name in the package       | Extracted as          |
|------------------------------------------------------|---------------------------|-----------------------|
| `<`, `>`, `:`, `"`, `/`, `\`, `\|`, `?`, `*` and `%` | `d:`, `100%`              | `d%3A`, `100%25`      |
| Control characters U+0000 to U+001F                  | a tab between `a` and `b` | `a%09b`               |
| A `.` or space at the end of the name                | `..`, `trailing `         | `.%2E`, `trailing%20` |
| The first character of a reserved device name        | `nul.txt`, `COM1`         | `%6Eul.txt`, `%43OM1` |

A name is a reserved device name when its part before the first `.` is `CON`, `PRN`, `AUX`, `NUL`, `COM1` to `COM9`
or `LPT1` to `LPT9`, in any letter case. An entry with an empty name cannot be extracted.

Packing reverses the escaping: every `%` followed by two hexadecimal digits, in either case, becomes the character
with that code, so a literal `%` in the name of a folder or file to pack is written `%25`.

## Worked example

A directory `sample` holds three files, last modified at 2024-05-06 07:08:09, 07:08:10 and 07:08:11 UTC:

```text
sample/
  data/
    maps.txt     "Map list\n"
    maps/
      intro.txt  "Intro\n"
    Readme.txt   "Read me first\n"
```

```sh
northlighttools rmdp pack sample sample.rmdp --game american-nightmare
```

The sorted keys give the order in which the entries are created:

| Key                   | Entry    |
|-----------------------|----------|
| `data\`               | folder 1 |
| `data\maps.txt`       | file 0   |
| `data\maps\`          | folder 2 |
| `data\maps\intro.txt` | file 1   |
| `data\readme.txt`     | file 2   |

`sample.bin`, 449 bytes, where `*` stands for repeated lines of zeros:

```text
00000000  00 07 00 00 00 03 00 00  00 03 00 00 00 01 00 00  |................|
00000010  00 00 00 00 00 28 00 00  00 64 3a 5c 64 61 74 61  |.....(...d:\data|
00000020  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
*
00000090  00 00 00 00 00 00 00 00  00 00 00 00 00 ff ff ff  |................|
000000a0  ff ff ff ff ff 00 00 00  00 ff ff ff ff 01 00 00  |................|
000000b0  00 ff ff ff ff 63 f3 f3  ad ff ff ff ff 00 00 00  |.....c..........|
000000c0  00 00 00 00 00 00 00 00  00 02 00 00 00 00 00 00  |................|
000000d0  00 a5 08 2e 47 ff ff ff  ff 01 00 00 00 00 00 00  |....G...........|
000000e0  00 0e 00 00 00 ff ff ff  ff 01 00 00 00 d6 e4 c6  |................|
000000f0  15 02 00 00 00 01 00 00  00 00 00 00 00 05 00 00  |................|
00000100  00 00 00 00 00 00 00 00  00 09 00 00 00 00 00 00  |................|
00000110  00 e6 24 8c d9 80 92 6c  26 84 9f da 01 ec 77 9c  |..$....l&.....w.|
00000120  35 ff ff ff ff 02 00 00  00 00 00 00 00 13 00 00  |5...............|
00000130  00 10 00 00 00 00 00 00  00 06 00 00 00 00 00 00  |................|
00000140  00 a8 26 0f 0e 00 29 05  27 84 9f da 01 08 8b 59  |..&...).'......Y|
00000150  22 ff ff ff ff 01 00 00  00 00 00 00 00 1d 00 00  |"...............|
00000160  00 18 00 00 00 00 00 00  00 0e 00 00 00 00 00 00  |................|
00000170  00 8e 3a b7 94 80 bf 9d  27 84 9f da 01 00 00 00  |..:.....'.......|
00000180  00 ff ff ff ff ff ff ff  ff 00 00 00 00 ff ff ff  |................|
00000190  ff ff ff ff ff ff ff ff  ff 64 61 74 61 00 6d 61  |.........data.ma|
000001a0  70 73 2e 74 78 74 00 6d  61 70 73 00 69 6e 74 72  |ps.txt.maps.intr|
000001b0  6f 2e 74 78 74 00 52 65  61 64 6d 65 2e 74 78 74  |o.txt.Readme.txt|
000001c0  00                                                |.|
```

The header, 153 bytes:

| Offset | Bytes                     | Value                                         |
|--------|---------------------------|-----------------------------------------------|
| 0x00   | `00`                      | little-endian                                 |
| 0x01   | `07 00 00 00`             | version 7                                     |
| 0x05   | `03 00 00 00`             | 3 folder records: the root, `data` and `maps` |
| 0x09   | `03 00 00 00`             | 3 file records                                |
| 0x0D   | `01 00 00 00 00 00 00 00` | unknown, 1                                    |
| 0x15   | `28 00 00 00`             | 40 bytes of names                             |
| 0x19   | `64 3a 5c 64 61 74 61 00` | base path `d:\data`, then zeros up to 0x99    |

The folder records, 28 bytes each from 0x99:

| Folder      | Offset | Checksum     | Next sibling | Parent | Unknown | Name offset | First child | First file |
|-------------|--------|--------------|--------------|--------|---------|-------------|-------------|------------|
| 0, the root | 0x99   | `0x00000000` | null         | null   | 0       | null        | 1           | null       |
| 1, `data`   | 0xB5   | `0xADF3F363` | null         | 0      | 0       | 0           | 2           | 0          |
| 2, `maps`   | 0xD1   | `0x472E08A5` | null         | 1      | 0       | 14          | null        | 1          |

The file records, 48 bytes each from 0xED:

| File            | Offset | Checksum     | Next sibling | Parent | Flags | Name offset | Data offset | Size | CRC-32       | Timestamp            |
|-----------------|--------|--------------|--------------|--------|-------|-------------|-------------|------|--------------|----------------------|
| 0, `maps.txt`   | 0xED   | `0x15C6E4D6` | 2            | 1      | 0     | 5           | 0x00        | 9    | `0xD98C24E6` | `0x01DA9F84266C9280` |
| 1, `intro.txt`  | 0x11D  | `0x359C77EC` | null         | 2      | 0     | 19          | 0x10        | 6    | `0x0E0F26A8` | `0x01DA9F8427052900` |
| 2, `Readme.txt` | 0x14D  | `0x22598B08` | null         | 1      | 0     | 29          | 0x18        | 14   | `0x94B73A8E` | `0x01DA9F84279DBF80` |

Folder `data` links to its subfolder `maps` and to its first file `maps.txt`, which links to `Readme.txt` as its next
sibling. The timestamps are 2024-05-06 07:08:09, 07:08:10 and 07:08:11 UTC.

The closing entry from 0x17D holds a checksum of 0, null links, an unknown field of 0 and a null name offset. The
names block from 0x199 holds `data` at 0, `maps.txt` at 5, `maps` at 14, `intro.txt` at 19 and `Readme.txt` at 29.

`sample.rmdp`, 40 bytes, with each file at a multiple of 8:

```text
00000000  4d 61 70 20 6c 69 73 74  0a 00 00 00 00 00 00 00  |Map list........|
00000010  49 6e 74 72 6f 0a 00 00  52 65 61 64 20 6d 65 20  |Intro...Read me |
00000020  66 69 72 73 74 0a 00 00                           |first...|
```

Packed with `--game alan-wake` instead, the index starts with `01 00 00 00 02`, a big-endian version 2, and still
stores the CRC-32 of `maps.txt` as `e6 24 8c d9`.
