"""Decide, in one place, which optional capabilities this installation keeps.

Several capabilities are opt-in, and each opt-in is read twice: the runtime uses
it to decide whether the capability is durable, and the desktop uses it to
decide whether to offer the surface at all. Those two readings must not be
written separately. Copies of one environment rule eventually disagree, and the
failure that follows is a person entering work into a panel that quietly forgets
it.

Every capability here defaults off. An unset environment behaves exactly like a
build without the capability, rather than like one that has it and is broken.
"""

from __future__ import annotations

from collections.abc import Mapping

VULNERABILITY_GRAPH_ENABLED_VARIABLE = "HYPATIA_VULNERABILITY_GRAPH_ENABLED"
HYPOTHESIS_ENABLED_VARIABLE = "HYPATIA_HYPOTHESIS_ENABLED"
FAILURE_MEMORY_ENABLED_VARIABLE = "HYPATIA_FAILURE_MEMORY_ENABLED"
REFLECTION_ENABLED_VARIABLE = "HYPATIA_REFLECTION_ENABLED"
CURIOSITY_ENABLED_VARIABLE = "HYPATIA_CURIOSITY_ENABLED"
RESEARCH_EXECUTION_PERSISTENCE_ENABLED_VARIABLE = (
    "HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED"
)
BACKGROUND_RESEARCH_ENABLED_VARIABLE = "HYPATIA_BACKGROUND_RESEARCH_ENABLED"
PLAN_AUTHORIZATION_ENABLED_VARIABLE = "HYPATIA_PLAN_AUTHORIZATION_ENABLED"
KALI_OPERATION_EXECUTION_ENABLED_VARIABLE = "HYPATIA_KALI_OPERATION_EXECUTION_ENABLED"

#: The single accepted value. Anything else, including "True", "1", and "yes",
#: leaves the capability off. An opt-in that guesses what someone meant is an
#: opt-in that turns itself on.
_ENABLED_VALUE = "true"


def opted_in(environment: Mapping[str, str], variable: str) -> bool:
    """Return whether one named capability is opted in for this process."""
    return environment.get(variable) == _ENABLED_VALUE


def vulnerability_graph_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether the weakness taxonomy is kept."""
    return opted_in(environment, VULNERABILITY_GRAPH_ENABLED_VARIABLE)


def hypothesis_engine_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether hypotheses are kept."""
    return opted_in(environment, HYPOTHESIS_ENABLED_VARIABLE)


def failure_memory_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether failure lessons are kept."""
    return opted_in(environment, FAILURE_MEMORY_ENABLED_VARIABLE)


def reflection_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether reflection history is kept."""
    return opted_in(environment, REFLECTION_ENABLED_VARIABLE)


def curiosity_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether curiosity proposals are kept."""
    return opted_in(environment, CURIOSITY_ENABLED_VARIABLE)


def research_execution_persistence_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether plan-execution snapshots are kept."""
    return opted_in(environment, RESEARCH_EXECUTION_PERSISTENCE_ENABLED_VARIABLE)


def background_research_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether background research tasks are kept."""
    return opted_in(environment, BACKGROUND_RESEARCH_ENABLED_VARIABLE)


def plan_authorization_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether human plan approvals are recorded durably.

    Off by default. Recording an approval starts nothing, but it is the first
    durable step toward work that would, and a capability nobody switched on is
    a capability nobody has to reason about yet.
    """
    return opted_in(environment, PLAN_AUTHORIZATION_ENABLED_VARIABLE)


def kali_operation_execution_enabled(environment: Mapping[str, str]) -> bool:
    """Return whether the reviewed WSL/Kali operation adapter is installed.

    Off by default. Enabling the adapter still does not run an operation by
    itself; every run must pass scope, digest, authorization, readiness and
    explicit run opt-in gates first.
    """
    return opted_in(environment, KALI_OPERATION_EXECUTION_ENABLED_VARIABLE)
