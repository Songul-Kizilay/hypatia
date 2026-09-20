"""Pure, bounded history derived from recorded source observations only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from research.SourceIdentity import identity_of


class ResearchSourceTemporalHistoryShape(StrEnum):
    SINGLE = "single_observation"
    LINEAR = "linear"
    BRANCHED = "branched"
    DISCONNECTED = "disconnected"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class ResearchSourceTemporalHistoryEdge:
    relation_id: str
    earlier_run_id: str
    earlier_observation_id: str
    later_run_id: str
    later_observation_id: str
    outcome: ResearchSourceRevalidationOutcome


@dataclass(frozen=True, slots=True)
class ResearchSourceTemporalHistoryObservation:
    run_id: str
    observation_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchSourceTemporalHistory:
    resource_identity: str
    observations: tuple[ResearchSourceTemporalHistoryObservation, ...]
    observation_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    relations: tuple[ResearchSourceTemporalHistoryEdge, ...]
    shape: ResearchSourceTemporalHistoryShape
    latest_recorded_observation_id: str | None
    limitations: tuple[str, ...]


def temporal_history_for(
    requested_url: str,
    *,
    observations: tuple[tuple[str, str, datetime], ...],
    relations: tuple[
        tuple[
            str,
            str,
            str,
            str,
            str,
            ResearchSourceRevalidationOutcome,
        ],
        ...,
    ],
    incomplete_limitations: tuple[str, ...] = (),
) -> ResearchSourceTemporalHistory:
    """Derive graph shape without a clock, fetch or claim about current state."""
    resource_identity = identity_of(requested_url)
    if not resource_identity:
        raise ResearchError("Temporal history requires a canonical requested resource.")
    identities: dict[tuple[str, str], datetime] = {}
    for run_id, observation_id, fetched_at in observations:
        if not run_id or not observation_id or not isinstance(fetched_at, datetime):
            raise ResearchError("Temporal history observation is invalid.")
        if fetched_at.utcoffset() is None or (run_id, observation_id) in identities:
            raise ResearchError("Temporal history observation is ambiguous.")
        identities[(run_id, observation_id)] = fetched_at
    if not identities and not incomplete_limitations:
        raise ResearchError("Temporal history requires at least one observation.")
    edges: list[ResearchSourceTemporalHistoryEdge] = []
    outgoing: dict[tuple[str, str], int] = {}
    incoming: dict[tuple[str, str], int] = {}
    for relation in relations:
        edge = ResearchSourceTemporalHistoryEdge(*relation)
        earlier = (edge.earlier_run_id, edge.earlier_observation_id)
        later = (edge.later_run_id, edge.later_observation_id)
        if earlier not in identities or later not in identities:
            raise ResearchError("Temporal history relation is not canonical.")
        if earlier == later or identities[earlier] >= identities[later]:
            raise ResearchError("Temporal history relation has invalid chronology.")
        if any(existing.relation_id == edge.relation_id for existing in edges):
            raise ResearchError("Temporal history contains duplicate relation IDs.")
        if any(
            (
                existing.earlier_run_id,
                existing.earlier_observation_id,
                existing.later_run_id,
                existing.later_observation_id,
            )
            == (
                edge.earlier_run_id,
                edge.earlier_observation_id,
                edge.later_run_id,
                edge.later_observation_id,
            )
            for existing in edges
        ):
            raise ResearchError("Temporal history contains duplicate relations.")
        edges.append(edge)
        outgoing[earlier] = outgoing.get(earlier, 0) + 1
        incoming[later] = incoming.get(later, 0) + 1
    branched = any(count > 1 for count in (*outgoing.values(), *incoming.values()))
    connected = len(edges) == len(identities) - 1 and len(identities) > 1
    shape = (
        ResearchSourceTemporalHistoryShape.INCOMPLETE
        if incomplete_limitations
        else (
            ResearchSourceTemporalHistoryShape.SINGLE
            if len(identities) == 1
            else (
                ResearchSourceTemporalHistoryShape.BRANCHED
                if branched
                else (
                    ResearchSourceTemporalHistoryShape.LINEAR
                    if connected
                    else ResearchSourceTemporalHistoryShape.DISCONNECTED
                )
            )
        )
    )
    latest_time = max(identities.values(), default=None)
    latest = (
        [key for key, value in identities.items() if value == latest_time]
        if latest_time is not None
        else []
    )
    limitations = ["external_state_unknown", *incomplete_limitations]
    if incomplete_limitations or len(latest) != 1:
        latest_id = None
        if latest:
            limitations.append("latest_observation_time_ambiguous")
    else:
        latest_id = latest[0][1]
    if shape is ResearchSourceTemporalHistoryShape.DISCONNECTED:
        limitations.append("explicit_relation_history_incomplete")
    if shape is ResearchSourceTemporalHistoryShape.BRANCHED:
        limitations.append("relation_history_branched")
    ordered = sorted(identities.items(), key=lambda item: (item[1], item[0]))
    edges.sort(
        key=lambda edge: (
            identities[(edge.earlier_run_id, edge.earlier_observation_id)],
            identities[(edge.later_run_id, edge.later_observation_id)],
            edge.relation_id,
        )
    )
    return ResearchSourceTemporalHistory(
        resource_identity=resource_identity,
        observations=tuple(
            ResearchSourceTemporalHistoryObservation(
                run_id=run_id, observation_id=observation_id, observed_at=observed_at
            )
            for (run_id, observation_id), observed_at in ordered
        ),
        observation_ids=tuple(key[1] for key, _ in ordered),
        relation_ids=tuple(edge.relation_id for edge in edges),
        relations=tuple(edges),
        shape=shape,
        latest_recorded_observation_id=latest_id,
        limitations=tuple(limitations),
    )
