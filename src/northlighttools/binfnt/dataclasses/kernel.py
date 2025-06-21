from dataclasses import dataclass


@dataclass
class Kernel:
    """Kerning pair for BMFont export/import."""

    first: int
    second: int
    amount: float
