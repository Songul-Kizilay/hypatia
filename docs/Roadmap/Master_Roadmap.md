# Hypatia master roadmap

Canonical long-term product direction: phases, ordering, and the
implemented/planned/experimental distinction. This document governs *what*
Hypatia is building toward and *why the order is what it is*. It does not
govern engineering process, quality gates, or milestone mechanics — those
live in [`CLAUDE.md`](../../CLAUDE.md). The single current bounded milestone
and the last delivered product milestone live in
[`docs/dev/MILESTONE.md`](../dev/MILESTONE.md). Delivered changes live in
[`CHANGELOG.md`](../../CHANGELOG.md). Present product state lives in
[`PROJECT_STATUS.md`](../../PROJECT_STATUS.md).

This document supersedes the older per-version theme files
(`v0.1.md`–`v5.0.md`) and the version table that used to live in
[`README.md`](README.md); that file is now an index pointing here. Two prior
reconciliation documents remain useful background and are not duplicated
here: [`Autonomous_Cybersecurity_Mission_Direction.md`](Autonomous_Cybersecurity_Mission_Direction.md)
(the cybersecurity-direction rationale this roadmap's phase ordering is
built on) and [`Master_Checklist_Reconciliation.md`](Master_Checklist_Reconciliation.md)
(an earlier, partial reconciliation pass from 2026-09-08, baseline `1399b16`
/ v0.3.319 — superseded in scope by this document but not factually wrong).

## Reconciliation basis

This roadmap was reconciled against repository ground truth at
`265ef451a8be584056d47a770c1e5cd954627848` (v0.3.395) on 2026-09-20 by
independent read-only inspection (hypatia-lead plus the hypatia-runtime,
hypatia-epistemics, hypatia-security and hypatia-qa specialists). Every
`[x]` item below is backed by an inspected file, class, or test — not by a
similarly named file, module, or folder existing. Every corrected item
below was previously mis-stated in one direction or the other; corrections
are noted inline. **Roadmap != current capability. Planned != implemented.
Capability != authority. Proposal != execution.**

**Follow-up reconciliation, 2026-09-22 (documentation-only, hypatia-lead):**
this v0.3.395 basis had gone stale in three places by v0.3.396-399 shipping
without a matching roadmap update. Phase 4 ("Provenance visualization"),
Phase 6 (Evaluate -> Adapt v1) and Phase 7 (cancellation/interruption,
atomic writes) were re-verified against current code, tests and
`origin/main` history and corrected below, each with inline evidence. This
was a targeted pass on those three phases only, not a full 25-phase
re-reconciliation — every other phase's status is carried forward unchanged
from the v0.3.395 basis above.

An item is complete only when repository evidence demonstrates the intended
behavior, and is never marked complete merely because a plausibly-named
file, class, test, document, or TODO exists.

### Scope note: legacy scaffold is not capability

The repository tree contains large directories — `src/agents/*`,
`src/modules/*`, most of `src/services/*` (books, cinema, gaming, home,
travel, music, news, cooking, career, recipes, spotify, suno, linkedin,
maps, weather, vision_ai, ocr, stt, tts, camera, …), `src/robotics`,
`src/vision`, `src/voice`, `src/xr`, `src/watch`, `src/mobile`,
`src/entertainment`, `src/home`, `src/rag`, `src/plugins`, `src/skills`,
`src/search`, `src/extensions` — that **nothing in `src/` or `tests/`
imports**. These are unreachable legacy scaffold from an earlier, broader
product direction. Their presence is not evidence that voice, vision,
robotics, smart-home, games, or any Phase 25 non-goal capability exists,
works, or is planned for near-term delivery. Treat them as dead code until a
specific milestone explicitly revives one, at which point that milestone
should say so.

## Status legend

- `[x]` implemented / delivered — repository evidence demonstrates the
  described behavior.
- `[~]` active or immediate next direction.
- `[ ]` planned; if partial infrastructure already exists uncredited, that
  is called out in a parenthetical note rather than checking the box early.
- `[-]` intentional non-goal for now.

## Hypatia north star

```text
USER provides:  goal + scope + authority + constraints + budget

HYPATIA:        understand -> plan -> execute -> observe -> verify
                -> adapt -> recover -> evaluate -> report -> learn
```

Core properties: **autonomous + verifiable + recoverable + explainable +
safe-by-boundary**.

## Permanent product / epistemic invariants

These are never weakened by any phase below. The full engineering-facing
version lives in CLAUDE.md's "Hypatia invariants" section; this is the
fuller epistemic list that explains *why* later phases (contradiction
handling, revalidation, evaluate/adapt, security reasoning) are shaped the
way they are.

plan created != work performed · tool success != result verified · source
fetched != evidence · source accepted != evidence verified · evidence !=
verified claim · semantic interpretation != fact · contradiction found !=
one side false · follow-up performed != contradiction resolved ·
comparison attempted != comparison supported · tentative comparison !=
verified comparison · possible_agreement != supported comparison ·
operator judgement != model truth · execution completed != mission goal
satisfied · goal satisfied != run closed · report produced != universal
truth · model confidence != evidence · unknown independence != independent
corroboration · source trust != truth · two URLs != independent sources ·
replanning creates strategy, not authority · restart != fresh authority ·
restart != fresh budget · retry strategy != retry authority · failed
attempt != universal inability · stored lesson != verified fact · same URL
!= same content · same content != same observation · historical
observation != current-world truth · revalidation != freshness ·
freshness recommendation != execution permission · runtime capability !=
runtime authority · schedule != permission · consensus != truth.

A model, tool, source, document, plugin, agent, mission result, or external
content may never grant itself authority.

**Evaluate/Adapt-specific (added with the v1 milestone, Phase 6):**
evaluation creates information. Proposal creates strategy. Only explicit
authorization creates permission to execute.

---

## Phase 1 — Desktop / LLM foundation

- [x] Windows desktop application — `src/desktop/TkinterDesktopWindow.py`
- [x] Ollama integration — `src/llm/LLMEndpointPolicy.py` (loopback-only HTTP)
- [x] OpenAI-compatible local LLM endpoint — `src/llm/OpenAICompatibleProvider.py`
- [x] Conversation/session model — `src/session/*`
- [x] Custom system prompt — `src/llm/HypatiaSystemPrompt.py`
- [x] Basic user memory/context — `src/memory/MemoryManager.py`, `LearnedMemory*`
- [x] Local document search — `src/knowledge/KnowledgeEngine.py`
- [x] Self-audit — `src/memory/LearnedMemoryAuditor.py`, `src/cognition/SecurityAgentApplicationService.py`
- [x] Runtime capability self-awareness — `src/cognition/RuntimeCapabilityProjection.py`, wired from real service-presence facts, fail-closed to `UNKNOWN`
- [x] Distinguish Hypatia application capabilities from LLM capabilities
- [x] Prevent unsupported capabilities from being presented as available
- [x] v0.3.447 capability/cross-session-memory claim truthfulness: a
      capability/status question no longer gets swallowed by the live-
      research refusal shortcut; `UNKNOWN` ("not confirmed") is no longer
      told to the model as a flat denial, only `UNAVAILABLE` is; the already-
      existing, already-wired cross-session recall path is now named in the
      capability list the model is told about; a capability correction must
      be stated plainly, never silent
- [x] v0.3.448 cross-session recall topic-term fix (live-validated): a
      natural recall sentence wrapping a real topic in ordinary recall
      instructions ("bul", "ve", "söyle"/find, "and", "tell") no longer
      returns a false NOT_FOUND -- the lexical term extractor's stop-word
      list now strips that boilerplate so the AND-intersection matcher is
      not defeated by words absent from the real record; detection, the
      matching algorithm, and session-exclusion/provenance are unchanged

- [ ] Model registry
- [ ] Task-specific model routing
- [ ] Local/cloud hybrid routing
- [ ] Structured model-output validation
- [ ] Model timeout/failure handling (**corrected**: partial — real per-request
      timeout config and `LLMError` wrapping already exist in
      `UrllibChatCompletionTransport`/`OpenAICompatibleProvider`; no
      retry/backoff exists yet, so the item stays open)
- [ ] Model-version provenance

## Phase 2 — Mission runtime

- [x] Mission, Goal, Scope, Authority, Constraints, Budget — `src/research/ResearchPlan*.py` family
- [x] Typed research planning
- [x] Execution state machine, Step state — `ResearchPlanExecutionState.py`, `ResearchPlanExecutionStatus.py`
- [x] Execution allowance, cumulative budget accounting — `ResearchExecutionAllowance.py`, `ResearchExecutionSpend.py`
- [x] Durable state, restart/recovery, crash recovery, replay safety —
      tested in `tests/research/test_execution_attempt_durability.py`,
      `tests/research/test_curiosity_execution_resume.py`,
      `tests/research/test_one_shot_deferred_execution.py`
- [x] Plan digest — `ResearchPlanDigest.py`
- [x] Mission recovery refusal logic — `ResearchAttemptRecovery.py`, `ResearchMissionRecoveryCheckpoint.py`

- [ ] Domain-generic bounded execution kernel
- [ ] A second genuine mission domain beyond research
- [ ] Split `CognitiveEngine.process()` into domain routers when justified
      (confirmed still a single 4,274-line research-coupled dispatcher; no
      second domain exists anywhere live)

Important: do not prematurely generalize the research runtime before a
second genuine domain demonstrates the need. **This applies directly to
Phase 6**: Evaluate -> Adapt v1 stays inside the research domain (it
proposes a new bounded research plan) — it is not, and must not become, a
second mission domain or a generic adaptation kernel.

## Phase 3 — Authority / policy / budget

Authority — all `[x]`, implemented and tested:

- [x] Explicit approval, digest-bound authorization, single-use
      authorization, expiring authorization
- [x] Scope expansion prevention, target expansion prevention, budget
      expansion prevention
- [x] Credential authority separation — `src/core/RuntimeOptIn.py`
- [x] Destructive-action boundary, exact runtime opt-in, refusal before side
      effect

Evidence: `ResearchPlanAuthorization*.py`, `ResearchKaliOperationAuthorization*.py`,
`DeferredExecutionGrant*.py`, `tests/research/test_deferred_execution_grants.py`.

- [ ] Domain-generic typed authority kernel

Policy engine — confirmed genuinely absent (no `ALLOW`/`DENY`/`REQUIRE_APPROVAL`
abstraction anywhere; only scattered per-domain authorization classes):

- [ ] Central policy evaluator
- [ ] Scope / authority / budget / network / credential / tool /
      destructive-action policy
- [ ] `ALLOW` / `DENY` / `REQUIRE_APPROVAL`
- [ ] Policy-version binding, policy-decision provenance
- [ ] Model cannot override policy engine

Resource/budget:

- [x] Source budget, network-operation budget, mission cumulative allowance
- [x] Time budget (**corrected — was `[ ]`, uncredited**): `ResearchAutonomyBudget.max_seconds`,
      enforced as `AutonomyStopReason.TIME_BUDGET_EXHAUSTED` in
      `ResearchAutonomyApplicationService.py`, tested in
      `tests/research/test_runtime_budget_exhaustion.py::ElapsedTimeCanExhaustTheGrantTests`

- [ ] Tool-call budget (**corrected**: partial — `max_llm_operations` caps
      LLM-operation count via `AutonomyStopReason.LLM_BUDGET_EXHAUSTED`; a
      generic budget over arbitrary tool calls does not exist because a
      generic tool registry (Phase 9) does not exist yet)
- [ ] Token budget
- [ ] Retry budget
- [ ] Per-step budget
- [ ] CPU/RAM/disk limits where appropriate
- [ ] Cost forecast before approval

## Phase 4 — Research / evidence / provenance

- [x] Approved research runs, source discovery, source fetch, source
      acceptance, evidence, claims, contradictions, evidence completion
- [x] Goal satisfaction evaluation with `unresolved` / `partially_satisfied`
      / `blocked` states — `ResearchMissionGoalSatisfaction.py`
- [x] "Source trust != truth" — `ResearchAssessmentAuthorization` note text
- [x] Unknown source independence — `ResearchSourceIndependence` defaults to `UNKNOWN`
- [x] "Two URLs != independent corroboration" — `SourceIdentity.identity_of`/`same_resource`,
      audited in `SecurityPostureAuditor._duplicate_findings`, tested in
      `tests/integration/test_duplicate_corroboration.py`

Observation/provenance:

- [x] Immutable observation identity, observation windows, typed temporal
      history — distinct types confirmed: `SourceIdentity` (resource
      identity) vs. `ResearchSourceContentRecord.content_sha256` (content
      identity) vs. `ResearchSourceTemporalHistoryObservation` (observation
      identity) are three separate dataclasses, not shared fields
- [x] "Same URL != same content", "same content != same observation"
- [x] Typed source-revalidation relations, `content_changed`/`content_unchanged`
      — `ResearchSourceRevalidationOutcome`
- [x] Provenance-aware temporal history

- [ ] Evidence lineage graph
- [x] Provenance visualization — `src/research/ResearchMissionAuditTraceabilityGraph.py`
      re-shapes `build_mission_audit`'s existing traceability data into
      typed nodes/edges; the `research_mission_audit_traceability_view`
      Brain intent and the desktop app's read-only `ttk.Treeview`
      ("View provenance graph", "3 Authored analysis" -> "Plan draft")
      let an operator browse it in-app (v0.3.399)
- [ ] Rich source-independence model
- [ ] Citation-chain / mirror / syndication detection

## Phase 5 — Revalidation / network safety

Bounded source revalidation — all `[x]`, tested beyond the happy path:

- [x] Bounded source revalidation, exact prior-observation binding,
      same-run restriction, prior requested URL reused, arbitrary URL
      substitution prevented
- [x] Normal source/network budget consumption (no separate budget)
- [x] New immutable observation after revalidation
- [x] Crash-safe revalidation recovery — `tests/research/test_source_revalidation.py::test_restart_restores_the_relation_and_suppresses_a_duplicate`
      (genuine process-restart test: new manager instance reloads from disk)
- [x] At-most-once per prior observation per run —
      `tests/research/test_source_revalidation_step_operation.py::test_the_manager_refuses_a_second_revalidation_of_the_same_prior`
- [x] Ambiguous fetch fails closed (implemented as fail-closed refusal; no
      code literally says "operator ruling" — that phrase is roadmap
      paraphrase for "refuses rather than inferring")

- [x] User-facing revalidation workflow — `src/desktop/RevalidationResearchDraft.py`,
      the desktop's "2 Sources & evidence" eligible-source picker and
      "Propose revalidation" button, and the `research_revalidation_step_preview`
      Brain intent let an operator propose one explicitly approved re-fetch
      of an already-accepted source through the ordinary, unmodified
      preview -> authorize -> confirm -> start flow (v0.3.401)
- [ ] Evaluate->Adapt may propose revalidation without granting authority
      (explicitly **not** in the v1 Evaluate -> Adapt milestone — see Phase 6;
      v1 supports exactly one action type, bounded research-plan proposal,
      not revalidation proposals)
- [ ] Cross-run freshness/revalidation policy

HTTP safety — all `[x]`, independently verified with real SSRF/redirect/
address-pinning tests:

- [x] Public HTTPS validation, loopback refusal, RFC1918/private refusal,
      link-local refusal, mixed public/private DNS refusal
- [x] Redirect validation — every redirect target revalidated, final URL
      revalidated again post-fetch
- [x] TLS-aware transport, address pinning — `PinnedHttpsTransport.py`
- [x] DNS rebinding / TOCTOU protections (bounded via single-resolution
      pinning within one short-lived call, not a separate keyed-rebind test)
- [x] Scoped fetch validation — `ScopedPublicHttpsUrlValidator.py`

Kali bounded operations:

- [x] Operation preview, human-reviewed command plan, authorization,
      execution, `DNS_RECORD_LOOKUP`, `HTTPS_HEADER_LOOKUP`
- [x] Resolved-address validation, `curl --resolve` pinning, DNS drift fails
      closed, validated/contacted address provenance
- [x] v0.3.395 Kali SSRF/address-pinning fix — verified with **zero**
      process calls on DNS drift:
      `tests/cognition/test_kali_operation_authorization_application_service.py::test_https_header_run_refuses_when_the_resolution_changes_before_run`
      (`adapter.calls == 0`, authorization remains unconsumed in the store)
- [x] v0.3.436 Safe Tool Gateway v2, first slice: the existing checks for
      both operation kinds moved behind one `KaliToolGateway`, same order,
      none weakened; a prior defect where an adapter exception after
      authorization consumption was misreported as "Execution: not
      started / Process: not created" is fixed — the stage at failure now
      determines whether the outcome is a genuine pre-dispatch refusal or
      an explicit "unknown outcome" (never "nothing happened")

- [ ] General typed tool-execution framework (confirmed: only two
      `ResearchKaliOperationKind` values exist repo-wide, no generic
      dispatcher — v0.3.436 centralized existing per-kind checks, it did
      not generalize the framework)

## Phase 6 — Evaluate -> Adapt

- [x] **Evaluate -> Adapt v1: typed bounded research-plan proposal** —
      delivered v0.3.396 (`500d22168f6a49a8e919b76b0ea673f05041640b`),
      reachable from `origin/main`, exact-SHA Linux (run `35509333572`) and
      Windows (run `35509334966`) CI both `success`. See "Desired eventual
      behavior" below for the item-by-item re-verification (2026-09-22).
      **v2 is not ready** — see product decision 2 and the checklist's
      `[-]` "Bounded source-revalidation proposal" line below for why.

### Existing precedents (name these explicitly; do not rediscover or duplicate them)

- **`ResearchMissionOutcome` / `ResearchMissionGoalSatisfaction` /
  `ResearchMissionCompletionReadiness`** (`src/research/ResearchMissionOutcome.py`,
  `ResearchMissionGoalSatisfaction.py`) — the existing, fully-tested, typed
  "mission evaluation result" with exactly the states this phase needs
  (`satisfied`, `partially_satisfied`, `unresolved`, `blocked`,
  `budget_limited`, `failed`, `cancelled`). This is the read-only projection
  Evaluate -> Adapt v1 consumes. It creates no new evaluation states.
- **`ResearchMissionFollowupDecision`** (`src/research/ResearchMissionFollowupDecision.py`)
  — an existing, separate, narrower mechanism. It describes the resolver's
  decision about **one fixed step inside one already-authorized plan**
  (a pre-approved conditional third-source slot, capability pinned to
  `SOURCE_FETCH`, bound to that plan's own digest). It authors no new plan,
  selects no new URL, and grants no new authority — it unlocks a slot the
  operator already approved when the original plan was authorized. **This
  is not the Evaluate -> Adapt mechanism.** Evaluate -> Adapt v1 is a
  distinct, new, cross-mission/cross-run capability: it looks at a *closed*
  mission's outcome and proposes a *new*, separately-authorized plan. The
  existing same-plan conditional follow-up behavior is unchanged by this
  milestone and must remain unchanged (v1 non-goal).
- **`ResearchCuriosityQuestion`** (`src/research/ResearchCuriosityQuestion.py`)
  — a second, lighter existing precedent for "proposed, not executed":
  its docstring states explicitly that accepting a question does not
  create a plan or queue work; turning a question into work stays a
  separate, explicit human decision. Same discipline Evaluate -> Adapt v1
  must follow.

### Product decisions (authoritative for v1 — recorded 2026-09-20)

1. **Eligible evaluation outcomes**: `unresolved` and `partially_satisfied`
   only. `budget_limited` and `blocked` are explicitly **not**
   proposal-eligible in v1 — budget exhaustion must never silently become a
   request for more budget, and a blocked state may reflect a genuine
   authority/scope/operator dependency that a proposal must not paper over.
   No new evaluation states are invented for this rule; it is expressed
   entirely in terms of the existing `ResearchMissionGoalSatisfactionStatus`
   enum. A future, separately-scoped milestone may design a typed "request
   fresh budget" or "operator dependency" flow — out of scope for v1.
2. **v1 action type**: exactly one — a bounded research-plan proposal.
   Source revalidation remains a separate, existing, unchanged capability;
   a later milestone may make it reachable through Evaluate -> Adapt as a
   second, separately-designed typed proposal/action once the v1 seam is
   proven. v1 does not combine both action types.
3. This document (`docs/Roadmap/Master_Roadmap.md`) is the canonical
   roadmap location; `docs/Roadmap/README.md` is its index.

### Desired eventual behavior (bounded to the decisions above for v1)

Re-verified against `src/research/ResearchMissionContinuationProposal.py`,
`ResearchMissionAuditApplicationService.proposal_for`, and
`tests/e2e/test_continuation_proposal_reentry.py` on 2026-09-22
(hypatia-epistemics + hypatia-lead). Each `[x]` below cites its evidence
directly rather than inheriting the v0.3.395 basis's `[ ]`.

- [x] Consume an existing mission-evaluation result (`ResearchMissionOutcome`)
      — `continuation_proposal_for(run, outcome, ...)` takes it directly
      (`ResearchMissionContinuationProposal.py:128-165`)
- [x] `unresolved` -> bounded follow-up proposal — `_ELIGIBLE_GOAL_STATUSES`
- [x] `partially_satisfied` -> bounded follow-up proposal — same set
- [-] `blocked` -> no v1 proposal (deferred to a future "operator dependency" milestone)
- [-] `budget_limited` -> no v1 proposal (deferred to a future "fresh budget request" milestone)
- [x] Typed proposal object — `ResearchMissionContinuationProposal`
      (frozen dataclass; `__post_init__` makes an ineligible instance
      impossible to construct)
- [x] Exactly one proposed next research-plan action — one `seed_question`
      field, no list/plurality
- [x] Proposal != authority; proposal != execution — no budget, scope,
      target, discovery-provider or plan-step field exists on the type
      (module docstring, lines 6-14)
- [x] Human approval remains required — approving a proposal manually
      extracts `seed_question` and threads it through the ordinary,
      completely unmodified question-preview -> authorization -> start
      flow (proven byte-for-byte identical to manual entry by
      `test_continuation_proposal_reentry.py`); the desktop's "Use this
      proposal's question" button (v0.3.400) only copies `seed_question`
      into the question field — there is still deliberately no dedicated
      "approve this proposal" method; populating the field is not itself
      approval, and the same unmodified manual preview -> authorization ->
      start walk is still required afterward
- [x] Reuse existing approval machinery (`ResearchPlanAuthorization*`) —
      no new authorization primitive (same re-entry test)
- [x] Reuse existing budget machinery — fresh, operator-set budget per
      proposed mission, never inherited/pooled/extended — re-entry calls
      `run_manager.create(...)` to start an unrelated new run
- [x] Prevent scope expansion, target expansion, budget expansion,
      credential expansion — structural: the absent fields above make
      expansion impossible to express, not merely refused at runtime
- [x] Restart/replay safety — pure function, nothing persisted ("never
      persisted, re-derived on demand," module docstring line 14)
- [x] Proposal provenance — `origin_run_id`, `origin_plan_digest`,
      `origin_stop_reason`, `origin_goal_status`, `origin_evidence_status`,
      `origin_evidence_limitations` fields all present
- [-] Bounded source-revalidation proposal (explicitly deferred past v1 —
      see product decision 2). **Investigated 2026-09-22 and found not
      simply reachable**: the fetch-based `source_revalidation` plan step
      (v0.3.393) is a hard single-run construct at three independent
      layers — `SourceRevalidationStepBinding` has exactly one
      `research_run_id` field, `SourceRevalidationStepOperation.run()`
      explicitly refuses when the binding's run differs from the execution
      context's run, and `ResearchRunManager` hardcodes
      `earlier_run_id=later_run_id=run.run_id` — with a dedicated refusing
      test (`tests/research/test_source_revalidation_step_operation.py::test_cross_run_provenance_is_refused_without_authority`).
      A version that delivers real cross-mission revalidation linking
      requires new cross-mission authority/budget-boundary design; this is
      **not** a bounded reuse of existing machinery and is out of scope for
      autonomous execution until a human makes that design decision.
- [ ] Independent security review, [ ] Independent QA — left unchecked:
      no milestone-specific v0.3.396 sign-off artifact survives in the tree
      (`docs/dev/MILESTONE.md`'s ledger has since rolled forward through
      v0.3.397-399), so a dedicated original-release review of that exact
      diff cannot be cited. Note for context, not a substitute for the
      above: the underlying authority-safety properties this milestone
      depends on (no budget/scope/target/credential field, fail-closed
      `__post_init__`, byte-identical re-entry) were independently
      re-traced and confirmed sound by hypatia-epistemics on 2026-09-22,
      and the standing Claude-team review process was already in active,
      CHANGELOG-documented use in the immediately adjacent
      v0.3.395/397/398 milestones.
- [x] Exact-SHA Linux + Windows CI delivery — Linux run `35509333572`,
      Windows run `35509334966`, both `success` on `500d22168f6a49a8e919b76b0ea673f05041640b`

### Critical constraints (unchanged from prior direction)

Do not create an autonomous planning loop. Do not make learning autonomous.
Do not allow evaluate to authorize adapt. Do not allow a proposal to
execute automatically. Do not convert mission evaluation into new
authority. If source revalidation becomes reachable through this seam in a
future milestone, it must continue through its normal explicit approval,
authority, budget, provenance, and replay-safety path — never a shortcut.

### Future direction: bounded delegated research & evidence-quality
completion (recorded 2026-09-22, product-direction only — not scoped,
not authorized, not started)

This is long-term product direction, not a locked milestone. It extends
Evaluate -> Adapt's existing "propose, never auto-execute" discipline
toward a broader model: an operator explicitly delegates *bounded*
continuation once, rather than approving every routine step, and research
completion becomes evidence-quality-driven rather than a fixed source
count or step quota. It touches Phase 2 (mission runtime), Phase 3
(authority/budget), Phase 4 (evidence/provenance), and Phase 10
(explainability); it does not introduce a new phase number so phase
ordering and existing cross-references stay intact.

**A. Bounded delegated research continuation** — `[ ]`, **requires human
authority-policy design before any implementation**. An explicit "continue
researching this topic" instruction from the operator should be able to
authorize routine continuation (further source lookups, comparisons,
revalidation steps, contradiction checks) within the scope/budget/target
already approved, without a fresh approval for each one — returning to
the operator only at a genuinely new decision boundary (material scope
change, new target, new credential authority, new execution authority).
This is explicitly NOT an autonomous loop: it must stay inside one
bounded, already-authorized budget and scope, matching this file's
existing "Do not create an autonomous planning loop" constraint above and
CLAUDE.md's "restart != fresh authority" family of invariants. Existing
partial support: `ResearchAutonomyApplicationService`'s bounded advance
loop (Phase 2, `[x]`) already runs multiple steps inside one approval
without per-step re-authorization — this direction is a further-bounded
extension of that existing pattern, not a new mechanism from scratch, but
deciding exactly what counts as "routine" vs. a "new decision boundary"
is itself a policy question requiring explicit human design and sign-off,
not an autonomous inference. No implementation may begin here without
that sign-off.

**B. Evidence quality over source count** — `[ ]`. Research completion
logic should weigh evidence quality/independence/contradiction state
over a fixed source or step quota. Existing partial support: `[x]`
"Unknown source independence" already defaults to `UNKNOWN`
(`ResearchSourceIndependence`) rather than assuming independence, and
`[x]` "Two URLs != independent corroboration" (`SourceIdentity.identity_of`/
`same_resource`) already prevents literal duplicate-URL double-counting.
Genuinely absent: automatic detection that multiple *different* URLs
share a common upstream/original source (so N sites repeating one wire
report don't read as N independent confirmations) — this would need new,
carefully-bounded content/citation analysis, not merely URL comparison,
and must preserve "same content != same observation" and "never infer
provenance from text" (existing permanent invariants) rather than
guessing common ancestry from prose similarity.

**C. Epistemic (not numeric) source comparison** — `[ ]`. When sources
disagree, comparison should be able to consider primary-vs-secondary
status, publication/update date, methodology, sample/population, scope,
and directness of evidence — not simply which position has more URLs.
Existing partial support: `[x]` operator-authored comparison notes and
reviews already exist (Phase 4/6 territory) and already preserve
unresolved disagreement rather than forcing a winner (`[x]` "possible
agreement != supported comparison"). `applicability`
(`ResearchSourceApplicability`: DIRECT/PARTIAL/BACKGROUND_ONLY/UNRELATED)
already covers directness of evidence — this predates this candidate's
text and was already true when v0.3.195 added it. As of v0.3.405, `[x]`
`evidence_type` (`ResearchSourceEvidenceType`:
UNKNOWN/PRIMARY/SECONDARY/TERTIARY) closes the primary-vs-secondary gap
specifically: a new operator-authored, citation-only dimension on
`ResearchSourceAssessmentRecord`, provably inert to claim calibration and
kept distinct from `independence` (a primary source that is the only
source is still exactly one source). Genuinely still absent: any
structured field for methodology or sample/population. Adding those as
new *operator-authored* fields (citation, not inference) would fit the
existing discipline; auto-*inferring* source quality from text would not,
and must not be built without a separate, explicit design pass on where
the line is.

**D. Confidence and uncertainty made visible** — `[~]` partially covered
by existing capability. `ResearchMissionGoalExplanation`'s
`reasons`/`caveats` and the teaching report (both Phase 10-adjacent,
`[x]` per prior archaeology) already explain what's supported, what's
uncertain, and why a mission stopped, in plain typed terms — desktop-
reachable today (v0.3.400/401 archaeology). As of v0.3.403, a bounded,
deterministic, code-literal "what would help close this gap" guidance
statement (`[x]`) is also attached, derived only from the existing typed
`ResearchEvidenceCompletionLimitation` values — no model-generated text,
no inference beyond the already-computed limitation. Genuinely still
absent: any numeric confidence score. Per this file's own existing
discipline (`model confidence != evidence`), do not introduce fabricated
numerical percentages without a defensible model for them — prefer
explainable typed evidence state over cosmetic scores, exactly as the
existing claim-calibration and goal-explanation types already do.

**E. Research saturation / evidence saturation / epistemic completeness**
— `[ ]`, name not yet committed. A future concept where research may
continue while new searches still yield meaningful information gain, and
approach completion when new searches mostly rediscover already-known
evidence, no new independent source or contradiction appears, and major
claims already have adequate independent support or clearly recorded
uncertainty. "All sources found" is explicitly not a valid claim this
concept could ever produce; it must reason in terms of practical,
bounded diminishing-return signals over the evidence this run has
actually gathered, never global/exhaustive coverage. This is a genuinely
new evaluation concept — no existing type computes anything like it
today — and depends on (B) and (C) above being real before "saturation"
can mean anything beyond "ran out of budget."

**F. Internal budget stays a safety rail, not the epistemic definition of
"done"** — `[ ]` as a product-terminology/framing direction, not a
technical change. `ResearchAutonomyBudget`/`ResearchExecutionAllowance`
(Phase 3, `[x]`, unchanged by this direction) remain exactly the
fail-safe resource limits they are today — this direction does not
propose removing or weakening them. It proposes that user-facing framing
increasingly prefer understandable terms (research progress, evidence
coverage, remaining uncertainty) over exposing raw budget/authority
counters as if exhausting them meant a question was answered. Consuming
a budget must never be presented as, or conflated with, reaching truth.

None of A–F is scoped, authorized, or started. A is explicitly blocked on
a human authority-policy decision per this file's stop-condition
discipline; B, C and E require their own separate design/scoping passes
before any implementation; D and F are the closest to being incremental
extensions of already-existing, already-reviewed capability.

## Phase 7 — Runtime hardening

Persistence/concurrency:

- [x] Atomic state writes (**re-corrected 2026-09-22**: closed by
      v0.3.397/v0.3.398, after the v0.3.395 basis above was written. All 12
      `JsonFile*Store` classes with a temp-file-then-`os.replace` save path
      now have a direct fault-injection test proving a genuine mid-write
      failure — real partial bytes physically written before the fault —
      leaves the destination byte-for-byte unchanged with no leftover
      temporary file, and that a nested cleanup failure still raises
      `ResearchError` with its cause chain intact, never a raw secondary
      `OSError` (e.g. `tests/research/test_json_file_research_execution_store.py`,
      plus ten more added in v0.3.398). This closes exactly the gap this
      line used to describe)
- [x] Corrupted/truncated state handling on **load** (**closed, v0.3.404**:
      the mid-write-*failure* case above was already closed; the remaining
      gap — a dedicated test that takes a real, previously-saved document
      and truncates its actual bytes at an arbitrary cut point (reproducing
      what a crash mid-`write()` on a non-atomic path, or a partially
      flushed filesystem, would leave behind) and asserts `load()` refuses
      it — is now closed for all 18 `JsonFile*Store` classes, each with a
      new `test_truncated_valid_prefix_on_load_fails_safely` fault-injection
      test performing a real save-then-truncate-then-load round trip, not a
      hand-written malformed string. Every store was already fail-closed
      before this milestone (no `src/` change was needed); this closes the
      test-fixture gap itself, not a behavior gap. See CHANGELOG.md's
      v0.3.404 entry for the full store list)
- [x] File locking, concurrent-writer prevention (**corrected — was `[ ]`,
      uncredited**): `tests/core/test_exclusive_store_ownership.py` spawns
      real OS subprocesses, takes a kernel-level file lock, and proves a
      second process is refused, the refused process leaves the store
      byte-for-byte untouched, and killing the owner frees the lock
- [x] Concurrent-reader safety (in-process race coverage) — (**corrected**):
      `tests/research/test_concurrent_execution_state.py::OnlyOneAttemptCanStartTests`
      proves two concurrent advances produce exactly one provider call,
      charged once
- [ ] State-version conflicts (beyond the schema-version-load cases already tested)
- [x] Duplicate-execution prevention, idempotency keys — same test as above
      plus `tests/research/test_one_shot_deferred_execution.py`
- [ ] Formally define at-most-once vs. exactly-once semantics as a
      document (the behavior is consistently at-most-once in practice; it
      is not written down as a cross-cutting rule anywhere)

Cancellation/interruption — **re-corrected 2026-09-22: this section's
"confirmed absent" language was wrong.** Direct re-inspection
(hypatia-runtime) found substantial, tested cancellation and timeout
mechanics already implemented, some predating the v0.3.395 basis:

- [x] Mission/step cancellation — two complementary mechanisms exist.
      `ResearchPlanExecutionApplicationService.process_cancel` (Brain
      intent `research_plan_execution_cancel`) is an explicit compare-and-
      set state transition, keyed by execution ID so it reaches a running
      attempt regardless of whether foreground, background-scheduled, or
      deferred work is driving it; a cooperative
      `src/core/CancellationSignal.py` `CancellationToken.is_cancelled()`
      is additionally checked at explicit safe checkpoints across 13 step
      operations plus the autonomy/background-scheduler loop-continuation
      gates. Graceful cancellation preserves already-completed step
      history (`ResearchPlanExecutionState.cancel()` cancels only
      non-terminal steps).
- [x] Model/network/tool timeout — real, per-request, already enforced:
      LLM chat completion (`UrllibChatCompletionTransport.py`,
      `DEFAULT_TIMEOUT_SECONDS = 30.0`, `LOCAL_DEFAULT_TIMEOUT_SECONDS =
      300.0`), source-fetch HTTPS (`HttpResearchSourceFetcher.py`,
      10s default, with `PinnedHttpsTransport`'s `PinnedHttpsConnection`
      additionally enforcing a deadline across the DNS/TCP/TLS handshake
      phases), and Kali/WSL subprocess operations
      (`WslKaliOperationProcessAdapter.py`, `subprocess.run(timeout=...)`,
      `MAX_KALI_OPERATION_TIMEOUT_SECONDS = 30.0` ceiling, `TimeoutExpired`
      caught and reported rather than propagating unbounded). No call site
      was found that can hang indefinitely with zero timeout.
- [x] `cancelled != failed` — directly proven:
      `tests/research/test_research_plan_execution_state.py::test_cancel_preserves_finished_steps_and_cancels_the_rest`
      (a completed step stays `COMPLETED` after cancel; execution status is
      `CANCELLED`, never `FAILED`), and
      `tests/research/test_concurrent_execution_state.py::test_a_failing_provider_cannot_overwrite_it_either`
      (even when the in-flight provider call fails *after* a cancel lands,
      the durable record stays `CANCELLED`, not `FAILED`).
- [x] `interrupted != failed` — `ResearchPlanExecutionSnapshot.restored()`
      turns a `RUNNING` step into `INTERRUPTED` on restart, never
      `COMPLETED`; `INTERRUPTED` is a distinct, non-terminal status from
      both `CANCELLED` and `FAILED`. Proven by
      `tests/research/test_research_plan_execution_snapshot.py` (`test_running_step_restores_as_interrupted_never_completed`,
      `test_completed_step_stays_completed`, `test_terminal_execution_stays_terminal`,
      `test_blocked_and_interrupted_are_distinct_and_non_terminal`).
- [ ] Hung-process detection, child-process cleanup, WSL process cleanup —
      **narrower than this line implies**: Kali operations are already
      bounded by the 30s ceiling above either way (no unbounded hang), so
      this is a resource-cleanup hygiene gap, not an availability/
      correctness one. The specific residual: `WslKaliOperationProcessAdapter`
      terminates the Windows-side `wsl.exe` launcher process on timeout,
      but nothing in this codebase verifies that reliably tears down the
      invoked command's process tree inside the WSL guest itself (no
      process-group kill inside the Linux namespace, no test asserting
      orphaned in-VM processes are reaped).

Errors — confirmed still absent as a unified taxonomy (re-checked
2026-09-22; individual typed errors like `ResearchError` exist per-domain,
plus narrow purpose-built enums like `ToolFailureKind`,
`ResearchPlanExecutionStatus`/`ResearchPlanStepStatus`,
`AutonomyStopReason` — none is a cross-cutting error-code space):

- [ ] Scope / authority / budget / policy-refusal / network-DNS-TLS / tool /
      model / evidence-insufficiency / persistence-corruption /
      timeout-cancellation-interruption / internal-invariant-violation
      error taxonomy (**sizing note, 2026-09-22**: an additive-only version
      — a new optional `code` field, default `None`, no raise site touched
      — would be small and safe but decorative, since nothing would
      populate or consume it; a version that is actually useful would need
      to touch a large fraction of the ~2,300 `raise ResearchError(...)`
      sites across the ~598 files that import `core.Exceptions`. Neither
      shape is a bounded single milestone)
- [ ] Machine-readable error codes

## Phase 8 — Schema / configuration / secrets

Unchanged from prior state — all confirmed `[ ]`, no contradicting evidence found.

- [ ] Unified migration framework, observation migration, run-store
      migration, memory migration, authorization migration
- [ ] Legacy compatibility, future-schema fail-closed, migration rollback strategy
- [ ] Typed configuration, startup validation, environment-variable schema,
      invalid config fails closed, feature flags, explicit dangerous-capability
      opt-ins, mission config snapshot, config provenance
- [ ] OS secret-store integration, credential references, credential
      scope, expiry/revocation, credential-use audit, secret redaction in
      logs/context/exceptions, credential rotation

## Phase 9 — Tool / capability platform

v0.3.453 delivered the first bounded slice — a descriptive foundation only,
not the platform: `tools.ProductCapabilityCatalog`, an immutable,
identity-keyed index describing capabilities that already exist, built by
projecting two already-authoritative sources rather than re-declaring
either's rules. Local-tool records read a real `ToolRegistry`'s own
registered `ToolDescriptor`s directly (capability, effects, read-only/
reaches-outside), so a tool absent from a given runtime composition is
correctly absent from the catalog, not silently assumed. Kali operation
records are built from existing named constants
(`EXPECTED_DIG_VERSION_PREFIX`, `EXPECTED_CURL_VERSION_PREFIX`,
`MAX_KALI_OPERATION_TIMEOUT_SECONDS`) and the existing
`ResearchKaliOperationKind`/`ResearchKaliCommandTransport` enums, covering
only the three kind/transport pairs a real production process adapter
actually accepts today (`DNS_RECORD_LOOKUP` over both transports;
`HTTPS_HEADER_LOOKUP` over `WSL_KALI` only — `VmwareKaliOperationProcessAdapter`
accepts no other plan, so `HTTPS_HEADER_LOOKUP` over `VMWARE_KALI` is
correctly absent rather than claimed). `CAPABILITY REGISTERED !=
CAPABILITY PERMITTED` throughout: the catalog has no execute, invoke,
authorize, grant, or consume method of any kind (asserted structurally, so
no caller could reach one that does not exist), construction and lookup
touch no process or network, entries are frozen, duplicate/unknown
identities both fail deterministically, and none of the three new modules
import anything that could carry chat, model, or request content. Not yet
wired into Bootstrap, `CognitiveEngine`, chat, or the desktop — this
milestone gave the registry something to describe, deliberately not yet
a caller to grant anything to. v0.3.454 added the second bounded slice —
pure capability version-drift *assessment*, still not live version
*discovery*: `tools.assess_capability_version(record, observation)`
compares an already-supplied, bounded, untrusted
`ProductCapabilityVersionObservation` against the same
`ProductCapabilityRecord.version` field v0.3.453 already carried, which
required no change at all — it already held exactly the authoritative
expected-prefix fact (`"DiG 9."`/`"curl "`, or `None` where no rule
exists) this milestone needed. The comparison reuses the one
version-check semantic that already existed in the repository (plain
substring containment, as `WslKaliRuntimeProbe`/
`SshVMwareKaliGuestReadinessProbe` already perform) rather than inventing
SemVer `>=`/`<=` comparison the codebase has never had. `VERSION
COMPATIBILITY != EXECUTION AUTHORITY`: the function is pure (no process,
network, or registry-mutation path of any kind), a capability with no
version rule reports `NOT_APPLICABLE` rather than fabricating one, and
`reason` is always one of four fixed, code-owned sentences, never text
built from the untrusted observation — proven against ten adversarial
observed-version strings (shell metacharacters, a fake `--upgrade`
option, literal `ALLOW`/`REQUIRE_APPROVAL` text, a fake system
instruction) that all remain inert data. Not wired into `Bootstrap`,
`ToolExecutionService`, `KaliToolGateway`, chat, or the desktop. The
remaining Phase 9 items — a policy engine, input/output schemas, live
version *discovery* (actually running a tool to find its version, out of
scope for both v0.3.453 and v0.3.454), a live availability *check* rather
than a descriptive reference, cost estimation — remain separate,
unstarted, future milestones.

- [x] v0.3.453 — typed tool/capability identity, human-readable name,
      category, network/credential/target-scope/destructive classification,
      version/timeout/retry where already authoritative (absent otherwise),
      availability *reference* (descriptive text, not a live check),
      capability != permission (proven structurally, not merely asserted)
- [x] v0.3.454 — pure version-drift *assessment* against an already-supplied
      observation (`MATCH`/`DRIFT`/`UNKNOWN`/`NOT_APPLICABLE`), reusing the
      existing prefix-containment semantic; version compatibility !=
      execution authority (proven structurally); no live discovery
- [ ] Input/output schemas, a policy engine any of this can be checked
      against, live tool-version *discovery*, a live availability check,
      cost estimate
- [ ] Filesystem/network restrictions, process allowlist, working-directory
      isolation, environment sanitization, resource limits, no shell
      interpolation by default, typed argv, WSL boundary controls,
      container isolation where useful

## Phase 10 — Observability / explainability / operator UX

Unchanged — confirmed absent as formal capabilities.

- [ ] Structured logs, mission/run IDs, step timeline, tool-call timeline,
      authority-decision log, budget log, retry/recovery log, provenance
      event log, sensitive-data redaction, crash diagnostic bundle,
      performance/model/tool latency metrics
- [ ] "Why this plan/step/source/tool?", "why refused/retried?", "why did
      the mission stop?", "what remains unresolved?", observation vs.
      inference, verified vs. assumed, replanning diff
- [ ] Approval inbox, exact requested scope/authority/budget, side-effect
      preview, authority diff, approve-once, reject, modify proposal,
      pause/resume/cancel, operator-decision provenance

## Phase 11 — Memory / knowledge / learning

- [x] v0.3.446 ordinary conversation grounding in accepted local knowledge:
      conservative lexical coverage, bounded untrusted excerpts, deterministic
      citations, and restart restoration. No autonomous research/tool execution;
      interactive BSCP teaching remains outside this milestone.
- [x] Basic user memory, mission-state persistence, observation history
- [x] Learning remains advisory-only — `FailureMemoryAdvisor.py`,
      `ResearchFailureLessonDeriver.py`
- [x] Failed attempt != universal inability — `FailureLessonKind.py` and
      advisory-recall tests

- [ ] Episodic mission memory, strategy memory, verified security-knowledge
      memory, memory provenance, memory confidence, staleness,
      retention/deletion governance
- [ ] Observation time / knowledge time / source publication time /
      validity window / staleness / superseded / contradicted /
      unknown-currentness / revalidation recommendation / knowledge lineage
- [ ] Failure -> improved bounded strategy, verified lesson extraction,
      confidence decay, transferable PortSwigger/HTB/THM/CTF learning, lab
      knowledge != real-world fact

## Phase 12 — Prompt-injection / untrusted-content defense

**Groundwork note (do not read as a completed capability):** a formal
prompt-injection firewall does not exist, and every item below correctly
stays `[ ]`. However, real, tested, informal groundwork already exists in
the LLM proposal-provider layer: `LLMSemanticEvidenceProposalProvider.py`,
`LLMSemanticComparisonProposalProvider.py`, and
`LLMResearchClaimContradictionProposalProvider.py` all (a) prefix fetched
source content with a literal `UNTRUSTED_DATA` marker, (b) carry an
explicit system instruction that the source is data, not instructions, and
that embedded commands must be ignored, and (c) — the strongest control —
require every evidence "quote" to be an exact, unique substring of the
fetched source, so the model cannot fabricate authority-bearing text and
pass it off as evidence. The known residual gap: the free-text `rationale`
field is not checked against source content, so a poisoned document could
still steer wording (not fabricate quotes), and none of this output is
treated as instruction anywhere downstream — it is evidence for human
review only. Any future Phase 12 work should build on this pattern rather
than starting from nothing, and any LLM participation added to Evaluate ->
Adapt in a later milestone must inherit this same discipline.

- [ ] External content treated as untrusted data (formal capability)
- [ ] Source cannot redefine system instructions (formal capability)
- [ ] Document cannot grant authority
- [ ] Tool output cannot grant authority
- [ ] Source cannot expand scope
- [ ] Source cannot request credential disclosure
- [ ] Prompt-injection detection/firewall
- [ ] Instruction/data separation (as a named, tested, cross-cutting capability)
- [ ] Poisoned-document tests, poisoned web/feed tests, indirect-injection tests
- [ ] Injection audit/provenance

## Phase 13 — CVE / security intelligence

Unchanged — confirmed not started at the product level (an `Nvd*` source
provider exists for research source discovery, which is not the same as
this phase's normalize/deduplicate/correlate/prioritize product).

- [ ] NVD, CISA KEV, GitHub Security Advisories, vendor advisories, CERT sources
- [ ] Normalize, deduplicate, correlate, product/version ranges, remediation
- [ ] Exploit available != confirmed exploitation, source independence,
      provenance, no fabricated CVSS, CVE finding states, product-specific
      prioritization

Do not start CVE Intelligence merely because it is exciting. The runtime,
evaluate/adapt, authority, provenance, and safety foundation must be ready first.

## Phase 14 — Scheduler / Sentinel

Unchanged — confirmed not started as a live product capability (`TrustedOneShotDeferredExecutionScheduler`
covers a single durable one-time attempt, not recurring scheduling; the
`src/modules/sentinel` directory is orphaned scaffold, not wired).

- [ ] Scheduled missions, recurring missions, delayed jobs, job queue,
      priorities, concurrency limits, restart persistence, duplicate
      prevention, schedule != permission, authority-expiry handling
- [ ] Source monitoring, meaningful-change detection, cosmetic vs. material
      changes, scheduled revalidation, CVE/vendor monitoring,
      exploit-intelligence changes, alerts, budget-aware continuous monitoring

## Phase 15 — Security reasoning

Unchanged — confirmed not started as a product capability.

- [ ] SQL injection, authentication, access control/IDOR, business logic,
      SSRF, XXE, SSTI, command injection, file upload, XSS, CSRF, OAuth,
      JWT, race conditions, request smuggling, deserialization, API/GraphQL
- [ ] Hypothesis -> evidence -> verification, false-positive reduction
- [ ] Repository ingestion, exact file/line evidence, data-flow reasoning,
      source->sink reasoning, authentication/authorization review,
      injection review, SSRF review, secrets review, crypto misuse,
      deserialization review, verified findings, remediation

## Phase 16 — Attack surface / security hypotheses

Unchanged — confirmed not started.

- [ ] Assets, hosts/IPs, domains, services, URLs/routes/APIs, identities,
      technologies, credential references, trust boundaries, findings,
      observations, relationships, canonical target identity
- [ ] Hypothesis state, required evidence, verification plan,
      disconfirmation, prioritization, unknown-unknown discovery,
      confidence != evidence, hypothesis != finding

## Phase 17 — Authorized pentest agent

- [ ] Authorized lab/CTF/owned/explicitly approved targets only
- [ ] Recon, enumeration, vulnerability hypotheses, verification, evidence
      collection, finding creation, reporting
- [ ] Tool allowlists, per-action authority, credential boundaries,
      destructive-action boundaries, scope-escape prevention (**partial,
      v0.3.406**: an explicit `IN_SCOPE`/`OUT_OF_SCOPE`/`UNCERTAIN` tri-state
      read, `ResearchTargetScope.resolve_hostname`/`resolve_addresses`, now
      makes the difference between an explicitly excluded target and a
      target no rule addresses legible and testable, over the pre-existing
      `ResearchTargetScope`/`ResearchProgramScopeRevision`/
      `ResearchProgramScopeEnrollmentService` scope backbone; this is a
      read-only explanatory addition, not the tool-allowlist/credential-
      boundary/destructive-action-boundary framework the rest of this line
      still needs, so the compound box stays unchecked), recovery, replay
      safety
- [-] Unrestricted autonomous pentesting

### Bug Bounty Researcher: bounded roadmap direction (recorded 2026-09-23,
product-direction only — not scoped as a whole, not authorized as a whole,
not started beyond the one delivered step named below)

This is long-term product direction for Phase 16/17, not a locked
milestone. It gives Hypatia's future bug-bounty-research capability a
concrete, dependency-ordered shape so later milestones have a known next
step instead of re-deriving priority from scratch each time. Locking any
one step below into an actual milestone still requires the same
repository-grounded discovery, scope lock, and review discipline every
other milestone in this document has used — this list is not permission to
skip that.

Recorded priority order (each item depends on the ones above it being
real, not merely named):

1. Asset Inventory + canonical asset identity
2. Recon Result Ingestion / normalization
3. HTTP Evidence model
4. Authentication / identity / session contexts
5. Credential + secret boundary
6. Security Hypothesis model
7. Finding lifecycle
8. Business-logic/state-transition model
9. Validation recipes
10. False-positive / root-cause correlation
11. Safe capability-based tool gateway
12. PII/sensitive-data guard
13. Impact reasoning
14. Report composer + validator
15. Evaluation harness
16. Bounty-session checkpoint/resume
17. Companion / Teaching / available-time modes
18. Bounded Bug Bounty Research Session
19. Evidence saturation / stopping reasoning

**Delivered so far**: v0.3.406 — explicit tri-state target-scope
resolution (`ResearchTargetScopeResolutionStatus`/
`ResearchTargetScopeResolution`), a foundation step underneath item 1
(canonical asset identity needs an unambiguous in/out/uncertain scope read
before an asset inventory can attach real authority to anything it
records) rather than item 1 itself. `require_hostname`/`require_addresses`
remain the only real enforcement gates; the tri-state read is additive and
explanatory only, and was independently security-reviewed to confirm no
path lets `UNCERTAIN` or a bare `IN_SCOPE` read reach an active action.
v0.3.407 delivered item 1, Asset Inventory + canonical asset identity
(`ResearchAssetKind`/`ResearchAssetProvenanceKind`/`ResearchAssetRelationKind`,
append-only observation/relation records, a derived-only `ResearchAsset`
projection). v0.3.408 delivered item 2, Recon Result Ingestion /
normalization, teaching the Asset Inventory to honestly attribute one
already-completed, already-authorized `DNS_RECORD_LOOKUP` Kali operation
result via a new `KALI_OPERATION_RESULT` provenance kind bound 1:1 to a
`source_operation_digest`. v0.3.409 delivered item 3, the HTTP Evidence
model: a new, narrowly-scoped `ResearchHttpEvidenceRecord` consuming one
already-completed, already-authorized `HTTPS_HEADER_LOOKUP` operation
result, with a deterministic content-derived `evidence_id` making
replay-safety structural and a live, never-cached scope-resolution view
threaded through every read. v0.3.410 delivered item 4's descriptive
foundation: an append-only, operator-authored `ResearchSessionContextRecord`
can label already-recorded same-program HTTP evidence as historically
unauthenticated or authenticated under a human-readable identity label. The
record is inert history, contains no credential or reusable live session, and
cannot perform a login/request or create authority; credential and secret
boundaries remain item 5. v0.3.411 delivered item 5's first conservative
secret-ingress boundary: high-confidence secret-bearing forms are classified
into fixed categories and refused before an operator-authored session context
can be persisted, without reflecting the candidate value. It is explicitly a
floor rather than complete secret detection and adds no secret storage,
credential reference/use, login, or authority. In every case, ingestion can
only ever reach
scope resolution through the existing, unchanged, live `resolve_hostname`/
`resolve_addresses`, and no path lets discovered evidence manufacture
authority. v0.3.415 delivered item 6, the Security Hypothesis model
foundation (`ResearchSecurityHypothesisRecord`, append-only evidence-link
and status-transition records, a derived-only `ResearchSecurityHypothesis`
projection) — reasoning over already-recorded evidence only, never itself
authority to act. v0.3.416 delivered item 7, the Finding Lifecycle
foundation on top of it, with the identical append-only/derived-read shape.
v0.3.417-v0.3.419 hardened both lines' evidence-integrity and
subject-binding guarantees (evidence cited in support of, contradiction of,
or — critically — validation of a hypothesis or finding must actually
describe that hypothesis's/finding's own subject, every citation in one
call must match, and a finding's carried-forward evidence is independently
re-verified against the live evidence store at creation), without ever
widening what a `VALIDATED` status means: it remains evidence-backed
reasoning, never a confirmed exploit or authority to act. v0.3.420 closed
part of the F4 lifecycle-replay gap those same milestones had all
deferred: both stores now replay each entity's status-transition history
against the closed state-machine table at load time, and the Finding store
also rejects a dangling or self-referencing duplicate/superseded-by
reference at load — hardening (Bug Bounty foundation, steps 6/7 made more
tamper-resistant), not a new numbered item. v0.3.421 delivered item 9's
foundation, Validation recipes: an operator-authored, append-only, purely
descriptive `ResearchSecurityValidationRecipeRecord` — an ordered list of
plain-text steps plus notes — attached to an already-recorded hypothesis or
finding for the same program, verified through the same cross-service-reader
pattern the Finding service already uses for its source hypothesis.
Recording a recipe never fetches, runs, authorizes anything, or mutates its
subject. v0.3.423 added the Validation Recipe desktop tab (pure UI layer,
no service change). v0.3.424 delivered "Reproduction record": an
operator's own observation of manually following a recorded recipe —
REPRODUCTION RECORD != EXECUTION AUTHORITY, and no outcome (including
`REPRODUCED`) asserts a confirmed vulnerability; no desktop panel yet.
v0.3.425 closed the remaining "full F4" cross-store gaps: a finding's
source hypothesis and evidence citations are now verified to exist (and
match subject) in their own separately-loadable stores at startup, no two
findings may share one source hypothesis, and a `VALIDATED` finding must
have at least one `VALIDATES` evidence link ever recorded — all replayed
by one pure `research`-layer function called once eagerly at `Bootstrap`
startup, not duplicated write-path logic. Deliberately not replayed,
because it is not provable from persisted, non-interleaved append-only
history: a hypothesis's status *at the exact moment* its finding was
created, and whether a `CONTRADICTS` link predates a `VALIDATED`
transition. v0.3.426 added the first piece of derived epistemic visibility
on top of that closed gap: `ResearchSecurityFinding.needs_attention`, a
pure, read-only property naming exactly the current-state tension a
reader could otherwise only notice by comparing two separately-printed
numbers — `status` currently `VALIDATED` while `contradicting_evidence`
is currently non-empty — surfaced in every finding response and the
desktop panel. It is deliberately narrower than the "not replayed"
history questions named above: a live derived read can honestly say "this
is true right now" without needing to prove *when* it became true, which
is exactly why replay (at load time, fail-closed for the whole
application) could not safely make the equivalent claim.
`CONTRADICTING EVIDENCE != AUTOMATIC REFUTATION` — no status changes, no
confidence score or number was introduced, and findings still have no
confidence field of any kind (the general-research `ResearchClaimConfidence`/
`ResearchClaimCalibrator` machinery was investigated and found not
mechanically reusable here: findings have no authored-confidence field to
calibrate, and finding evidence links carry no trust/independence
dimension, unlike `ResearchSourceAssessmentRecord`). v0.3.427 built the
join `ResearchReproductionRecord` was missing: a finding's preview now
also shows its currently-associated reproduction history, joined live via
`finding_id -> recipe(subject_kind=FINDING, subject_id=finding_id) ->
reproductions(recipe_id)`, reusing an already-existing, already-tested
read (`ResearchReproductionApplicationService.reproductions_for_subject`)
rather than new business logic. Composed one layer up in `CognitiveEngine`
specifically to avoid giving `ResearchSecurityFindingApplicationService` a
reverse dependency on the Reproduction service (which already depends on
it, the opposite direction) — `ResearchSecurityFindingApplicationService`
itself has zero diff. `REPRODUCTION RECORD != EXECUTION AUTHORITY` and
`REPRODUCED != CONFIRMED VULNERABILITY` both hold exactly as before:
`finding.status`/`needs_attention` are read, never written, by this
visibility. v0.3.428 closed the remaining M1 gap: `ResearchSecurityFinding
.evidence_ceiling`, a pure, read-only `ResearchSecurityFindingEvidenceCeiling`
(`UNASSESSED`/`LOW`/`MEDIUM`/`HIGH`) naming what the recorded evidence
*structure* can defensibly support — presence/absence of `SUPPORTS`/
`VALIDATES`/`CONTRADICTS` links plus `REFUTED` status, never a probability.
Deliberately a separate type from `ResearchClaimConfidence` (only the
*pattern* — contradiction collapses confidence — is reused, never the
code), because finding evidence links carry no `ResearchInformationTrust`/
`ResearchSourceIndependence`-equivalent dimension. `HIGH` is declared but
permanently unreachable today: reaching it would require an independence/
trust judgement over cited evidence that this record does not carry — a
future, separate milestone's concern (richer per-citation evidence
quality), not something this one could honestly invent. `MODEL CONFIDENCE
!= EVIDENCE` throughout: the ceiling reads no free-text field and no
Reproduction Record outcome. v0.3.449 laid transport-architecture
foundation underneath the already-delivered Kali execution surface, not a
new numbered item: a second, explicit
`ResearchKaliCommandTransport.VMWARE_KALI` identity alongside the existing
`WSL_KALI`, bound into the existing operation-preview digest so an
authorization recorded for one transport can never be replayed against the
other, plus a wholly separate VMware **host-only** readiness contract
(`vmrun -T ws list`, read-only; a local `.vmx` identity-match text read;
never a guest login, guest credential, guest command or VM power-state
change). `TRANSPORT AVAILABILITY != EXECUTION AUTHORITY`, `HOST READY !=
GUEST READY`: nothing in this milestone runs a Kali operation through
VMware, adds a new operation kind, or widens the Kali tool catalogue: zero
target traffic, zero guest execution. Real VMware-backed `DNS_RECORD_LOOKUP`
execution (item 11-adjacent: the gateway dispatching to a second, equally
reviewed transport) remains a distinct, separately-authorized future
milestone. v0.3.450 took the next step of that deferred future milestone,
still not real execution: a VMware **guest** readiness boundary verifying,
only once host readiness is already `HOST_READY`, whether the one fixed,
networkless command `/usr/bin/dig -v` is reachable inside the Kali guest.
Read-only inspection of this host's real `vmrun.exe` usage text confirmed
its guest-authentication flags (`-gu`/`-gp`) require the guest password as
a plaintext command-line argument -- rejected as a production credential
transport, since that would place a secret in process argv visible to any
other process able to list command lines. Restricted SSH was chosen
instead: key-based authentication only, a pinned host key
(`StrictHostKeyChecking=yes` against a dedicated known_hosts file),
password/keyboard-interactive authentication disabled, no agent or port
forwarding, no pseudo-terminal, and the remote command is a module-level
constant with no parameter that could substitute a different executable or
argument. `GUEST READY != EXECUTION AUTHORITY`: the readiness report's own
`kali_operation_authorization_created` field is structurally pinned
`False`, and nothing in this milestone wires the guest probe into
`KaliToolGateway` or any other real-dispatch path. On this development
machine the Kali VM was confirmed powered off (read-only `vmrun list`,
never a power action) throughout, so live guest execution was not
verified; the dedicated SSH key, pinned host-key entry and minimum-
privilege guest account this boundary requires do not exist yet either --
deliberately not created automatically, reported as a user-setup blocker
instead. Real VMware-backed `DNS_RECORD_LOOKUP` execution remains a
distinct, separately-authorized future milestone.

v0.3.451 narrows guest-readiness failure classification: exit 126 means
`TOOL_UNEXECUTABLE`, 127 means `TOOL_MISSING`; SSH publickey rejection
requires exit 255 and a complete endpoint-specific OpenSSH stderr line.
Generic permission errors do not imply authentication failure. This is
diagnostic hardening only: zero target traffic, no live guest probe, no VM
power mutation, no credential setup and no new execution authority.

v0.3.452 took the deferred step those milestones set up for: the existing,
already-reviewed `DNS_RECORD_LOOKUP` operation now actually executes over
`ResearchKaliCommandTransport.VMWARE_KALI`, through the same single
`KaliToolGateway` authority chain WSL already used -- no second dispatch
path, no new operation kind, no widened tool catalogue. A new
`VmwareKaliRuntimeProbe` composes the unchanged v0.3.449/450 host- and
guest-readiness contracts behind the existing `ResearchKaliRuntimeProbe`
interface; a new `VmwareKaliOperationProcessAdapter` runs only the one
reviewed `dig +time=5 +tries=1 +short <hostname> <A|AAAA|CNAME>` argv plan
over the same restricted, key-only, host-key-pinned SSH flags the guest
probe already used, never `vmrun -gu`/`-gp`. The adapter structurally
re-validates the exact argv shape (fixed options, allowed record types,
and a hostname-grammar re-check mirroring -- never relaxing -- the
authoritative `ResearchTargetScope` grammar) before any subprocess starts,
closing the specific risk that OpenSSH joins remote arguments unquoted for
the guest shell to parse. `TRANSPORT AVAILABLE != EXECUTION AUTHORITY`
gained a second concrete form: transport is trusted, code-owned Bootstrap
configuration (`HYPATIA_KALI_OPERATION_TRANSPORT`, strict `wsl_kali`/
`vmware_kali` allowlist, fails closed on anything else), never request
metadata, model output or chat text, and is bound into the existing
operation digest -- changing transport changes the digest, so an
authorization for one transport can never run the other. Production
bootstrap installs the VMware execution pair only when execution,
host-readiness and guest-readiness opt-ins and complete trusted VMware
configuration are *all* present; any one missing leaves VMware execution
unavailable rather than silently substituting WSL or a partial VMware
path. On this development machine the Kali VM was confirmed running
(read-only `vmrun list`, no power action), but no dedicated, pinned
Hypatia guest SSH key/known_hosts pair exists -- only the operator's own
personal key does, which this boundary must not reuse -- so real live DNS
execution remains a reported blocker, not a workaround; zero target
traffic occurred. v0.3.453+ (HTTPS over VMware, or any new Kali tool)
remains separately authorized and unstarted.

With this, every leg of M1's target lifecycle (Finding -> Evidence ->
Validation -> Confidence -> Contradiction -> Final State) now has a
repository-grounded, defensible treatment: Evidence (v0.3.416-419),
Validation (the `_require_validation_gate`/cross-store replay chain,
v0.3.416-425), Confidence (v0.3.428, capped at what current evidence can
honestly support), Contradiction (v0.3.417-420/425/426), and Final State
(the closed status transition table and terminal-state set, unchanged
since v0.3.416). **M1 — Finding Lifecycle Closure is considered complete**
as of v0.3.428, with the explicit, permanent caveat that `evidence_ceiling`
stays capped below `HIGH` until a later, separate milestone gives finding
evidence its own trust/independence dimension — that is new scope, not an
M1 shortfall. Item 8 (Business-logic/state-transition model, which has no
existing precedent or design in this codebase) remains not yet started and
is the natural next candidate, belonging to M2 rather than M1.

v0.3.429 delivered one narrow, self-contained foundation piece underneath
item 8 — not item 8 itself, which remains a substantially larger,
still-unscoped undertaking. The existing `ResearchPlanExecutionState`
machine gained a durable, non-authoritative way to name exactly which
authority a paused step is missing: `research
.ResearchAuthorityRequirementKind` (closed `StrEnum`, one member today,
`PLAN_AUTHORIZATION`) and `research.ResearchPlanExecutionAuthorityPause`
(step, requirement kind, plan digest, research run, detail), modeled
parallel to the already-shipped `advance_refusal_*` mechanism rather than
as a new terminal execution status, cleared only when the exact named
step successfully starts and never by presenting any authorization,
correct or not. M2 as a whole remains unscoped: this milestone is a
foundation step, not a claim that any numbered roadmap item is complete.

v0.3.430 was originally scoped as binding a second
`ResearchAuthorityRequirementKind` member — `DeferredExecutionGrant` or
`ResearchKaliOperationAuthorization` — into that same `authority_pause`
mechanism. Repository-grounded audit found neither candidate has a
legitimate integration point with it: Kali operations carry no
execution/step/plan-digest binding and are not even a
`ResearchPlanStepCapability` member, so there is no plan step for a
pause to attach to; `DeferredExecutionGrant`'s own authorization check
runs one layer above `ResearchPlanExecutionApplicationService
.process_advance`, as a scheduler-level precondition with no existing
cross-layer signal to hook into without inventing an artificial flag or
breaking `ResearchPlanExecutionApplicationService`'s sole ownership of
execution state. Forcing either in would have been exactly the kind of
fabricated, non-reachable feature this process exists to refuse. The
milestone was redirected instead to a different, real gap the same
audit surfaced: of Hypatia's three named authority domains
(`ResearchPlanAuthorization`, `ResearchKaliOperationAuthorization`,
`DeferredExecutionGrant`), only `DeferredExecutionGrant` — the one
authorizing fully *unattended* execution, arguably the highest-stakes
case since no human is present when it fires — carried no expiry at
all. `DeferredExecutionGrant.expires_at` (a derived property of
`granted_at`, never a stored field) and a matching check inserted at
`TrustedOneShotDeferredExecutionScheduler.fire` (the actual trigger for
unattended execution, not merely its decision-helper) close that gap.
Item 8 itself, and the rest of M2, remain exactly as unscoped as before.

v0.3.431 hardened both prior steps rather than extending M2's own scope:
`cancel()`/`block_step()`'s already-identified stale-pause bug (v0.3.429's
own QA observation) turned out, under independent review, to also apply
to `fail_step()` and one of `resolve_interrupted_step()`'s two routes to
`BLOCKED` — all four now clear `authority_pause`/`advance_refusal_*`
unconditionally on their existing terminal/blocked transition. Separately,
the expired-`DeferredExecutionGrant` UX gap (an expired-but-not-revoked
grant blocking a fresh one) is closed: a verified renewal is now let
through, the old grant retired under its own honest provenance
(`DeferredGrantAuthorizer.SUPERSEDED_BY_RENEWAL`) rather than reusing the
human-operator one. Neither fix touches item 8 or widens M2's scope.

**Companion product principle** (preserve for future UI/roadmap work):
Hypatia is intended to be both a bounded security research partner and a
teaching/companion assistant for the operator. Personality and
conversation must remain structurally separate from security authority —
friendly language must never weaken enforcement, and a warm explanation of
a refusal is still a refusal. A future Teaching/Companion mode (item 17
above) should be able to explain what was observed, why it was
interesting, what hypothesis it suggested, what evidence supports or
contradicts it, and how the operator could reproduce the reasoning
manually — none of which is itself authority, exactly as this file's
existing "evaluation creates information, proposal creates strategy, only
explicit authorization creates permission" invariant already requires.
This principle is not implemented by any milestone yet; it is recorded
here so a future Companion/Teaching milestone does not have to rediscover
it from conversation history.

## Phase 18 — Findings / reporting

Unchanged — confirmed not started.

- [ ] Hypothesis, candidate, observed, reproduced, verified, false
      positive, mitigated, retested, closed, reopened
- [ ] Technical report, executive summary, evidence attachments,
      reproduction steps, remediation, evidence-backed severity, CVSS only
      when grounded, Markdown/HTML/PDF export

## Phase 19 — Product UI

Unchanged — confirmed not started as a dedicated dashboard; desktop panels
today (`MissionComparisonReview.py`, `MissionSourceIndependenceReview.py`,
`KaliOperationPanel.py`) cover narrow existing capabilities, not this phase's
scope.

- [ ] Mission dashboard, mission timeline, current state, authority view,
      remaining budget, evidence view, sources view, contradictions view,
      provenance view, findings view, approval queue, failure/recovery
      view, model/capability status, search, export, accessibility

## Phase 20 — Privacy / data governance

Unchanged — confirmed not started.

- [ ] Public/internal/confidential/secret classification, personal-data
      handling, data minimization, model-context minimization, local-only
      missions, cloud-model restrictions, retention rules, mission
      deletion, memory deletion, user-data export, audit-log privacy,
      source licensing metadata

## Phase 21 — Packaging / operations

Unchanged — confirmed not started.

- [ ] Windows installer, signed executable/artifacts, stable/beta/dev
      channels, update checking, user-approved updates, rollback, offline
      install, migration-aware upgrades
- [ ] Mission/memory/knowledge/config export, backup, restore, restore
      validation, corrupted-backup detection

## Phase 22 — Supply chain / self-security

- [x] GitHub Actions pinning (**corrected — was `[ ]`, uncredited**): both
      `.github/workflows/linux-desktop.yml` and `windows-desktop.yml` pin
      `actions/checkout`, `actions/setup-python`, and `actions/upload-artifact`
      to full commit SHAs with version comments.

- [ ] Dependency pinning (`pyproject.toml` declares no `[project.dependencies]`
      block yet — nothing to pin)
- [ ] Dependency vulnerability scanning (`.github/dependabot.yml` exists but
      is empty — a non-functional placeholder, not real coverage)
- [ ] Package provenance, secret scanning, code scanning, SBOM, artifact
      checksums, reproducible builds where practical

Red-team Hypatia itself — unchanged, confirmed not started as a dedicated
test suite (individual SSRF/authorization/digest-tampering behaviors are
covered under Phase 3/5's own tests, but not organized or framed as a
red-team-Hypatia suite):

- [ ] Prompt injection, authority escalation, scope escape, budget bypass,
      replay attacks, digest tampering, state corruption, DNS rebinding,
      SSRF, redirect attacks, poisoned sources/memory/tool output,
      credential exfiltration, path traversal, command injection,
      crash/restart abuse, concurrent-run abuse, jailbreak regression suite

## Phase 23 — Benchmarking / performance

Unchanged — confirmed not started as a formal benchmark suite.

- [ ] Research-quality, authority-boundary, provenance, recovery,
      prompt-injection, security-reasoning, false-positive/negative,
      model-comparison, regression benchmarks, golden fixtures,
      release-to-release quality comparison
- [ ] Large missions, large document corpora, thousands of observations,
      large provenance graphs, database/index strategy, caching with
      provenance, memory-pressure handling, UI responsiveness,
      background-worker isolation

## Phase 24 — Extensibility / internal multi-agent

Unchanged — confirmed not started.

- [ ] Stable plugin API, plugin manifest, declared capabilities/permissions,
      network/credential declarations, plugin sandbox, plugin signing/trust,
      plugin versioning, plugin cannot self-grant authority, plugin provenance
- [ ] Planner/researcher/verifier/security-reviewer/reporter internal
      agents, shared mission state, agent-specific authority, agent
      isolation, no silent authority delegation, agent disagreement
      handling, consensus != truth, independent verification

Important: **the Claude Code software team is not Hypatia's future internal
multi-agent runtime.** Claude agents develop Hypatia. Hypatia's own
multi-agent system would be a later product capability entirely separate
from the development team described in CLAUDE.md.

## Phase 25 — Long-term non-goals for now

- [-] Voice, vision, robotics, smart-home control, general-purpose computer
      administration, unrestricted autonomous internet agent, unrestricted
      autonomous exploitation

Do not prioritize these until the core security AI system is mature. Note:
scaffold source directories for several of these (`src/vision`, `src/voice`,
`src/robotics`, `src/home`, `src/xr`, `src/watch`, `src/mobile`) already
exist in the repository tree but are orphaned — see the scope note above.
Their existence is not a commitment or a head start; it is unused legacy
code from an earlier, broader product direction.

---

## Development infrastructure

Claude software team — all `[x]`, live and in use (see CLAUDE.md for the
operating model):

- [x] hypatia-lead, hypatia-runtime, hypatia-epistemics, hypatia-security,
      hypatia-qa, hypatia-release
- [x] Parallel specialist review, independent security review, independent
      QA, dedicated release flow
- [x] CLAUDE.md development constitution, safety hooks, force-push
      protection, `start_hypatia_team.bat`, Context7 MCP

- [ ] GitHub MCP authentication (`.mcp.json` needs `HYPATIA_GITHUB_MCP_PAT`,
      currently unset in the working shell; the `gh` CLI itself is
      separately authenticated and unaffected)
- [ ] SonarQube when justified
- [ ] Docker MCP when justified
- [ ] CVE-intelligence specialist when Phase 13 begins

Testing/release:

- [x] Restart tests, budget tests, recovery tests, SSRF tests, DNS drift
      tests, authorization/replay tests, provenance tests
- [x] Black, Ruff, MyPy, `git diff --check` — independently reproduced
      clean on HEAD `265ef451a8be` (6,416 tests pass, 3 skipped, 118s)
- [x] Exact-SHA Linux CI, exact-SHA Windows CI
- [x] No automatic merge, no force push, no automatic tags/releases

- [~] Corrupted/truncated persistence tests (**corrected**: broadly
      covered for corrupted/malformed content; true mid-write truncation
      specifically remains untested — see Phase 7)
- [x] Concurrent-writer tests (**corrected — was `[ ]`, uncredited**): see
      Phase 7 / `test_exclusive_store_ownership.py`
- [ ] More outer-boundary tampering tests
- [ ] Security-test organization cleanup (**confirmed accurate**:
      `tests/security/` contains only 2 files, both about Windows-rooted
      path handling; the real security-critical tests — SSRF, DNS/address
      pinning, Kali authorization, exclusive store ownership — live
      scattered across `tests/research`, `tests/cognition`, `tests/core`,
      and `tests/integration`. The directory name is misleading relative to
      its contents; this is real, independent, low-risk cleanup work, not
      gated on Evaluate -> Adapt)

## Default development order

Unless repository evidence establishes a prerequisite or concrete blocker,
prefer this order. This is a preferred sequence, not permission to ignore
repository evidence — a concrete safety or correctness prerequisite may
interrupt it, and a later capability being more impressive is never a
reason to jump forward.

1. ~~Evaluate -> Adapt~~ — **v1 delivered, v0.3.396** (see Phase 6). v2
   (cross-mission revalidation proposal) was investigated 2026-09-22 and
   found to require new cross-mission authority/budget design; it is not a
   queued next step, it is blocked on a human authority decision.
2. Persistence / concurrency / cancellation hardening — **re-scoped down
   further, 2026-09-22**: cancellation/timeout mechanics and mid-write-
   failure atomicity are now both confirmed already implemented and tested
   (see Phase 7). The only remaining residuals are a mid-write-truncation-
   on-*load* test fixture, WSL in-guest process-tree cleanup hygiene on
   Kali timeout, and a formal error taxonomy (confirmed either decorative
   or architecturally large, not a bounded milestone by itself) — none of
   these is substantial enough alone to justify a dedicated milestone; a
   future pass may bundle the two small ones together as maintenance.
3. Tool registry + policy engine — **next candidate direction**: this is
   the first phase-order item without a confirmed-already-done or
   confirmed-blocked status as of 2026-09-22. Note it is authority-adjacent
   (a policy engine's `ALLOW`/`DENY`/`REQUIRE_APPROVAL` primitive is close
   to a new authority-class decision) — starting it should include an
   explicit human check-in on scope before autonomous implementation
   begins, per this constitution's stop conditions.
4. Observability + operator UX
5. Prompt-injection / untrusted-content defense — build on the existing
   `UNTRUSTED_DATA`/verbatim-quote groundwork (Phase 12) rather than
   starting from nothing; any LLM participation added to a future
   Evaluate -> Adapt extension inherits this discipline immediately, not
   only once Phase 12 is formally complete
6. Memory + knowledge lifecycle
7. CVE intelligence
8. Scheduler + Sentinel
9. Security reasoning
10. Security code review
11. Attack-surface model + security hypothesis engine
12. Authorized pentest agent
13. Finding lifecycle + reporting
14. Product UI + packaging + privacy hardening
15. Plugins + Hypatia internal multi-agent system

Independent, low-cost cleanup (e.g. security-test reorganization) may
proceed alongside any phase above without reordering the list — it is not
a prerequisite for, and does not block, product milestones.
