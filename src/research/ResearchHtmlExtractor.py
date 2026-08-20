"""Small standard-library HTML-to-text extractor for research sources."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from core.Exceptions import ResearchError

_BLOCK_ELEMENTS = {
    "article",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "main",
    "p",
    "section",
}
_IGNORED_ELEMENTS = {"noscript", "script", "style", "svg"}


class ResearchHtmlExtractor(HTMLParser):
    """Extract a page title and readable block text without executing content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        normalized = tag.casefold()
        if normalized in _IGNORED_ELEMENTS:
            self._ignored_depth += 1
        if normalized == "title" and self._ignored_depth == 0:
            self._in_title = True
        if normalized in _BLOCK_ELEMENTS and self._ignored_depth == 0:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "title":
            self._in_title = False
        if normalized in _IGNORED_ELEMENTS and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return
        if normalized in _BLOCK_ELEMENTS and self._ignored_depth == 0:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data)
            return
        self._text_parts.append(data)

    def extracted(self) -> tuple[str, str]:
        """Return normalized title and paragraph text after parsing is complete."""
        title = _collapse_inline_whitespace(" ".join(self._title_parts))
        blocks = [
            _collapse_inline_whitespace(block)
            for block in "".join(self._text_parts).splitlines()
            if block.strip()
        ]
        content = "\n\n".join(blocks)
        if not content:
            raise ResearchError("Research source did not contain readable text.")
        return title, content


def _collapse_inline_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
