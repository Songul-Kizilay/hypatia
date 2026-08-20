"""Bounded source metadata proposed by a replaceable discovery provider."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchSourceCandidate:
    """Describe an unaccepted HTTPS result without acquiring its content."""

    url: str
    title: str
    snippet: str

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ResearchError("Research source candidate URL cannot be empty.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ResearchError("Research source candidate title cannot be empty.")
        if not isinstance(self.snippet, str):
            raise ResearchError("Research source candidate snippet must be text.")

        url = self.url.strip()
        title = " ".join(self.title.split())
        snippet = " ".join(self.snippet.split())
        if len(url) > 2_048:
            raise ResearchError("Research source candidate URL is too long.")
        if len(title) > 500:
            raise ResearchError("Research source candidate title is too long.")
        if len(snippet) > 1_000:
            raise ResearchError("Research source candidate snippet is too long.")
        if any(character in url for character in ("\r", "\n", "\t")):
            raise ResearchError("Research source candidate URL is invalid.")

        parsed = urlparse(url)
        try:
            port = parsed.port
        except ValueError as error:
            raise ResearchError("Research source candidate URL is invalid.") from error
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
        ):
            raise ResearchError(
                "Research source candidates must use credential-free HTTPS."
            )

        object.__setattr__(self, "url", url)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "snippet", snippet)
