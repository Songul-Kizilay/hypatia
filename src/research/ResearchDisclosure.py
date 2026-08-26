"""What an approval permits to leave the machine, as a separate permission.

Being allowed to read something locally is not being allowed to send it to a
model endpoint. Hypatia supports OpenAI-compatible endpoints and may run either
local or remote inference, so "the model can see it" is a different question
from "the file was readable", and conflating them is how private content
reaches a third party without anyone deciding that it should.

The decision is carried explicitly on an authorization rather than inferred.
Nothing may derive it from an endpoint being configured, from inference being
enabled, or from the endpoint happening to be loopback today. A default of NONE
matches the existing autonomy budget, whose `max_llm_operations` is also zero.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchDisclosure(StrEnum):
    """Name what one authorization permits to reach a model endpoint."""

    NONE = "none"
    LOCAL_ONLY = "local_only"
    REMOTE_PERMITTED = "remote_permitted"

    @property
    def permits_model_call(self) -> bool:
        """Return whether any model call is permitted at all."""
        return self is not ResearchDisclosure.NONE

    @property
    def permits_remote_endpoint(self) -> bool:
        """Return whether a non-loopback endpoint is permitted.

        Only the explicit remote decision does. Kept as a property so the
        answer is asserted in a test rather than re-derived by each caller,
        which is where a default would quietly become permission.
        """
        return self is ResearchDisclosure.REMOTE_PERMITTED
