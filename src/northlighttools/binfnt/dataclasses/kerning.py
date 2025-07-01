from dataclasses import dataclass


@dataclass
class Kerning:
    first: int
    second: int
    amount: float
