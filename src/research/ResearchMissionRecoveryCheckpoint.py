"""Durable, non-content checkpoint for a bounded semantic research mission.

The checkpoint names only canonical predecessor records and accounting facts.  It
never persists an inspected preview, model proposal, or source body: those are
either already owned by their canonical stores or cannot safely be replayed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchMissionRecoveryCheckpoint:
    """The persisted observations that can be re-derived without new authority."""

    discovery_id: str = ""
    acquired_urls: tuple[str, ...] = ()
    body_hashes: tuple[str, ...] = ()
    inspected_bytes: int = 0
    evidence_ids: tuple[str, ...] = ()
    assessment_ids: tuple[str, ...] = ()
    semantic_note_id: str = ""
    semantic_input_fingerprint: str = ""
    semantic_relation: str = ""
    contradiction_initial_note_id: str = ""
    contradiction_initial_evidence_ids: tuple[str, ...] = ()
    contradiction_initial_source_document_ids: tuple[str, ...] = ()
    contradiction_initial_assessment_ids: tuple[str, ...] = ()
    contradiction_initial_input_fingerprint: str = ""
    contradiction_initial_relation: str = ""
    contradiction_followup_note_id: str = ""
    contradiction_followup_evidence_id: str = ""
    contradiction_followup_source_document_id: str = ""
    contradiction_followup_assessment_id: str = ""
    contradiction_followup_input_fingerprint: str = ""
    contradiction_followup_relation: str = ""
    contradiction_outcome: str = ""
    # The pre-approved follow-up after an empty initial proposal.  It records
    # only that the authorized branch ran and what typed relation it retained;
    # an absent value (legacy or not yet run) never implies a supported result.
    evidence_gap_followup_note_id: str = ""
    evidence_gap_followup_input_fingerprint: str = ""
    evidence_gap_followup_relation: str = ""
    evidence_gap_outcome: str = ""
    # The authorized URL each acquired source was requested from, in slot order
    # beside ``acquired_urls`` (which holds the validated final URL).  A redirect
    # makes them differ; without the requested identity a restart could select
    # and fetch the same candidate again.  Empty in legacy checkpoints.
    requested_urls: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.acquired_urls,
            self.body_hashes,
            self.evidence_ids,
            self.assessment_ids,
            self.contradiction_initial_evidence_ids,
            self.contradiction_initial_source_document_ids,
            self.contradiction_initial_assessment_ids,
        )
        if (
            not isinstance(self.discovery_id, str)
            or type(self.inspected_bytes) is not int
            or self.inspected_bytes < 0
            or not all(isinstance(value, tuple) for value in values)
            or any(
                not isinstance(item, str) or not item.strip()
                for value in values
                for item in value
            )
            or not isinstance(self.requested_urls, tuple)
            or any(
                not isinstance(item, str) or not item.strip() or item != item.strip()
                for item in self.requested_urls
            )
            or (
                bool(self.requested_urls)
                and len(self.requested_urls) != len(self.acquired_urls)
            )
            or len(self.requested_urls) != len(set(self.requested_urls))
            or len(self.acquired_urls) != len(self.body_hashes)
            or len(self.acquired_urls) != len(set(self.acquired_urls))
            or len(self.evidence_ids) != len(set(self.evidence_ids))
            or len(self.assessment_ids) != len(set(self.assessment_ids))
            or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in self.body_hashes
            )
            or not isinstance(self.semantic_note_id, str)
            or not isinstance(self.semantic_input_fingerprint, str)
            or not isinstance(self.semantic_relation, str)
            or not all(
                isinstance(value, str)
                for value in (
                    self.contradiction_initial_note_id,
                    self.contradiction_initial_input_fingerprint,
                    self.contradiction_initial_relation,
                    self.contradiction_followup_note_id,
                    self.contradiction_followup_evidence_id,
                    self.contradiction_followup_source_document_id,
                    self.contradiction_followup_assessment_id,
                    self.contradiction_followup_input_fingerprint,
                    self.contradiction_followup_relation,
                    self.contradiction_outcome,
                )
            )
            or any(
                value != value.strip()
                for value in (
                    self.contradiction_initial_note_id,
                    self.contradiction_initial_input_fingerprint,
                    self.contradiction_initial_relation,
                    self.contradiction_followup_note_id,
                    self.contradiction_followup_evidence_id,
                    self.contradiction_followup_source_document_id,
                    self.contradiction_followup_assessment_id,
                    self.contradiction_followup_input_fingerprint,
                    self.contradiction_followup_relation,
                    self.contradiction_outcome,
                )
            )
            or self.semantic_note_id != self.semantic_note_id.strip()
            or self.semantic_relation
            not in {
                "",
                "possible_agreement",
                "possible_conflict",
                "not_comparable",
                "no_supported_comparison",
            }
            or bool(self.semantic_note_id) != bool(self.semantic_input_fingerprint)
            or bool(self.semantic_note_id) != bool(self.semantic_relation)
            or (
                self.semantic_input_fingerprint
                and (
                    len(self.semantic_input_fingerprint) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in self.semantic_input_fingerprint
                    )
                )
            )
            or not self._valid_contradiction_state()
            or not self._valid_evidence_gap_state()
        ):
            raise ResearchError("Mission recovery checkpoint is invalid.")
        object.__setattr__(self, "discovery_id", self.discovery_id.strip())
        object.__setattr__(self, "semantic_note_id", self.semantic_note_id.strip())
        object.__setattr__(
            self,
            "semantic_input_fingerprint",
            self.semantic_input_fingerprint.strip(),
        )
        for field in (
            "acquired_urls",
            "body_hashes",
            "evidence_ids",
            "assessment_ids",
            "contradiction_initial_evidence_ids",
            "contradiction_initial_source_document_ids",
            "contradiction_initial_assessment_ids",
        ):
            object.__setattr__(
                self,
                field,
                tuple(value.strip() for value in getattr(self, field)),
            )
        for field in (
            "contradiction_initial_note_id",
            "contradiction_initial_input_fingerprint",
            "contradiction_initial_relation",
            "contradiction_followup_note_id",
            "contradiction_followup_evidence_id",
            "contradiction_followup_source_document_id",
            "contradiction_followup_assessment_id",
            "contradiction_followup_input_fingerprint",
            "contradiction_followup_relation",
            "contradiction_outcome",
        ):
            object.__setattr__(self, field, getattr(self, field).strip())

    def _valid_contradiction_state(self) -> bool:
        """Keep the bounded follow-up outcome self-consistent and non-authoritative."""
        relations = {
            "possible_agreement",
            "possible_conflict",
            "not_comparable",
            "no_supported_comparison",
        }
        initial_values = (
            self.contradiction_initial_note_id,
            self.contradiction_initial_evidence_ids,
            self.contradiction_initial_source_document_ids,
            self.contradiction_initial_assessment_ids,
            self.contradiction_initial_input_fingerprint,
            self.contradiction_initial_relation,
        )
        followup_values = (
            self.contradiction_followup_note_id,
            self.contradiction_followup_evidence_id,
            self.contradiction_followup_source_document_id,
            self.contradiction_followup_assessment_id,
            self.contradiction_followup_input_fingerprint,
            self.contradiction_followup_relation,
            self.contradiction_outcome,
        )
        if not any(initial_values):
            return not any(followup_values)
        if not all(initial_values):
            return False
        if (
            len(self.contradiction_initial_evidence_ids) != 2
            or len(self.contradiction_initial_source_document_ids) != 2
            or len(self.contradiction_initial_assessment_ids) != 2
            or len(set(self.contradiction_initial_evidence_ids)) != 2
            or len(set(self.contradiction_initial_source_document_ids)) != 2
            or len(set(self.contradiction_initial_assessment_ids)) != 2
            or self.contradiction_initial_relation != "possible_conflict"
            or self.contradiction_initial_note_id != self.semantic_note_id
            or self.contradiction_initial_input_fingerprint
            != self.semantic_input_fingerprint
            or self.contradiction_initial_relation != self.semantic_relation
            or not self._fingerprint(self.contradiction_initial_input_fingerprint)
        ):
            return False
        if not any(followup_values):
            return True
        return (
            all(followup_values)
            and self.contradiction_followup_relation in relations
            and self.contradiction_outcome in {"unresolved", "structurally_clarified"}
            and self._fingerprint(self.contradiction_followup_input_fingerprint)
        )

    def _valid_evidence_gap_state(self) -> bool:
        """Keep the empty-proposal follow-up outcome typed and self-consistent."""
        values = (
            self.evidence_gap_followup_note_id,
            self.evidence_gap_followup_input_fingerprint,
            self.evidence_gap_followup_relation,
            self.evidence_gap_outcome,
        )
        if not all(
            isinstance(value, str) and value == value.strip() for value in values
        ):
            return False
        if not any(values):
            return True
        relations = {
            "possible_agreement",
            "possible_conflict",
            "not_comparable",
            "no_supported_comparison",
        }
        expected_outcome = (
            "no_supported_comparison"
            if self.evidence_gap_followup_relation == "no_supported_comparison"
            else "followup_comparison_recorded"
        )
        return (
            all(values)
            and self.semantic_relation == "no_supported_comparison"
            and not self.contradiction_initial_note_id
            and self.evidence_gap_followup_relation in relations
            and self.evidence_gap_outcome == expected_outcome
            and self.evidence_gap_followup_note_id != self.semantic_note_id.strip()
            and self._fingerprint(self.evidence_gap_followup_input_fingerprint)
        )

    @staticmethod
    def _fingerprint(value: str) -> bool:
        return len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )
