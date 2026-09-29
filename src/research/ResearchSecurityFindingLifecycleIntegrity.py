"""Cross-store replay validation for the security finding lifecycle.

`JsonFileResearchSecurityFindingStore`'s own `__post_init__` (F4 phase 1,
v0.3.420) already replays every invariant expressible from its own single
document: evidence-link/status-transition dangling references, duplicate-of/
superseded-by referential integrity, and closed status-transition-sequence
legality. It cannot replay the invariants below, because they require the
*separately* loadable hypothesis and HTTP-evidence store documents, and a
store must not silently read another store's file — persistence ownership
stays with the application services that already own these cross-store
reads at write time
(`ResearchSecurityFindingApplicationService.create_finding`/
`attach_evidence`/`transition_status`). This module is the reconciliation
boundary: a pure, dependency-free function over three already-loaded
documents, reusing no I/O of its own, callable both by tests in isolation
and by `core.Bootstrap` once at startup after all three stores load.

Four invariants are replayed here, each one a fact the live write path
already guarantees and that a hand-tampered file could otherwise violate
undetected after a restart:

1. **Source-hypothesis binding.** Every finding's `source_hypothesis_id`
   must resolve to a real hypothesis in the *same* `program_id`, and the
   finding's `finding_kind`/`subject_kind`/`subject_canonical_value` must
   exactly match that hypothesis's own `hypothesis_kind`/`subject_kind`/
   `subject_canonical_value` — `create_finding` copies these three fields
   directly from the hypothesis at creation time and never accepts them as
   independent caller-supplied arguments, so any legitimately-created
   finding satisfies this by construction.
2. **Evidence-link binding.** Every finding evidence link's `evidence_id`
   must resolve to a real HTTP evidence record in the same `program_id`,
   and that evidence's `target_kind`/`target_canonical_value` must match
   the citing finding's own `subject_kind`/`subject_canonical_value` — the
   identical comparison `attach_evidence`'s F1 check already proves at
   write time, and which every evidence link carried forward from a
   hypothesis also satisfies transitively (the hypothesis service's own
   `create_hypothesis`/`attach_evidence` enforce the same match against the
   hypothesis's subject, and a legitimately-created finding's subject
   always equals its source hypothesis's subject per check 1).
3. **One finding per source hypothesis.** `create_finding` refuses a second
   finding for a `source_hypothesis_id` that already has one, regardless of
   that first finding's current status (even `DUPLICATE`/`SUPERSEDED`) —
   so no two findings may ever share `(source_hypothesis_id, program_id)`.
4. **`VALIDATED` requires validating evidence, ever.** `transition_status`
   refuses a transition to `VALIDATED` unless at least one `VALIDATES`
   evidence link already exists at that call. Evidence links are
   append-only and never removed, so if a `VALIDATES` link existed at any
   real transition call, it still exists in the final document: a finding
   with a `VALIDATED` transition anywhere in its history but zero
   `VALIDATES` links anywhere in the final document could never have been
   produced by the live service.

Two related checks are deliberately NOT replayed here, because the
persisted, non-interleaved append-only logs cannot prove them without
inventing information that was never recorded:

- The source hypothesis's status *at the exact moment* `create_finding`
  was called. Only the hypothesis's *current* derived status is ever
  computed from its own transition log; there is no persisted snapshot of
  "status when finding X was created," and reconstructing one from
  wall-clock `recorded_at` values would violate this codebase's own
  no-wall-clock-reordering discipline. Inventing this fact during replay
  is exactly the kind of fabricated provenance this codebase forbids.
- Whether any `CONTRADICTS` evidence link existed *before* a `VALIDATED`
  transition. `transition_status` only refuses `VALIDATED` while a
  `CONTRADICTS` link is present *at that call*; `attach_evidence` has no
  gate of its own, so a legitimate history can freely attach `CONTRADICTS`
  evidence *after* an already-recorded `VALIDATED` transition. The
  finding-store document records two independently-append-ordered lists
  (`evidence_links`, `status_transitions`) with no persisted interleaving
  between them, so a final document containing both a `VALIDATED`
  transition and a `CONTRADICTS` link is consistent with more than one
  possible history — one legitimate, one not — and replay cannot tell them
  apart. Asserting "no `CONTRADICTS` link may ever coexist with a
  `VALIDATED` transition" would reject real, legitimately-producible
  histories, not just tampered ones.

Reject-whole on violation, matching this codebase's existing fail-closed
precedent for every other document-level/cross-store invariant: `raise
ResearchError` rather than returning a partial or advisory report.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchSecurityFindingStore import (
    ResearchSecurityFindingDocument,
)
from research.JsonFileResearchSecurityHypothesisStore import (
    ResearchSecurityHypothesisDocument,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus


def verify_finding_lifecycle_integrity(
    finding_document: ResearchSecurityFindingDocument,
    hypothesis_document: ResearchSecurityHypothesisDocument,
    http_evidence_document: ResearchHttpEvidenceDocument,
) -> None:
    """Raise `ResearchError` if the three documents are mutually inconsistent
    in a way the live application services could never have produced.

    Pure and read-only: takes already-loaded, already-validated documents
    and performs no I/O, no mutation, and no persistence of its own.
    """
    _verify_source_hypothesis_binding(finding_document, hypothesis_document)
    _verify_evidence_link_binding(finding_document, http_evidence_document)
    _verify_one_finding_per_source_hypothesis(finding_document)
    _verify_validated_requires_validates_evidence(finding_document)


def _verify_source_hypothesis_binding(
    finding_document: ResearchSecurityFindingDocument,
    hypothesis_document: ResearchSecurityHypothesisDocument,
) -> None:
    hypotheses_by_key = {
        (hypothesis.hypothesis_id, hypothesis.program_id): hypothesis
        for hypothesis in hypothesis_document.hypotheses
    }
    for finding in finding_document.findings:
        hypothesis = hypotheses_by_key.get(
            (finding.source_hypothesis_id, finding.program_id)
        )
        if hypothesis is None:
            raise ResearchError(
                "A security finding's source hypothesis was not found for its"
                " program."
            )
        if hypothesis.hypothesis_kind != finding.finding_kind:
            raise ResearchError(
                "A security finding's kind does not match its source"
                " hypothesis's kind."
            )
        if (
            hypothesis.subject_kind != finding.subject_kind
            or hypothesis.subject_canonical_value != finding.subject_canonical_value
        ):
            raise ResearchError(
                "A security finding's subject does not match its source"
                " hypothesis's subject."
            )


def _verify_evidence_link_binding(
    finding_document: ResearchSecurityFindingDocument,
    http_evidence_document: ResearchHttpEvidenceDocument,
) -> None:
    evidence_by_key = {
        (evidence.evidence_id, evidence.program_id): evidence
        for evidence in http_evidence_document.records
    }
    # `finding_document`'s own `__post_init__` already proved every evidence
    # link references a finding recorded in this same document (F4 phase 1),
    # so this lookup cannot miss.
    findings_by_key = {
        (finding.finding_id, finding.program_id): finding
        for finding in finding_document.findings
    }
    for link in finding_document.evidence_links:
        evidence = evidence_by_key.get((link.evidence_id, link.program_id))
        if evidence is None:
            raise ResearchError(
                "A security finding evidence link cites HTTP evidence that is"
                " not recorded for its program."
            )
        finding = findings_by_key[(link.finding_id, link.program_id)]
        if (
            evidence.target_kind != finding.subject_kind
            or evidence.target_canonical_value != finding.subject_canonical_value
        ):
            raise ResearchError(
                "A security finding evidence link cites HTTP evidence that"
                " does not match the finding's own subject."
            )


def _verify_one_finding_per_source_hypothesis(
    finding_document: ResearchSecurityFindingDocument,
) -> None:
    seen: set[tuple[str, str]] = set()
    for finding in finding_document.findings:
        key = (finding.source_hypothesis_id, finding.program_id)
        if key in seen:
            raise ResearchError(
                "More than one security finding exists for the same source"
                " hypothesis in the same program."
            )
        seen.add(key)


def _verify_validated_requires_validates_evidence(
    finding_document: ResearchSecurityFindingDocument,
) -> None:
    has_validates_evidence: set[tuple[str, str]] = set()
    for link in finding_document.evidence_links:
        if link.relation is ResearchSecurityFindingEvidenceRelation.VALIDATES:
            has_validates_evidence.add((link.finding_id, link.program_id))
    for transition in finding_document.status_transitions:
        if transition.status is ResearchSecurityFindingStatus.VALIDATED:
            key = (transition.finding_id, transition.program_id)
            if key not in has_validates_evidence:
                raise ResearchError(
                    "A security finding was transitioned to validated without"
                    " ever recording validating evidence."
                )
