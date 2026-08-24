"""What a tool actually did, keeping running and succeeding apart.

The two flags mirror research step operations, for the same reason. A tool can
genuinely run and still not produce what was wanted, and collapsing that into
one boolean turns "I tried and it did not work" into either a lie or a silence.

``performed`` is set only by a tool that really executed. A refusal before
invocation performs nothing, and nothing that performed nothing may report
success.

``disposition`` says which of the two unsuccessful things happened, because the
flags cannot. A tool that read its arguments and said no, and a tool that took
the request and hit an error partway through, both report ``succeeded=False``,
and for a while the only difference between them was the wording of ``detail``.
That made an important distinction depend on prose, so it is a bounded value
now. Use ``declined`` and ``failed`` to build the two, rather than setting the
flags by hand and hoping they agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolDisposition import ToolDisposition

MAX_TOOL_DETAIL_LENGTH = 500
MAX_TOOL_VALUES = 20
MAX_TOOL_VALUE_LENGTH = 300


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Report whether a tool ran, whether it worked, and what it returned."""

    capability: ToolCapability
    performed: bool
    detail: str
    succeeded: bool = True
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    disposition: ToolDisposition | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ToolCapability):
            raise ResearchError("A tool result capability must be bounded.")
        for flag, label in (
            (self.performed, "performed flag"),
            (self.succeeded, "succeeded flag"),
        ):
            if not isinstance(flag, bool):
                raise ResearchError(f"A tool result {label} must be boolean.")
        if self.succeeded and not self.performed:
            raise ResearchError("A tool that performed nothing cannot have succeeded.")
        if not self.detail.strip():
            raise ResearchError("A tool result detail cannot be empty.")
        if len(self.detail) > MAX_TOOL_DETAIL_LENGTH:
            raise ResearchError("A tool result detail is too long.")
        self._settle_disposition()
        self._validate_values()

    def _settle_disposition(self) -> None:
        """Fill in the disposition when obvious, and refuse it when it disagrees.

        Success and never-reached are both derivable from the flags, so a caller
        does not have to repeat itself. The one case that cannot be derived is
        the interesting one: an unsuccessful result that did reach the tool is
        either a decline or a failure, and only the tool knows which. That
        defaults to DECLINED, the weaker claim — reporting "your request was not
        accepted" when something actually broke is a smaller lie than reporting
        a broken environment when the request was simply wrong, and it does not
        invite a caller to retry the same thing waiting for the world to change.
        """
        settled = self.disposition
        if settled is None:
            if not self.performed:
                settled = ToolDisposition.NOT_REACHED
            elif self.succeeded:
                settled = ToolDisposition.COMPLETED
            else:
                settled = ToolDisposition.DECLINED
        if not isinstance(settled, ToolDisposition):
            raise ResearchError("A tool result disposition must be bounded.")
        if settled.entered_the_tool is not self.performed:
            raise ResearchError(
                "A tool result disposition must agree with whether it performed."
            )
        if settled.succeeded is not self.succeeded:
            raise ResearchError(
                "A tool result disposition must agree with whether it succeeded."
            )
        object.__setattr__(self, "disposition", settled)

    @property
    def declined_request(self) -> bool:
        """Return whether the tool read the request and would not take it."""
        return self.disposition is ToolDisposition.DECLINED

    @property
    def failed_execution(self) -> bool:
        """Return whether the tool took the request and could not finish it."""
        return self.disposition is ToolDisposition.FAILED

    def _validate_values(self) -> None:
        if len(self.values) > MAX_TOOL_VALUES:
            raise ResearchError("A tool result returned too many values.")
        for name, value in self.values:
            if not isinstance(name, str) or not isinstance(value, str):
                raise ResearchError("A tool result name and value must be text.")
            if not name.strip():
                raise ResearchError("A tool result value name cannot be empty.")
            if len(value) > MAX_TOOL_VALUE_LENGTH:
                raise ResearchError("A tool result value is too long.")
        names = [name for name, _ in self.values]
        if len(names) != len(set(names)):
            raise ResearchError("A tool result repeated a value name.")
        if self.values and not self.performed:
            raise ResearchError("A tool that performed nothing returned values.")

    def lines(self) -> tuple[str, ...]:
        """Render the returned values as bounded, labelled lines."""
        return tuple(f"{name}: {value}" for name, value in self.values)

    @classmethod
    def refused(cls, capability: ToolCapability, reason: str) -> ToolResult:
        """Return a result for a tool that was never invoked."""
        return cls(
            capability=capability,
            performed=False,
            detail=reason,
            succeeded=False,
            disposition=ToolDisposition.NOT_REACHED,
        )

    @classmethod
    def declined(
        cls,
        capability: ToolCapability,
        reason: str,
        *,
        values: tuple[tuple[str, str], ...] = (),
    ) -> ToolResult:
        """Return a result for a tool that was reached and would not proceed.

        Nothing was attempted, so nothing is half-done. The request is the
        thing to change.
        """
        return cls(
            capability=capability,
            performed=True,
            detail=reason,
            succeeded=False,
            values=values,
            disposition=ToolDisposition.DECLINED,
        )

    @classmethod
    def failed(
        cls,
        capability: ToolCapability,
        reason: str,
        *,
        values: tuple[tuple[str, str], ...] = (),
    ) -> ToolResult:
        """Return a result for a tool that accepted the request and could not
        finish it.

        The request was fine as far as the tool could tell. Something else went
        wrong, so the environment is the thing to look at.
        """
        return cls(
            capability=capability,
            performed=True,
            detail=reason,
            succeeded=False,
            values=values,
            disposition=ToolDisposition.FAILED,
        )
