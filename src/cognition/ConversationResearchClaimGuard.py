"""Catch a model reply that claims research Hypatia did not perform.

A system prompt can ask a model not to say "I found these sources". It cannot
make it true. Small local models in particular will narrate research they never
did, complete with authors, outlets, and dates, and the resulting text is
indistinguishable from a real finding.

So the guard is deterministic and sits after generation. It reads only the
reply Hypatia is about to return, looks for first-person research claims, and
compares them against canonical persisted state. When the state does not support
the claim, the reply is annotated — never silently edited — with a bounded
correction naming exactly what does and does not exist.

The guard never removes the model's text. Deleting it would hide that the model
made the claim, and the person deserves to see both the claim and the
correction. It also never adds a claim: it can only report counts that the
research operations themselves recorded.
"""

from __future__ import annotations

from research.CanonicalResearchSummary import CanonicalResearchSummary

MAX_INSPECTED_CHARACTERS = 8000

RESEARCH_CLAIM_PHRASES = (
    "i researched",
    "i have researched",
    "i collected evidence",
    "i gathered evidence",
    "i have collected",
    "i verified",
    "i have verified",
    "i confirmed",
    "i found these sources",
    "i found the following sources",
    "my sources show",
    "my sources are",
    "according to my research",
    "based on my research",
    "based on the sources i",
    "the sources i found",
    "sources i collected",
    "i searched the web",
    "i searched the internet",
    "i looked it up online",
    "arastirdim",
    "araştırdım",
    "kanit topladim",
    "kanıt topladım",
    "kanitlari topladim",
    "kanıtları topladım",
    "dogruladim",
    "doğruladım",
    "kaynaklarim",
    "kaynaklarım",
    "internette aradim",
    "internette aradım",
    "taradim",
    "taradım",
)

CORRECTION_HEADING = "Correction — what actually happened:"


class ConversationResearchClaimGuard:
    """Annotate a reply that claims research canonical state does not record."""

    def inspect(self, reply: str) -> bool:
        """Return whether this reply claims research in the first person."""
        if not isinstance(reply, str) or not reply.strip():
            return False
        forms = _normalized_forms(reply[:MAX_INSPECTED_CHARACTERS])
        return any(
            phrase in form for form in forms for phrase in RESEARCH_CLAIM_PHRASES
        )

    def annotate(self, reply: str, summary: CanonicalResearchSummary) -> str:
        """Return the reply with a bounded correction when it overclaims."""
        if not self.inspect(reply):
            return reply
        return "\n".join((reply.rstrip(), "", *self.correction(summary)))

    @staticmethod
    def correction(summary: CanonicalResearchSummary) -> tuple[str, ...]:
        """Render the bounded correction from canonical counts only."""
        return (
            CORRECTION_HEADING,
            "That reply was written by the language model from its own text. "
            "This turn performed no source discovery, no fetch, no source "
            "acceptance, and recorded no evidence.",
            *summary.lines(),
            "Anything named above as a source, paper, outlet, or date is model "
            "output, not something Hypatia read or verified.",
        )


def _normalized_forms(reply: str) -> tuple[str, ...]:
    """Return casefolded variants so Turkish dotted capitals also match."""
    plain = reply.casefold()
    turkish = reply.replace("İ", "i").replace("I", "ı").casefold()
    if turkish == plain:
        return (plain,)
    return (plain, turkish)
