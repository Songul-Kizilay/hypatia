"""Resolve approved predecessor bindings, never execute or grant permission.

Transient observations are bounded to one source per execution. Canonical run,
knowledge, approval, executor and allowance remain the only owners of durable
facts and authority. Missing observations fail closed; no refetch or retry.
"""

from dataclasses import dataclass, replace
from hashlib import sha256
from ipaddress import ip_address
from urllib.parse import urlsplit

from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchQueryTerms import normalized_terms
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourcePreview import ResearchSourcePreview
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker


@dataclass(slots=True)
class _Observations:
    digest: str
    run_id: str
    discovery_id: str = ""
    selected_url: str = ""
    preview: ResearchSourcePreview | None = None


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
        if step.capability is Cap.SOURCE_FETCH:
            if observed.selected_url:
                raise ResearchError("Mission source attempt cannot be repeated.")
            ranked = ResearchSourceRelevanceRanker().rank(
                plan.question, record.candidates
            )
            candidate = next(
                (
                    r.candidate
                    for r in ranked
                    if not r.is_duplicate
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
                or not self._public_reference(preview.source.url)
            ):
                raise ResearchError("Fetched preview failed mission inspection.")
            observed.preview = preview
        elif step.capability is Cap.EVIDENCE_RECORDING:
            # Retain origin identity to prevent replay, discard transient body.
            observed.preview = None

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
