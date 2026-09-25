"""What kind of evidence one security hypothesis evidence link cites.

Exactly one member: HTTP Evidence is the first realistic subject this
milestone builds against. Asset observations, general research evidence, and
session contexts are deferred, additive future members — nothing here
guesses at their shape ahead of a milestone that actually needs them.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityHypothesisEvidenceKind(StrEnum):
    """Name the kind of evidence record one hypothesis evidence link cites."""

    HTTP_EVIDENCE = "http_evidence"
