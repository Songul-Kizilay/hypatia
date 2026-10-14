"""The future Hypatia Kali Guest-Agent's typed, transport-neutral message contract.

This module is a protocol *foundation*: an immutable, in-memory, deterministic,
side-effect-free description of what one request to a future Kali guest agent
and one response from it may contain. It starts no process, opens no socket,
contacts no VMware host, uses no SSH or WSL, and dispatches nothing. Nothing
here is wired into `KaliToolGateway`, `Bootstrap`, `CognitiveEngine`, chat, or
the desktop -- this module has zero production callers today.

PROTOCOL REQUEST != EXECUTION AUTHORITY. REQUEST DIGEST != AUTHORIZATION.
NONCE != AUTHORIZATION. REQUEST ID != AUTHORIZATION. AUTHENTICATED PEER !=
AUTHORITY. GUEST AGENT READY != EXECUTION AUTHORITY. AGENT RESPONSE != TRUSTED
FACT. Host-side existing authority (`ResearchKaliOperationAuthorization`,
`ResearchKaliOperationAuthorizationStore`, `KaliToolGateway`'s scope/preview/
authorization/runtime/consume-before-dispatch chain) remains exactly as
authoritative as before this module existed, and none of it imports this
module or anything in it.

A possible future flow is sketched here only as documentation, never as code
this milestone wires up:

    scope -> preview -> operation digest -> explicit authorization ->
    consume-before-dispatch -> guest-agent transport -> guest agent ->
    allowlisted implementation

`GuestAgentRequest`/`GuestAgentResponse` describe the last hop of that chain
in the shape a future transport could carry; every earlier step's existing
authority is untouched and unreferenced by construction here.

Capability identity is `research.ResearchKaliOperationPreview.ResearchKaliOperationKind`
directly -- not a new identity scheme, and not the compound
`ProductCapabilityCatalogDefaults.kali_operation_identity` string
("kali:<kind>:<transport>"). That compound identity deliberately names a
*current* process-adapter transport (`WSL_KALI`/`VMWARE_KALI`); a guest-agent
message travels over a different, future transport entirely, so binding it to
one of today's transport names would be a false claim, not a reuse. Using the
operation-kind enum directly is simultaneously the smallest possible design
and the strongest possible guarantee that a local-only tool capability (for
example `tools.ToolCapability.CLOCK_READ`) can never appear here: the two
enums are disjoint Python types, so admitting one is not a validation rule to
remember, it is a type the other value cannot be.

No arbitrary command channel exists anywhere in this module. There is no
field, type, or concept here named (or meaning) shell, command, command_line,
argv, executable, script, powershell, bash, run, exec, or raw_command --
proven structurally in `tests/research/test_guest_agent_protocol.py` by
introspecting every dataclass field. A caller that wants Hypatia to run
`nmap -sV ...`, `rm ...`, `bash -c ...`, or any other literal command line has
no field here to put it in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationKind,
    is_kali_operation_digest,
)

MAX_REQUEST_ID_LENGTH = 200
MAX_NONCE_LENGTH = 200
MAX_LOGICAL_INPUT_FIELDS = 10
MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH = 100
MAX_LOGICAL_INPUT_VALUE_LENGTH = 4000
MAX_RESPONSE_DETAIL_LENGTH = 500


class GuestAgentProtocolVersion(StrEnum):
    """Name one closed, code-owned Guest-Agent protocol generation.

    Product version and protocol version are different facts: a product
    version like `v0.3.456` is when a generation was introduced, not what
    it is called. Anything that is not a named member below -- including a
    string that merely looks like a future version -- must fail closed,
    never silently downgrade to an earlier one.

    `V1` names the original generation: a typed operation request with no
    execution-limit binding. `V2` names the execution-bound generation
    introduced in v0.3.466: a typed operation request that additionally
    carries the signed `GuestAgentExecutionLimits` a future bounded
    execution gate would need. V1 REQUEST != EXECUTION-BOUND REQUEST --
    see `GuestAgentRequest.execution_limits`'s own docstring. Neither
    version is, or implies, execution authority; `V2` closes a missing-
    fact gap (the guest previously had no signed, host-approved process-
    time ceiling to honor), it does not grant a new one.
    """

    V1 = "hypatia-kali-guest-agent/1"
    V2 = "hypatia-kali-guest-agent/2"


class GuestAgentResponseStatus(StrEnum):
    """Name one closed, bounded outcome a future guest-agent response may report.

    Only outcomes meaningful at the protocol-contract level today are
    listed. `REPLAY_REJECTED` names that a request's one-time replay
    identity (see `research.GuestAgentReplayProtector`) was already
    consumed -- it is a descriptive protocol outcome only, exactly like
    every other member here: it grants nothing, it is never produced by
    the host deciding anything about *authority*, and it carries no
    successful output (`permits_output` is `False` for it, same as every
    non-`SUCCESS` member). REPLAY REJECTED != AUTHORITY DECISION: this
    status says a token was already spent, never that an operation was
    disallowed.
    """

    SUCCESS = "success"
    DECLINED = "declined"
    FAILED = "failed"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INVALID_REQUEST = "invalid_request"
    REPLAY_REJECTED = "replay_rejected"

    @property
    def permits_output(self) -> bool:
        """Return whether this outcome may carry non-empty output lines."""
        return self is GuestAgentResponseStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class GuestAgentExecutionLimits:
    """The signed execution-limit facts a V2 request binds; grants nothing.

    EXECUTION LIMIT PRESENT != EXECUTION AUTHORITY. EXECUTION LIMIT VALID
    != EXECUTION AUTHORITY. SIGNED EXECUTION LIMIT != EXECUTION SUCCESS.
    This type only bounds what a future executor MAY consume; it never
    grants a new operation, and admitting or verifying one does not imply
    any capability may run.

    `max_seconds` is the one genuinely execution-relevant fact a future
    guest executor needs that the V1 protocol never carried: audited
    directly against `cognition.KaliToolGateway.run`, which passes
    `timeout_seconds=min(preview.max_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS)`
    to the process adapter -- the exact host-approved upper bound on how
    long a reviewed operation's process may run. Every other
    `ResearchKaliOperationPreview` field audited for this milestone
    (`permitted_ports`, `max_request_count`, `max_requests_per_minute`,
    `program_id`, scope/policy digests) is consumed only by host-side
    preview construction or the operation digest itself, never passed to
    `ResearchKaliOperationProcessAdapter.run` -- so carrying only this one
    field, rather than the whole preview, is a deliberate, audited
    decision, not an oversight.

    Validation mirrors the stricter of this repository's two existing
    timeout-bound checks
    (`research.WslKaliOperationProcessAdapter._timeout`'s chained
    `0 < value <= ...` comparison, which already rejects NaN and
    infinities by how Python chained comparisons evaluate) rather than
    `ResearchKaliOperationPreview.__post_init__`'s own looser `<= 0`-only
    check, which does not reject NaN. No new upper ceiling is invented
    here: the exact host-approved value is carried uncapped, exactly as
    `ResearchKaliOperationPreview.max_seconds` itself carries it uncapped
    -- `MAX_KALI_OPERATION_TIMEOUT_SECONDS` is applied only once, later, at
    the same point production code already applies it (computing a
    prepared invocation's actual process timeout), never here. A bare
    `int`/`float` is normalized to `float` on construction so this type's
    own canonical wire encoding is deterministic regardless of whether a
    caller passed a whole number as `int` or `float` -- never rounded,
    truncated, or widened.
    """

    max_seconds: float

    def __post_init__(self) -> None:
        if isinstance(self.max_seconds, bool) or not isinstance(
            self.max_seconds, int | float
        ):
            raise ResearchError(
                "Guest-agent execution limit time budget must be a number."
            )
        if not math.isfinite(self.max_seconds) or self.max_seconds <= 0:
            raise ResearchError("Guest-agent execution limit time budget is invalid.")
        object.__setattr__(self, "max_seconds", float(self.max_seconds))


@dataclass(frozen=True, slots=True)
class GuestAgentRequest:
    """One typed request a future host transport could send to a Kali guest
    agent; grants nothing by existing.

    `operation_digest` carries the existing host-side
    `ResearchKaliOperationPreview.operation_digest` -- the one authority
    digest this repository already has -- rather than inventing a second.
    This type does not recompute, verify, or bind that digest to any scope,
    policy, or authorization; it only carries the already-produced value
    opaquely, exactly as `ResearchKaliOperationAuthorization.operation_digest`
    already does. A future transport integrity digest over the protocol
    message bytes themselves, if one is ever needed, must remain a visibly
    separate field/concept from this one -- this milestone adds no such
    field because none is yet needed to describe the contract.

    `request_id` and `nonce` are both inert opaque correlation data only.
    Neither is generated here (construction never manufactures a secret);
    both must be supplied already-chosen, and neither one is interchangeable
    with the other or with `operation_digest`: `request_id` exists to match
    a response back to this request, `nonce` exists only so a *future*
    replay-protection layer has somewhere to put a one-time token, and
    `operation_digest` exists to say which already-authorized operation this
    is about. None of the three can authorize anything; none of them checks
    anything against a store, because this module holds no store.

    `logical_inputs` mirrors the existing `tools.ToolInvocation.arguments` /
    `tools.ToolResult.values` shape deliberately: a bounded, ordered tuple of
    `(name, value)` string pairs, names code/schema-owned rather than
    dynamically defined, values untrusted bounded text never interpreted as
    instructions. Duplicate names are rejected here, unconditionally; whether
    a given name is one a specific capability's schema actually recognizes
    is a separate, optional check -- see
    `tools.GuestAgentRequestSchemaValidation.validate_guest_agent_request_inputs`
    -- because this type must stay valid on its own without requiring a live
    `tools.ProductCapabilitySchemaCatalog` to exist, and because `research`
    does not depend on `tools` (the existing direction is the other way:
    `tools.ProductCapabilitySchemaDefaults` already depends on `research`).

    `execution_limits` is version-coupled, never independently optional:
    a `V1` request must carry `None` (V1 REQUEST != EXECUTION-BOUND
    REQUEST -- the original generation never described an execution
    limit, so it must never silently acquire one), and a `V2` request
    must carry a real `GuestAgentExecutionLimits` (never `None`, never a
    caller-chosen default -- there is no "if missing, use 30 seconds"
    anywhere in this type). This coupling is enforced here, structurally,
    not merely by convention: constructing a mismatched pair always
    raises, whether the caller is this repository's own signing code or
    wire-decoded data (`research.GuestAgentProtocolSerialization` relies
    on exactly this check rather than duplicating it).
    """

    protocol_version: GuestAgentProtocolVersion
    request_id: str
    nonce: str
    operation_kind: ResearchKaliOperationKind
    operation_digest: str
    logical_inputs: tuple[tuple[str, str], ...] = ()
    execution_limits: GuestAgentExecutionLimits | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.protocol_version, GuestAgentProtocolVersion):
            raise ResearchError("Guest-agent request protocol version is invalid.")
        self._require_bounded_text(
            self.request_id, "request identifier", MAX_REQUEST_ID_LENGTH
        )
        self._require_bounded_text(self.nonce, "nonce", MAX_NONCE_LENGTH)
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError("Guest-agent request capability identity is invalid.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("Guest-agent request operation digest is invalid.")
        self._validate_logical_inputs()
        self._validate_execution_limits()

    def _validate_execution_limits(self) -> None:
        if self.protocol_version is GuestAgentProtocolVersion.V1:
            if self.execution_limits is not None:
                raise ResearchError(
                    "Guest-agent V1 request must not carry execution limits."
                )
        elif self.protocol_version is GuestAgentProtocolVersion.V2:
            if not isinstance(self.execution_limits, GuestAgentExecutionLimits):
                raise ResearchError("Guest-agent V2 request requires execution limits.")

    def _validate_logical_inputs(self) -> None:
        if not isinstance(self.logical_inputs, tuple):
            raise ResearchError(
                "Guest-agent request logical inputs must be an immutable sequence."
            )
        if len(self.logical_inputs) > MAX_LOGICAL_INPUT_FIELDS:
            raise ResearchError("Guest-agent request carries too many logical inputs.")
        names = []
        for entry in self.logical_inputs:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or not isinstance(entry[0], str)
                or not isinstance(entry[1], str)
            ):
                raise ResearchError(
                    "Guest-agent request logical input name and value must be text."
                )
            name, value = entry
            self._require_bounded_text(
                name,
                "logical input field name",
                MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH,
            )
            if len(value) > MAX_LOGICAL_INPUT_VALUE_LENGTH:
                raise ResearchError("Guest-agent request logical input is too long.")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ResearchError(
                    "Guest-agent request logical input contains control data."
                )
            names.append(name)
        if len(names) != len(set(names)):
            raise ResearchError(
                "Guest-agent request repeated a logical input field name."
            )

    @staticmethod
    def _require_bounded_text(value: object, label: str, maximum: int) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Guest-agent request {label} cannot be empty.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(f"Guest-agent request {label} contains control data.")
        if len(value) > maximum:
            raise ResearchError(f"Guest-agent request {label} is too long.")


@dataclass(frozen=True, slots=True)
class GuestAgentResponse:
    """One typed response a future Kali guest agent could return; a trusted
    fact about nothing.

    AGENT RESPONSE != TRUSTED FACT. This type cannot grant authorization,
    change scope, register or redefine a capability, redefine a schema, or
    make an operation validated merely by existing -- there is no field here
    that means any of those things, and no method that does anything but
    hold already-bounded data. `output_trust` reuses the exact existing
    `research.ResearchKaliOperationExecution.KALI_OPERATION_OUTPUT_TRUST`
    label a real Kali process result already carries, rather than inventing
    a second untrusted-output marker for what is the same kind of fact.

    `detail` is always one of a small fixed set of code-owned sentences --
    never text built from whatever a future guest agent sent -- exactly as
    `tools.ToolResult.detail` and `tools.ProductCapabilityVersionAssessment.reason`
    already keep that distinction. `output_lines` is bounded by the same
    `MAX_KALI_OPERATION_OUTPUT_LINES`/`MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS`
    ceiling a real `ResearchKaliOperationProcessResult.stdout_lines` already
    enforces, reused rather than restated with a new number. A response
    whose `status` does not permit output (`GuestAgentResponseStatus.permits_output`)
    cannot carry any -- a declined or failed attempt reported nothing, so it
    has nothing to show.
    """

    protocol_version: GuestAgentProtocolVersion
    request_id: str
    status: GuestAgentResponseStatus
    detail: str
    output_lines: tuple[str, ...] = ()
    output_trust: str = KALI_OPERATION_OUTPUT_TRUST

    def __post_init__(self) -> None:
        if not isinstance(self.protocol_version, GuestAgentProtocolVersion):
            raise ResearchError("Guest-agent response protocol version is invalid.")
        GuestAgentRequest._require_bounded_text(
            self.request_id, "request identifier", MAX_REQUEST_ID_LENGTH
        )
        if not isinstance(self.status, GuestAgentResponseStatus):
            raise ResearchError("Guest-agent response status is invalid.")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ResearchError("Guest-agent response detail cannot be empty.")
        if len(self.detail) > MAX_RESPONSE_DETAIL_LENGTH:
            raise ResearchError("Guest-agent response detail is too long.")
        if "\x00" in self.detail or "\r" in self.detail or "\n" in self.detail:
            raise ResearchError("Guest-agent response detail contains control data.")
        self._validate_output_lines()
        if self.output_trust != KALI_OPERATION_OUTPUT_TRUST:
            raise ResearchError("Guest-agent response output trust label is invalid.")

    def _validate_output_lines(self) -> None:
        if not isinstance(self.output_lines, tuple):
            raise ResearchError(
                "Guest-agent response output lines must be an immutable sequence."
            )
        if len(self.output_lines) > MAX_KALI_OPERATION_OUTPUT_LINES:
            raise ResearchError("Guest-agent response has too many output lines.")
        for line in self.output_lines:
            if (
                not isinstance(line, str)
                or "\x00" in line
                or len(line) > MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
            ):
                raise ResearchError("Guest-agent response output line is invalid.")
        if self.output_lines and not self.status.permits_output:
            raise ResearchError(
                "Guest-agent response status does not permit output lines."
            )
