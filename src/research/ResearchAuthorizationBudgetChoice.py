"""Read the budget a person chose to grant, without ever choosing it for them.

The budget an approval carries is authority, so the only safe way to arrive at
one is that somebody typed it. This reads what they typed and nothing else: a
field left alone keeps the standing default, and a field filled in badly is
refused outright. There is deliberately no path where unreadable input becomes a
number, because the permissive direction is the dangerous one and "it did not
parse, so we used the default" is exactly how authority leaks.

The bounds are not invented here. `ResearchAutonomyBudget` already refuses
negatives, non-integers and anything above the hard ceilings it enforces, so
this hands values to it and lets it judge them.

Model operations are not offered. Every capability the operation registry knows
declares a cost of zero there, so granting more would be granting authority
nothing can spend — and this chain reaches no model at all. The dimension stays
at its default rather than appearing as a control that does nothing.
"""

from __future__ import annotations

from typing import Any

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget

#: The dimensions an operator may set, paired with how each is read. Model
#: operations are absent on purpose; see the module docstring.
_OPERATOR_CHOSEN_FIELDS = ("max_step_advances", "max_network_operations")
_SECONDS_FIELD = "max_seconds"


def budget_from(metadata: dict[str, Any]) -> ResearchAutonomyBudget:
    """Return the budget an operator asked for, or the standing default.

    Absent fields keep their default, which is how leaving the form alone means
    "grant the usual". Present fields must parse exactly; there is no lenient
    reading and no fallback, so a typo refuses the approval rather than quietly
    granting something nobody asked for.
    """
    if not isinstance(metadata, dict):
        raise ResearchError("A budget choice needs the request that carried it.")
    chosen: dict[str, Any] = {}
    for field in _OPERATOR_CHOSEN_FIELDS:
        if field in metadata and _present(metadata[field]):
            chosen[field] = _whole_number(metadata[field], field)
    if _SECONDS_FIELD in metadata and _present(metadata[_SECONDS_FIELD]):
        chosen[_SECONDS_FIELD] = _seconds(metadata[_SECONDS_FIELD])
    return ResearchAutonomyBudget(**chosen)


def _present(value: Any) -> bool:
    """Return whether the operator actually put something in this field."""
    return not (isinstance(value, str) and not value.strip())


def _whole_number(value: Any, field: str) -> int:
    """Return one exact count, refusing anything that is not one.

    Booleans are refused explicitly. Python would read `True` as one, and an
    approval is not somewhere to accept a value that only accidentally means a
    number. Fractions are refused rather than rounded, in either direction: a
    rounded budget is a budget nobody chose.
    """
    if isinstance(value, bool):
        raise ResearchError(f"A {field} budget must be a whole number.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ResearchError(f"A {field} budget must be a whole number.")
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError as error:
            raise ResearchError(f"A {field} budget must be a whole number.") from error
    raise ResearchError(f"A {field} budget must be a whole number.")


def _seconds(value: Any) -> float:
    """Return one exact time bound, refusing anything that is not one.

    Infinities and not-a-number are refused by name. They would each pass an
    ordinary float check and then mean "no limit", which is the one answer this
    boundary must never accept.
    """
    if isinstance(value, bool):
        raise ResearchError("A time budget must be a number of seconds.")
    if isinstance(value, int | float):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError as error:
            raise ResearchError("A time budget must be a number of seconds.") from error
    else:
        raise ResearchError("A time budget must be a number of seconds.")
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        raise ResearchError("A time budget must be a finite number of seconds.")
    return parsed
