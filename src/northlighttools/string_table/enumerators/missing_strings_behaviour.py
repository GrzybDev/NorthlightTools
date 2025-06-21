from enum import Enum


class MissingStringBehaviour(str, Enum):
    """
    What to do when a localized string is missing.

    Attributes:
        KeyAndOriginal: Use the key and the original string as the localized string. This is the default.
        Key: Use the key as the localized string.
        Original: Use only original string as the localized string.
        Empty: Use an empty string as the localized string.
        Remove: Remove the key from the localization file.
        Error: Raise an error when a localized string is missing.
    """

    KeyAndOriginal = "key+original"
    Key = "key"
    Original = "original"
    Empty = "empty"
    Remove = "remove"
    Error = "error"
