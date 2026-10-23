# Binary fonts (.binfnt)

A `.binfnt` file holds one font of a Northlight game: a mesh for each glyph (usually one textured rectangle), a table
giving the glyph of each character, kerning pairs and the texture the glyphs are drawn from, embedded as a DDS file.
`northlighttools binfnt` reads and writes every version below and turns a font into an msdf-atlas-gen JSON document and
back.

## Versions

| Version | Games                                     | Kerning       | Values of unknown meaning | Texture size field | DDS header |
|---------|-------------------------------------------|---------------|---------------------------|--------------------|------------|
| 3       | Alan Wake, Alan Wake's American Nightmare | none          | none                      | yes                | D3DX       |
| 4       | Alan Wake Remastered                      | 12-byte pairs | none                      | yes                | DirectXTex |
| 6       | Quantum Break, in its fixedsys font only  | none          | two u32                   | no                 | DirectXTex |
| 7       | Quantum Break, Control                    | 8-byte pairs  | two u32                   | no                 | DirectXTex |

The tool refuses other version numbers.

## Layout

All values are little-endian. `u16` and `u32` are unsigned integers, `i32` is a signed one, `f32` an IEEE 754
single-precision float and `f16` a half-precision one. Sections follow one another with no padding or alignment.
Nothing in the file is compressed or encrypted, apart from DXT5 textures, which are block-compressed.

In the table, V, I, G and K are the vertex, index, glyph and kerning pair counts, and C is the offset of the character
map.

| Offset                  | Type                               | Field                                                   | Versions |
|-------------------------|------------------------------------|---------------------------------------------------------|----------|
| 0x00                    | u32                                | Version                                                 | all      |
| 0x04                    | u32                                | V                                                       | all      |
| 0x08                    | V × [vertex](#vertices)            | Vertex buffer                                           | all      |
| 8 + 16V                 | u32                                | I                                                       | all      |
| 12 + 16V                | I × u16                            | [Index buffer](#indices)                                | all      |
| 12 + 16V + 2I           | u32                                | G                                                       | all      |
| 16 + 16V + 2I           | G × [glyph record](#glyph-records) | Glyphs                                                  | all      |
| C = 16 + 16V + 2I + 44G | 65536 × u16                        | [Character map](#character-map)                         | all      |
| C + 0x20000             | u32                                | K, also written when it is 0                            | 4, 7     |
| C + 0x20004             | K × [kerning pair](#kerning)       | Kerning                                                 | 4, 7     |
| follows                 | 2 × u32                            | [Values of unknown meaning](#values-of-unknown-meaning) | 6, 7     |
| follows                 | u32                                | Size of the DDS file in bytes                           | 3, 4     |
| follows                 | bytes                              | [Texture](#texture), a DDS file                         | all      |

The texture ends the file. In versions 6 and 7 it takes every remaining byte; in versions 3 and 4 the tool refuses bytes
after it. Data that ends early is refused in every version.

## Vertices

Each vertex is 16 bytes:

| Offset | Type | Field |
|-------:|------|-------|
|   0x00 | f32  | x     |
|   0x04 | f32  | y     |
|   0x08 | f32  | u     |
|   0x0C | f32  | v     |

x and y are in em units, measured from the pen position on the baseline, with y pointing up. u and v are texture
coordinates from 0 to 1, measured from the texture's top-left corner, with v pointing down; u × width and v × height
give texel positions.

## Indices

Each index is a u16, and every three indices form a triangle. An index counts from the glyph's first vertex, not from
the start of the vertex buffer, so a rectangle glyph's indices are the same wherever its vertices lie.

The games' rectangle glyphs list their corners as bottom-left, bottom-right, top-right and top-left, and draw the
triangles 0 1 2 and 0 2 3. Some glyphs use another triangle order or a mesh of more vertices.

## Glyph records

Each record is 44 bytes:

| Offset | Type    | Field                                                                                      |
|-------:|---------|--------------------------------------------------------------------------------------------|
|   0x00 | u16     | First vertex in the vertex buffer                                                          |
|   0x02 | u16     | Vertex count                                                                               |
|   0x04 | u16     | First index in the index buffer                                                            |
|   0x06 | u16     | Index count, three per triangle                                                            |
|   0x08 | u32     | Texture channel: 0 red, 1 green, 2 blue, 3 alpha (see [Channel packing](#channel-packing)) |
|   0x0C | 8 × f32 | Layout box: x and y of its bottom-left, bottom-right, top-right and top-left corners       |

The glyphs' ranges follow one another in glyph order and together cover both buffers: each glyph starts where the
previous one ends. Every font of the games is stored this way, and the tool refuses fonts that are not, as well as
glyphs whose indices reach past their own vertices. Since the first vertex and first index are u16, no glyph can start
past vertex or index 65535.

The layout box is in em units, like the vertices. In nearly all of the games' glyphs it is a rectangle whose left edge
is at 0 and whose right edge is the glyph's advance; the rest have other corners.

## Character map

65536 u16 entries (0x20000 bytes), one per character code from U+0000 to U+FFFF: entry n holds the index of the glyph
drawn for U+n, or 0 when the font lacks the character, which is then drawn with glyph 0. Since 0 means none, no
character maps to glyph 0 explicitly, and characters outside the Basic Multilingual Plane cannot be mapped. The tool
refuses entries pointing past the last glyph.

In the games' fonts every glyph after glyph 0 serves exactly one character; `decompile` refuses fonts where a glyph
serves several characters or none, which its JSON document cannot hold.

## Kerning

Versions 4 and 7 only: a u32 pair count, then the pairs. Pairs name characters, not glyphs. The tool refuses to write
kerning pairs into a version 3 or 6 font.

Version 4, 12 bytes per pair:

| Offset | Type | Field                              |
|-------:|------|------------------------------------|
|   0x00 | u32  | First character code               |
|   0x04 | u32  | Second character code              |
|   0x08 | i32  | Amount, an integer of unknown unit |

Version 7, 8 bytes per pair:

| Offset | Type | Field                 |
|-------:|------|-----------------------|
|   0x00 | u16  | First character code  |
|   0x02 | u16  | Second character code |
|   0x04 | f32  | Amount in em units    |

The version 4 amounts in Alan Wake Remastered lie between -145 and 60; the tool refuses to write amounts that are not
whole numbers into a version 4 font.

## Values of unknown meaning

Versions 6 and 7 store two u32 values of unknown meaning, after the character map in version 6 and after the kerning in
version 7. The tool keeps them as they are, in the `unknown` field of the JSON document's `northlight` object, and
writes exactly two into these versions and none into the others. The games' fonts hold these:

| Values | Fonts                                                                     |
|--------|---------------------------------------------------------------------------|
| 0, 0   | Version 6 fonts, and version 7 fonts with an A8R8G8B8 texture             |
| 4, 64  | Version 7 fonts whose distance fields reach 4 texels outside the glyphs   |
| 4, 128 | Version 7 fonts whose distance fields reach 8 texels or more outside them |

## Texture

The texture is a complete DDS file: a 4-byte magic, a 124-byte header and the pixel data of each mipmap level. Its
dimensions need not be powers of two.

### DDS header

Offsets from the start of the DDS file:

| Offset | Type     | Field                | Value                                  |
|-------:|----------|----------------------|----------------------------------------|
|   0x00 | 4 bytes  | Magic                | `DDS `                                 |
|   0x04 | u32      | Header size          | 124                                    |
|   0x08 | u32      | Flags                | see the flags table                    |
|   0x0C | u32      | Height               |                                        |
|   0x10 | u32      | Width                |                                        |
|   0x14 | u32      | Pitch or linear size | see [conventions](#header-conventions) |
|   0x18 | u32      | Depth                | 0 or 1                                 |
|   0x1C | u32      | Mipmap count         |                                        |
|   0x20 | 11 × u32 | Reserved             | 0                                      |
|   0x4C | u32      | Pixel format size    | 32                                     |
|   0x50 | u32      | Pixel format flags   | see the flags table                    |
|   0x54 | 4 bytes  | FourCC               | see [pixel formats](#pixel-formats)    |
|   0x58 | u32      | Bits per texel       | 0 for FourCC formats                   |
|   0x5C | u32      | Red mask             | 0 for FourCC formats                   |
|   0x60 | u32      | Green mask           | 0 for FourCC formats                   |
|   0x64 | u32      | Blue mask            | 0 for FourCC formats                   |
|   0x68 | u32      | Alpha mask           | 0 for FourCC formats                   |
|   0x6C | u32      | Caps                 | see the flags table                    |
|   0x70 | 3 × u32  | Caps 2 to 4          | 0                                      |
|   0x7C | u32      | Reserved             | 0                                      |
|   0x80 | bytes    | Mipmap levels        |                                        |

Flags used in the games' fonts:

| Field              |      Bit | Name             | Meaning                                      |
|--------------------|---------:|------------------|----------------------------------------------|
| Flags              |      0x1 | DDSD_CAPS        | Caps are valid                               |
| Flags              |      0x2 | DDSD_HEIGHT      | Height is valid                              |
| Flags              |      0x4 | DDSD_WIDTH       | Width is valid                               |
| Flags              |      0x8 | DDSD_PITCH       | Pitch holds the bytes per row                |
| Flags              |   0x1000 | DDSD_PIXELFORMAT | Pixel format is valid                        |
| Flags              |  0x20000 | DDSD_MIPMAPCOUNT | Mipmap count is valid                        |
| Flags              |  0x80000 | DDSD_LINEARSIZE  | Pitch holds the byte size of the first level |
| Pixel format flags |      0x1 | DDPF_ALPHAPIXELS | The alpha mask is valid                      |
| Pixel format flags |      0x4 | DDPF_FOURCC      | FourCC names the format                      |
| Pixel format flags |     0x40 | DDPF_RGB         | Bits per texel and the masks name the format |
| Caps               |      0x2 | DDSCAPS_ALPHA    | Set by D3DX for uncompressed formats         |
| Caps               |      0x8 | DDSCAPS_COMPLEX  | The file holds more than one image           |
| Caps               |   0x1000 | DDSCAPS_TEXTURE  | Always set                                   |
| Caps               | 0x400000 | DDSCAPS_MIPMAP   | The file holds mipmaps                       |

When reading, the tool checks the magic, the header size and the pixel format size, and takes the pixel format from the
pixel format flags with the FourCC, or with the bits per texel and the four masks. It reads as many levels as the
mipmap count gives when DDSD_MIPMAPCOUNT is set and the count is not 0, otherwise one level. It ignores the pitch, the
depth, the caps and the reserved fields, and refuses bytes after the last level.

### Header conventions

Version 3 fonts carry the header D3DX writes; later versions carry the header DirectXTex writes, which also fills the
pitch and the depth. The tool writes the same conventions, so a rebuilt font matches the games' bytes:

| Field              | Version 3 (D3DX)                                                      | Versions 4, 6 and 7 (DirectXTex)                                   |
|--------------------|-----------------------------------------------------------------------|--------------------------------------------------------------------|
| Flags              | 0x1007, plus 0x20000 with mipmaps                                     | 0x2100F; 0xA1007 for DXT5                                          |
| Pitch              | 0                                                                     | Width × bytes per texel; for DXT5 the byte size of the first level |
| Depth              | 0                                                                     | 1                                                                  |
| Mipmap count       | 0 for a single level, otherwise the number of levels                  | The number of levels, 1 for a single level                         |
| Caps               | 0x1000, plus 0x2 for uncompressed formats, plus 0x400008 with mipmaps | 0x1000, plus 0x400008 with mipmaps                                 |
| Pixel format flags | 0x41 for A4R4G4B4 and A8R8G8B8, 0x4 for DXT5 and R16F                 | The same                                                           |

### Pixel formats

| Format   | Identified by                                                           | Size                     | Texel layout                                            | Games                                                           |
|----------|-------------------------------------------------------------------------|--------------------------|---------------------------------------------------------|-----------------------------------------------------------------|
| A4R4G4B4 | DDPF_RGB, 16 bits, masks 0x0F00, 0x00F0, 0x000F, 0xF000                 | 2 bytes per texel        | u16: alpha in bits 12–15, red 8–11, green 4–7, blue 0–3 | Alan Wake, Alan Wake's American Nightmare                       |
| A8R8G8B8 | DDPF_RGB, 32 bits, masks 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000 | 4 bytes per texel        | Bytes blue, green, red, alpha                           | All                                                             |
| DXT5     | DDPF_FOURCC, FourCC `DXT5`                                              | 16 bytes per 4 × 4 block | DXT5 (BC3) blocks                                       | Alan Wake, Alan Wake's American Nightmare, Alan Wake Remastered |
| R16F     | DDPF_FOURCC, FourCC `6F 00 00 00` (D3DFMT_R16F, 111)                    | 2 bytes per texel        | f16 distance                                            | Quantum Break, Control                                          |

The masks are listed red, green, blue, alpha. A level of w × h texels takes w × h × the bytes per texel, or for DXT5
max(1, ⌈w / 4⌉) × max(1, ⌈h / 4⌉) × 16 bytes. The tool refuses other pixel formats. It converts A4R4G4B4,
A8R8G8B8 and R16F textures to images and back, and keeps DXT5 textures as DDS files.

### Mipmaps

The levels follow the header with no padding, the full-size image first. Level n is max(1, width >> n) ×
max(1, height >> n) texels.

In the games' fonts, the textures with mipmaps are A4R4G4B4 textures of Alan Wake's American Nightmare (10 levels),
A8R8G8B8 textures of Alan Wake Remastered (2 levels) and DXT5 textures (2, 3 or 9 levels); the others, all distance
fields included, have a single level.

The games' uncompressed mipmaps average 2 × 2 blocks of the level above, channel by channel on the stored 4-bit or
8-bit values, rounding halves up: (a + b + c + d + 2) div 4. An odd last row or column is dropped, and along a side
that is 1 texel long each texel counts twice. The tool rebuilds mipmaps this way, which reproduces the games' own
exactly. For R16F, which the games store without mipmaps, it averages in single precision, rounds to the nearest half
float and writes 0x7FFF for every block that holds a not-a-number.

### Channel packing

A glyph's channel field names the texture channel that holds it. Many fonts of Alan Wake, Alan Wake's American
Nightmare and Alan Wake Remastered pack up to four glyphs into the same texels, one per channel, so the texels of a
glyph's rectangle also carry other glyphs in their other channels. In Quantum Break and Control every glyph has
channel 0.

| Channel   | A4R4G4B4 bits | A8R8G8B8 byte |
|-----------|---------------|--------------:|
| 0 (red)   | 8–11          |             2 |
| 1 (green) | 4–7           |             1 |
| 2 (blue)  | 0–3           |             0 |
| 3 (alpha) | 12–15         |             3 |

### Distance fields

R16F textures hold signed distance fields: each texel holds its distance in texels to the glyph's outline, negative
inside the glyph and positive outside it. Texels beyond the field's reach hold 0x7FFF, a not-a-number. In the games'
fonts the fields reach 4 to 9 texels outside the glyphs.

## Worked example

An invented version 7 font, built with the tool. It has glyph 0 for missing characters and glyphs for A (U+0041) and
V (U+0056). Each glyph is a rectangle from (-0.125, -0.125) to (0.625, 0.625) em with a layout box from 0 to 0.5
across and from -0.25 to 0.75 up. One kerning pair gives A followed by V the amount -0.125 em, the values of
unknown meaning are 4 and 128, and the texture is a 4 × 4 R16F image with a single level whose top-left, top-right
and bottom-left quarters hold the three glyphs. The file is 131,628 (0x2022C) bytes, 131,072 of them the character
map.

The version and the vertices of glyph 0:

```
00000000  07 00 00 00 0c 00 00 00 00 00 00 be 00 00 00 be
00000010  00 00 00 00 00 00 00 3f 00 00 20 3f 00 00 00 be
00000020  00 00 00 3f 00 00 00 3f 00 00 20 3f 00 00 20 3f
00000030  00 00 00 3f 00 00 00 00 00 00 00 be 00 00 20 3f
00000040  00 00 00 00 00 00 00 00
```

| Offset | Field                  | Value                                                  |
|-------:|------------------------|--------------------------------------------------------|
|   0x00 | Version                | 7                                                      |
|   0x04 | Vertex count           | 12                                                     |
|   0x08 | Vertex 0, bottom-left  | x -0.125, y -0.125, u 0, v 0.5                         |
|   0x18 | Vertex 1, bottom-right | x 0.625, y -0.125, u 0.5, v 0.5                        |
|   0x28 | Vertex 2, top-right    | x 0.625, y 0.625, u 0.5, v 0                           |
|   0x38 | Vertex 3, top-left     | x -0.125, y 0.625, u 0, v 0                            |
|   0x48 | Vertices 4 to 11       | Glyphs A and V, with u and v in their texture quarters |

The index buffer and the glyph count:

```
000000c8  12 00 00 00 00 00 01 00 02 00 00 00 02 00 03 00
000000d8  00 00 01 00 02 00 00 00 02 00 03 00 00 00 01 00
000000e8  02 00 00 00 02 00 03 00 03 00 00 00
```

| Offset | Field       | Value                                                             |
|-------:|-------------|-------------------------------------------------------------------|
|   0xC8 | Index count | 18                                                                |
|   0xCC | Indices     | 0 1 2 0 2 3 for each glyph, counted from the glyph's first vertex |
|   0xF0 | Glyph count | 3                                                                 |

The glyph records:

```
000000f4  00 00 04 00 00 00 06 00 00 00 00 00 00 00 00 00
00000104  00 00 80 be 00 00 00 3f 00 00 80 be 00 00 00 3f
00000114  00 00 40 3f 00 00 00 00 00 00 40 3f 04 00 04 00
00000124  06 00 06 00 00 00 00 00 00 00 00 00 00 00 80 be
00000134  00 00 00 3f 00 00 80 be 00 00 00 3f 00 00 40 3f
00000144  00 00 00 00 00 00 40 3f 08 00 04 00 0c 00 06 00
00000154  00 00 00 00 00 00 00 00 00 00 80 be 00 00 00 3f
00000164  00 00 80 be 00 00 00 3f 00 00 40 3f 00 00 00 00
00000174  00 00 40 3f
```

| Offset | Field       | Value                                                                                         |
|-------:|-------------|-----------------------------------------------------------------------------------------------|
|   0xF4 | Glyph 0     | Vertices 0 to 3, indices 0 to 5, channel 0, box (0, -0.25) (0.5, -0.25) (0.5, 0.75) (0, 0.75) |
|  0x120 | Glyph 1 (A) | Vertices 4 to 7, indices 6 to 11, the same channel and box                                    |
|  0x14C | Glyph 2 (V) | Vertices 8 to 11, indices 12 to 17, the same channel and box                                  |

The character map runs from 0x178 to 0x20177. The entries for U+0041 at 0x178 + 2 × 0x41 = 0x1FA and for U+0056 at
0x224 hold glyphs 1 and 2; every other entry is 0:

```
000001f8  00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00
00000208  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00000218  00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00
```

The kerning, the values of unknown meaning and the texture:

```
00020178  01 00 00 00 41 00 56 00 00 00 00 be 04 00 00 00
00020188  80 00 00 00 44 44 53 20 7c 00 00 00 0f 10 02 00
00020198  04 00 00 00 04 00 00 00 08 00 00 00 01 00 00 00
000201a8  01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
000201b8  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
000201c8  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
000201d8  20 00 00 00 04 00 00 00 6f 00 00 00 00 00 00 00
000201e8  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
000201f8  00 10 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00020208  00 00 00 00 00 38 00 38 00 38 00 38 00 b8 00 b8
00020218  00 b8 00 b8 00 38 00 38 ff 7f ff 7f 00 b8 00 b8
00020228  ff 7f ff 7f
```

|  Offset | Field                            | Value                             |
|--------:|----------------------------------|-----------------------------------|
| 0x20178 | Kerning pair count               | 1                                 |
| 0x2017C | Kerning pair                     | U+0041, U+0056, -0.125            |
| 0x20184 | Values of unknown meaning        | 4, 128                            |
| 0x2018C | DDS magic, header size           | `DDS `, 124                       |
| 0x20194 | Flags                            | 0x2100F                           |
| 0x20198 | Height, width                    | 4, 4                              |
| 0x201A0 | Pitch                            | 8 (4 texels × 2 bytes)            |
| 0x201A4 | Depth, mipmap count              | 1, 1                              |
| 0x201AC | Reserved                         | 44 zero bytes                     |
| 0x201D8 | Pixel format size, flags, FourCC | 32, 0x4 (DDPF_FOURCC), 111 (R16F) |
| 0x201E4 | Bits per texel and masks         | 0                                 |
| 0x201F8 | Caps                             | 0x1000                            |
| 0x201FC | Caps 2 to 4, reserved            | 0                                 |
| 0x2020C | Texels                           | 4 rows of 4 half floats           |

The texel rows are 0.5 (`00 38`) four times; -0.5 (`00 b8`) four times; 0.5, 0.5 and 0x7FFF twice; -0.5, -0.5 and
0x7FFF twice. The top row of each glyph's quarter lies outside its outline and the bottom row inside, and the unused
quarter lies beyond the field.

As a version 4 font, the same glyphs would take 12 bytes per kerning pair with a whole-number amount, drop the values
of unknown meaning and put the DDS file's size, `a0 00 00 00` (160), before it. As a version 3 font, they would also
drop the kerning section and carry the D3DX header: flags 0x1007, pitch 0, depth 0, mipmap count 0 and caps 0x1002.
