from dataclasses import dataclass

from northlighttools.binfnt.enumerators.font_version import FontVersion


@dataclass
class Kerning:
    first: int
    second: int
    amount: float

    def without_font_size(self, font_size: float, version: FontVersion):
        if version in [FontVersion.ALAN_WAKE, FontVersion.ALAN_WAKE_REMASTERED]:
            self.amount /= font_size
        else:
            self.amount *= font_size

        return self
