"""The paragraphs of a text and the layout around them.

Texts are laid out with line breaks and \\n escape sequences. A layout run is a
stretch of them together with the spaces and tabs next to them; translation
formats offer the paragraphs between layout runs for translation and carry the
layout runs unchanged, so a text comes back exactly as it was.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

# A run starts at its first blank; trying the later ones would take quadratic time.
_LAYOUT = re.compile(r"(?<![ \t])[ \t]*(?:(?:\r\n|[\r\n]|\\n)[ \t]*)+")


@dataclass(frozen=True)
class Layout:
    """A text as its paragraphs and the layout runs before, between and after them.

    There is always one run more than paragraphs; the outer ones may be empty.
    A text with no paragraph, empty or all layout, is one empty paragraph
    followed by its layout, so every text has at least one paragraph.
    """

    paragraphs: tuple[str, ...]
    runs: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.runs) != len(self.paragraphs) + 1:
            msg = "A layout needs one run more than it has paragraphs"
            raise ValueError(msg)

    @classmethod
    def of(cls, text: str) -> "Layout":
        """Split a text into its paragraphs and layout runs."""
        parts = _LAYOUT.split(text)
        matches = _LAYOUT.findall(text)
        paragraphs = tuple(part for part in parts if part)
        if not paragraphs:
            return cls(("",), ("", text))
        before = "" if parts[0] else matches[0]
        after = (
            matches[index] if index < len(matches) else ""
            for index, part in enumerate(parts)
            if part
        )
        return cls(paragraphs, (before, *after))

    def join(self, paragraphs: Sequence[str]) -> str:
        """Lay out these paragraphs, the text's own or translations of them."""
        if len(paragraphs) != len(self.paragraphs):
            msg = f"Expected {len(self.paragraphs)} paragraphs, got {len(paragraphs)}"
            raise ValueError(msg)
        return self.runs[0] + "".join(
            paragraph + run
            for paragraph, run in zip(paragraphs, self.runs[1:], strict=True)
        )
