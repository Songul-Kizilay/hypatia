"""Resolve approved predecessor bindings, never execute or grant permission.

Transient text is bounded cumulatively across the mission. Canonical run,
knowledge, approval, executor and allowance remain the only owners of durable
facts and authority. Missing observations fail closed; no refetch or retry.
"""

from dataclasses import dataclass, replace
from hashlib import sha256
from ipaddress import ip_address
from urllib.parse import urlsplit

from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchAssessmentAuthorization import ResearchAssessmentAuthorization
from research.ResearchCapabilityCost import cost_for
from research.ResearchComparisonAuthorization import ResearchComparisonAuthorization
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchMissionFollowupDecision import (
    ResearchMissionFollowupDecision,
    ResearchMissionFollowupDecisionStatus,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionStepSnapshot
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchQueryTerms import normalized_terms
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import HTTPS_ACQUISITION, ResearchSource
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourcePreview import ResearchSourcePreview
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker
from research.SemanticComparisonRequest import SemanticComparisonRequest
from research.SemanticComparisonStepBinding import SemanticComparisonStepBinding
from research.SemanticComparisonStepResult import SemanticComparisonStepResult
from research.SourceIdentity import identity_of


@dataclass(slots=True)
class _Observations:
    digest: str
    run_id: str
    discovery_id: str = ""
    selected_url: str = ""
    selected_candidate_id: str = ""
    preview: ResearchSourcePreview | None = None
    attempted_urls: tuple[str, ...] = ()
    acquired_urls: tuple[str, ...] = ()
    # Requested (authorized) URL of each acquired source, beside acquired_urls.
    requested_urls: tuple[str, ...] = ()
    body_hashes: tuple[str, ...] = ()
    inspected_bytes: int = 0
    evidence: tuple[ResearchEvidenceRecord, ...] = ()
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = ()
    comparison: SemanticComparisonStepResult | None = None
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
    evidence_gap_followup_note_id: str = ""
    evidence_gap_followup_input_fingerprint: str = ""
    evidence_gap_followup_relation: str = ""
    evidence_gap_outcome: str = ""


class ResearchMissionStepResolver:
    """Bind ordinary executor slots to canonical predecessor output only."""

    def __init__(
        self,
        runs: ResearchRunManager,
        knowledge: KnowledgeEngine,
        providers: dict[ResearchDiscoveryProviderName, str],
    ) -> None:
        self._runs = runs
        self._knowledge = knowledge
        self._providers = dict(providers)
        self._observed: dict[str, _Observations] = {}

    def resolve(
        self,
        plan: ResearchPlan,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> tuple[ResearchPlanStep, ResearchPlanExecutionContext]:
        scope = plan.mission_scope
        if scope is None or context.cancelled or context.research_run_id is None:
            raise ResearchError("Mission derivation lacks scope or was cancelled.")
        scope.validate_steps(plan.steps)
        run = self._runs.get(context.research_run_id)
        if run.question != plan.question or run.status.terminal:
            raise ResearchError("Mission cannot change its original question or run.")
        observed = self._observed.get(plan.plan_id)
        if observed is None:
            if step != plan.steps[0] or run.discoveries or run.sources or run.evidence:
                raise ResearchError("Mission predecessor state is unavailable.")
            if len(self._observed) >= 20:
                raise ResearchError("Mission observation capacity reached.")
            observed = _Observations(plan_digest(plan), run.run_id)
            self._observed[plan.plan_id] = observed
        if observed.digest != plan_digest(plan) or observed.run_id != run.run_id:
            raise ResearchError("Derivation cannot change original mission authority.")
        if step.capability in {Cap.LOCAL_KNOWLEDGE_SEARCH, Cap.SOURCE_DISCOVERY}:
            return step, context
        record = next(
            (d for d in run.discoveries if d.discovery_id == observed.discovery_id),
            None,
        )
        if (
            record is None
            or record.query != plan.question
            or record.provider != self._providers.get(scope.provider)
        ):
            raise ResearchError("Mission discovery provenance no longer matches.")
        if step.capability is Cap.SOURCE_COMPARISON:
            if scope.semantic_policy is not None:
                return self._semantic_note(step, observed, run), context
            return self._comparison(plan, step, context, observed, run), context
        if step.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON:
            self._validate_recorded_evidence(observed, run)
            policy = scope.semantic_policy
            if policy is None or context.disclosure is not policy.disclosure:
                raise ResearchError("Mission semantic disclosure was not approved.")
            if len(observed.evidence) not in (2, 3) or len(observed.assessments) != len(
                observed.evidence
            ):
                raise ResearchError(
                    "Semantic selection lacks complete predecessor evidence."
                )
            pair = (observed.evidence[0], observed.evidence[-1])
            if len({e.source_document_id for e in pair}) != 2:
                raise ResearchError("Mission comparison requires two distinct sources.")
            request = SemanticComparisonRequest(
                run.run_id, plan.question, pair, limit=1
            )
            if len(request.model_input_json().encode("utf-8")) > policy.max_input_bytes:
                raise ResearchError("Approved per-call disclosure limit exhausted.")
            return (
                replace(
                    step,
                    semantic_mission_policy=None,
                    semantic_comparison_binding=SemanticComparisonStepBinding(
                        request, policy.endpoint, policy.model, policy.disclosure
                    ),
                ),
                context,
            )
        if step.capability is Cap.SOURCE_ASSESSMENT:
            self._validate_recorded_evidence(observed, run)
            evidence = observed.evidence[-1]
            return (
                replace(
                    step,
                    assessment_authorization=ResearchAssessmentAuthorization(
                        evidence.source_document_id,
                        (evidence.evidence_id,),
                        "Automatic source-grounding assessment only. The cited "
                        "excerpt matches its indexed source at this check. Lexical "
                        "relevance is not correctness; trust, independence, "
                        "applicability and publication status remain "
                        f"unassessed/unknown. Mission {observed.digest}.",
                    ),
                ),
                context,
            )
        if step.capability is Cap.SOURCE_FETCH:
            decision = self.followup_decision(plan, step.step_id)
            if (
                decision.status
                is not ResearchMissionFollowupDecisionStatus.NOT_APPLICABLE
                and not decision.proposed
            ):
                raise ResearchError(self.followup_refusal(decision.status))
            if (
                observed.selected_url
                or len(observed.attempted_urls) >= scope.max_sources
            ):
                raise ResearchError("Mission source attempt cannot be repeated.")
            if observed.inspected_bytes >= scope.max_source_bytes:
                raise ResearchError("Cumulative inspected-text budget exhausted.")
            ranked = ResearchSourceRelevanceRanker().rank(
                plan.question, record.candidates
            )
            candidate = next(
                (
                    r.candidate
                    for r in ranked
                    if not r.is_duplicate
                    and identity_of(r.candidate.url)
                    not in {
                        identity_of(url)
                        for url in (*observed.attempted_urls, *observed.acquired_urls)
                    }
                    and r.relevance.score > 0
                    and set(normalized_terms(plan.question)).intersection(
                        normalized_terms(r.candidate.title + " " + r.candidate.snippet)
                    )
                    and self._public_reference(r.candidate.url)
                ),
                None,
            )
            if candidate is None:
                raise ResearchError("No in-scope relevant source candidate; no retry.")
            observed.selected_url = candidate.url
            observed.selected_candidate_id = record.candidate_id_of(candidate) or ""
            observed.attempted_urls += (candidate.url,)
            return replace(step, authorized_source_url=candidate.url), context
        preview = observed.preview
        if (
            preview is None
            or preview.execution_id != plan.plan_id
            or preview.run_id != run.run_id
            or preview.requested_url != observed.selected_url
            or preview.content_byte_count > scope.max_source_bytes
            or not any(c.url == observed.selected_url for c in record.candidates)
        ):
            raise ResearchError("Exact inspected source preview is unavailable.")
        context = replace(context, source_preview=preview)
        if step.capability is Cap.SOURCE_ACCEPT:
            return replace(step, authorized_source_url=observed.selected_url), replace(
                context, discovery_candidate_id=observed.selected_candidate_id
            )
        if step.capability is not Cap.EVIDENCE_RECORDING:
            raise ResearchError("Mission cannot derive another capability.")
        document_id = preview.source.to_document().document_id
        if not any(s.document_id == document_id for s in run.sources):
            raise ResearchError("Mission source has not been canonically accepted.")
        terms = set(normalized_terms(plan.question))
        # A lexical candidate is not semantic analysis or a truth assessment.
        # Preserve the canonical Chunk; no caller or model supplies the quote.
        candidates = [
            c
            for c in self._knowledge.chunks()
            if c.document_id == document_id
            and c.content in preview.source.content
            and terms.intersection(normalized_terms(c.content))
        ]
        if not candidates:
            raise ResearchError("No grounded evidence candidate; no fabricated quote.")
        candidate_chunk = sorted(
            candidates,
            key=lambda c: (
                -len(terms.intersection(normalized_terms(c.content))),
                c.index,
            ),
        )[0]
        digest = sha256(candidate_chunk.content.encode("utf-8")).hexdigest()
        return replace(
            step,
            evidence_authorization=ResearchEvidenceAuthorization(
                document_id,
                candidate_chunk.index,
                "Automatic lexical evidence candidate; exact source text checked, "
                "not independently corroborated or a verified claim. "
                f"Mission {observed.digest}; discovery {observed.discovery_id}; "
                f"source SHA256 {preview.content_sha256}.",
            ),
        ), replace(context, evidence_chunk_sha256=digest)

    def checkpoint(
        self, plan: ResearchPlan
    ) -> ResearchMissionRecoveryCheckpoint | None:
        """Return non-content predecessor facts for one safely resumable mission."""
        observed = self._observed.get(plan.plan_id)
        if observed is None:
            return None
        return ResearchMissionRecoveryCheckpoint(
            discovery_id=observed.discovery_id,
            acquired_urls=observed.acquired_urls,
            requested_urls=observed.requested_urls,
            body_hashes=observed.body_hashes,
            inspected_bytes=observed.inspected_bytes,
            evidence_ids=tuple(value.evidence_id for value in observed.evidence),
            assessment_ids=tuple(value.assessment_id for value in observed.assessments),
            semantic_note_id=observed.semantic_note_id,
            semantic_input_fingerprint=observed.semantic_input_fingerprint,
            semantic_relation=observed.semantic_relation,
            contradiction_initial_note_id=observed.contradiction_initial_note_id,
            contradiction_initial_evidence_ids=(
                observed.contradiction_initial_evidence_ids
            ),
            contradiction_initial_source_document_ids=(
                observed.contradiction_initial_source_document_ids
            ),
            contradiction_initial_assessment_ids=(
                observed.contradiction_initial_assessment_ids
            ),
            contradiction_initial_input_fingerprint=(
                observed.contradiction_initial_input_fingerprint
            ),
            contradiction_initial_relation=observed.contradiction_initial_relation,
            contradiction_followup_note_id=observed.contradiction_followup_note_id,
            contradiction_followup_evidence_id=(
                observed.contradiction_followup_evidence_id
            ),
            contradiction_followup_source_document_id=(
                observed.contradiction_followup_source_document_id
            ),
            contradiction_followup_assessment_id=(
                observed.contradiction_followup_assessment_id
            ),
            contradiction_followup_input_fingerprint=(
                observed.contradiction_followup_input_fingerprint
            ),
            contradiction_followup_relation=(observed.contradiction_followup_relation),
            contradiction_outcome=observed.contradiction_outcome,
            evidence_gap_followup_note_id=observed.evidence_gap_followup_note_id,
            evidence_gap_followup_input_fingerprint=(
                observed.evidence_gap_followup_input_fingerprint
            ),
            evidence_gap_followup_relation=observed.evidence_gap_followup_relation,
            evidence_gap_outcome=observed.evidence_gap_outcome,
        )

    def restore(
        self,
        plan: ResearchPlan,
        checkpoint: ResearchMissionRecoveryCheckpoint | None,
        steps: tuple[ResearchPlanExecutionStepSnapshot, ...],
        run_id: str,
    ) -> None:
        """Rebuild only durable predecessor observations after a process restart.

        A fetch preview and a model proposal are intentionally transient. If a
        restart finds either boundary half-complete, it refuses before another
        provider/model operation can be reached.
        """
        scope = plan.mission_scope
        if scope is None or scope.semantic_policy is None:
            raise ResearchError(
                "Mission recovery requires the recorded semantic scope."
            )
        if plan.plan_id in self._observed:
            raise ResearchError(
                "Mission observations are already live in this process."
            )
        if len(self._observed) >= 20:
            raise ResearchError("Mission observation capacity reached.")
        by_id = {step.step_id: step for step in steps}
        if {step.step_id for step in plan.steps} != set(by_id):
            raise ResearchError(
                "Mission recovery steps do not match the approved plan."
            )
        accept_boundary = self._reject_transient_boundary(plan, by_id)
        if checkpoint is None:
            if any(
                step.status is ResearchPlanStepStatus.COMPLETED
                for step in by_id.values()
            ):
                raise ResearchError(
                    "Mission durable predecessor checkpoint is unavailable."
                )
            self._observed[plan.plan_id] = _Observations(plan_digest(plan), run_id)
            return
        run = self._runs.get(run_id)
        if run.question != plan.question or run.status.terminal:
            raise ResearchError("Mission cannot change its original question or run.")
        if not checkpoint.discovery_id:
            # Stopped after local search and before discovery: nothing external
            # happened, so resume exactly as a mission with no checkpoint does.
            # Any recorded observation or completed later step still refuses.
            if (
                checkpoint == ResearchMissionRecoveryCheckpoint()
                and not (
                    run.discoveries
                    or run.sources
                    or run.evidence
                    or run.assessments
                    or run.comparison_notes
                )
                and not any(
                    step.capability is not Cap.LOCAL_KNOWLEDGE_SEARCH
                    and by_id[step.step_id].status is ResearchPlanStepStatus.COMPLETED
                    for step in plan.steps
                )
            ):
                self._observed[plan.plan_id] = _Observations(plan_digest(plan), run_id)
                return
            raise ResearchError("Mission discovery checkpoint is unavailable.")
        discovery = next(
            (
                value
                for value in run.discoveries
                if value.discovery_id == checkpoint.discovery_id
            ),
            None,
        )
        if (
            discovery is None
            or discovery.query != plan.question
            or discovery.provider != self._providers.get(scope.provider)
        ):
            raise ResearchError("Mission discovery checkpoint no longer matches.")
        sources = {value.document_id: value for value in run.sources}
        if any(
            not any(source.url == url for source in sources.values())
            for url in checkpoint.acquired_urls
        ):
            raise ResearchError("Mission source checkpoint no longer matches.")
        evidence_by_id = {value.evidence_id: value for value in run.evidence}
        assessment_by_id = {value.assessment_id: value for value in run.assessments}
        try:
            evidence = tuple(evidence_by_id[value] for value in checkpoint.evidence_ids)
            assessments = tuple(
                assessment_by_id[value] for value in checkpoint.assessment_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Mission evidence checkpoint no longer matches."
            ) from error
        evidence_ids = {value.evidence_id for value in evidence}
        if any(value.source_document_id not in sources for value in evidence) or any(
            not set(value.evidence_ids).issubset(evidence_ids) for value in assessments
        ):
            raise ResearchError("Mission assessment checkpoint no longer matches.")
        if (
            checkpoint.acquired_urls
            and not checkpoint.requested_urls
            and any(
                step.capability is Cap.SOURCE_FETCH
                and by_id[step.step_id].status is ResearchPlanStepStatus.PENDING
                for step in plan.steps
            )
        ):
            # A legacy checkpoint kept only final URLs.  After a redirect the
            # requested candidate is not recognisable, so another fetch could
            # acquire the same source again; refuse rather than risk it.
            raise ResearchError(
                "Mission checkpoint lacks requested source identities; a further "
                "fetch could repeat an acquired source, so no fetch is replayed."
            )
        observed = _Observations(
            digest=plan_digest(plan),
            run_id=run_id,
            discovery_id=checkpoint.discovery_id,
            # In a live process attempted URLs are the requested ones, and their
            # count is the slot count; final URLs stay excluded via acquired.
            attempted_urls=checkpoint.requested_urls or checkpoint.acquired_urls,
            acquired_urls=checkpoint.acquired_urls,
            requested_urls=checkpoint.requested_urls,
            body_hashes=checkpoint.body_hashes,
            inspected_bytes=checkpoint.inspected_bytes,
            evidence=evidence,
            assessments=assessments,
        )
        # Stopped after accepting the first slot's source, before its evidence:
        # exactly one acquired and accepted source and nothing else yet.
        first_slot_accepted = bool(
            accept_boundary is not None
            and len(checkpoint.acquired_urls) == 1
            and len(run.sources) == 1
            and not (checkpoint.assessment_ids or checkpoint.semantic_note_id)
            and not (run.evidence or run.assessments or run.comparison_notes)
        )
        if checkpoint.evidence_ids:
            self._validate_recorded_evidence(observed, run)
        elif not first_slot_accepted and (
            checkpoint.acquired_urls
            or checkpoint.assessment_ids
            or checkpoint.semantic_note_id
            or run.sources
            or run.evidence
            or run.assessments
            or run.comparison_notes
            or any(
                step.capability is not Cap.LOCAL_KNOWLEDGE_SEARCH
                and step.capability is not Cap.SOURCE_DISCOVERY
                and by_id[step.step_id].status is ResearchPlanStepStatus.COMPLETED
                for step in plan.steps
            )
        ):
            # Nothing past discovery may have happened without recorded evidence;
            # anything else means the checkpoint no longer describes the run.
            raise ResearchError("Mission evidence changed or is missing.")
        # With no recorded evidence the mission stopped at or before its first
        # source slot; the discovery provenance above is all it needs to resume.
        self._restore_semantic_adaptation(plan, by_id, checkpoint, observed, run)
        self._restore_contradiction_investigation(
            plan, by_id, checkpoint, observed, run
        )
        self._restore_evidence_gap_followup(plan, by_id, checkpoint, observed, run)
        if accept_boundary is not None:
            observed.preview = self._restored_accepted_preview(
                plan, accept_boundary, checkpoint, observed, run
            )
            observed.selected_url = observed.preview.requested_url
        self._observed[plan.plan_id] = observed

    def _restored_accepted_preview(
        self,
        plan: ResearchPlan,
        accept_index: int,
        checkpoint: ResearchMissionRecoveryCheckpoint,
        observed: _Observations,
        run: ResearchRun,
    ) -> ResearchSourcePreview:
        """Rebuild the inspected preview of a source that was durably accepted.

        The fetched text itself is transient, but acceptance persisted it: the
        run records this run's own source with the content SHA-256 it observed,
        the knowledge index holds that exact content version, and the checkpoint
        names the requested URL, final URL and body hash of the slot.  Only when
        all of these agree is the preview restored; nothing is fetched, and no
        legacy record lacking the identities is trusted.
        """
        refusal = ResearchError(
            "Mission accepted source lacks its durable evidence checkpoint; "
            "no inferred preview or replay is permitted."
        )
        fetch_step = plan.steps[accept_index - 1] if accept_index > 0 else None
        if (
            fetch_step is None
            or fetch_step.capability is not Cap.SOURCE_FETCH
            or not checkpoint.acquired_urls
            or len(checkpoint.requested_urls) != len(checkpoint.acquired_urls)
            or len(observed.evidence) != len(checkpoint.acquired_urls) - 1
        ):
            raise refusal
        final_url = checkpoint.acquired_urls[-1]
        body_hash = checkpoint.body_hashes[-1]
        record = next(
            (
                source
                for source in run.sources
                if source.url == final_url and source.content_sha256 == body_hash
            ),
            None,
        )
        document = (
            self._knowledge.loaded_document(record.document_id)
            if record is not None
            else None
        )
        if record is None or document is None:
            raise refusal
        try:
            source = ResearchSource(
                url=record.url,
                title=record.title,
                content=document.content,
                content_type=record.content_type,
                fetched_at=record.fetched_at,
                content_resource=str(document.metadata.get("content_resource", "")),
                acquisition=str(
                    document.metadata.get("acquisition", HTTPS_ACQUISITION)
                ),
            )
            preview = ResearchSourcePreview(
                execution_id=plan.plan_id,
                run_id=run.run_id,
                step_id=fetch_step.step_id,
                requested_url=checkpoint.requested_urls[-1],
                source=source,
            )
        except ResearchError as error:
            raise refusal from error
        if (
            preview.content_sha256 != body_hash
            or source.content_version_id() != record.document_id
        ):
            raise refusal
        return preview

    @staticmethod
    def _reject_transient_boundary(
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
    ) -> int | None:
        """Refuse uncertain previews/model results rather than replaying them.

        Returns the index of a completed acceptance whose evidence step has not
        completed.  That preview is durable through acceptance and is rebuilt
        from recorded state or refused by the caller; it is never refetched.
        """
        accept_boundary: int | None = None
        for index, step in enumerate(plan.steps):
            state = steps[step.step_id]
            if step.capability is Cap.SOURCE_FETCH and (
                state.status is ResearchPlanStepStatus.COMPLETED
                and (
                    index + 1 >= len(plan.steps)
                    or steps[plan.steps[index + 1].step_id].capability
                    is not Cap.SOURCE_ACCEPT
                    or steps[plan.steps[index + 1].step_id].status
                    is not ResearchPlanStepStatus.COMPLETED
                )
            ):
                raise ResearchError(
                    "Mission inspected preview was not durably accepted; no refetch "
                    "or replay is permitted."
                )
            if step.capability is Cap.SOURCE_ACCEPT and (
                state.status is ResearchPlanStepStatus.COMPLETED
                and (
                    index + 1 >= len(plan.steps)
                    or steps[plan.steps[index + 1].step_id].capability
                    is not Cap.EVIDENCE_RECORDING
                    or steps[plan.steps[index + 1].step_id].status
                    is not ResearchPlanStepStatus.COMPLETED
                )
            ):
                accept_boundary = index
            if step.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON and (
                state.status is ResearchPlanStepStatus.COMPLETED
                and (
                    index + 1 >= len(plan.steps)
                    or steps[plan.steps[index + 1].step_id].capability
                    is not Cap.SOURCE_COMPARISON
                    or steps[plan.steps[index + 1].step_id].status
                    is not ResearchPlanStepStatus.COMPLETED
                )
            ):
                raise ResearchError(
                    "Mission model output was not durably retained; no model replay "
                    "is permitted."
                )
        return accept_boundary

    def observe(
        self,
        plan: ResearchPlan,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
        result: ResearchPlanStepOperationResult,
    ) -> None:
        if not result.performed or not result.succeeded:
            return
        observed = self._observed[plan.plan_id]
        if context.cancelled:
            raise ResearchError("Mission cancelled; successor work is forbidden.")
        if step.capability is Cap.SOURCE_DISCOVERY:
            if not result.discovery_id:
                raise ResearchError("Discovery did not return canonical provenance.")
            observed.discovery_id = result.discovery_id
        elif step.capability is Cap.SOURCE_FETCH:
            preview = result.source_preview
            scope = plan.mission_scope
            if (
                preview is None
                or scope is None
                or preview.execution_id != plan.plan_id
                or preview.run_id != observed.run_id
                or preview.step_id != step.step_id
                or preview.requested_url != observed.selected_url
                or preview.content_byte_count > scope.max_source_bytes
                or observed.inspected_bytes + preview.content_byte_count
                > scope.max_source_bytes
                or identity_of(preview.source.url)
                in {identity_of(url) for url in observed.acquired_urls}
                or not self._public_reference(preview.source.url)
            ):
                raise ResearchError("Fetched preview failed mission inspection.")
            observed.preview = preview
            observed.acquired_urls += (preview.source.url,)
            observed.requested_urls += (observed.selected_url,)
            observed.body_hashes += (preview.content_sha256,)
            observed.inspected_bytes += preview.content_byte_count
        elif step.capability is Cap.EVIDENCE_RECORDING:
            run = self._runs.get(observed.run_id)
            evidence = next(
                (e for e in run.evidence if e.evidence_id == result.evidence_id), None
            )
            if (
                evidence is None
                or observed.preview is None
                or evidence.source_document_id
                != observed.preview.source.to_document().document_id
            ):
                raise ResearchError("Recorded evidence provenance is unavailable.")
            observed.evidence += (evidence,)
            # Retain origin identity to prevent replay, discard transient body.
            observed.preview = None
            observed.selected_url = ""
            observed.selected_candidate_id = ""
        elif step.capability is Cap.SOURCE_ASSESSMENT:
            run = self._runs.get(observed.run_id)
            assessment = next(
                (a for a in run.assessments if a.assessment_id == result.assessment_id),
                None,
            )
            if (
                assessment is None
                or not observed.evidence
                or assessment.evidence_ids != (observed.evidence[-1].evidence_id,)
            ):
                raise ResearchError("Recorded assessment provenance is unavailable.")
            observed.assessments += (assessment,)
        elif step.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON:
            value = result.semantic_comparison
            if (
                value is None
                or step.semantic_comparison_binding is None
                or value.request != step.semantic_comparison_binding.request
                or value.execution_id != plan.plan_id
                or value.step_id != step.step_id
            ):
                raise ResearchError("Mission semantic result was lost or changed.")
            observed.comparison = value
        elif (
            step.capability is Cap.SOURCE_COMPARISON and plan.mission_scope is not None
        ):
            if plan.mission_scope.semantic_policy is None:
                return
            self._observe_semantic_note(
                plan, step, observed, self._runs.get(observed.run_id)
            )

    def followup_unnecessary(self, plan: ResearchPlan, step_id: str | None) -> bool:
        """Say whether the existing slot is truthfully unnecessary.

        This retains the existing delivery stop behavior while making the
        decision itself available as a typed, digest-bound projection.
        """
        return (
            self.followup_decision(plan, step_id).status
            is ResearchMissionFollowupDecisionStatus.NOT_NEEDED
        )

    def followup_decision(
        self,
        plan: ResearchPlan,
        step_id: str | None,
        allowance: ResearchExecutionAllowance | None = None,
    ) -> ResearchMissionFollowupDecision:
        """Project the one existing third-source slot without creating work.

        The plan already contains this conditional slot and its original digest
        remains the only authority. This method neither picks a future source
        nor consumes allowance; it only reports whether the executor may reach
        the normal resolver path for that one slot.
        """
        scope = plan.mission_scope
        if (
            scope is None
            or scope.semantic_policy is None
            or len(plan.steps) <= 12
            or step_id != plan.steps[12].step_id
            or plan.steps[12].capability is not Cap.SOURCE_FETCH
        ):
            return ResearchMissionFollowupDecision(
                ResearchMissionFollowupDecisionStatus.NOT_APPLICABLE
            )
        observed = self._observed.get(plan.plan_id)
        if (
            observed is None
            or observed.digest != plan_digest(plan)
            or not observed.semantic_note_id
            or not observed.semantic_input_fingerprint
            or not observed.semantic_relation
        ):
            return self._followup_decision(
                plan,
                step_id,
                ResearchMissionFollowupDecisionStatus.BLOCKED_PREDECESSOR,
            )
        if observed.contradiction_outcome or observed.evidence_gap_outcome:
            return self._followup_decision(
                plan,
                step_id,
                ResearchMissionFollowupDecisionStatus.COMPLETED,
                observed,
            )
        if observed.semantic_relation in {"possible_agreement", "not_comparable"}:
            return self._followup_decision(
                plan,
                step_id,
                ResearchMissionFollowupDecisionStatus.NOT_NEEDED,
                observed,
            )
        if len(observed.attempted_urls) >= scope.max_sources:
            return self._followup_decision(
                plan,
                step_id,
                ResearchMissionFollowupDecisionStatus.ALREADY_ATTEMPTED,
                observed,
            )
        if observed.inspected_bytes >= scope.max_source_bytes or (
            allowance is not None and not allowance.affords(cost_for(Cap.SOURCE_FETCH))
        ):
            return self._followup_decision(
                plan,
                step_id,
                ResearchMissionFollowupDecisionStatus.BUDGET_LIMITED,
                observed,
            )
        return self._followup_decision(
            plan, step_id, ResearchMissionFollowupDecisionStatus.PROPOSED, observed
        )

    @staticmethod
    def _followup_decision(
        plan: ResearchPlan,
        step_id: str,
        status: ResearchMissionFollowupDecisionStatus,
        observed: _Observations | None = None,
    ) -> ResearchMissionFollowupDecision:
        return ResearchMissionFollowupDecision(
            status=status,
            plan_digest=plan_digest(plan),
            step_id=step_id,
            capability=Cap.SOURCE_FETCH,
            semantic_note_id=observed.semantic_note_id if observed else "",
            semantic_input_fingerprint=(
                observed.semantic_input_fingerprint if observed else ""
            ),
            semantic_relation=observed.semantic_relation if observed else "",
        )

    @staticmethod
    def followup_refusal(status: ResearchMissionFollowupDecisionStatus) -> str:
        """Return bounded refusal text for a non-proposed existing slot."""
        return {
            ResearchMissionFollowupDecisionStatus.NOT_NEEDED: (
                "Follow-up is unnecessary; no further source call."
            ),
            ResearchMissionFollowupDecisionStatus.BLOCKED_PREDECESSOR: (
                "Follow-up predecessor state is unavailable; no source call."
            ),
            ResearchMissionFollowupDecisionStatus.BUDGET_LIMITED: (
                "Follow-up is outside the remaining bounded budget; no source call."
            ),
            ResearchMissionFollowupDecisionStatus.ALREADY_ATTEMPTED: (
                "Follow-up source was already attempted; no retry is permitted."
            ),
            ResearchMissionFollowupDecisionStatus.COMPLETED: (
                "Follow-up outcome is already recorded; no duplicate source call."
            ),
        }.get(status, "Follow-up slot is not available; no source call.")

    def _observe_semantic_note(
        self,
        plan: ResearchPlan,
        step: ResearchPlanStep,
        observed: _Observations,
        run: ResearchRun,
    ) -> None:
        """Bind one retained semantic result to its canonical comparison note."""
        result = observed.comparison
        authorization = step.comparison_authorization
        if result is None or authorization is None:
            raise ResearchError(
                "Mission semantic note lacks validated comparison state."
            )
        note = next(
            (
                value
                for value in reversed(run.comparison_notes)
                if value.source_document_ids == authorization.document_ids
                and value.evidence_ids == authorization.evidence_ids
                and value.assessment_ids == authorization.assessment_ids
                and value.text == authorization.text
            ),
            None,
        )
        if note is None:
            raise ResearchError("Mission semantic note was not durably retained.")
        relation = (
            result.candidates[0].relation.value
            if result.candidates
            else "no_supported_comparison"
        )
        if len(observed.evidence) == 2:
            if observed.semantic_note_id or observed.contradiction_initial_note_id:
                raise ResearchError("Initial contradiction note cannot be repeated.")
            observed.semantic_note_id = note.note_id
            observed.semantic_input_fingerprint = result.request.content_fingerprint
            observed.semantic_relation = relation
            if relation == "possible_conflict":
                observed.contradiction_initial_note_id = note.note_id
                observed.contradiction_initial_evidence_ids = note.evidence_ids
                observed.contradiction_initial_source_document_ids = (
                    note.source_document_ids
                )
                observed.contradiction_initial_assessment_ids = note.assessment_ids
                observed.contradiction_initial_input_fingerprint = (
                    result.request.content_fingerprint
                )
                observed.contradiction_initial_relation = relation
            return
        if len(observed.evidence) != 3:
            raise ResearchError("Mission contradiction follow-up lacks three sources.")
        if (
            observed.semantic_relation == "no_supported_comparison"
            and not observed.contradiction_initial_note_id
        ):
            # The same pre-approved third-source slot, reached because the
            # initial proposal supported nothing.  Record what it retained; a
            # second empty result is an evidence gap, not an execution failure.
            if observed.evidence_gap_outcome:
                raise ResearchError("Mission evidence-gap follow-up cannot repeat.")
            first_evidence = observed.evidence[0]
            gap_evidence = observed.evidence[-1]
            gap_assessment = next(
                (
                    value
                    for value in observed.assessments
                    if value.evidence_ids == (gap_evidence.evidence_id,)
                ),
                None,
            )
            if (
                gap_assessment is None
                or note.evidence_ids
                != (first_evidence.evidence_id, gap_evidence.evidence_id)
                or note.source_document_ids
                != (first_evidence.source_document_id, gap_evidence.source_document_id)
                or gap_assessment.assessment_id not in note.assessment_ids
            ):
                raise ResearchError(
                    "Mission evidence-gap follow-up provenance changed."
                )
            observed.evidence_gap_followup_note_id = note.note_id
            observed.evidence_gap_followup_input_fingerprint = (
                result.request.content_fingerprint
            )
            observed.evidence_gap_followup_relation = relation
            observed.evidence_gap_outcome = (
                "no_supported_comparison"
                if relation == "no_supported_comparison"
                else "followup_comparison_recorded"
            )
            return
        if (
            observed.contradiction_initial_relation != "possible_conflict"
            or not observed.contradiction_initial_note_id
            or observed.contradiction_outcome
        ):
            raise ResearchError("Mission contradiction follow-up is not authorized.")
        followup_evidence = observed.evidence[-1]
        followup_assessment = next(
            (
                value
                for value in observed.assessments
                if value.evidence_ids == (followup_evidence.evidence_id,)
            ),
            None,
        )
        if (
            followup_assessment is None
            or note.evidence_ids
            != (
                observed.contradiction_initial_evidence_ids[0],
                followup_evidence.evidence_id,
            )
            or note.source_document_ids
            != (
                observed.contradiction_initial_source_document_ids[0],
                followup_evidence.source_document_id,
            )
            or followup_assessment.assessment_id not in note.assessment_ids
        ):
            raise ResearchError("Mission contradiction follow-up provenance changed.")
        observed.contradiction_followup_note_id = note.note_id
        observed.contradiction_followup_evidence_id = followup_evidence.evidence_id
        observed.contradiction_followup_source_document_id = (
            followup_evidence.source_document_id
        )
        observed.contradiction_followup_assessment_id = (
            followup_assessment.assessment_id
        )
        observed.contradiction_followup_input_fingerprint = (
            result.request.content_fingerprint
        )
        observed.contradiction_followup_relation = relation
        observed.contradiction_outcome = (
            "structurally_clarified"
            if relation == "possible_agreement"
            else "unresolved"
        )

    def _restore_semantic_adaptation(
        self,
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
        checkpoint: ResearchMissionRecoveryCheckpoint,
        observed: _Observations,
        run: ResearchRun,
    ) -> None:
        """Restore only a recorded note's bounded branch decision.

        The model response remains transient.  This reads the canonical retained
        note plus the non-content checkpoint and never attempts to recreate a
        model result or infer one from ordinary note prose.
        """
        semantic_index = next(
            (
                index
                for index, value in enumerate(plan.steps)
                if value.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON
                and steps[value.step_id].status is ResearchPlanStepStatus.COMPLETED
            ),
            None,
        )
        if semantic_index is None:
            return
        note_index = semantic_index + 1
        if (
            note_index >= len(plan.steps)
            or plan.steps[note_index].capability is not Cap.SOURCE_COMPARISON
            or steps[plan.steps[note_index].step_id].status
            is not ResearchPlanStepStatus.COMPLETED
        ):
            return
        if not checkpoint.semantic_note_id:
            raise ResearchError(
                "Mission semantic note adaptation checkpoint is unavailable."
            )
        note = next(
            (
                value
                for value in run.comparison_notes
                if value.note_id == checkpoint.semantic_note_id
            ),
            None,
        )
        if note is None:
            raise ResearchError("Mission semantic note checkpoint no longer matches.")
        expected_evidence = tuple(value.evidence_id for value in observed.evidence[:2])
        expected_documents = tuple(
            value.source_document_id for value in observed.evidence[:2]
        )
        expected_assessments = tuple(
            value.assessment_id
            for value in observed.assessments
            if value.evidence_ids[0] in expected_evidence
        )
        if (
            note.evidence_ids != expected_evidence
            or note.source_document_ids != expected_documents
            or note.assessment_ids != expected_assessments
            or f"Input SHA256 {checkpoint.semantic_input_fingerprint};" not in note.text
            or f"mission {plan_digest(plan)}." not in note.text
            or "Mission semantic research note; tentative interpretation, not truth."
            not in note.text
            or (
                checkpoint.semantic_relation == "no_supported_comparison"
                and "No supported comparison proposal; evidence gap remains."
                not in note.text
            )
            or (
                checkpoint.semantic_relation != "no_supported_comparison"
                and f"Tentative relation: {checkpoint.semantic_relation}."
                not in note.text
            )
        ):
            raise ResearchError("Mission semantic note provenance no longer matches.")
        observed.semantic_note_id = checkpoint.semantic_note_id
        observed.semantic_input_fingerprint = checkpoint.semantic_input_fingerprint
        observed.semantic_relation = checkpoint.semantic_relation

    def _restore_contradiction_investigation(
        self,
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
        checkpoint: ResearchMissionRecoveryCheckpoint,
        observed: _Observations,
        run: ResearchRun,
    ) -> None:
        """Restore a completed bounded follow-up without reinterpreting it.

        The outcome is only an accounting projection over canonical records.  It
        never recreates model output, selects a winner, or treats a tentative
        relation as a truth claim.
        """
        if not checkpoint.contradiction_initial_note_id:
            return
        initial_evidence = tuple(value.evidence_id for value in observed.evidence[:2])
        initial_documents = tuple(
            value.source_document_id for value in observed.evidence[:2]
        )
        initial_assessments = tuple(
            value.assessment_id for value in observed.assessments[:2]
        )
        if (
            checkpoint.contradiction_initial_note_id != checkpoint.semantic_note_id
            or checkpoint.contradiction_initial_evidence_ids != initial_evidence
            or checkpoint.contradiction_initial_source_document_ids != initial_documents
            or checkpoint.contradiction_initial_assessment_ids != initial_assessments
            or checkpoint.contradiction_initial_input_fingerprint
            != checkpoint.semantic_input_fingerprint
            or checkpoint.contradiction_initial_relation != "possible_conflict"
            or checkpoint.semantic_relation != "possible_conflict"
        ):
            raise ResearchError("Mission contradiction checkpoint no longer matches.")
        initial_note = next(
            (
                value
                for value in run.comparison_notes
                if value.note_id == checkpoint.contradiction_initial_note_id
            ),
            None,
        )
        if (
            initial_note is None
            or initial_note.evidence_ids != initial_evidence
            or initial_note.source_document_ids != initial_documents
            or initial_note.assessment_ids != initial_assessments
        ):
            raise ResearchError("Mission contradiction note no longer matches.")
        observed.contradiction_initial_note_id = (
            checkpoint.contradiction_initial_note_id
        )
        observed.contradiction_initial_evidence_ids = initial_evidence
        observed.contradiction_initial_source_document_ids = initial_documents
        observed.contradiction_initial_assessment_ids = initial_assessments
        observed.contradiction_initial_input_fingerprint = (
            checkpoint.contradiction_initial_input_fingerprint
        )
        observed.contradiction_initial_relation = (
            checkpoint.contradiction_initial_relation
        )
        if not checkpoint.contradiction_followup_note_id:
            return
        followup_note_step = self._followup_note_step(plan, steps)
        if followup_note_step is None:
            raise ResearchError(
                "Mission contradiction follow-up was not durably retained."
            )
        followup_evidence = observed.evidence[-1]
        followup_assessment = next(
            (
                value
                for value in observed.assessments
                if value.evidence_ids == (followup_evidence.evidence_id,)
            ),
            None,
        )
        followup_note = next(
            (
                value
                for value in run.comparison_notes
                if value.note_id == checkpoint.contradiction_followup_note_id
            ),
            None,
        )
        expected_evidence = (initial_evidence[0], followup_evidence.evidence_id)
        expected_documents = (
            initial_documents[0],
            followup_evidence.source_document_id,
        )
        expected_assessments = (
            initial_assessments[0],
            followup_assessment.assessment_id if followup_assessment else "",
        )
        expected_outcome = (
            "structurally_clarified"
            if checkpoint.contradiction_followup_relation == "possible_agreement"
            else "unresolved"
        )
        if (
            followup_assessment is None
            or followup_note is None
            or checkpoint.contradiction_followup_evidence_id
            != followup_evidence.evidence_id
            or checkpoint.contradiction_followup_source_document_id
            != followup_evidence.source_document_id
            or checkpoint.contradiction_followup_assessment_id
            != followup_assessment.assessment_id
            or followup_note.evidence_ids != expected_evidence
            or followup_note.source_document_ids != expected_documents
            or followup_note.assessment_ids != expected_assessments
            or "Bounded follow-up compared the first source with one new source."
            not in followup_note.text
            or f"Input SHA256 {checkpoint.contradiction_followup_input_fingerprint};"
            not in followup_note.text
            or f"mission {plan_digest(plan)}." not in followup_note.text
            or (
                checkpoint.contradiction_followup_relation == "no_supported_comparison"
                and "No supported comparison proposal; evidence gap remains."
                not in followup_note.text
            )
            or (
                checkpoint.contradiction_followup_relation != "no_supported_comparison"
                and "Tentative relation: "
                f"{checkpoint.contradiction_followup_relation}."
                not in followup_note.text
            )
            or checkpoint.contradiction_outcome != expected_outcome
        ):
            raise ResearchError(
                "Mission contradiction follow-up provenance no longer matches."
            )
        observed.contradiction_followup_note_id = (
            checkpoint.contradiction_followup_note_id
        )
        observed.contradiction_followup_evidence_id = followup_evidence.evidence_id
        observed.contradiction_followup_source_document_id = (
            followup_evidence.source_document_id
        )
        observed.contradiction_followup_assessment_id = (
            followup_assessment.assessment_id
        )
        observed.contradiction_followup_input_fingerprint = (
            checkpoint.contradiction_followup_input_fingerprint
        )
        observed.contradiction_followup_relation = (
            checkpoint.contradiction_followup_relation
        )
        observed.contradiction_outcome = checkpoint.contradiction_outcome

    def _restore_evidence_gap_followup(
        self,
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
        checkpoint: ResearchMissionRecoveryCheckpoint,
        observed: _Observations,
        run: ResearchRun,
    ) -> None:
        """Restore a completed empty-proposal follow-up without reinterpreting it.

        A completed follow-up note with no durable typed outcome refuses rather
        than being read from note prose or assumed supported.
        """
        gap_branch = (
            checkpoint.semantic_relation == "no_supported_comparison"
            and not checkpoint.contradiction_initial_note_id
        )
        if not checkpoint.evidence_gap_followup_note_id:
            if gap_branch and self._followup_note_step(plan, steps) is not None:
                raise ResearchError(
                    "Mission evidence-gap follow-up outcome is unavailable."
                )
            return
        if (
            not gap_branch
            or len(observed.evidence) != 3
            or self._followup_note_step(plan, steps) is None
        ):
            raise ResearchError(
                "Mission evidence-gap follow-up was not durably retained."
            )
        first_evidence = observed.evidence[0]
        gap_evidence = observed.evidence[-1]
        gap_assessment = next(
            (
                value
                for value in observed.assessments
                if value.evidence_ids == (gap_evidence.evidence_id,)
            ),
            None,
        )
        gap_note = next(
            (
                value
                for value in run.comparison_notes
                if value.note_id == checkpoint.evidence_gap_followup_note_id
            ),
            None,
        )
        relation = checkpoint.evidence_gap_followup_relation
        if (
            gap_assessment is None
            or gap_note is None
            or gap_note.evidence_ids
            != (first_evidence.evidence_id, gap_evidence.evidence_id)
            or gap_note.source_document_ids
            != (first_evidence.source_document_id, gap_evidence.source_document_id)
            or gap_assessment.assessment_id not in gap_note.assessment_ids
            or "Bounded follow-up compared the first source with one new source."
            not in gap_note.text
            or f"Input SHA256 {checkpoint.evidence_gap_followup_input_fingerprint};"
            not in gap_note.text
            or f"mission {plan_digest(plan)}." not in gap_note.text
            or (
                relation == "no_supported_comparison"
                and "No supported comparison proposal; evidence gap remains."
                not in gap_note.text
            )
            or (
                relation != "no_supported_comparison"
                and f"Tentative relation: {relation}." not in gap_note.text
            )
        ):
            raise ResearchError(
                "Mission evidence-gap follow-up provenance no longer matches."
            )
        observed.evidence_gap_followup_note_id = (
            checkpoint.evidence_gap_followup_note_id
        )
        observed.evidence_gap_followup_input_fingerprint = (
            checkpoint.evidence_gap_followup_input_fingerprint
        )
        observed.evidence_gap_followup_relation = relation
        observed.evidence_gap_outcome = checkpoint.evidence_gap_outcome

    @staticmethod
    def _followup_note_step(
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
    ) -> ResearchPlanExecutionStepSnapshot | None:
        """Return the one completed source-comparison slot after the third source."""
        semantic_indices = [
            index
            for index, value in enumerate(plan.steps)
            if value.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON
        ]
        if len(semantic_indices) != 2:
            return None
        note_index = semantic_indices[1] + 1
        if (
            note_index >= len(plan.steps)
            or plan.steps[note_index].capability is not Cap.SOURCE_COMPARISON
        ):
            return None
        state = steps[plan.steps[note_index].step_id]
        return state if state.status is ResearchPlanStepStatus.COMPLETED else None

    def _semantic_note(
        self, step: ResearchPlanStep, observed: _Observations, run: ResearchRun
    ) -> ResearchPlanStep:
        self._validate_recorded_evidence(observed, run)
        result = observed.comparison
        if result is None or result.request.run_id != run.run_id:
            raise ResearchError("No validated mission comparison to retain.")
        rows = []
        for c in result.candidates:
            rows.append(
                f"Tentative relation: {c.relation.value}.\n"
                f"A quotation (first 350 characters): {c.left_quote[:350]}\n"
                f"B quotation (first 350 characters): {c.right_quote[:350]}\n"
                f"Untrusted model rationale (first 160 characters): {c.rationale[:160]}"
            )
        text = (
            "Mission semantic research note; tentative interpretation, not truth.\n"
            + (
                "\n".join(rows)
                or "No supported comparison proposal; evidence gap remains."
            )
            + "\nUnique exact quotations were checked against recorded excerpts. "
            "This does not establish meaning, independence or correctness. "
            "No verified claim or trust promotion. "
            + (
                "Bounded follow-up compared the first source with one new source. "
                if len(observed.evidence) == 3
                else "Initial pair comparison. "
            )
            + f"Input SHA256 {result.request.content_fingerprint}; "
            f"mission {observed.digest}."
        )
        ids = tuple(e.evidence_id for e in result.request.evidence)
        return replace(
            step,
            comparison_authorization=ResearchComparisonAuthorization(
                tuple(e.source_document_id for e in result.request.evidence),
                ids,
                tuple(
                    a.assessment_id
                    for a in observed.assessments
                    if a.evidence_ids[0] in ids
                ),
                text,
            ),
        )

    def _validate_recorded_evidence(
        self, observed: _Observations, run: ResearchRun
    ) -> None:
        if not observed.evidence or any(
            e not in run.evidence for e in observed.evidence
        ):
            raise ResearchError("Mission evidence changed or is missing.")
        audit = ResearchEvidenceIntegrityAuditor(self._knowledge).audit([run])
        if (
            not audit.available
            or audit.changed_evidence_count
            or audit.missing_evidence_count
        ):
            raise ResearchError("Mission evidence no longer matches canonical content.")

    def _comparison(
        self,
        plan: ResearchPlan,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
        observed: _Observations,
        run: ResearchRun,
    ) -> ResearchPlanStep:
        self._validate_recorded_evidence(observed, run)
        if (
            plan.mission_scope is None
            or plan.mission_scope.max_sources != 2
            or len(observed.evidence) != 2
            or len(observed.assessments) != 2
            or len({e.source_document_id for e in observed.evidence}) != 2
            or any(a not in run.assessments for a in observed.assessments)
            or context.cancelled
        ):
            raise ResearchError(
                "Comparison requires two complete mission evidence chains."
            )
        left, right = observed.evidence
        query_terms = set(normalized_terms(plan.question))
        left_terms = query_terms.intersection(normalized_terms(left.excerpt))
        right_terms = query_terms.intersection(normalized_terms(right.excerpt))

        def terms(values: set[str]) -> str:
            return ", ".join(sorted(values))[:200] or "none"

        repeated = observed.body_hashes[0] == observed.body_hashes[1]
        body_relationship = (
            "identical; possible duplicate content" if repeated else "different bytes"
        )
        text = (
            "Automatic lexical evidence comparison (not a semantic verdict).\n"
            f"Evidence A: {left.evidence_id}; B: {right.evidence_id}.\n"
            f"Question terms in both excerpts: {terms(left_terms & right_terms)}.\n"
            f"Terms only in A's excerpt: {terms(left_terms - right_terms)}.\n"
            f"Terms only in B's excerpt: {terms(right_terms - left_terms)}.\n"
            f"Exact fetched bodies: {body_relationship}.\n"
            "Different URLs do not establish independent sources or corroboration. "
            "A term missing from an excerpt is not absent from the full source. "
            "Agreement and contradiction remain unassessed; no winner or trust "
            "promotion. Both cited chunks passed current integrity checks. "
            f"Cumulative inspected text: {observed.inspected_bytes} UTF-8 bytes. "
            f"Mission {observed.digest}."
        )
        return replace(
            step,
            comparison_authorization=ResearchComparisonAuthorization(
                tuple(e.source_document_id for e in observed.evidence),
                tuple(e.evidence_id for e in observed.evidence),
                tuple(a.assessment_id for a in observed.assessments),
                text,
            ),
        )

    @staticmethod
    def _public_reference(url: str) -> bool:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or host == "localhost"
            or host.endswith((".localhost", ".local"))
        ):
            return False
        try:
            return ip_address(host).is_global
        except ValueError:
            # DNS resolution, rebinding and redirects remain enforced by the
            # canonical source fetcher, never by this lexical admission filter.
            return True
