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
from research.ResearchComparisonAuthorization import ResearchComparisonAuthorization
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
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
    preview: ResearchSourcePreview | None = None
    attempted_urls: tuple[str, ...] = ()
    acquired_urls: tuple[str, ...] = ()
    body_hashes: tuple[str, ...] = ()
    inspected_bytes: int = 0
    evidence: tuple[ResearchEvidenceRecord, ...] = ()
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = ()
    comparison: SemanticComparisonStepResult | None = None
    semantic_note_id: str = ""
    semantic_input_fingerprint: str = ""
    semantic_relation: str = ""


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
            if self.followup_unnecessary(plan, step.step_id):
                raise ResearchError("Follow-up is unnecessary; no further source call.")
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
            return replace(step, authorized_source_url=observed.selected_url), context
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
            body_hashes=observed.body_hashes,
            inspected_bytes=observed.inspected_bytes,
            evidence_ids=tuple(value.evidence_id for value in observed.evidence),
            assessment_ids=tuple(value.assessment_id for value in observed.assessments),
            semantic_note_id=observed.semantic_note_id,
            semantic_input_fingerprint=observed.semantic_input_fingerprint,
            semantic_relation=observed.semantic_relation,
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
        self._reject_transient_boundary(plan, by_id)
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
        observed = _Observations(
            digest=plan_digest(plan),
            run_id=run_id,
            discovery_id=checkpoint.discovery_id,
            attempted_urls=checkpoint.acquired_urls,
            acquired_urls=checkpoint.acquired_urls,
            body_hashes=checkpoint.body_hashes,
            inspected_bytes=checkpoint.inspected_bytes,
            evidence=evidence,
            assessments=assessments,
        )
        self._validate_recorded_evidence(observed, run)
        self._restore_semantic_adaptation(plan, by_id, checkpoint, observed, run)
        self._observed[plan.plan_id] = observed

    @staticmethod
    def _reject_transient_boundary(
        plan: ResearchPlan,
        steps: dict[str, ResearchPlanExecutionStepSnapshot],
    ) -> None:
        """Refuse uncertain previews/model results rather than replaying them."""
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
                raise ResearchError(
                    "Mission accepted source lacks its durable evidence checkpoint; "
                    "no inferred preview or replay is permitted."
                )
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
            step.capability is Cap.SOURCE_COMPARISON
            and plan.mission_scope is not None
            and len(plan.steps) > 11
            and step.step_id == plan.steps[11].step_id
        ):
            if plan.mission_scope.semantic_policy is None:
                return
            self._observe_semantic_note(
                plan, step, observed, self._runs.get(observed.run_id)
            )

    def followup_unnecessary(self, plan: ResearchPlan, step_id: str | None) -> bool:
        scope = plan.mission_scope
        if (
            scope is None
            or scope.semantic_policy is None
            or step_id != plan.steps[12].step_id
        ):
            return False
        observed = self._observed.get(plan.plan_id)
        if (
            observed is None
            or observed.digest != plan_digest(plan)
            or not observed.semantic_relation
        ):
            return False
        return observed.semantic_relation in {
            "possible_agreement",
            "not_comparable",
        }

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
        observed.semantic_note_id = note.note_id
        observed.semantic_input_fingerprint = result.request.content_fingerprint
        observed.semantic_relation = relation

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
