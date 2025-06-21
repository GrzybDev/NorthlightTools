from dataclasses import dataclass


@dataclass
class Unknown:
    """Unknown 6-value structure from binfnt file."""

    n1: int
    n2: int
    n3: int
    n4: int
    n5: int
    n6: int
