from dataclasses import dataclass


@dataclass
class UVMapping:
    """UV mapping rectangle for a character in the texture."""

    UVLeft: float
    UVTop: float
    UVRight: float
    UVBottom: float
