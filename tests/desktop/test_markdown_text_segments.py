"""Markdown segmentation must never lose a character of a reply.

The desktop transcript showed raw markers like **Morvella**. Styling them is
presentation, so the one hard rule is that presentation cannot change content:
stripping the marker characters from the input and from the rendered text must
yield the same string, and anything the parser cannot match confidently is left
literal rather than guessed at.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.MarkdownTextSegments import (
    MarkdownSegment,
    MarkdownStyle,
    markdown_segments,
    rendered_text,
)

SAMPLES = (
    "",
    "plain text",
    "Your secret word is **Morvella**.",
    "This is *emphasis* and this is _also emphasis_.",
    "Call `markdown_segments(value)` to split it.",
    "Mixed **bold**, *italic*, and `code` together.",
    "An unclosed **marker stays literal.",
    "Empty ** ** and **** spans.",
    "snake_case_identifier_stays_plain",
    "Line one **bold**\nLine two *italic*",
    "A star * on its own.",
    "Markers across\n**a line break** do not pair with the first line.",
)


class MarkdownSegmentTests(unittest.TestCase):
    def test_no_sample_loses_a_content_character(self) -> None:
        """Styling removes markers and nothing else, in the original order."""
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                rendered = rendered_text(markdown_segments(sample))
                self.assertEqual(_without_markers(rendered), _without_markers(sample))

    def test_segment_text_always_concatenates_to_the_rendered_text(self) -> None:
        for sample in SAMPLES:
            with self.subTest(sample=sample):
                segments = markdown_segments(sample)
                self.assertEqual(
                    "".join(segment.text for segment in segments),
                    rendered_text(segments),
                )

    def test_bold_is_recognised_and_its_markers_are_removed(self) -> None:
        segments = markdown_segments("Your secret word is **Morvella**.")

        self.assertEqual(
            segments,
            (
                MarkdownSegment("Your secret word is "),
                MarkdownSegment("Morvella", MarkdownStyle.BOLD),
                MarkdownSegment("."),
            ),
        )
        self.assertEqual(rendered_text(segments), "Your secret word is Morvella.")

    def test_italic_is_recognised_with_either_marker(self) -> None:
        for sample in ("an *emphasis* here", "an _emphasis_ here"):
            with self.subTest(sample=sample):
                styles = [segment.style for segment in markdown_segments(sample)]
                self.assertIn(MarkdownStyle.ITALIC, styles)

    def test_inline_code_is_recognised_and_not_parsed_further(self) -> None:
        segments = markdown_segments("Run `a ** b` now.")

        self.assertEqual(
            segments[1],
            MarkdownSegment("a ** b", MarkdownStyle.CODE),
        )

    def test_bold_wins_over_italic_at_the_same_position(self) -> None:
        segments = markdown_segments("**strong**")

        self.assertEqual(segments, (MarkdownSegment("strong", MarkdownStyle.BOLD),))

    def test_an_unclosed_marker_stays_literal(self) -> None:
        segments = markdown_segments("An unclosed **marker stays literal.")

        self.assertEqual(
            segments,
            (MarkdownSegment("An unclosed **marker stays literal."),),
        )

    def test_an_empty_span_stays_literal(self) -> None:
        self.assertEqual(
            markdown_segments("nothing **** here"),
            (MarkdownSegment("nothing **** here"),),
        )

    def test_an_identifier_keeps_its_underscores(self) -> None:
        segments = markdown_segments("call learned_memory_context now")

        self.assertEqual(
            segments,
            (MarkdownSegment("call learned_memory_context now"),),
        )
        self.assertEqual(
            rendered_text(segments),
            "call learned_memory_context now",
        )

    def test_a_span_never_crosses_a_line_break(self) -> None:
        segments = markdown_segments("first *line\nsecond* line")

        self.assertEqual(segments, (MarkdownSegment("first *line\nsecond* line"),))

    def test_styles_are_applied_per_line_independently(self) -> None:
        segments = markdown_segments("one **bold**\ntwo *italic*")
        styles = [segment.style for segment in segments]

        self.assertIn(MarkdownStyle.BOLD, styles)
        self.assertIn(MarkdownStyle.ITALIC, styles)
        self.assertEqual(rendered_text(segments), "one bold\ntwo italic")

    def test_an_empty_or_invalid_value_yields_no_segments(self) -> None:
        self.assertEqual(markdown_segments(""), ())
        self.assertEqual(markdown_segments(None), ())  # type: ignore[arg-type]

    def test_plain_text_is_one_segment(self) -> None:
        self.assertEqual(
            markdown_segments("plain text"),
            (MarkdownSegment("plain text"),),
        )


def _without_markers(value: str) -> str:
    """Drop every marker character so only content remains for comparison."""
    return value.replace("**", "").replace("*", "").replace("_", "").replace("`", "")


if __name__ == "__main__":
    unittest.main()
