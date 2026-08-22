"""
Hypatia Version Information
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    """
    Represents the current Hypatia version.
    """

    major: int = 0
    minor: int = 3
    patch: int = 111
    codename: str = "Genesis"

    @property
    def short(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def full(self) -> str:
        return f"{self.short} ({self.codename})"


VERSION = Version()
