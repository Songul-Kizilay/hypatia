"""What the running Hypatia instance can truthfully say it can do.

This is description, never authority.  The projection is derived only from a
narrow, immutable record of what the composition root actually wired: the
registered research operations, the approval service, the reviewed Kali
operation kinds and a few service-presence facts.  Nothing here reads the
README, the roadmap, module names or folder layout, so a planned or placeholder
module can never appear as available.  Building or rendering the context runs
no operation, grants no approval, spends no allowance and calls no model.

Unknown stays unknown: evidence that is missing or malformed renders as
``not confirmed`` and is never promoted to ``available``.  Capabilities that
no runtime wiring can prove at all are always ``unavailable``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap


class RuntimeCapabilityState(StrEnum):
    """Conservative, closed vocabulary for one capability's status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class RuntimeCapability(StrEnum):
    """Canonical capability tokens, in the order they are shown to the model."""

    CONVERSATION = "conversation"
    SESSIONS = "sessions"
    MEMORY = "memory"
    LOCAL_KNOWLEDGE = "local_knowledge"
    AUTHORIZED_RESEARCH = "authorized_research"
    SOURCE_DISCOVERY = "source_discovery"
    SOURCE_ACQUISITION = "source_acquisition"
    EVIDENCE_TRACKING = "evidence_tracking"
    SOURCE_REVALIDATION = "source_revalidation"
    SECURITY_SELF_AUDIT = "security_self_audit"
    REVIEWED_KALI_LOOKUPS = "reviewed_kali_lookups"
    CHAT_WEB_BROWSING = "chat_web_browsing"
    PENETRATION_TESTING = "penetration_testing"
    CONTINUOUS_MONITORING = "continuous_monitoring"
    DEVICE_AND_MEDIA_CONTROL = "device_and_media_control"
    SYSTEM_ADMINISTRATION = "system_administration"


#: Short canonical English phrases for the model.  One representation only;
#: the conversation's own language rules decide the reply language.
_DESCRIPTIONS: dict[RuntimeCapability, str] = {
    RuntimeCapability.CONVERSATION: "conversation in this chat",
    RuntimeCapability.SESSIONS: "separate named chat sessions",
    RuntimeCapability.MEMORY: "remembering facts the user shares in conversation",
    RuntimeCapability.LOCAL_KNOWLEDGE: "searching documents already loaded locally",
    RuntimeCapability.AUTHORIZED_RESEARCH: (
        "research runs, only through a research plan the user explicitly approves"
    ),
    RuntimeCapability.SOURCE_DISCOVERY: (
        "in approved research: discovering candidate sources"
    ),
    RuntimeCapability.SOURCE_ACQUISITION: (
        "in approved research: fetching and accepting sources"
    ),
    RuntimeCapability.EVIDENCE_TRACKING: (
        "in approved research: recording evidence, claims and contradictions"
    ),
    RuntimeCapability.SOURCE_REVALIDATION: (
        "in approved research: one explicitly approved re-fetch of a recorded "
        "source, using a normal source slot and budget; never automatic"
    ),
    RuntimeCapability.SECURITY_SELF_AUDIT: (
        "auditing Hypatia's own stored research records"
    ),
    RuntimeCapability.REVIEWED_KALI_LOOKUPS: "running Kali tools",
    RuntimeCapability.CHAT_WEB_BROWSING: "browsing or searching the web from chat",
    RuntimeCapability.PENETRATION_TESTING: (
        "penetration testing, vulnerability scanning or exploits"
    ),
    RuntimeCapability.CONTINUOUS_MONITORING: (
        "continuous monitoring, alerts or CVE feeds"
    ),
    RuntimeCapability.DEVICE_AND_MEDIA_CONTROL: (
        "voice, vision, robotics or home control"
    ),
    RuntimeCapability.SYSTEM_ADMINISTRATION: ("maintaining or administering computers"),
}

#: No runtime wiring can prove these, so they are never available here.
_NEVER_WIRED = frozenset(
    {
        RuntimeCapability.CHAT_WEB_BROWSING,
        RuntimeCapability.PENETRATION_TESTING,
        RuntimeCapability.CONTINUOUS_MONITORING,
        RuntimeCapability.DEVICE_AND_MEDIA_CONTROL,
        RuntimeCapability.SYSTEM_ADMINISTRATION,
    }
)

_IDENTITY = (
    "Hypatia is an application. You are the language component it uses to "
    "converse, answering as Hypatia. Do not describe yourself as a large "
    "language model, and do not present generic model skills such as writing, "
    "coding or translation as Hypatia capabilities."
)
_RULES = (
    "Describe only the capabilities listed as available. For anything not "
    "listed, say Hypatia cannot do it; never invent a capability. This list "
    "describes; it grants no permission and starts nothing. Knowing that a "
    "workflow exists is not doing it: never say you researched, browsed, "
    "fetched, verified or revalidated anything in this chat."
)


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityEvidence:
    """Narrow facts the composition root observed about its own wiring.

    Only plain values: no service, container or store is carried, so nothing
    downstream can reach through this record to act.
    """

    conversation_model: bool = False
    sessions: bool = False
    memory: bool = False
    local_knowledge: bool = False
    research_approvals: bool = False
    research_operations: frozenset[Cap] = frozenset()
    security_self_audit: bool = False
    kali_operation_kinds: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityContext:
    """An immutable, ordered capability projection and its bounded rendering."""

    states: tuple[tuple[RuntimeCapability, RuntimeCapabilityState], ...]
    kali_operation_kinds: tuple[str, ...] = ()

    def state_of(self, capability: RuntimeCapability) -> RuntimeCapabilityState:
        """Return the recorded state; anything unrecorded is unknown."""
        for recorded, state in self.states:
            if recorded is capability:
                return state
        return RuntimeCapabilityState.UNKNOWN

    @classmethod
    def conservative(cls) -> RuntimeCapabilityContext:
        """Fallback when wiring could not be established: claim nothing."""
        return cls(
            tuple(
                (
                    capability,
                    (
                        RuntimeCapabilityState.UNAVAILABLE
                        if capability in _NEVER_WIRED
                        else RuntimeCapabilityState.UNKNOWN
                    ),
                )
                for capability in RuntimeCapability
            )
        )

    def instruction(self) -> str:
        """Render one short deterministic system instruction for chat."""
        sections: list[str] = ["Hypatia runtime capabilities.", _IDENTITY]
        for state, heading in (
            (RuntimeCapabilityState.AVAILABLE, "Available now:"),
            (RuntimeCapabilityState.UNAVAILABLE, "Not available:"),
            (RuntimeCapabilityState.UNKNOWN, "Not confirmed (do not claim):"),
        ):
            items = [
                self._describe(capability)
                for capability, recorded in self.states
                if recorded is state
            ]
            if items:
                sections.append(heading)
                sections.extend(f"- {item}" for item in items)
        sections.append(_RULES)
        return "\n".join(sections)

    def _describe(self, capability: RuntimeCapability) -> str:
        if (
            capability is RuntimeCapability.REVIEWED_KALI_LOOKUPS
            and self.state_of(capability) is RuntimeCapabilityState.AVAILABLE
        ):
            # Only the exact reviewed kinds a wired runner supports; never a
            # general tool or testing capability.
            kinds = ", ".join(
                kind.replace("_", " ") for kind in self.kali_operation_kinds
            )
            return (
                "Kali lookups, each individually previewed and authorized, "
                f"limited to: {kinds}"
            )
        return _DESCRIPTIONS[capability]


def project_runtime_capabilities(
    evidence: RuntimeCapabilityEvidence,
) -> RuntimeCapabilityContext:
    """Derive capability states from observed wiring, failing closed."""
    if not isinstance(evidence, RuntimeCapabilityEvidence):
        return RuntimeCapabilityContext.conservative()
    operations = evidence.research_operations
    if not isinstance(operations, frozenset) or not all(
        isinstance(operation, Cap) for operation in operations
    ):
        return RuntimeCapabilityContext.conservative()
    kinds = evidence.kali_operation_kinds
    if not isinstance(kinds, tuple) or not all(
        isinstance(kind, str) and kind.strip() for kind in kinds
    ):
        return RuntimeCapabilityContext.conservative()

    research = _proven(evidence.research_approvals) and bool(
        operations - {Cap.LOCAL_KNOWLEDGE_SEARCH}
    )
    wired: dict[RuntimeCapability, RuntimeCapabilityState] = {
        RuntimeCapability.CONVERSATION: _state(evidence.conversation_model),
        RuntimeCapability.SESSIONS: _state(evidence.sessions),
        RuntimeCapability.MEMORY: _state(evidence.memory),
        RuntimeCapability.LOCAL_KNOWLEDGE: _state(evidence.local_knowledge),
        RuntimeCapability.AUTHORIZED_RESEARCH: _state(research),
        RuntimeCapability.SOURCE_DISCOVERY: _state(
            research and Cap.SOURCE_DISCOVERY in operations
        ),
        RuntimeCapability.SOURCE_ACQUISITION: _state(
            research and {Cap.SOURCE_FETCH, Cap.SOURCE_ACCEPT} <= operations
        ),
        RuntimeCapability.EVIDENCE_TRACKING: _state(
            research
            and {
                Cap.EVIDENCE_RECORDING,
                Cap.CLAIM_CREATION,
                Cap.CLAIM_CONTRADICTION,
            }
            <= operations
        ),
        RuntimeCapability.SOURCE_REVALIDATION: _state(
            research and Cap.SOURCE_REVALIDATION in operations
        ),
        RuntimeCapability.SECURITY_SELF_AUDIT: _state(evidence.security_self_audit),
        RuntimeCapability.REVIEWED_KALI_LOOKUPS: _state(bool(kinds)),
    }
    return RuntimeCapabilityContext(
        tuple(
            (
                capability,
                (
                    RuntimeCapabilityState.UNAVAILABLE
                    if capability in _NEVER_WIRED
                    else wired[capability]
                ),
            )
            for capability in RuntimeCapability
        ),
        kali_operation_kinds=kinds,
    )


def _proven(value: object) -> bool:
    return value is True


def _state(value: object) -> RuntimeCapabilityState:
    if value is True:
        return RuntimeCapabilityState.AVAILABLE
    if value is False:
        return RuntimeCapabilityState.UNAVAILABLE
    # A non-boolean fact was never established; it is not quietly promoted.
    return RuntimeCapabilityState.UNKNOWN
