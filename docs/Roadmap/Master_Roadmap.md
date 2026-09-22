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

- [ ] User-facing revalidation workflow
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

- [ ] General typed tool-execution framework (confirmed: only two
      `ResearchKaliOperationKind` values exist repo-wide, no generic dispatcher)

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
- [ ] Corrupted/truncated state handling on **load** (**re-corrected
      2026-09-22**: the mid-write-*failure* case above is now closed; the
      remaining gap is narrower than this line's v0.3.395 wording — a
      dedicated test that takes a real, previously-saved document and
      truncates its actual bytes at an arbitrary cut point (reproducing
      what a crash mid-`write()` on a non-atomic path, or a partially
      flushed filesystem, would leave behind) and asserts `load()` refuses
      it. 10+ JSON stores already have malformed-content-refuses tests
      (e.g. `tests/integration/test_research_execution_restart.py::test_corrupted_store_refuses_rather_than_fabricating_state`)
      and legacy-schema-load tests, and the existing exception-handling
      machinery (blanket `except (UnicodeDecodeError, json.JSONDecodeError)`
      plus required-field validation) very likely already covers this
      case — but the specific truncated-valid-prefix fixture itself is
      confirmed absent across every `JsonFile*Store` test file checked,
      not merely undocumented)
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

Unchanged — confirmed absent; Kali operations remain a narrow, two-kind
mechanism, not a general typed tool registry.

- [ ] Typed tool registry, tool identity/version, input/output schemas,
      required authority/scope, network/credential requirement, side-effect
      classification, destructive/non-destructive classification,
      timeout/retry policy, cost estimate, tool availability check,
      tool-version drift detection, capability != permission
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

Unchanged — confirmed not started.

- [ ] Authorized lab/CTF/owned/explicitly approved targets only
- [ ] Recon, enumeration, vulnerability hypotheses, verification, evidence
      collection, finding creation, reporting
- [ ] Tool allowlists, per-action authority, credential boundaries,
      destructive-action boundaries, scope-escape prevention, recovery,
      replay safety
- [-] Unrestricted autonomous pentesting

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
