"""Whether one execution may begin, and the approval it spent if so.

A verdict plus the record it came from. The verdict is what callers branch on;
the approval is there so a caller can report exactly which permission was used
without going back to the store to look it up.

`authorization` is present only on VALID, and only then is it already consumed.
Anything else means no approval was spent and no work was reached.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanAuthorizationVerdict import ResearchPlanAuthorizationVerdict


@dataclass(frozen=True, slots=True)
class ResearchPlanAuthorizationDecision:
    """One bounded answer to: may this exact execution begin?"""

    verdict: ResearchPlanAuthorizationVerdict
    authorization: ResearchPlanAuthorization | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, ResearchPlanAuthorizationVerdict):
            raise ResearchError("An execution authorization verdict is invalid.")
        if self.verdict.authorizes and not isinstance(
            self.authorization, ResearchPlanAuthorization
        ):
            raise ResearchError("A permitted execution must name its approval.")
        if not self.verdict.authorizes and self.authorization is not None:
            raise ResearchError("A refused execution spent no approval.")
        if self.authorization is not None and not self.authorization.is_consumed:
            raise ResearchError("A permitted execution must have spent its approval.")

    @property
    def permits_start(self) -> bool:
        """Return whether execution may begin."""
        return self.verdict.authorizes

    @classmethod
    def refused(
        cls,
        verdict: ResearchPlanAuthorizationVerdict,
    ) -> ResearchPlanAuthorizationDecision:
        """Refuse without spending anything."""
        return cls(verdict=verdict)

    @classmethod
    def permitted(
        cls,
        authorization: ResearchPlanAuthorization,
    ) -> ResearchPlanAuthorizationDecision:
        """Permit exactly one execution, naming the approval already spent."""
        return cls(
            verdict=ResearchPlanAuthorizationVerdict.VALID,
            authorization=authorization,
        )
