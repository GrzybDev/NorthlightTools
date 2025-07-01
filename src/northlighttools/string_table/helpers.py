from northlighttools.string_table.enumerators.missing_string_behaviour import (
    MissingStringBehaviour,
)


def get_translated_string(key, original_string, translated_string, missing_strings):
    # Only for CSV and PO files, JSON files are handled in apply methods
    if translated_string:
        return translated_string

    match missing_strings:
        case MissingStringBehaviour.KeyAndOriginal:
            return f"({key}) {original_string}"
        case MissingStringBehaviour.Key:
            return key
        case MissingStringBehaviour.Original:
            return original_string
        case MissingStringBehaviour.Empty:
            return ""
        case MissingStringBehaviour.Remove:
            return None
        case MissingStringBehaviour.Error:
            raise Exception(f"Missing localized string for {key}")
