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
    #: Implemented as a deterministic preview/fixture only: no real external
    #: action (no process, no network call) is ever performed. Distinct from
    #: AVAILABLE so the model is never told a simulation is a working feature.
    SIMULATED = "simulated"
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
    "Describe only the capabilities listed as available or simulated. For "
    "anything not listed there, say Hypatia cannot do it; never invent a "
    "capability. This list describes; it grants no permission and starts "
    "nothing. Knowing that a workflow exists is not doing it: never say you "
    "researched, browsed, fetched, verified or revalidated anything in this "
    "chat. A capability listed as simulated performs no real action -- never "
    "describe a simulated result as a real one, and never say a real lookup "
    "ran or completed when only the simulation is available."
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
    #: Whether the no-process Kali preview/fake-run path is wired, independent
    #: of `kali_operation_kinds`: the simulation requires only a scope and an
    #: authorization store, never the real runtime probe or process adapter.
    kali_simulation_available: bool = False
    #: The running build's own version string (e.g. "0.3.437 (Genesis)"), read
    #: once from `core.Version` by the composition root. Plain descriptive
    #: text, not authority: stating it enables nothing and unblocks nothing.
    hypatia_version: str = ""


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityContext:
    """An immutable, ordered capability projection and its bounded rendering."""

    states: tuple[tuple[RuntimeCapability, RuntimeCapabilityState], ...]
    kali_operation_kinds: tuple[str, ...] = ()
    hypatia_version: str = ""

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
        """Render one short deterministic system instruction for chat.

        "Not available" is split in two: a capability Hypatia never wires at
        all (`_NEVER_WIRED`, e.g. penetration testing) reads as not
        implemented, distinct from one this process simply did not enable
        (e.g. memory, with no store configured) -- an operator question with
        a different honest answer than "Hypatia cannot do that at all".
        """
        sections: list[str] = ["Hypatia runtime capabilities.", _IDENTITY]
        if self.hypatia_version:
            sections.append(f"Hypatia version: {self.hypatia_version}.")
        groups: tuple[tuple[str, list[str]], ...] = (
            ("Available now:", []),
            ("Simulated only, no real action performed:", []),
            ("Not implemented in Hypatia:", []),
            ("Not enabled in this configuration:", []),
            ("Not confirmed (do not claim):", []),
        )
        buckets = dict(groups)
        for capability, state in self.states:
            item = self._describe(capability)
            if state is RuntimeCapabilityState.AVAILABLE:
                buckets["Available now:"].append(item)
            elif state is RuntimeCapabilityState.SIMULATED:
                buckets["Simulated only, no real action performed:"].append(item)
            elif state is RuntimeCapabilityState.UNAVAILABLE:
                heading = (
                    "Not implemented in Hypatia:"
                    if capability in _NEVER_WIRED
                    else "Not enabled in this configuration:"
                )
                buckets[heading].append(item)
            else:
                buckets["Not confirmed (do not claim):"].append(item)
        for heading, items in groups:
            if items:
                sections.append(heading)
                sections.extend(f"- {item}" for item in items)
        sections.append(_RULES)
        return "\n".join(sections)

    def _describe(self, capability: RuntimeCapability) -> str:
        if capability is RuntimeCapability.REVIEWED_KALI_LOOKUPS:
            state = self.state_of(capability)
            if state is RuntimeCapabilityState.AVAILABLE:
                # Only the exact reviewed kinds a wired runner supports; never
                # a general tool or testing capability.
                kinds = ", ".join(
                    kind.replace("_", " ") for kind in self.kali_operation_kinds
                )
                return (
                    "Kali lookups, each individually previewed and authorized, "
                    f"limited to: {kinds}"
                )
            if state is RuntimeCapabilityState.SIMULATED:
                return (
                    "Kali lookups: only a deterministic preview/simulation is "
                    "available -- it performs no real DNS or HTTPS request"
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
    version = evidence.hypatia_version
    version = version.strip() if isinstance(version, str) else ""

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
        RuntimeCapability.REVIEWED_KALI_LOOKUPS: _kali_lookup_state(
            kinds, evidence.kali_simulation_available
        ),
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
        hypatia_version=version,
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


def _kali_lookup_state(
    kinds: tuple[str, ...], simulation_available: object
) -> RuntimeCapabilityState:
    """Real execution, if wired, always outranks the simulation fact.

    A real `kali_operation_kinds` tuple proves the reviewed runner is wired
    and reports AVAILABLE regardless of `simulation_available` -- the two
    facts are never combined into one ambiguous reading. Only once there is
    no real runner does the simulation fact get to decide SIMULATED versus
    UNAVAILABLE versus UNKNOWN, through the same boolean-only rule `_state`
    applies everywhere else.
    """
    if kinds:
        return RuntimeCapabilityState.AVAILABLE
    if simulation_available is True:
        return RuntimeCapabilityState.SIMULATED
    if simulation_available is False:
        return RuntimeCapabilityState.UNAVAILABLE
    return RuntimeCapabilityState.UNKNOWN
