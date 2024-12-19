# Northlight Tools

Collection of various tools for Northlight Engine used for Polish fan translation of Quantum Break!

Table of Contents
-----------------
- [Usage](#usage)
- [Credits](#credits)

Usage
-----

You can append `--help` to each command to see more detailed usage!

### RMDP Archive Tools

#### Unpack `ep999-000-en.rmdp` archive (to the same folder as archive):
```
northlighttools rmdp unpack path/to/ep999-000-en.rmdp
```

#### Unpack `ep999-000-en.emdp` archive to `output` folder:
```
northlighttools rmdp unpack path/to/ep999-000-en.rmdp output
```

#### Pack folder back to `ep999-000-en.rmdp` file
```
northlighttools rmdp pack path/to/input/folder ep999-000-en.rmdp
```

Pack command also supports following optional parameters:

`--archive-endianness` with possible values being either `little` or `big`, this will force archive to specific endianness

`--archive-version` with possible values being `2`, `7`, `8`, `9`, this will force archive to be in specific version

| Version | Compatible with game          |
|:-------:|:-----------------------------:|
| 2       | Alan Wake                     |
| 7       | Alan Wake: American Nightmare |
| 8       | Quantum Break                 |
| 9       | Control                       |


### BINFNT Tools

#### Decompile `customer_facing.binfnt` to `output` folder
```
northlighttools binfnt decompile customer_facing.binfnt output
```

#### Decompile `customer_facing.binfnt` to `output` folder with character textures seperated
```
northlighttools binfnt decompile customer_facing.binfnt output --seperate-char-bitmap
```

#### Compile `customer_facing.fnt` using `customer_facing_orig.binfnt` as reference to `customer_facing_new.binfnt`
```
northlighttools binfnt compile d:\Mods\QuantumBreakPL\d_\data\fonts\locale\en\customer_facing.binfnt D:\Fonts\QuantumBreak\customer_facing\customer_facing.fnt test.binfnt
```

### String Table Tools

#### Supported input/output file formats

- XML (default)
- JSON
- CSV
- PO

#### Export `string_table.bin` to XML
```
northlighttools string_table export string_table.bin
```

#### Export `string_table.bin` to PO
```
northlighttools string_table export string_table.bin --output-type po
```

#### Import `string_table.csv` to `string_table.bin`
```
northlighttools string_table import string_table.csv string_table.bin
```

Import tool can take optional `--missing-strings` parameter which will change behaviour for strings that doesn't have translation (...yet)

***Note: Missing strings handling are only available if importing from either CSV or PO!***

| --missing-strings | Description | Example Entry |
|:-----------------:|:-----------:|:--------------:
| key+original      | Use the key and the original string as the localized string. This is the default. | (example_key) Example Value
| key               | Use the key as the localized string. | example_key |
| original          | Use only original string as the localized string. | Example Value
| empty             | Use an empty string as the localized string. | |
| remove            | Remove the key from the localization file. | N/A |
| error             | Raise an error when a localized string is missing. | N/A |


Credits
-------

- [GrzybDev](https://grzyb.dev)

Thanks to:
- [Nostritius](https://github.com/Nostritius) who created [AWTools](https://github.com/Nostritius/AWTools) which helped with understanding rmdp and string table formats
- [eprilx](https://github.com/eprilx) who created [NorthlightFontMaker](https://github.com/eprilx/NorthlightFontMaker) which helped with understanding binfnt format!

Special thanks to:
- Remedy Entertainment (for making Northlight Engine)
