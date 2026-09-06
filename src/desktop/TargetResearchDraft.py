"""Strict desktop fields for explicit bounded public HTTPS text acquisition.

Parsing performs no DNS, network access, confirmation or permission grant.
Names still require public DNS answers when execution actually begins. This
form cannot express path exclusions or grant permission for scans or probes.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from core.Exceptions import ResearchError
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator
from research.ResearchPlan import MAX_RESEARCH_PLAN_STEPS
from research.ResearchPlanStep import MAX_RESEARCH_PLAN_AUTHORIZED_URL_CHARACTERS
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchTargetScope import (
    MAX_SCOPE_RULES,
    ResearchTargetScope,
    TargetHostRule,
)

MAX_TARGET_FORM_FIELD_CHARACTERS = 65_536
_ACTIONS = frozenset({"source_fetch", "source_accept"})


def _field(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise ResearchError(f"Target {label} must be text.")
    if len(value) > MAX_TARGET_FORM_FIELD_CHARACTERS:
        raise ResearchError(f"Target {label} is too large.")
    return value


def _lines(value: str, label: str, maximum: int) -> tuple[str, ...]:
    value = _field(value, label)
    # Only ordinary form line endings delimit records. Other controls must not
    # be interpreted as hidden separators or disappear during normalization.
    value = value.replace("\r\n", "\n")
    if any(ord(char) < 32 and char != "\n" or ord(char) == 127 for char in value):
        raise ResearchError(f"Target {label} contains unsupported controls.")
    rows = tuple(row.strip(" ") for row in value.split("\n") if row.strip(" "))
    if len(rows) > maximum:
        raise ResearchError(f"Target {label} has too many entries.")
    return rows


def _host_rule(value: str) -> TargetHostRule:
    wildcard = value.startswith("*.")
    return TargetHostRule(value[2:] if wildcard else value, wildcard)


def target_scope_from_fields(
    allowed_hosts: str,
    excluded_hosts: str,
    allowed_networks: str,
    excluded_networks: str,
) -> ResearchTargetScope:
    """Parse the scope portion of the desktop target form without I/O."""
    groups = tuple(
        _lines(value, label, MAX_SCOPE_RULES)
        for value, label in (
            (allowed_hosts, "allowed hosts"),
            (excluded_hosts, "excluded hosts"),
            (allowed_networks, "allowed networks"),
            (excluded_networks, "excluded networks"),
        )
    )
    if sum(len(group) for group in groups) > MAX_SCOPE_RULES:
        raise ResearchError("Target scope has too many rules.")
    return ResearchTargetScope(
        allowed_hosts=tuple(_host_rule(row) for row in groups[0]),
        excluded_hosts=tuple(_host_rule(row) for row in groups[1]),
        allowed_networks=groups[2],
        excluded_networks=groups[3],
    )


def _source_url(value: str, scope: ResearchTargetScope) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_RESEARCH_PLAN_AUTHORIZED_URL_CHARACTERS
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
        or "\\" in value
    ):
        raise ResearchError("Target source URL is invalid or too long.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        PublicHttpsUrlValidator._validate_parts(parsed, port)
    except ValueError as error:
        raise ResearchError("Target source URL is invalid.") from error
    if not parsed.netloc.isascii() or parsed.netloc.endswith(":"):
        raise ResearchError("Target source authority must be explicit ASCII HTTPS.")
    if parsed.fragment:
        raise ResearchError("Target source URLs cannot include ignored fragments.")
    assert parsed.hostname is not None
    hostname = parsed.hostname.lower().removesuffix(".")
    # Validate the authored authority before normalization can erase ambiguity.
    scope.require_hostname(parsed.hostname)
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        formatted_host = hostname
    else:
        if not literal.is_global or literal.is_multicast:
            raise ResearchError("Target literal addresses must be public internet IPs.")
        scope.require_addresses((str(literal),))
        formatted_host = (
            f"[{literal.compressed}]"
            if isinstance(literal, ipaddress.IPv6Address)
            else literal.compressed
        )
    netloc = formatted_host if port is None else f"{formatted_host}:{port}"
    normalized = urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))
    if len(normalized) > MAX_RESEARCH_PLAN_AUTHORIZED_URL_CHARACTERS:
        raise ResearchError("Target source URL is too long.")
    return normalized


@dataclass(frozen=True, slots=True)
class TargetResearchDraft:
    """An immutable authored scope and exact ordered acquisition steps."""

    binding: ResearchPlanTargetBinding
    steps: tuple[ResearchPlanStepDraftInput, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ResearchPlanTargetBinding):
            raise ResearchError("Target draft requires a validated binding.")
        if (
            not isinstance(self.steps, tuple)
            or not 1 <= len(self.steps) <= MAX_RESEARCH_PLAN_STEPS
            or any(
                not isinstance(step, ResearchPlanStepDraftInput) for step in self.steps
            )
        ):
            raise ResearchError("Target draft requires a bounded immutable step tuple.")
        action = self.steps[0].capability
        if (
            not isinstance(action, str)
            or action not in _ACTIONS
            or any(step.capability != action for step in self.steps)
        ):
            raise ResearchError("Target action must be source_fetch or source_accept.")
        for step in self.steps:
            if (
                _source_url(step.authorized_source_url, self.binding.scope)
                != step.authorized_source_url
            ):
                raise ResearchError("Target draft URLs must already be normalized.")

    @classmethod
    def from_fields(
        cls,
        program_id: str,
        allowed_hosts: str,
        excluded_hosts: str,
        allowed_networks: str,
        excluded_networks: str,
        source_urls: str,
        action: str = "source_fetch",
    ) -> TargetResearchDraft:
        """Parse every nonblank row, or reject the entire draft without I/O."""
        program_id = _field(program_id, "program ID")
        if any(
            char.isspace() and char != " " or ord(char) < 32 or ord(char) == 127
            for char in program_id
        ):
            raise ResearchError("Target program ID contains unsupported whitespace.")
        action = _field(action, "action")
        if action not in _ACTIONS:
            raise ResearchError("Target action must be source_fetch or source_accept.")
        scope = target_scope_from_fields(
            allowed_hosts,
            excluded_hosts,
            allowed_networks,
            excluded_networks,
        )
        binding = ResearchPlanTargetBinding(program_id, scope)
        urls = _lines(source_urls, "source URLs", MAX_RESEARCH_PLAN_STEPS)
        if not urls:
            raise ResearchError(
                "Target draft requires at least one explicit source URL."
            )
        instruction = (
            "Fetch explicitly selected public HTTPS text."
            if action == "source_fetch"
            else "Fetch and accept explicitly selected public HTTPS text."
        )
        return cls(
            binding=binding,
            steps=tuple(
                ResearchPlanStepDraftInput(
                    instruction=instruction,
                    capability=action,
                    authorized_source_url=_source_url(url, scope),
                )
                for url in urls
            ),
        )

    def to_fields(self) -> dict[str, str]:
        """Return the same explicit fields for editing, preserving rule order."""
        scope = self.binding.scope
        return {
            "program_id": self.binding.program_id,
            "allowed_hosts": "\n".join(
                ("*." if rule.subdomains_only else "") + rule.host
                for rule in scope.allowed_hosts
            ),
            "excluded_hosts": "\n".join(
                ("*." if rule.subdomains_only else "") + rule.host
                for rule in scope.excluded_hosts
            ),
            "allowed_networks": "\n".join(scope.allowed_networks),
            "excluded_networks": "\n".join(scope.excluded_networks),
            "source_urls": "\n".join(step.authorized_source_url for step in self.steps),
            "action": str(self.steps[0].capability),
        }
