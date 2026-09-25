"""Conservative secret-ingress refusal for research free-text fields.

This policy is deliberately a floor, not complete secret detection. It catches
only a small set of high-confidence secret-bearing forms before persistence.
It returns a bounded category and never returns, logs, hashes, masks, or
otherwise carries the candidate value.
"""

from __future__ import annotations

import re
from enum import StrEnum

__all__ = ["ResearchSensitiveInputClass", "ResearchSensitiveInputPolicy"]

MAX_RESEARCH_SENSITIVE_INPUT_CHARACTERS = 2_000


class ResearchSensitiveInputClass(StrEnum):
    """Name one bounded refusal class without carrying secret material."""

    NONE = "none"
    CREDENTIAL_BEARING_URL = "credential_bearing_url"
    AUTHENTICATION_HEADER = "authentication_header"
    PRIVATE_KEY_MATERIAL = "private_key_material"
    SECRET_ASSIGNMENT = "secret_assignment"
    TOKEN_FORMAT = "token_format"

    @property
    def operator_label(self) -> str:
        return _OPERATOR_LABELS[self]

    @property
    def refused(self) -> bool:
        return self is not ResearchSensitiveInputClass.NONE


_OPERATOR_LABELS: dict[ResearchSensitiveInputClass, str] = {
    ResearchSensitiveInputClass.NONE: "no sensitive class",
    ResearchSensitiveInputClass.CREDENTIAL_BEARING_URL: ("a credential-bearing URL"),
    ResearchSensitiveInputClass.AUTHENTICATION_HEADER: (
        "authentication or cookie header material"
    ),
    ResearchSensitiveInputClass.PRIVATE_KEY_MATERIAL: "private-key material",
    ResearchSensitiveInputClass.SECRET_ASSIGNMENT: "an explicit secret assignment",
    ResearchSensitiveInputClass.TOKEN_FORMAT: "a high-confidence token format",
}

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_CREDENTIAL_URL_PATTERN = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s/@]+@",
    re.IGNORECASE,
)
_AUTHENTICATION_HEADER_PATTERN = re.compile(
    r"(?:^|[\s;,])(?:authorization|proxy-authorization|cookie|set-cookie)"
    r"\s*:\s*\S+",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?:^|[\s;,?&])"
    r"(?:password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|session(?:[_-]?id)?|token)"
    r"\s*[:=]\s*[\"']?[^\s,;]+",
    re.IGNORECASE,
)
_TOKEN_FORMAT_PATTERNS = (
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:sk|gh[pousr]|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class ResearchSensitiveInputPolicy:
    """Classify bounded text using explicit, high-confidence patterns."""

    def classify(self, value: str) -> ResearchSensitiveInputClass:
        if not isinstance(value, str):
            raise TypeError("Sensitive-input classification requires text.")
        if len(value) > MAX_RESEARCH_SENSITIVE_INPUT_CHARACTERS:
            raise ValueError("Sensitive-input classification requires bounded text.")
        if _PRIVATE_KEY_PATTERN.search(value):
            return ResearchSensitiveInputClass.PRIVATE_KEY_MATERIAL
        if _CREDENTIAL_URL_PATTERN.search(value):
            return ResearchSensitiveInputClass.CREDENTIAL_BEARING_URL
        if _AUTHENTICATION_HEADER_PATTERN.search(value):
            return ResearchSensitiveInputClass.AUTHENTICATION_HEADER
        if _SECRET_ASSIGNMENT_PATTERN.search(value):
            return ResearchSensitiveInputClass.SECRET_ASSIGNMENT
        if any(pattern.search(value) for pattern in _TOKEN_FORMAT_PATTERNS):
            return ResearchSensitiveInputClass.TOKEN_FORMAT
        return ResearchSensitiveInputClass.NONE
