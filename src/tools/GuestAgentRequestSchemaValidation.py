"""Cross-check a Guest-Agent request's logical inputs against a real schema.

`research.GuestAgentProtocol.GuestAgentRequest` stays valid entirely on its
own (bounded, non-duplicated logical input field names) without ever needing
a live `ProductCapabilitySchemaCatalog` to exist. This module adds exactly
one further, optional, still-pure check: whether a request's logical input
field names are ones a specific capability's already-described
`ProductCapabilityInputSchema` can prove are *unknown* to it.

SCHEMA VALID != EXECUTION AUTHORIZED. This function never authorizes, never
executes, never dispatches, and never mutates either argument; it returns
nothing but raises on a proven mismatch, exactly like
`tools.ProductCapabilityVersionAssessment.assess_capability_version` is a
pure comparison and nothing more. `ProductCapabilitySchema` remains
descriptive only -- calling this function does not make it anything else.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentRequest
from tools.ProductCapabilitySchema import ProductCapabilityInputSchema


def validate_guest_agent_request_inputs(
    request: GuestAgentRequest,
    input_schema: ProductCapabilityInputSchema,
) -> None:
    """Raise when a request names a logical input field the schema proves
    is unknown; otherwise return `None`.

    A field this function cannot find in `input_schema.fields` by name is
    reported as unknown. A schema marked
    `ProductCapabilitySchemaCompleteness.UNDECLARED` or `PARTIAL` may
    legitimately not enumerate every real field a capability eventually
    accepts, so this check is a *mismatch detector*, not a complete
    allowlist enforcement mechanism -- it proves disagreement where the
    schema is precise enough to prove one, and says nothing where it is not.
    """
    if not isinstance(request, GuestAgentRequest):
        raise ResearchError("Guest-agent request schema check requires a request.")
    if not isinstance(input_schema, ProductCapabilityInputSchema):
        raise ResearchError(
            "Guest-agent request schema check requires a bounded input schema."
        )
    known_names = {field.name for field in input_schema.fields}
    for name, _ in request.logical_inputs:
        if name not in known_names:
            # Deliberately a fixed sentence, never one built by interpolating
            # the field name itself: that name is still caller-chosen text,
            # and `tools.ToolResult.detail`/`ProductCapabilityVersionAssessment.reason`
            # already keep this exact line between bounded data and a raised
            # message -- this function holds it too.
            raise ResearchError(
                "Guest-agent request names a logical input field this "
                "capability's schema does not describe."
            )
