# Master checklist — repository reconciliation, 2026-09-08

The user's 36-phase checklist is the desired product direction, not a verified
inventory. This initial reconciliation covers its critical path; other boxes
remain unverified. Baseline: `1399b16`, v0.3.319, with v0.3.320 timeout repair
in progress. Do not infer whole-project completion or a percentage from it.

## Priority order adopted

1. General-purpose bounded research loop and research executor.
2. Controlled research discovery and source navigation.
3. Defensive NVD/CISA/GitHub/vendor intelligence and source correlation.
4. Sentinel monitoring with meaningful-change notification and deduplication.
5. Scope records, evidence review, defensive hypothesis assessment and reporting.

Voice, vision, games, robotics, smart home, mobile and XR remain deferred.
The supported security direction is defensive intelligence and operator-reviewed
research. Autonomous exploitation, intrusion and automated vulnerability-testing
workflows against targets are outside this implementation plan.

## Critical-path reality

| Checklist statement | Inspected evidence | Actual conclusion |
| --- | --- | --- |
| Phase 14: plans are previews only | `src/cognition/ResearchPlanExecutionApplicationService.py`: `process_start`, `process_advance`, `process_continue`; routes in `CognitiveEngine.py` | Stale statement. Start and execution exist; start remains zero-step. |
| Phase 15: agent loop absent | `ResearchAutonomyApplicationService.py` loops over the existing advance boundary; `ResearchAutonomyBudget.py` bounds advances, network/model operations and seconds | Bounded continuation exists. This does not prove autonomous goal interpretation, adaptive planning or the complete requested report journey. |
| Phase 15: execution states absent | `ResearchPlanExecutionStatus.py` has ready/running/completed/failed/cancelled/blocked/interrupted | Reuse these lifecycle semantics; planning/evaluating/replanning are not automatically equivalent states. |
| Phase 15/16: persistent execution absent | `JsonFileResearchExecutionStore.py`, `ResearchPlanExecutionSnapshot.py`, and `ResearchPlanExecutionApplicationService._restore` | Persistence/recovery infrastructure exists. Per-requirement behavior needs its tests, not a second store by default. |
| Phase 18: NVD absent | `NvdResearchSourceDiscoveryProvider.py`, `NvdResearchSourceFetcher.py`, `NvdVulnerabilityDocument.py` | Provider and document code exist. Not proof of every CVSS/CWE/product-field checkbox or a vulnerability correlation product. |
| Phase 30: one-time scheduler absent | `TrustedOneShotDeferredExecutionScheduler.py`, schedule/store types | A durable one-time attempt exists. It does not prove recurring Sentinel watches or multi-feed change detection. |
| Phase 22: scope absent | `ResearchProgramScopeRevision.py`, `ResearchTargetScope.py`, enrollment UI | Explicit scope revisions and host/network exclusions exist. Arbitrary prose restrictions are not automatically enforceable. |
| Phase 28: tool UI | `KaliOperationPanel.py` and `DesktopController.py` | Two existing manually selected diagnostics are exposed; no general terminal or autonomous security-test loop. |
| PROJECT_STATUS version | Old header said v0.3.265 while runtime was v0.3.319 | Header corrected during v0.3.320; the older narrative still needs an item-by-item audit. |

Evidence anchors for verification:

- `tests/e2e/test_explicit_research_execution_scenario.py`
- `tests/integration/test_research_autonomy.py`
- `tests/integration/test_foreground_execution_control.py`
- `tests/integration/test_research_execution_restart.py`
- `tests/research/test_nvd_research_source_discovery_provider.py`
- `tests/research/test_nvd_source_ingestion.py`
- `tests/research/test_one_shot_deferred_execution.py`

File existence alone is not a passing gate. Current full-suite results establish
that tests run, not that all requested product behavior has been exercised.

The existing end-to-end `test_question_to_closed_run_with_uncertainty_intact`
was inspected: it manually authors and authorizes individual typed steps,
collects returned source/evidence IDs in the test, supplies claim wording and
then records comparison/completion. This proves the explicit execution chain.
It does not prove that an agent derives those choices from a natural-language
goal. The first major milestone therefore remains open even when that test passes.

## Next substantive milestone: first research journey gap assessment

The ten requested activities are now mapped to inspected code and missing
connections in [First research journey audit](First_Research_Journey_Audit.md).
The decisive next boundary is provisional fetched-text handoff: current
`source_fetch` returns a summary, not content usable by a later extractor.

Use the user's example: “Research indirect prompt injection defenses.” Keep it
general research; no target testing or Kali integration in this milestone.

### Opening connection added in v0.3.321

`ResearchPlanDraftService.preview_question` builds a fixed two-step opening:
local knowledge search followed by discovery on an explicitly selected provider.
`research_question_plan_preview` reaches it through the existing application
service. The advanced desktop button displays the ordinary plan preview. It does
not transfer the proposal into the editor, create approval or start execution.
Same question and provider preserve the same canonical content digest.

The earlier generic `Planner` only supplied heuristic task titles (or Clarify
goal), while the research draft boundary required already-authored steps. This
opening fills the first drafting gap without modifying those legacy semantics.
It is a fixed template, not LLM goal decomposition or adaptive replanning.

Version v0.3.322 connects that exact preview to the ordinary authorization and
zero-step start interface through an explicit selection. Prior editor contents
are retained for restoration. A fake-provider end-to-end test verifies approval,
consumption and bounded continuation to candidate discovery, without fetch or
acceptance. This proves the opening journey, not the complete research loop.

Follow-up: assess bounded candidate acquisition and evidence proposals through
existing operations, retaining separate review for permanent source acceptance.
Discovery alone provides neither evidence, candidate claims nor a report.

- [ ] Trace natural-language goal input to the actual planner, approval and execution paths.
- [ ] Map each of the ten requested first-major-milestone steps to a reachable
      operation and a test, or explicitly mark it missing.
- [ ] Check whether source discovery/fetch and evidence candidates can form a
      bounded multi-step journey without manual stepping at every operation.
- [ ] Preserve separate consent for permanent source acceptance, generated claims
      and contradictions; identify where the journey must wait.
- [ ] Check cancellation, repeated-query/action handling, cumulative byte/token
      accounting and restart behavior at the journey boundary. Existing step,
      request and time limits do not prove these additional budgets.
- [ ] Implement the first missing general-research connection through the existing
      application services. Add a deterministic end-to-end fixture with fake
      providers and an explicit supported/unsupported capability inventory.
- [ ] Produce a cited candidate report with unknowns and unresolved contradictions
      visible; model text and source text must not become instruction authority.

Do not introduce AgentTask/AgentGoal/AgentRun classes merely to match a list of
names. Add a domain type only when an inspected behavior needs it. Do not turn
an approved plan into permission for new capabilities or targets during replan.

## Delivery gates

Focused behavior tests, full suite, Ruff, Black, MyPy, diff review, changelog and
PROJECT_STATUS updates precede publication. Record exact commit CI results.
Distinguish locally tested, pushed, CI-passed, and live-provider validated.
No whole-project completion claim is supported by this initial reconciliation.
