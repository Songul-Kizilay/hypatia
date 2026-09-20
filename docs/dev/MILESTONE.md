# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.

## Current

| Field | Value |
| --- | --- |
| Milestone | Evaluate -> Adapt v1: typed bounded research-plan proposal |
| Base SHA | 265ef451a8be584056d47a770c1e5cd954627848 |
| Status | release |
| Specialists | hypatia-epistemics + hypatia-runtime (implementation: complete), hypatia-security (independent review: APPROVED WITH NOTES, both hardening notes applied), hypatia-qa (independent verification: READY FOR RELEASE, full canonical gates reproduced green) |
| Blockers | none |

Scope: consume one closed mission's existing, unchanged
`ResearchMissionOutcome`. When `goal_satisfaction.status` is
`UNRESOLVED` or `PARTIALLY_SATISFIED` (and only then — `SATISFIED`,
`BLOCKED`, `BUDGET_LIMITED`, `FAILED`, `CANCELLED` are all explicitly
ineligible for v1), derive a new typed, frozen, read-only
`ResearchMissionContinuationProposal` (`src/research/ResearchMissionContinuationProposal.py`):
a pure function of already-canonical state, zero network/LLM/store-write
side effects, deterministic, never persisted. It carries only: a citation
to the originating run/plan/evaluation (`origin_run_id`, `origin_plan_digest`
— the *old* mission's digest, provenance only, never a live authorization),
the original `seed_question` (verbatim `ResearchRun.question`, derived
internally, never caller-supplied separately), and a snapshot of the
evidence/stop-reason state that explains why it was proposed. It carries no
budget, scope, target, discovery-provider, or plan-step field — the
absence of those fields is the structural guarantee against authority
widening, not a runtime check alone. `origin_goal_status` outside the two
eligible values is rejected in `__post_init__`, so an ineligible instance
cannot even be constructed. `origin_plan_digest` is validated with the
existing `ResearchPlanDigest.is_plan_digest`.

Wiring: one new read method, `proposal_for(plan_id)`, added to the existing
`ResearchMissionAuditApplicationService` (`src/cognition/`), reusing its
existing constructor dependencies — no new store, no `Bootstrap.py` change.
It assembles `run`/`checkpoint`/`stop_reason` exactly as `render()` already
does, and fails closed (returns `None`, never fabricates a partial
proposal) whenever the underlying snapshot, run, or stop-reason is missing
or malformed, mirroring `build_mission_audit`'s existing
`if run is not None and stop is not None` gate.

Approval: the proposal carries no plan digest or step content for a *new*
plan, by design — following the existing `ResearchCuriosityQuestion`
precedent that turning a question into a plan stays a separate, explicit
human decision. A human takes `proposal.seed_question` into the existing,
completely unmodified `research_question_plan_preview` intent ->
`ResearchPlanDraftService.preview_question` -> ordinary
`ResearchPlanAuthorization.for_plan` / `verify_plan_authorization` ->
ordinary `ResearchPlanAuthorizationApplicationService` flow — byte-for-byte
the same path a manually-typed question already uses. No new authorization
primitive is introduced anywhere. Security review confirmed re-entry
through `preview_question` is provably identical in privilege to manual
entry (discovery provider is a separate, explicitly-required argument;
question text is never parsed for scope/target/capability) and confirmed
`ResearchPlanAuthorization` can only ever be constructed via `for_plan`.

Non-goals for v1: no revalidation-candidate proposal type (a separate,
existing, unchanged capability — may become reachable through this seam in
a later, separately-scoped milestone); no new desktop UI panel (backend/
service-layer seam only for v1 — a human can act on the proposal via the
existing manual question-entry flow); no proposal from `budget_limited` or
`blocked` outcomes (explicitly deferred to a future "fresh budget request"
/ "operator dependency" milestone); no change whatsoever to the existing
same-plan conditional follow-up mechanism (`ResearchMissionFollowupDecision`
/ `ResearchMissionStepResolver.followup_decision()`), which remains a
distinct, narrower, unmodified mechanism; no new mission domain; no LLM
participation (generation is pure/deterministic, so the "untrusted model
output" caveat is correctly moot for v1).

Permanent invariant this milestone adds: evaluation creates information.
Proposal creates strategy. Only explicit authorization creates permission
to execute.

Also in this milestone's diff (documentation, not product behavior):
adopted `docs/Roadmap/Master_Roadmap.md` as the canonical long-term
roadmap (superseding the stale `docs/Roadmap/README.md` version table),
with corrections from the read-only reconciliation that preceded this
milestone (undercounted items credited, e.g. time budget, GitHub Actions
pinning, concurrent-writer tests; existing Evaluate -> Adapt precedents
named; legacy scaffold directories marked unreachable, not capability); and
a short `CLAUDE.md` pointer to that roadmap.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.395: close Kali HTTPS_HEADER_LOOKUP SSRF/address-pinning gap |
| SHA | 265ef451a8be584056d47a770c1e5cd954627848 |
| Linux desktop CI | success (run 35463425962) |
| Windows desktop CI | success (run 35463427737) |

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
