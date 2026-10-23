"""Reading and writing the index (.bin) of a Remedy package.

The index holds a header, a table of folders, a table of files, a block of
NUL-terminated names and, in some packages, a list of extra paths. Folders and
files form a tree through first-child and next-sibling links; the games' own
packages create entries in the order of their sorted paths, which encoding
reproduces.
"""

from northlighttools.rmdp.index.decoder import decode_index
from northlighttools.rmdp.index.encoder import encode_index, patch_index

__all__ = ["decode_index", "encode_index", "patch_index"]
