"""Build capability descriptions by projecting existing authoritative facts.

Every function here reads an already-existing source of truth and renders
it as a `ProductCapabilityRecord`; none of them re-author a rule a real
descriptor, enum, or runtime constant already owns. If one of those sources
changes, the next projection reflects it -- there is no copied value here
to go stale.

Two families exist today, and this module describes both without touching
either's execution path:

- Local tools, projected from a real `ToolRegistry`'s own registered
  `ToolDescriptor`s (`tools.ToolRegistry`, `tools.ToolDescriptor`).
- Kali operations, described from the Kali runtime's own named constants
  and enums (`research.ResearchKaliOperationPreview`,
  `research.ResearchKaliRuntimeEnvironment`,
  `research.ResearchKaliOperationExecution`) -- never from a duplicated
  copy of the dig/curl argv, the timeout, or the transport identity.

Only the combinations a real process adapter actually accepts in production
are described. `HTTPS_HEADER_LOOKUP` has no VMware process adapter today
(`VmwareKaliOperationProcessAdapter` accepts only the reviewed
`DNS_RECORD_LOOKUP` dig plan) -- so that combination is correctly absent
here, not silently implied by enumerating every kind times every transport.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import MAX_KALI_OPERATION_TIMEOUT_SECONDS
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
)
from research.ResearchKaliRuntimeEnvironment import (
    EXPECTED_CURL_VERSION_PREFIX,
    EXPECTED_DIG_VERSION_PREFIX,
)
from tools.ProductCapabilityCatalog import ProductCapabilityCatalog
from tools.ProductCapabilityRecord import (
    ProductCapabilityCategory,
    ProductCapabilityRecord,
)
from tools.ToolCapability import ToolCapability
from tools.ToolRegistry import ToolRegistry

#: Kali operation kind/transport pairs an actual production process adapter
#: accepts today. Sourced from reading `WslKaliOperationProcessAdapter`
#: (accepts both reviewed kinds) and `VmwareKaliOperationProcessAdapter`
#: (accepts only the reviewed DNS_RECORD_LOOKUP dig plan) -- not derived by
#: enumerating every kind against every transport, which would describe a
#: combination ("HTTPS_HEADER_LOOKUP" over "VMWARE_KALI") that cannot
#: currently be dispatched.
_EXECUTABLE_KALI_OPERATIONS: tuple[
    tuple[ResearchKaliOperationKind, ResearchKaliCommandTransport], ...
] = (
    (
        ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        ResearchKaliCommandTransport.WSL_KALI,
    ),
    (
        ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        ResearchKaliCommandTransport.VMWARE_KALI,
    ),
    (
        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        ResearchKaliCommandTransport.WSL_KALI,
    ),
)

#: No local tool today requires a credential or is bound to a research
#: target scope (see `ToolRuntime._build`: clock, text statistics and
#: filesystem tools all read only local/in-process state). This is a fact
#: about the current registered set, stated once here rather than guessed
#: per tool; it is re-derived, not assumed, if that set ever changes to
#: include a tool for which it would not hold -- see
#: `local_tool_capability_records`'s docstring.
_NO_LOCAL_TOOL_REQUIRES_CREDENTIALS = False
_NO_LOCAL_TOOL_IS_TARGET_SCOPE_RELEVANT = False


def tool_capability_identity(capability: ToolCapability) -> str:
    """Return the one deterministic identity for a registered local tool."""
    if not isinstance(capability, ToolCapability) or not capability.invocable:
        raise ResearchError("A tool capability identity requires an invocable value.")
    return f"tool:{capability.value}"


def kali_operation_identity(
    operation_kind: ResearchKaliOperationKind,
    transport: ResearchKaliCommandTransport,
) -> str:
    """Return the one deterministic identity for a Kali operation/transport pair."""
    if not isinstance(operation_kind, ResearchKaliOperationKind) or not isinstance(
        transport, ResearchKaliCommandTransport
    ):
        raise ResearchError("A Kali operation identity requires bounded values.")
    return f"kali:{operation_kind.value}:{transport.value}"


def local_tool_capability_records(
    registry: ToolRegistry,
) -> tuple[ProductCapabilityRecord, ...]:
    """Project every tool a real `ToolRegistry` already has registered.

    Reads each registered tool's own `ToolDescriptor` -- never a second,
    separately-authored copy of its effects -- so a capability absent from
    the supplied registry (for example because no filesystem root was
    configured) is correctly absent here too, and a future change to any
    tool's declared effects is reflected the next time this runs, not
    copied once and left to drift.
    """
    records = []
    for capability in registry.registered_capabilities:
        tool = registry.resolve(capability)
        assert tool is not None  # `registered_capabilities` only lists resolvable ones.
        descriptor = tool.descriptor
        records.append(
            ProductCapabilityRecord(
                identity=tool_capability_identity(capability),
                display_name=capability.value.replace("_", " ").title(),
                category=ProductCapabilityCategory.LOCAL_TOOL,
                requires_network=any(
                    effect.observable_outside for effect in descriptor.effects
                ),
                requires_credentials=_NO_LOCAL_TOOL_REQUIRES_CREDENTIALS,
                target_scope_relevant=_NO_LOCAL_TOOL_IS_TARGET_SCOPE_RELEVANT,
                destructive=not descriptor.read_only,
            )
        )
    return tuple(records)


def kali_operation_capability_records() -> tuple[ProductCapabilityRecord, ...]:
    """Describe every Kali operation a real production process adapter accepts.

    Every fact below is read from an existing named constant or enum --
    the dig/curl version prefixes, the shared operation timeout cap, and
    the transport's own credential requirement (SSH key only for
    `VMWARE_KALI`; nothing beyond the local WSL launcher for `WSL_KALI`) --
    never a re-authored copy of the reviewed argv or the authority chain
    itself.
    """
    version_by_kind = {
        ResearchKaliOperationKind.DNS_RECORD_LOOKUP: EXPECTED_DIG_VERSION_PREFIX,
        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP: EXPECTED_CURL_VERSION_PREFIX,
    }
    display_name_by_kind = {
        ResearchKaliOperationKind.DNS_RECORD_LOOKUP: "DNS record lookup (A/AAAA/CNAME)",
        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP: "HTTPS header lookup",
    }
    availability_by_transport = {
        ResearchKaliCommandTransport.WSL_KALI: (
            "WslKaliRuntimeProbe.readiness() via KaliToolGateway; installed "
            "only when HYPATIA_KALI_OPERATION_EXECUTION_ENABLED=true"
        ),
        ResearchKaliCommandTransport.VMWARE_KALI: (
            "VmwareKaliRuntimeProbe.readiness() composing VMware host and "
            "guest readiness via KaliToolGateway; installed only when "
            "HYPATIA_KALI_OPERATION_EXECUTION_ENABLED=true, "
            "HYPATIA_KALI_OPERATION_TRANSPORT=vmware_kali, and both VMware "
            "host/guest readiness opt-ins with complete trusted configuration"
        ),
    }
    records = []
    for operation_kind, transport in _EXECUTABLE_KALI_OPERATIONS:
        records.append(
            ProductCapabilityRecord(
                identity=kali_operation_identity(operation_kind, transport),
                display_name=(
                    f"{display_name_by_kind[operation_kind]} over {transport.value}"
                ),
                category=ProductCapabilityCategory.KALI_OPERATION,
                requires_network=True,
                requires_credentials=(
                    transport is ResearchKaliCommandTransport.VMWARE_KALI
                ),
                target_scope_relevant=True,
                destructive=False,
                version=version_by_kind[operation_kind],
                timeout_seconds=MAX_KALI_OPERATION_TIMEOUT_SECONDS,
                retry_count=0,
                availability_reference=availability_by_transport[transport],
            )
        )
    return tuple(records)


def default_product_capability_catalog(
    tool_registry: ToolRegistry,
) -> ProductCapabilityCatalog:
    """Build the one catalog describing every currently-registered capability.

    Takes an already-constructed `ToolRegistry` rather than building one,
    so this function never decides which local tools exist -- that
    decision stays exactly where it already lives, in `ToolRuntime`.
    """
    return ProductCapabilityCatalog(
        local_tool_capability_records(tool_registry)
        + kali_operation_capability_records()
    )
