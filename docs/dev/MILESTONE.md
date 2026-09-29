# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.
`delivered` requires verified reachability from `origin/main` (CLAUDE.md's
"Default-branch integration"), not merely green exact-SHA CI on the
development branch — `release`/`ci-pending` cover that intermediate state.

## Current — v0.3.425

| Field | Value |
| --- | --- |
| Milestone | Cross-store security finding lifecycle replay integrity (closes the "full F4 scope" gaps deferred by v0.3.420's F4 phase 1) |
| Base SHA | 3cd6bfe (origin/main tip, v0.3.424 delivered) |
| Branch | `feature/finding-lifecycle-integrity-v0.3.425`, a `git worktree` forked directly from refreshed `origin/main` |
| Status | release |
| Specialists | hypatia-lead: sole implementer; hypatia-epistemics: independent review, PASS, no residual epistemic risk found; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, PASS, closed one real coverage gap with a mutation-verified regression test |
| Blockers | none |

Rationale: v0.3.420's own ledger entry ("Historical scope: v0.3.420")
explicitly deferred "the full F4 scope" as needing "a genuine
design/refactor decision (duplicate business-rule logic out of
`cognition`'s application services into a shared `research`-layer pure
module, or accept duplication)" — specifically: cross-store referential
checks (a finding's `source_hypothesis_id` against the separate hypothesis
store, an evidence link's `evidence_id` against the separate HTTP-evidence
store), the `VALIDATED`-evidence-gate replay, and the
one-finding-per-hypothesis-dedup replay. This milestone makes that design
decision: a new pure, dependency-free function,
`research.ResearchSecurityFindingLifecycleIntegrity.verify_finding_lifecycle_integrity`,
takes the three already-loaded documents (finding, hypothesis, HTTP
evidence) and raises `ResearchError` if they are mutually inconsistent in a
way the live application services could never have produced — reusing no
duplicated business-rule logic (it re-derives each invariant fresh from the
persisted records themselves, the same technique the existing single-store
F4 phase 1 checks already use for `is_valid_status_transition`), and adding
no coupling between the three independently-owned store files (none of them
import each other; the new module is the reconciliation boundary, called
once eagerly by `core.Bootstrap.initialize()` right after all three stores
are constructed, mirroring the existing eager
`ResearchSourceContentRestorer.restore(...)` precedent already in that same
method).

Four invariants are now replayed at startup, each a fact the live write
path already guarantees:
1. Every finding's `source_hypothesis_id` resolves to a real hypothesis in
   the same program, and the finding's `finding_kind`/`subject_kind`/
   `subject_canonical_value` exactly match that hypothesis's own fields
   (`create_finding` copies these three fields directly from the
   hypothesis and never accepts them as independent arguments).
2. Every finding evidence link's `evidence_id` resolves to a real HTTP
   evidence record in the same program, whose `target_kind`/
   `target_canonical_value` match the citing finding's own subject (the
   identical comparison `attach_evidence`'s F1 check already proves;
   evidence carried forward from a hypothesis is transitively safe because
   the hypothesis service's own `create_hypothesis`/`attach_evidence`
   enforce the same match against the hypothesis's subject).
3. No two findings share one `(source_hypothesis_id, program_id)`
   (`create_finding`'s dedup check refuses a second finding unconditionally,
   regardless of the first finding's current status).
4. A finding with any `VALIDATED` transition in its history has at least
   one `VALIDATES` evidence link somewhere in the final document (evidence
   links are append-only and never removed, so a link present at the real
   `_require_validation_gate` call is still present in the final document).

Two related checks were deliberately investigated and NOT added, per this
session's explicit instruction not to invent unprovable provenance during
replay:
- The source hypothesis's derived status *at the exact moment*
  `create_finding` was called. Only the hypothesis's *current* status is
  ever computed; no snapshot of "status when finding X was created" is
  persisted, and `READY_FOR_VALIDATION -> NEEDS_EVIDENCE`/`REFUTED` are
  both legal later hops (hypatia-epistemics independently verified this
  against `ResearchSecurityHypothesisStatus`'s own closed transition
  table), so a hypothesis can legitimately move off `READY_FOR_VALIDATION`
  after spawning its finding. Checking "current status" would reject real
  histories.
- Whether a `CONTRADICTS` evidence link existed *before* a `VALIDATED`
  transition. `attach_evidence` has no gate of its own (confirmed by
  reading its full body), so a legitimate history can attach `CONTRADICTS`
  evidence *after* an already-recorded `VALIDATED` transition. The finding
  document persists `evidence_links` and `status_transitions` as two
  independently-append-ordered lists with no interleaving field between
  them, so replay cannot distinguish a legitimate post-validation
  contradiction from a tampering artifact. Asserting "no `CONTRADICTS` link
  may ever coexist with a `VALIDATED` transition" would reject real,
  legitimately-producible histories.

Scope: one new file
(`src/research/ResearchSecurityFindingLifecycleIntegrity.py`), a ~15-line
addition to `core/Bootstrap.py`'s `initialize()` (three eager `.load()`
calls plus the new function call, no new store, no schema/version bump,
no change to any application-service write-path behavior or public method
signature), one new test file
(`tests/research/test_research_security_finding_lifecycle_integrity.py`,
22 tests including a `MutationTests` class proving each of the four checks
is load-bearing by monkeypatching it to a no-op), and a new
`BootstrapFindingLifecycleIntegrityTests` class appended to
`tests/test_bootstrap.py` (4 tests: one consistent-history-plus-restart
success case, three fail-closed tampering cases). Desktop panels, Brain
intent surface, and every existing store's schema/version are untouched.

Security invariants (restated, unchanged by this milestone): MODEL OUTPUT
!= AUTHORITY; a `VALIDATED` finding is never authority to act. The new
function performs no I/O of its own (pure, over three already-loaded
in-memory documents), no fetch, no process, no network request, and
touches no credential. A cross-store violation now fails `Bootstrap
.initialize()` closed for the *entire* application — a necessary
consequence of the invariant spanning multiple independently-owned store
files (there is no single document to "reject whole" on), matching this
codebase's existing reject-whole-document precedent, not a new class of
capability (session/memory/research-run stores are already loaded eagerly
and fail closed in that same method).

Review findings and how each was resolved:
- **hypatia-epistemics** (independent, read-only): PASS. Traced both
  write paths line-by-line and confirmed none of the four checks can
  reject a legitimately-producible history; independently verified the
  two deliberately-deferred checks against `ResearchSecurityHypothesisStatus`'s
  closed transition table and `attach_evidence`'s full body.
- **hypatia-security** (independent, read-only): PASS, no findings.
  Attempted to hand-craft bypasses for all four checks; all correctly
  rejected. Confirmed every cross-referencing dict key is `(id,
  program_id)`, never a bare ID. Confirmed the new eager-startup blast
  radius is a generalization of an already-established pattern, not a new
  capability.
- **hypatia-qa** (independent): PASS. Found one real, concrete
  test-coverage gap — nothing distinguished "evidence link cites evidence
  with a mismatched subject" from a hypothetical, more permissive
  implementation that treats "subject exists somewhere in the document" as
  satisfying the match, since every existing fixture used only a single
  finding. **Closed**: added
  `test_evidence_matching_a_different_findings_subject_still_fails_closed`
  (two findings with different subjects; evidence matching finding-1's
  subject cited by a link on finding-2), verified load-bearing against a
  deliberately-broken doc-wide-membership variant, then the source was
  restored unmodified (no source change was in fact needed).

Verification (2026-09-29, Windows canonical environment, hypatia-lead):
7666 tests, `OK (skipped=3)` — 26 net new over v0.3.424's 7640 (25 from
hypatia-lead, 1 from hypatia-qa). Black, Ruff, MyPy (`src`, 613 source
files) all clean. `git diff --check` clean.

## Historical scope: v0.3.424 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Reproduction record foundation (Bug Bounty Researcher roadmap, next step after item 9's Validation Recipe) |
| Base SHA | 3b138d3 (origin/main tip, v0.3.423 delivered) |
| Branch | `feature/reproduction-record-v0.3.424`, a `git worktree` forked directly from refreshed `origin/main` |
| Status | delivered |
| Specialists | implementation (domain type, outcome enum, derived reads, store, application service, `CognitiveEngine`/`Bootstrap`/`ResponseComposer` wiring) found already complete but untested in this worktree at session start; hypatia-lead wrote the missing test coverage (mirroring the sibling Validation Recipe feature's test structure exactly) and completed the milestone; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, PASS-with-caveats, closed one real gap with two mutation-verified regression tests |
| PR | #403, MERGED 2026-09-29T09:08:54Z, standard merge commit `3cd6bfefd70be02a2eb1b1aaca48c8f6ee1a05de` |
| origin/main reachability | verified: merge commit `3cd6bfef` has parents `3b138d38feb92d03aabf49a3fdbc9f833ead96d4` (prior `origin/main`) and `8f2eec0dbdc5776f2bbedc9c4c750d537288cf0f` (this release); `git merge-base --is-ancestor 8f2eec0d origin/main` succeeds |
| Blockers | none |

Post-merge verification (2026-09-29, hypatia-lead): PR #403 base `main`,
head `feature/reproduction-record-v0.3.424`, carried 2 commits (a docs-only
ledger reconciliation for v0.3.423 and this release commit) across 20
changed files, matching this milestone's own stated scope exactly. Both
PR-triggered `test-build-smoke` checks passed against the release SHA,
independently of the exact-SHA `workflow_dispatch` runs (Linux `36546347086`,
Windows `36546351357`) dispatched before the PR was opened. Author/committer
identity unchanged (Songül Kızılay via GitHub noreply email, Claude Sonnet 5
co-author trailer preserved).

Rationale: at session start, `D:\hypatia-worktrees\reproduction-record`
already held a complete, uncommitted implementation of the next Bug Bounty
Researcher lifecycle step — an operator-authored "reproduction record" of
what happened when they manually followed an already-recorded Validation
Recipe's steps — forked from `origin/main`'s v0.3.423 tip with zero
commits ahead of it. Per standing instruction not to abandon or duplicate
in-progress work, hypatia-lead inspected it file-by-file rather than
starting fresh: the domain type
(`ResearchReproductionRecord`/`ResearchReproductionOutcome`), the pure
derived-reads module (`ResearchReproduction.py`), the append-only store
(`JsonFileResearchReproductionStore.py`), the application service
(`ResearchReproductionApplicationService.py`), and all `CognitiveEngine`/
`Bootstrap`/`ResponseComposer`/`BrainResponse` wiring were already present
and followed the sibling Validation Recipe feature's established patterns
exactly (evidence-subject matching reusing the same F1 target/subject
comparison, subject fields copied from the recipe never caller-supplied,
append-only enforcement, `ResearchSensitiveInputPolicy` reuse). Only test
coverage was incomplete: the original session had written tests for the
domain record/enum layer only (15 tests), leaving the derived-reads
module, the store, the application service, and the `CognitiveEngine`
wiring entirely untested — a genuine, material completion gap, not a
stylistic one.

Scope: no production-code changes beyond what was already present at
session start except `ResearchSecurityValidationRecipeApplicationService
.recipe_by_id` (also already present, added by the same prior session).
hypatia-lead added five test files/additions:
`tests/research/test_research_reproduction.py`,
`tests/research/test_json_file_research_reproduction_store.py`,
`tests/cognition/test_research_reproduction_application_service.py`, and
a new `ReproductionDispatchTests` class appended to
`tests/cognition/test_cognitive_engine.py`, mirroring
`test_research_security_validation_recipe.py`/
`test_json_file_research_security_validation_recipe_store.py`/
`test_research_security_validation_recipe_application_service.py`/
`SecurityValidationRecipeDispatchTests` structurally. hypatia-qa
independently added two further regression tests to the store test file
(see Review findings below).

REPRODUCTION RECORD != EXECUTION AUTHORITY, verified structurally by
hypatia-security: no code path added or already present in this diff
calls `transition_status` on any hypothesis/finding service (confirmed by
grep — the identifier appears only in docstrings), `means_confirmed_
vulnerability` is hard-coded `False` for every `ResearchReproductionOutcome`
member including `REPRODUCED`, and `subject_kind`/`subject_id` are copied
only from the looked-up recipe object, never read from caller/request
metadata.

Review findings and how each was resolved:
- **hypatia-security** (independent, read-only): PASS, no findings across
  all six reviewed axes (authority, fail-closed correctness, program/
  subject isolation, store integrity, secret handling, `CognitiveEngine`
  wiring). Full reasoning recorded in this session's transcript.
- **hypatia-qa** (independent): PASS-with-caveats. Found one real,
  concrete gap — the store's `MAX_REPRODUCTIONS`/
  `MAX_REPRODUCTION_STORE_BYTES` ceilings were pinned as constants by
  `test_the_declared_ceilings_are_the_reviewed_values` but never proven
  actually enforced. **Closed**: added
  `test_bounded_record_count_is_enforced`/
  `test_oversized_store_is_rejected_on_load`, each mutation-verified by
  temporarily neutralizing the corresponding guard in
  `JsonFileResearchReproductionStore.py`, confirming the new test failed,
  then restoring the source unmodified. Two further gaps were noted but
  explicitly left open as pre-existing, codebase-wide patterns shared
  with the sibling hypothesis/finding/recipe evidence-matching tests, not
  regressions this milestone introduced: (1) no fixture anywhere in the
  codebase exercises an evidence-target-*kind* mismatch (only canonical-
  value mismatches are covered); (2) the preview response's not-authority
  notice text is asserted for the record path but not the preview path.

Verification (2026-09-29, Windows canonical environment, hypatia-lead):
7640 tests, `OK (skipped=3)` — 61 net new over v0.3.423's 7579 (59 from
hypatia-lead, 2 from hypatia-qa). Black, Ruff, MyPy (`src`, 612 source
files) all clean. `git diff --check` clean. Desktop UI deliberately out
of scope, mirroring the v0.3.421-then-v0.3.423 foundation-then-UI
precedent — confirmed no `src/desktop` file is touched.

## Historical scope: v0.3.420 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Security Hypothesis/Finding store load-time replay validation, phase 1 (F4 phase 1; Bug Bounty foundation, hardening the delivered step 6/7 lifecycle) |
| Base SHA | d1e3b18 (v0.3.419 delivery reconciliation) |
| Status | delivered |
| Specialists | hypatia-security, hypatia-epistemics, hypatia-runtime, hypatia-qa: independent parallel read-only investigation (2026-09-28), converged on F4 as highest-priority real gap; hypatia-lead: sole implementer; hypatia-security: independent review, PASS, no findings; hypatia-epistemics: independent review, PASS, empirically re-verified both the fix and its intentional boundary; hypatia-runtime: independent review, PASS, no caveats; hypatia-qa: independent review, PASS-with-caveats (one non-blocking test-strategy-literalness gap, closed by hypatia-lead before release); hypatia-lead: release |
| PR | #399, MERGED 2026-09-28T18:05:34Z, standard merge commit `30c28ad2b88d0e87032618f00990a9de717a6146` |
| origin/main reachability | verified: merge commit `30c28ad2` has parents `06c22aa174ad87a07f9a0c0de3115f9a0b521156` (prior `origin/main`) and `32be4e09be2544884efac77e8f4d501ddb83e7aa` (this release); `git merge-base --is-ancestor 32be4e09... origin/main` succeeds |
| Blockers | none |

Rationale: after v0.3.419 delivered (PR #398, merge commit `06c22aa1`, verified
reachable from `origin/main`), four specialists independently investigated
the Bug Bounty Researcher pipeline read-only in parallel (2026-09-28) to
select the next bounded milestone, per the standing "F4 lifecycle replay
validation on load" deferral recorded in every one of the v0.3.416-419
ledger entries. All four converged on the same conclusion without being
told each other's answer: F4 is a real, currently-exploitable-by-tampering
gap (not speculative), but the *full* F4 (a point-in-time replay of every
business-rule invariant, including the `VALIDATED` evidence gate and
cross-store checks) is correctly sized as its own future milestone, not
this one — because that full scope needs a genuine design/refactor decision
(duplicate business-rule logic out of `cognition`'s application services
into a shared `research`-layer pure module, or accept duplication) that
this session's investigation does not make. Both hypatia-epistemics and
hypatia-runtime independently proposed narrowing to exactly the slice that
is *already* cleanly implementable today with zero new coupling: the
closed status-transition state-machine table (`is_valid_status_transition`)
is already a pure, dependency-free function living in `research/` on both
sides, imported (never the reverse) by the two `cognition` application
services — replaying it at load time duplicates nothing and creates no
import-cycle risk. Separately, hypatia-security and hypatia-qa
independently found and precisely reproduced the *same* concrete, narrow,
already-real defect: `JsonFileResearchSecurityFindingStore`'s own module
docstring claims "no dangling relation... as defence in depth against a
hand-edited or partially-written file" but this is literally false for one
field pair — `duplicate_of_finding_id`/`superseded_by_finding_id` on a
status transition is never checked against the document's own known
findings at load time, only at write time by the application service's
`_require_linked_finding`. hypatia-epistemics independently reproduced the
lifecycle-tampering gap empirically: a hand-crafted, structurally valid
finding-store document with one finding, zero evidence links, and a single
status transition straight to `validated` loads successfully today and the
derived read model reports `status=validated` with zero validating
evidence — a state the real application service could never produce.
hypatia-qa's own recommendation named this exact scope as the next
milestone, ahead of starting any new functional capability, "since it would
build on top of a store whose defense-in-depth claim is currently false for
one field." This is Option A from Phase 5 (a concrete slice of F4), chosen
over roadmap item 8 ("Business-logic/state-transition model" — confirmed by
three of four specialists, independently, to have "no existing precedent or
design in this codebase," and therefore not size-appropriate for a bounded
milestone) and over any speculative trust-taxonomy/correlation-ID/
tool-gateway work (all four specialists independently found no live problem
motivating any of those, matching the same rejections already on record in
the v0.3.416-419 ledger entries).

Scope: two narrow additions to `ResearchSecurityHypothesisDocument.__post_init__`
(`src/research/JsonFileResearchSecurityHypothesisStore.py`) and
`ResearchSecurityFindingDocument.__post_init__`
(`src/research/JsonFileResearchSecurityFindingStore.py`), using only
already-imported, already-pure functions and already-persisted fields — no
new dependency, no new coupling between the two independent store files, no
import from `cognition` into `research`:

1. **Status-transition sequence legality replay** (both stores). Group
   `status_transitions` by `(hypothesis_id, program_id)` /
   `(finding_id, program_id)`, preserving the document's own persisted list
   order (already guaranteed append-order-causal by `save()`'s
   prefix-preservation check — never re-derived from `recorded_at`, per the
   same discipline `_latest_status`/`_current_status` already follow). Walk
   each entity's own subsequence from the implicit zero-transition default
   status (`OPEN` for Hypothesis, `CANDIDATE` for Finding, matching
   `_latest_status`'s own default exactly) and confirm
   `is_valid_status_transition(current, next)` holds at every step,
   reusing the existing pure closed-table function
   (`research.ResearchSecurityHypothesisStatus.is_valid_status_transition`/
   `research.ResearchSecurityFindingStatus.is_valid_status_transition`) —
   the identical function the application service already calls on write,
   never duplicated or reimplemented. Reject the whole document on the
   first illegal hop found, matching this codebase's existing
   reject-whole-document precedent for every other document-level
   invariant in both stores (no quarantine infrastructure of any kind).
2. **Duplicate/superseded referential integrity** (Finding store only —
   Hypothesis has no such field). For every status transition whose
   `duplicate_of_finding_id`/`superseded_by_finding_id` is not `None`,
   require the referenced finding ID to (a) exist in the document's own
   `known_findings` under the *same* `program_id` as the transition
   (mirroring the application service's own `_require_linked_finding`
   program-scoping exactly), and (b) not equal the transition's own
   `finding_id` (no self-reference) — the same two rules
   `_require_linked_finding` already enforces at write time, now also
   replayed at load time. Reject the whole document on violation.
3. Correct `JsonFileResearchSecurityFindingStore`'s module docstring (lines
   13-17), which currently overclaims "no dangling relation... as defence
   in depth" for every relation when it did not previously cover this one
   field pair; update both store module docstrings to name the new
   invariant precisely.
4. Close the QA-identified store-test-file asymmetry: port the Finding
   store test file's atomic-write-failure test
   (`test_a_failed_atomic_write_keeps_the_original_and_leaves_no_temp_file`),
   its truncated/invalid-content matrix
   (`test_truncated_or_non_json_content_fails_closed`), and its
   status-transition-history tamper matrix
   (`test_save_rejects_removal_or_alteration_of_status_transition_history`)
   onto the Hypothesis store test file, which currently lacks all three
   despite both stores sharing byte-for-byte identical code shapes for the
   paths those tests exercise (`save()`'s prefix-preservation guard,
   atomic-write failure handling, and content-parsing failure handling).

Non-goals (exhaustive): no cross-store referential checks (a finding's
`source_hypothesis_id` existence/status-at-creation-time against the
separate hypothesis-store file, or an evidence link's `evidence_id`
existence against the separate HTTP-evidence-store file) — hypatia-runtime's
investigation confirmed these would require new coupling between
independently-loadable store files, a real design decision not made this
session; no `VALIDATED`-evidence-gate replay (`_require_validation_gate`'s
logic lives only in `cognition.ResearchSecurityFindingApplicationService`
and is not currently expressible as a dependency-free `research`-layer
function without either accepting duplication or extracting/refactoring the
application service — a genuine product/design call per hypatia-runtime,
correctly deferred); no one-finding-per-hypothesis dedup replay (same
reasoning); no subject-binding replay (already independently enforced at
the service layer per hypatia-security's investigation, not a load-time
gap); no schema or version bump in either store (this uses fields and
positions already on disk today); no change to any application-service
write-path behavior, business logic, or public method signature — this
milestone touches only the two documents' `__post_init__` load-time
validation; no roadmap item 8 ("Business-logic/state-transition model" —
confirmed by three specialists to have no existing precedent, not
size-appropriate for a bounded milestone); no generic trust taxonomy,
correlation-ID/request-ID persistence, Safe Tool Gateway work, autonomous
agent/model-triggered creation, or any authority/budget/target/credential
change of any kind (all four specialists independently found no live
problem motivating any of these).

Security invariants (restated, unchanged by this milestone): MODEL OUTPUT
!= AUTHORITY; SUBAGENT OUTPUT != AUTHORITY; a `VALIDATED` finding is never
authority to act. No lifecycle transition, evidence citation, or store
load/validation path may run a tool, create a process, make a network
request, or expand/grant scope, credential, budget, or execution authority
— this milestone adds only pure, in-memory, already-imported validation
logic to two document dataclasses' own `__post_init__`; it introduces no
new I/O, no new store coupling, and no new field. Program isolation and
subject-binding remain fully enforced at the service layer exactly as
before (untouched by this change); this milestone only makes the stores'
load-time defense-in-depth match what their own docstrings already claim.

Acceptance criteria:
- A hand-crafted `security_findings.json`-shaped document whose
  `status_transitions` includes a `duplicate_of_finding_id`/
  `superseded_by_finding_id` naming a finding ID absent from that program's
  `findings` list fails to load with `ResearchError`.
- The same, but naming the transition's own `finding_id` (self-reference),
  fails to load.
- The same, but naming a real finding ID that exists only under a
  *different* program, fails to load (cross-program linkage rejected at
  load exactly as the live write path already rejects it).
- A hand-crafted document whose per-entity status-transition subsequence
  (grouped by `(id, program_id)`, in persisted append order) is not a legal
  walk of `is_valid_status_transition`'s closed table fails to load with
  `ResearchError`, independently proven for both the Hypothesis store and
  the Finding store.
- A hand-crafted document whose per-entity subsequence *is* a legal walk —
  including a realistic multi-hop sequence ending in each terminal status —
  continues to load successfully, byte-identical to today's behavior.
- Every existing v0.3.406-419 regression fixture in both store test files
  and both application-service test files is unaffected: no accept/refuse
  outcome changes for any document a live application-service write path
  could actually produce.
- The Hypothesis store test file gains the same three test shapes already
  present in the Finding store test file (atomic-write-failure,
  truncated/invalid-content matrix, status-transition tamper matrix),
  closing the asymmetry hypatia-qa identified, with no production-code
  implication.

Affected architectural layers: `research` only (two JSON store files' own
document-level load validation) — `cognition`, persistence schema/version,
desktop panels, and Brain intent surface all untouched.

Persistence/schema impact: none. No schema/version bump in either store;
no new field on any record; this uses only fields and append-order
positions already persisted by every prior delivered milestone back to
v0.3.415/v0.3.416.

Migration implications: none for this repository's own test fixtures and
CI state (all hand-constructed, none contain an illegal sequence or a
dangling/self-referencing linkage). Documented as a forward compatibility
note for any real future deployment: a persisted document that already
contained an illegal transition sequence or a dangling/self-referencing
duplicate/superseded-by reference before this milestone would newly fail
to load after it — this is the explicit point of the fix (reject-whole
matches this codebase's existing fail-closed precedent for every other
document-level invariant), not an accidental regression, and no such state
is reachable via the live application-service write path in the first
place.

Test strategy: hand-tampered document fixtures constructed directly against
`ResearchSecurityHypothesisDocument`/`ResearchSecurityFindingDocument` (the
same technique every existing dangling-reference test already uses),
bypassing the application service entirely, for every negative acceptance
criterion above; realistic multi-hop legal sequences (including one ending
in each terminal state, for both Hypothesis and Finding) for the positive
criteria; the three ported test shapes for the Hypothesis store; a full
differential run of both store test files and both application-service
test files to prove zero accept/refuse outcome changes for legitimate
write-path-producible documents; impacted suites focused first, full
canonical gates once at release.

Mutation strategy: revert the duplicate/superseded referential-existence
check; revert the self-reference check; revert the cross-program linkage
check; revert the transition-sequence-legality replay on the Hypothesis
store; revert it on the Finding store — five targeted mutants via in-memory
monkeypatching, never written to disk, each expected to be caught by
exactly its own new test (not incidentally by an unrelated existing test).

Rollback strategy: pure logic addition inside two documents'
`__post_init__`, using only already-persisted fields and already-guaranteed
append-order positions; no schema/version bump; rollback is a plain revert
of the release commit with zero data-migration concern in either direction.

Deferred findings carried forward: the full F4 scope — cross-store
referential checks (finding -> hypothesis existence/status-at-creation-time,
evidence-link -> HTTP-evidence existence) and the `VALIDATED`
evidence-gate/one-finding-per-hypothesis-dedup replay — remains explicitly
deferred to its own future dedicated milestone, needing the shared-logic
extraction/duplication design decision hypatia-runtime's investigation
identified as a genuine product call, not pure investigation. Roadmap item
8 ("Business-logic/state-transition model") remains correctly unscoped, no
existing precedent. Request-ID/correlation-ID persistence, generic trust
taxonomy, and Safe Tool Gateway generalization remain rejected as
speculative, no live problem found by any of the four specialists this
session. The Windows `ResourceWarning` test-hygiene debt remains untraced
and out of scope. `docs/Roadmap/Master_Roadmap.md`'s "Delivered so far"
note under the Bug Bounty Researcher section was reconciled at this
milestone's release to name items 6/7's delivery (v0.3.415-419) and this
milestone's own hardening, as a documentation-only correction bundled with
this release commit.

Security review (hypatia-security, 2026-09-28): PASS, no findings. Read the
full diff of all four changed files plus the mirrored write-path logic in
`ResearchSecurityFindingApplicationService._require_linked_finding`/
`_require_linkage`, both closed state-machine tables, and the record-level
1:1 linkage binding. Confirmed the new checks fail-closed with zero partial
persistence; confirmed the duplicate/superseded check mirrors
`_require_linked_finding`'s exact semantics (self-reference check before
program-scoped existence); confirmed the sequence replay uses persisted
list order only, never `recorded_at`; confirmed the new checks run strictly
after every pre-existing check, so no prior early-exit behavior changed;
confirmed zero `cognition` import, zero new store-to-store coupling, zero
schema/version change, and exactly the four intended files touched. Ran the
full impacted suites (228 tests) plus ruff/black/mypy, all clean. One
informational, non-blocking observation: an error-message f-string is
built via adjacent-literal concatenation at a Black line-wrap point —
functionally correct, purely cosmetic.

Epistemics review (hypatia-epistemics, 2026-09-28): PASS. Independently
re-reproduced its own earlier empirical finding (a hand-crafted, one-hop
`CANDIDATE -> VALIDATED` finding document with zero evidence still loads
and reports `status=validated`) against the finished code, confirming this
milestone correctly does NOT also implement evidence-gate replay (that
scope boundary held exactly as locked) while confirming the two invariants
this phase DOES cover work as intended. Verified the per-entity grouping
preserves relative transition order by construction of Python's
deterministic iteration, not by assumption. Copied the pre-diff production
files into a scratch tree and ran the new tests against old code to prove
non-vacuousness directly rather than reasoning about it. Confirmed the
ledger's and docstrings' framing of what remains deferred is accurate
against the finished diff, not just the pre-implementation plan.

Runtime review (hypatia-runtime, 2026-09-28): PASS, no caveats. Confirmed
zero import from `cognition` anywhere in the diff and zero change to any
`cognition` file, `CognitiveEngine.py`, `Bootstrap.py`, or store
constructor/wiring. Traced both the `load()` and `save()` call paths to
confirm the new checks apply uniformly regardless of which path constructs
the document. Confirmed rollback safety (pure logic addition, no schema/
version bump, no new persisted field). Verified the two ported Hypothesis-
store test shapes (atomic-write-failure, truncated-content matrix)
line-by-line against their Finding-store counterparts, and independently
confirmed, against the actual `_VALID_TRANSITIONS` tables, that the
Finding-side "reordered" tamper case genuinely cannot stay sequence-legal
(unlike the Hypothesis side, where it can) — the asymmetric test handling
this required is correct, not an oversight.

QA review (hypatia-qa, 2026-09-28): PASS-with-caveats. Built a byte-
identical copy of the pre-diff production code and ran the new tests
against it, confirming exactly the 12 new negative assertions fail on old
code and nothing else — proving non-vacuousness systematically rather than
by spot-check. Built a full acceptance-criterion traceability table; every
criterion maps to a specific test. Verified the pre-existing Finding-store
test fixture repair (forced by the new sequence check rejecting its
original same-status-twice fixture) is a legitimate repair preserving the
test's original append-only-coverage intent, not a weakening, by hand-
tracing both graphs' `_VALID_TRANSITIONS` tables directly. One non-blocking
caveat: the new positive multi-hop test only exercised a chain ending in
`REFUTED`, not `DUPLICATE`/`SUPERSEDED`, against this milestone's own
stated test-strategy wording — closed by hypatia-lead before release with
two additional tests (`test_a_legal_multi_hop_sequence_ending_in_duplicate_is_accepted`/
`..._ending_in_superseded_is_accepted`) and a follow-up wording fix to one
test's explanatory comment, which QA had also flagged as slightly
imprecise about the exact mechanism (still correct about the underlying
claim).

Mutation pass (2026-09-28, hypatia-lead): five targeted mutants applied via
in-memory monkeypatching in a throwaway scratch script, never written to
any repository file — (1) remove the whole duplicate/superseded referential
check, (2) loosen it to ignore program scoping (existence-anywhere instead
of existence-in-program), (3) remove only the self-reference check, (4)
disable the Finding store's sequence-legality replay
(`is_valid_status_transition` forced to always return `True`), (5) same for
the Hypothesis store. All five caught; all control assertions against the
real, unmutated code passed both before and after the mutation pass.

Release gates (2026-09-28, Windows canonical environment, hypatia-lead):
7471 tests, OK (skipped=3) — 18 net new tests over v0.3.419's 7453; Black
(1019 files), Ruff, and MyPy (601 source files) clean; `git diff --check`
clean; `git status` confirmed exactly the intended files touched, no
untracked artifacts.

## Historical scope: v0.3.421 (delivered)

Note on ledger structure (kept for record; superseded by delivery below):
this entry was originally written while PR #399 was still open, on a
deliberately separate independent branch so as not to contaminate it. Both
have since merged to `origin/main` in sequence, verified below.

| Field | Value |
| --- | --- |
| Milestone | Validation recipes, foundation (Bug Bounty Researcher roadmap item 9) |
| Base SHA | 32be4e0 (v0.3.420, same commit PR #399 carried as HEAD) |
| Branch | `feature/research-security-validation-recipe-v0.3.421` |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer, sole reviewer (single bounded autonomous milestone; no dual-writer risk since the isolated worktree has no concurrent writer) |
| PR | #400, MERGED 2026-09-28T18:11:21Z, standard merge commit `2e0abcb0d82e61c892421e78af6c7c1fade41e46` |
| origin/main reachability | verified: merge commit `2e0abcb0` has parents `30c28ad2b88d0e87032618f00990a9de717a6146` (v0.3.420's own merge, prior `origin/main`) and `d672cc5b41ea2381080f2e50d7db07c2c49a5343` (this release); `git merge-base --is-ancestor d672cc5b... origin/main` succeeds; PR #400's diff against its base (`main`@`30c28ad2`) was exactly the 20 files this milestone's own scope names, with no overlap from v0.3.420 |
| Blockers | none |

Rationale: continuing this autonomous session's read-only roadmap discovery
after completing v0.3.420's independent external review (EVREN +
Abacus/RouteLLM, both completed; no verified defect found in the frozen
diff — see the repo-external review artifacts referenced in that session's
handoff, not committed here), the roadmap's own recorded priority order
names item 9 ("Validation recipes") as the next unstarted step after item 7
(Finding Lifecycle, hardened through v0.3.420, delivered/hardening-only
through this point). Item 8 ("Business-logic/state-transition model") was
considered and rejected for this pass, matching the v0.3.420 entry's own
finding: "no existing precedent or design in this codebase," a poor fit for
a bounded milestone. Item 9 has an equally undocumented design (the roadmap
names it in one line with no elaboration), but — unlike item 8 — it maps
directly onto an already-four-times-proven structural pattern in this exact
codebase (append-only record + derived projection + application service +
JSON store), including a cross-service-reader Protocol precedent
(`ResearchSecurityFindingApplicationService.SecurityHypothesisReader`) that
needed no adaptation, only duplication under a new name for the
finding-reader half. Chosen over continuing further F4 internal hardening
per this session's explicit instruction not to let "endless internal-hardening
work... consume the roadmap" and to deliver "tangible Bug Bounty Researcher
user value" instead.

Scope: four new files under `src/research/`
(`ResearchSecurityValidationRecipeSubjectKind.py`,
`ResearchSecurityValidationRecipeRecord.py`,
`JsonFileResearchSecurityValidationRecipeStore.py`,
`ResearchSecurityValidationRecipe.py`) and one new file under
`src/cognition/` (`ResearchSecurityValidationRecipeApplicationService.py`),
plus five edited files for wiring/version only
(`src/brain/BrainResponse.py` — two new optional fields;
`src/response/ResponseComposer.py` — four new methods and a dedicated
not-authority notice constant, see the self-review note below;
`src/cognition/CognitiveEngine.py` — one new constructor parameter, one new
service field, two new dispatch branches;
`src/core/Bootstrap.py` — one new store factory method, one new
constructor argument; `src/core/Version.py` — patch bump). No existing
store, service, record, or write path
was modified. `ResearchSecurityValidationRecipeRecord` is purely
descriptive text (steps + notes), screened by the existing
`ResearchSensitiveInputPolicy`, bounded (at most 20 steps, 300 characters
each, single-line; notes bounded, may be empty). The application service's
`record_validation_recipe` verifies its subject exists for the exact
`program_id` via `SecurityHypothesisReader.hypothesis_by_id`/
`SecurityFindingReader.finding_by_id`, structurally satisfied by the real
`ResearchSecurityHypothesisApplicationService`/
`ResearchSecurityFindingApplicationService` with no modification to either.
Two new Brain intents (`research_security_validation_recipe_record`,
`research_security_validation_recipe_preview`), wired into `CognitiveEngine`
only when the recipe store *and* both the hypothesis and finding services
are present — proven by a dedicated test
(`test_recipe_service_requires_both_hypothesis_and_finding_services`) that a
half-wired engine (recipe store present, Hypothesis/Finding stores absent)
still reports "not available" rather than partially accepting an
unverifiable recipe. No desktop panel this milestone (deliberately deferred
and named as such in CHANGELOG/PROJECT_STATUS, not silently dropped).

Verification (2026-09-28, Windows canonical environment, hypatia-lead, sole
author and sole reviewer of this isolated milestone): 57 new tests (28
record/store validation, persistence, and pure-derivation coverage, 24
application-service including subject-existence/cross-program (both
hypothesis- and finding-subject directions)/restart/Brain-intent coverage,
5 CognitiveEngine wiring/dispatch including the half-wired proof above)
plus the full pre-existing suite, all green — 7528 tests total,
`OK (skipped=3)`, 57 net new over v0.3.420's 7471. Black, Ruff, and MyPy
(`src`) clean on the whole tree. `git diff --check` clean. `git status` on
the new branch showed exactly the files listed above (10 source, 5 test;
`git diff --stat` against v0.3.420's exact commit confirms 14 files under
`src`/`tests`, plus `pyproject.toml` and the four doc files this paragraph
lives in) touched, no unrelated or untracked changes. `Bootstrap().initialize()`
smoke-tested directly (temporary memory path) to confirm the new store
factory and `CognitiveEngine` wiring construct without error end-to-end,
not merely via unit-level mocks — the same category of gap ("Bootstrap
wiring was untested") a past milestone's independent QA review flagged for
a different feature.

Self-review pass (2026-09-28, hypatia-lead, before final handoff): found and
closed one real gap and one real defect before either was ever externally
reviewed. Gap: cross-program isolation was tested for a finding-kind subject
but not a hypothesis-kind subject, despite both reading through the
identically-shaped "fails closed by construction" `hypotheses_for_program`/
`findings_for_program` scoping — added
`test_a_cross_program_hypothesis_reference_fails_closed`, confirmed the
underlying mechanism (verified by reading
`ResearchSecurityHypothesisApplicationService.hypothesis_by_id`'s docstring
and body) was already sound; the test closes a coverage gap, not a
production defect. Also added a direct pure-function test file for
`ResearchSecurityValidationRecipe.py` (`validation_recipes_for`/
`current_validation_recipe_for`), matching the existing
`test_research_security_finding.py`/`test_research_security_hypothesis.py`
convention this milestone's original pass had skipped. Defect: the record/
preview response messages reused `SECURITY_FINDING_NOT_AUTHORITY_NOTICE`
verbatim ("...This *status* does not grant authority..."), which
misdescribes a validation recipe — recipes have no status of their own.
Replaced with a new, dedicated `SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE`
constant and added a regression test asserting the correct wording appears
and the finding-specific wording does not.

## Historical scope: v0.3.422 (delivered)

Note on ledger structure (kept for record; superseded by delivery below):
built on `feature/llm-lifecycle-grounding-v0.3.422`, a `git worktree`
sibling forked from v0.3.421's exact commit
(`d672cc5b41ea2381080f2e50d7db07c2c49a5343`), so neither PR #399's
checkout nor the published v0.3.421 branch history was touched or
rewritten. All three (v0.3.420, v0.3.421, v0.3.422) have since merged to
`origin/main` in sequence, verified below.

| Field | Value |
| --- | --- |
| Milestone | Authoritative conversation grounding for security lifecycle semantics |
| Base SHA | d672cc5 (v0.3.421, self-review-fixed tip) |
| Branch | `feature/llm-lifecycle-grounding-v0.3.422` |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer; hypatia-security/hypatia-epistemics/hypatia-runtime/hypatia-qa: independent parallel review, each PASS-with-one-CONCERN; EVREN (deepseek-v4.1-flash): independent external review, NEEDS_LOCAL_VERIFICATION, 5 findings; all concerns/findings triaged and the substantive ones closed before release |
| PR | #401, MERGED 2026-09-28T18:17:47Z, standard merge commit `9f06388a9bb8c624af5df7f567d100be041d33d9` |
| origin/main reachability | verified: merge commit `9f06388a` has parents `2e0abcb0d82e61c892421e78af6c7c1fade41e46` (v0.3.421's own merge, prior `origin/main`) and `a60b6937ab501dbfdb0c1d56a6a30149cf7bf79e` (this release); `git merge-base --is-ancestor a60b6937... origin/main` succeeds; PR #401's diff against its base (`main`@`2e0abcb0`) was exactly the 8 files this milestone's own scope names |
| Blockers | none |

Rationale: the user reported that EVREN, now answering fluently in
Turkish, had invented a wrong Hypatia lifecycle rule in conversation —
claiming a `READY_FOR_VALIDATION` security hypothesis with 2 `SUPPORTS` +
1 `CONTRADICTS` evidence could not become a finding. Before encoding
anything, every claim was independently re-verified against source, not
assumed from the report: `ResearchSecurityFindingApplicationService.
create_finding` (`src/cognition/ResearchSecurityFindingApplicationService.py:133-234`)
gates only on `hypothesis.status is READY_FOR_VALIDATION`; it never
inspects evidence relations, and both supporting and contradicting links
are carried forward via `_carried_relation` (lines 690-695) rather than
being dropped — the observed claim was concretely, verifiably false.
`ResearchSecurityFindingStatus._VALID_TRANSITIONS[CANDIDATE]`
(`src/research/ResearchSecurityFindingStatus.py:74-82`) includes
`VALIDATED` directly, and `_require_validation_gate` (lines 720-748)
requires exactly one condition pair: at least one `VALIDATES` citation and
zero `CONTRADICTS` citations, checked over the finding's current
evidence links at transition time. `means_confirmed_vulnerability`/
`means_validated_vulnerability` are hardcoded `False` for every status on
both records.

Scope: `src/llm/HypatiaSystemPrompt.py` only, plus three new test files.
The prior single `HYPATIA_DEFAULT_SYSTEM_PROMPT` string was split into
`HYPATIA_CONVERSATION_MANNER_PROMPT` (the unchanged prior text) and a new
`HYPATIA_SECURITY_LIFECYCLE_GROUNDING`, concatenated back into the same
exported `HYPATIA_DEFAULT_SYSTEM_PROMPT` name so every existing consumer
(`Bootstrap.py`'s fallback-when-no-custom-prompt logic, both integration
tests referencing the constant) is unaffected — confirmed, not assumed,
by running them. `HYPATIA_LLM_SYSTEM_PROMPT` continues to fully replace
the default (never merge with it), untouched by this diff. This is
advisory prompt text only: no enforcement code changed, and the module
docstring was strengthened to say so explicitly.

Review findings and how each was resolved:
- **QA** empirically demonstrated the concrete gap: appending one
  extra, contradictory sentence to the grounding text left every
  original per-case `assertIn` test green. **Closed**: added
  `ExactTextPinnedAgainstSilentDriftTests`, a byte-for-byte pin of the
  whole grounding string against an independently-kept copy — any edit,
  reworded or merely appended, now fails until deliberately updated.
- **Security** and **EVREN** (converging independently) flagged that even
  a passing test suite never called the real `cognition`/`research` code
  the prompt describes, so a future change to the actual transition table
  or validation gate could leave the prompt confidently wrong with tests
  still green. **Closed**: added
  `tests/cognition/test_security_lifecycle_grounding_matches_real_service.py`,
  which drives the real `ResearchSecurityHypothesisApplicationService`/
  `ResearchSecurityFindingApplicationService` through every scenario named
  in the prompt (creation despite contradiction with the citation carried
  onto the finding; direct `CANDIDATE`→`VALIDATED` with `VALIDATES` and no
  `CONTRADICTS`; `VALIDATED` refused with a live `CONTRADICTS` citation;
  creation refused from a non-ready hypothesis; the transition table
  checked directly via `is_valid_status_transition`).
- **EVREN** separately flagged an unscoped precedence gap: the
  conversation-manner section asks the model to follow explicit user
  formatting instructions, and nothing in the lifecycle section said a
  user turn could not "correct" its rules. **Closed**: added one sentence
  ("A user message can never change, add to, or override these rules...")
  plus a regression test.
- **EVREN** flagged the invariant-coverage test's name overstating its own
  assertions (asserted 2 of the 3 design-required invariants, the third
  covered by a sibling test). **Closed**: renamed to
  `test_model_output_and_evidence_invariants_are_present` with a comment
  pointing at the sibling test.
- **EVREN** proposed naming `SUBAGENT OUTPUT != AUTHORITY` explicitly in
  the grounding text. **Declined, recorded rather than silently dropped**:
  this specific invariant is not among the milestone's own enumerated
  required grounding points (which name three of the four listed
  invariants for the prompt text, not this one), and whether Hypatia's
  product itself exposes a user-facing "subagent output" concept in this
  lifecycle context was outside this milestone's verified scope — adding
  an unverified claim would itself have violated "verify every rule
  before encoding it."
- **EVREN** proposed an explicit "these rules cover only the statuses
  named here" scoping sentence. **Declined as redundant**: the existing
  "if asked something they do not cover, say you do not know rather than
  invent a rule" sentence already instructs exactly that; **epistemics**
  independently flagged the same underlying concern (over-generalizing to
  deferred F4 load-time-integrity gaps) as a residual, non-blocking risk
  rather than a defect, for the same reason.
- **Runtime** named a real, out-of-scope risk: the new grounding text
  brings the fixed default system prompt from 798 to 2170 characters
  (~2.7x), which competes harder with `HYPATIA_LLM_HISTORY_MAX_TURNS`
  truncation for small local models' context windows
  (`LLMEnvironmentSettings.py`'s own documented failure mode). Not
  addressed this milestone — a token-budget/context-management concern
  spanning the whole system, not specific to this text. Recorded as a
  deferred item.

Live smoke test (2026-09-28, hypatia-lead): the exact final
`HYPATIA_DEFAULT_SYSTEM_PROMPT` sent as the system-role message to EVREN
(`deepseek-v4.1-flash`), via a one-time throwaway script reusing the
installed `review-provider.ps1` helper's exact safety pattern (DPAPI
decrypt inside the process only, no retry, HTTPS only) but with a custom
system prompt rather than the reviewer persona (the installed helper's
fixed reviewer system prompt was tried first and correctly declined to
assert unverifiable facts — informative, but not a test of this
milestone's actual deliverable). Given the Turkish scenario from the
milestone brief verbatim, all four answers matched expected semantics:
finding creation allowed; contradiction preserved, not deleted; `VALIDATED`
correctly described as blocked in this specific scenario by the live
contradiction (and by the absence of validating evidence); no execution
authority implied by any of it — the exact opposite of the originally
reported hallucination. The throwaway script was deleted immediately
after use; nothing was installed.

Verification (2026-09-28, Windows canonical environment, hypatia-lead):
27 new tests (21 prompt-text tests including the exact-match drift guard,
5 real-service cross-checks, 1 covered above) plus the full pre-existing
suite, all green — 7555 tests total, `OK (skipped=3)`, 27 net new over
v0.3.421's 7528. Black, Ruff, and MyPy (`src`) clean. `git diff --check`
clean. One external review (EVREN) was run on the finished diff; Abacus
was deliberately not also run for this smaller, lower-risk, prompt-text-only
change, given the claims were independently proven against live service
behavior in the same pass — judged sufficient convergent verification
without spending a second external call pointlessly.

## Historical scope: v0.3.423 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Security Validation Recipe desktop workflow (Bug Bounty Researcher roadmap item 9, desktop UI) |
| Base SHA | 9f06388 (origin/main tip, after v0.3.420-422 all delivered) |
| Branch | `feature/validation-recipe-desktop-v0.3.423`, a `git worktree` forked directly from refreshed `origin/main` |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer; hypatia-security/hypatia-epistemics/hypatia-runtime: independent parallel review, each PASS with zero findings; hypatia-qa: independent review, PASS with one real test-coverage gap, closed before release; Abacus (route-llm): independent external review, NEEDS_LOCAL_VERIFICATION, independently converged on the same gap QA found plus resolved one NEEDS_VERIFICATION question against source; EVREN attempted and failed closed (no retry, per policy) |
| PR | #402, MERGED 2026-09-28T19:12:11Z, standard merge commit `3b138d38feb92d03aabf49a3fdbc9f833ead96d4` |
| origin/main reachability | verified: merge commit `3b138d38` has parents `9f06388a9bb8c624af5df7f567d100be041d33d9` (prior `origin/main`) and `9e28c7b9cf31fbcfd48f91e1d12197572db181e5` (this release); `git merge-base --is-ancestor 9e28c7b9 origin/main` succeeds |
| Blockers | none |

Post-merge verification (2026-09-29, hypatia-lead): PR #402 base `main`,
head `feature/validation-recipe-desktop-v0.3.423`, carried 10 changed files
(3 source, 2 test, 5 doc/version), matching this milestone's own stated
scope exactly. Both PR-triggered checks (`Linux desktop` run `36469985546`,
`Windows desktop` run `36469985557`) passed against the release SHA,
independently of the exact-SHA `workflow_dispatch` runs (`Linux desktop`
run `36467190195`, `Windows desktop` run `36467193736`) dispatched before
the PR was opened. Author/committer identity unchanged (Songül Kızılay via
GitHub noreply email, Claude Sonnet 5 co-author trailer preserved).

Rationale: with v0.3.420, v0.3.421, and v0.3.422 all delivered to
`origin/main` this session (verified below, Phase 5 main-health check
green — 7555 tests, `OK (skipped=3)`, all gates clean, all three release
SHAs confirmed ancestors via genuine 2-parent merges), read-only discovery
for the next Bug Bounty Researcher milestone inspected the actual desktop
architecture (`src/desktop/TkinterDesktopWindow.py`,
`ResearchSecurityFindingPanel.py`, `ResearchSecurityHypothesisPanel.py`,
`DesktopController.py`) rather than assuming the suggested title. v0.3.421
delivered the Validation Recipe application-service/store foundation with
explicitly no desktop panel, deliberately deferred. That foundation is
otherwise reachable only through raw Brain intents — no researcher-facing
surface exists for it yet. This is the smallest coherent next step:
`ResearchSecurityValidationRecipeApplicationService` was already fully
built, tested, and wired into `CognitiveEngine`/`Bootstrap`; the desktop
layer needed no `CognitiveEngine`/`Bootstrap`/service changes at all —
`DesktopController` methods only construct a `BrainRequest` and dispatch
through the already-existing Brain intents, exactly like every sibling
panel's controller methods.

Scope: `src/desktop/ResearchSecurityValidationRecipePanel.py` (new): a
subject block (program ID, subject kind combobox, subject ID — the
service has no program-wide listing, only a per-subject one, so load and
record share the same three fields), a multi-line steps entry (one step
per line, split/stripped/blank-filtered client-side) plus a notes entry, a
`Treeview` + detail pane listing that subject's recipes in persisted
append order. Reuses the exact `ttk.Treeview`/scrollbar/`<<TreeviewSelect>>`/
`iid -> detail-text` pattern `ResearchSecurityFindingPanel`/
`ResearchSecurityHypothesisPanel` already established, and imports
`SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE` (added in v0.3.421)
rather than restating it. Two new `DesktopController` methods
(`record_research_security_validation_recipe`,
`preview_research_security_validation_recipes`), matching the file's
existing local-validate-then-dispatch pattern exactly. One new tab in
`TkinterDesktopWindow.py`, wired inside the identical
`if self._program_scope_enrollment_service is not None:` gate already
wrapping the Findings/Hypotheses tabs — confirmed by a dedicated
`WindowReachabilityTests` negative case that a window built without that
service constructs no recipe panel and no "Load recipes" control. No
change to `ResearchSecurityValidationRecipeApplicationService`, its store,
or any Brain/CognitiveEngine wiring — this milestone is a pure UI layer.

VALIDATION RECIPE != AUTHORITY TO ACT, preserved structurally: no code
path added by this diff fetches, executes a tool, spawns a process, or
expands scope. A recipe's steps render as plain `ttk.Label` text in the
detail pane, never as a clickable or bound-command affordance; `_on_select`
only reads an already-loaded local dict and issues no request. Recording a
recipe cannot mutate its subject — confirmed directly from
`ResearchSecurityValidationRecipeApplicationService.record_validation_recipe`,
whose only subject-touching call is the existing read-only
`hypothesis_by_id`/`finding_by_id` existence check (no writer is even
injected into that service).

Review findings and how each was resolved:
- **hypatia-qa** found a concrete, real test-coverage gap: no test
  exercised `_render` with a successful, empty recipe list, so nothing
  distinguished "zero recipes recorded" from "the request failed" beyond
  incidental message text a future change could silently break.
  **Independently confirmed by Abacus's own review of the same diff**
  (its Finding 1, same root cause, same missing branch). **Closed**:
  added `test_render_distinguishes_a_successful_empty_result_from_a_failure`.
- **Abacus** separately raised a NEEDS_VERIFICATION question: whether the
  panel's independent `program_id` field was an isolation inconsistency
  versus other panels sharing a "current program" selector this one
  lacks. **Resolved by direct inspection, not left open**: grepped
  `ResearchSecurityFindingPanel.py`/`ResearchSecurityHypothesisPanel.py`
  — both already use the identical independent-per-panel
  `self.program_id = tk.StringVar(master=parent)` pattern; no shared
  "current program" selector exists anywhere in this desktop app for
  these tabs. Not an inconsistency.
- **Abacus** noted (Informational, explicitly "not a pinnable UI defect
  within this diff") that steps/notes are advisory-only free text with no
  redaction, and asked whether any downstream export/log path could turn
  this into an exfiltration surface. **Scoped out, not silently
  dropped**: this diff introduces no export/log path of any kind; it
  matches the identical precedent `ResearchSecurityFindingRecord.
  required_followup` already sets, cited in this panel's own module
  docstring. A downstream-export audit, if ever needed, is unrelated to
  this milestone's actual diff.
- **EVREN**'s live call failed closed (no diagnostic content — errors are
  suppressed to protect credentials, per the review helper's design). No
  retry, per policy. Abacus was tried as the independent external review
  instead of retrying the same provider, and completed cleanly.

Verification (2026-09-28, Windows canonical environment, hypatia-lead):
panel construction also smoke-tested directly in a real, withdrawn
`tk.Tk()` root (not just the `RecordingWidget` test harness, which never
builds a real widget tree) to catch any genuine Tkinter grid/layout
exception — succeeded with no exception. 24 new tests (16 panel + 8
controller) plus the full pre-existing suite, all green. Black, Ruff, and
MyPy (`src`) clean. `git diff --check` clean. `git status` on the branch
showed exactly 10 files touched (3 source, 2 test, 5 doc/version), no
unrelated or untracked changes.

## Historical scope: v0.3.419 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Security Hypothesis creation-time subject-binding symmetry (Bug Bounty foundation, step 6 continued) |
| Base SHA | b52c23f (v0.3.418 delivery reconciliation) |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer; hypatia-security: independent review, PASS; hypatia-epistemics: independent review, PASS; hypatia-runtime: independent review, PASS; hypatia-qa: independent review, PASS-with-caveats (one non-blocking test-strength recommendation, applied); hypatia-lead: release |
| Blockers | none |

Rationale: closes the last named residual gap explicitly deferred by the
v0.3.418 ledger's own Non-goals. `create_hypothesis` required only "at
least one" cited supporting-evidence item to match the new hypothesis's
declared `subject_kind`/`subject_canonical_value`, yet unconditionally
turned *every* cited evidence ID into a `SUPPORTS` link regardless of
whether it individually matched — so a mismatched-subject citation riding
alongside one matching citation in the same creation call could still
become a spurious `SUPPORTS` link, the exact defect class already fixed on
`ResearchSecurityFindingApplicationService.attach_evidence` (v0.3.417) and
`ResearchSecurityHypothesisApplicationService.attach_evidence` (v0.3.418).

Investigated directly, not assumed: a prior hypatia-runtime review
(v0.3.417 ledger entry) had characterized this "at least one" aggregation
as *intentionally* different from `attach_evidence`'s "all must match" —
reasoning that `create_hypothesis` "establishes" a hypothesis's initial
subject from its evidence while `attach_evidence` merely "gates an
addition" to an already-established one. This session's hypatia-epistemics
review traced the actual code and found that framing unsupported:
`subject_kind`/`subject_canonical_value` are explicit, caller-supplied
parameters to `create_hypothesis`, never derived from or established by
the cited evidence at any point — structurally identical to `attach_evidence`,
which likewise never derives a hypothesis's subject from evidence, just
reads it from an already-persisted field instead of a fresh parameter. The
evidence-matching check in both methods is the same anti-hallucination/
provenance-integrity floor, not two different design intents. This
supersedes and corrects the v0.3.417 runtime note.

Also considered and rejected this session (read-only investigation before
locking): F4 (lifecycle replay validation on load) remains real engineering
surface — a point-in-time evidence-gate replay, an import-cycle-safe way to
share validation logic between the `research` store and `cognition`
application service, and a new replay-equivalence characterization test —
correctly sized for its own dedicated future milestone, not this one. The
next roadmap item after the delivered evidence-hypothesis-finding chain
(`docs/Roadmap/Master_Roadmap.md`'s Bug Bounty Researcher priority order,
item 8, "Business-logic/state-transition model") has no existing precedent
or design in this codebase and is not size-appropriate for a bounded
milestone; it is left for a future dedicated design pass. This milestone
is chosen per the stated preference order: it closes a real, confirmed
correctness gap, is small and reviewable, needs no schema change, is fully
deterministic, and is meaningful progress on the already-delivered
Hypothesis/Finding lifecycle line.

Scope: `ResearchSecurityHypothesisApplicationService.create_hypothesis`
(`src/cognition/ResearchSecurityHypothesisApplicationService.py`) only —
the subject-matching check changes from `any(...)` ("at least one cited
evidence item matches") to a `mismatched_subject` tuple check mirroring
`attach_evidence`'s exact aggregation shape ("every cited evidence item
must match, or the whole call is refused"). The check runs strictly before
`self._load()`/`self._save()`, so refusal is fail-closed with zero partial
persistence — no hypothesis, and no evidence link, is ever written on
refusal. Docstring and module-level docstring updated to match. No schema
or on-disk document change of any kind; no change to `attach_evidence` or
`transition_status` (both already correct since v0.3.418); no new evidence
relation, status, or kind.

Non-goals (exhaustive): no F4 lifecycle-replay work; no request-ID/
correlation-ID persistence; no change to any Finding-side file (already
strict since v0.3.417); no new roadmap capability (item 8 or later); no
schema/version bump in either store; no agent autonomy, new tool
execution, Safe Tool Gateway work, model-output authority, network
capability, or any authority/budget/target/credential change of any kind.

Security invariants (unchanged, restated): hypothesis creation must never
execute a network request, spawn a process, run a tool, or modify scope/
credential/budget/target state. A hypothesis's supporting evidence must
actually describe the hypothesis's own subject in full, not merely share
its program or partially match. MODEL OUTPUT != AUTHORITY; SUBAGENT OUTPUT
!= AUTHORITY.

Acceptance criteria:
- `create_hypothesis` refuses a mixed citation set (one matching, one
  mismatched) in a single call, in full — nothing is persisted.
- A single mismatched citation continues to be refused (pre-existing
  coverage, unaffected in outcome, renamed for clarity).
- A genuinely all-matching multi-citation call continues to succeed and
  every cited evidence ID is linked as `SUPPORTS`.
- Every existing v0.3.415/v0.3.416/v0.3.417/v0.3.418 regression fixture is
  unaffected — no fixture in this codebase relied on the old "at least
  one" behavior with a genuinely mismatched co-citation.

Test strategy: renamed the pre-existing single-citation-mismatch test for
accuracy (no behavior change); replaced the old positive
"at-least-one-of-several-succeeds" test with a same-named-pattern negative
test proving the whole mixed-citation call is refused and nothing is
persisted (`hypotheses_for_program(...) == ()`); added a new positive test
proving an all-matching multi-citation call succeeds and asserting the
exact linked evidence IDs and `SUPPORTS` relation (tightened per
hypatia-qa's non-blocking review recommendation, applied); full differential
run of the 45-test module plus the store's own test file.

Mutation strategy: one targeted mutant (temporarily reverting the
`mismatched_subject` check back to the old `any(...)` check) applied and
reverted via direct file edit under version control (not written to any
committed state), confirming exactly one test
(`test_a_mixed_citation_set_is_rejected_in_full`) fails under the mutant
and all 11 sibling `CreateHypothesisTests` remain green — non-vacuous,
narrowly targeted.

Security review (hypatia-security): PASS. Confirmed the check precedes
every read/write in the method with no partial-persistence path; confirmed
no authority/budget/replay/provenance invariant is touched; confirmed
program isolation is unaffected (evidence is still scoped to
`_evidence_for_program` before the subject check ever runs); confirmed the
new error message is textually distinct from every other error this method
raises.

Epistemics review (hypatia-epistemics): PASS. Independently traced
`create_hypothesis`'s parameters to confirm the subject is never
evidence-derived, correcting the v0.3.417 runtime note's "different call
semantics" framing; confirmed every existing fixture citing more than one
evidence ID together already used only matching subjects; confirmed the
desktop panel test calls a mock, not the real service, and is unaffected;
ran the full module (45/45) and `mypy` on the touched file.

Runtime review (hypatia-runtime): PASS, no caveats. Confirmed zero diff in
any store/persistence file and zero wiring change in `CognitiveEngine.py`
(the actual construction site — not `Bootstrap.py`); grepped `src/` for
any other independent subject-vs-evidence comparison and found only the
sibling Finding-side `attach_evidence`, already correct and untouched;
confirmed rollback safety (pure logic change, no persisted-data migration
concern); ran 78/78 tests across the module and the store's own test file.

QA review (hypatia-qa): PASS-with-caveats. Directly traced the removed
`any(...)` logic against the new mixed-citation fixture to confirm it is a
genuine behavioral discriminator, not a wording-only change; confirmed the
"nothing persisted on refusal" assertion documents the fail-closed
invariant even though it cannot currently fail independently of the
accompanying `assertRaisesRegex`, given the single-write-path architecture;
one non-blocking recommendation — tighten the new positive test to assert
exact linked evidence IDs and relation, not just a count — applied by
hypatia-lead before release; confirmed zero diff to the desktop panel test.

Release gates (Windows canonical environment, hypatia-lead): 7453 tests,
OK (skipped=3) — 1 net new test over v0.3.418's 7452; Black, Ruff, and
MyPy (601 source files) clean; `git diff --check` clean (the same
pre-existing CRLF-on-disk normalization warning as every prior milestone,
not introduced by this diff).

## Historical scope: v0.3.418 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Hypothesis Evidence subject-binding symmetry (Bug Bounty foundation, step 6 continued) |
| Base SHA | b4a4f257d00845fbf77e9af62abd81e64f9048a9 |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer; hypatia-security: independent review, PASS, no findings; hypatia-epistemics: independent review, PASS-with-caveats, one accurate residual-gap finding folded into Non-goals/Deferred above, no defect in delivered code; hypatia-qa: independent review, PASS, full acceptance-criterion traceability; hypatia-runtime: independent review, PASS, no caveats; hypatia-lead: release |
| Blockers | none |

Rationale: bounded continuation of roadmap item 6/7, closing a deferred
finding named explicitly in v0.3.417's own ledger. Three candidate next
directions were investigated read-only in parallel by hypatia-epistemics,
hypatia-security, hypatia-runtime, and hypatia-qa (2026-09-28) before this
lock: (A) the symmetric F1-class subject-binding gap on the Hypothesis
side's own `attach_evidence`; (B) F4 lifecycle replay validation on store
load; (C) request-ID/correlation-ID persistence into research records for
a future replay layer. All four specialists converged: (A) is small,
precedented, zero schema impact, and ready now; (B) is not actually an
undecided product-policy fork — the codebase's own precedent
(`JsonFileVulnerabilityGraphStore`, which already replays business-rule
invariants via the same runtime mutation methods used on write, and is
reject-whole; zero quarantine precedent exists anywhere in this codebase)
already decides "reject whole document on any violation" — but its correct
implementation is nontrivial engineering (a point-in-time evidence-gate
replay simulating append order rather than final state, a
research/cognition import-cycle-safe way to share the validation logic
between the store and the application service, and a new characterization
test proving the replay is exactly as permissive as the write path, so the
store never becomes stricter than legitimate history) and is deliberately
NOT bundled into this narrow milestone; (C) was rejected outright — a full-
tree grep for "correlation" found zero hits, no existing reader/audit/
replay mechanism ever joins a research record back to its originating
`BrainRequest`, and the one existing request-ID precedent
(`ResearchMissionAudit.mission_request_id`) is a different, already-
authority-bearing autonomous-mission subsystem, not evidence of a live gap
here — speculative architecture with no observed pain point, correctly
rejected per this investigation's own instruction to reject speculative
justification.

Severity of (A), stated precisely per the security/epistemics reviews:
provenance-integrity hardening, not authority-escalation. Traced the worst
case directly: `ResearchSecurityHypothesisEvidenceRelation` has only
`SUPPORTS`/`CONTRADICTS` (no `VALIDATES` member exists on the Hypothesis
side at all), and `create_finding`'s `_carried_relation` can therefore
never turn carried-forward hypothesis evidence into a `VALIDATES` link on
a finding — the sole gate for `VALIDATED`. So subject-mismatched evidence
smuggled into a hypothesis via the unfixed `attach_evidence`, then carried
forward into a finding, can only ever add a spurious `SUPPORTS` (no effect
on any gate) or a spurious `CONTRADICTS` (over-conservative, blocks
validation) — never a false `VALIDATED` finding. This matches, and closes
the remaining half of, the exact deferred-findings note already recorded
in v0.3.417's own ledger entry above.

Scope: mirror the exact F1 fix pattern v0.3.417 already delivered and
independently reviewed clean on the Finding side, applied to
`ResearchSecurityHypothesisApplicationService.attach_evidence`
(`src/cognition/ResearchSecurityHypothesisApplicationService.py:231-292`),
plus one bundled, same-file/same-method-family test-coverage gap QA found
during this investigation: `attach_evidence` under the wrong `program_id`
is covered only by a loose `assertRaisesRegex(ResearchError, "was not
found")` inside `AttachEvidenceTests`
(`tests/cognition/test_research_security_hypothesis_application_service.py:533-546`)
rather than the precise, M21-style message assertion inside
`ProgramIsolationTests`, and `transition_status` under the wrong
`program_id` (the M22-equivalent case) has no test at all in this file.

In scope:
- `attach_evidence`: change the existing boolean `any(...)` hypothesis
  lookup (lines 255-259) into a bound-record lookup (mirroring
  `next(...)`-style lookup already used on the Finding side), then add a
  subject-binding check comparing every cited evidence's `target_kind`/
  `target_canonical_value` against the *matched hypothesis's own*
  `subject_kind`/`subject_canonical_value` — "all cited evidence in this
  call must match" (the same aggregation v0.3.417 used, not
  `create_hypothesis`'s "at least one", per the same reasoning: this
  method gates an *addition* to an already-subject-established record, so
  every citation in one call should describe that subject, not merely one
  of them). Applied to both relations (`SUPPORTS`/`CONTRADICTS` — there is
  no `VALIDATES` on this side to also cover).
- Add a `ProgramIsolationTests`-style regression test proving
  `attach_evidence` itself refuses a real hypothesis ID under the wrong
  program with the exact service-level message, and a new
  `transition_status`-under-wrong-program test (the M22-equivalent case),
  closing the coverage gap QA identified — same file, same method family,
  no scope widening.

Non-goals (exhaustive): no change to `create_hypothesis`'s existing "at
least one" subject check — deliberately out of scope, NOT because it is
already correct: hypatia-epistemics's 2026-09-28 review traced it end to
end and found that once at least one citation matches, `create_hypothesis`
still turns *every* `supporting_evidence_ids` entry into a `SUPPORTS` link
(`ResearchSecurityHypothesisApplicationService.py:210-221`), including any
that fail the subject match — the same class of spurious-`SUPPORTS`-link
gap this milestone fixes for `attach_evidence`, just unaddressed at the
creation call site. This is a known, separately-scoped residual gap
(recorded in Deferred findings below), not a closed one; severity is
unaffected by leaving it deferred (still `SUPPORTS`-only, structurally
incapable of reaching `VALIDATES`, per the Rationale above). No change to
`ResearchSecurityFindingApplicationService`/any Finding-side
file (v0.3.417 already closed that half); no F4 lifecycle-replay work of
any kind (deferred, see Rationale, needs its own dedicated milestone given
the real engineering surface identified); no request-ID/correlation-ID
work; no schema/version bump in either store; no new evidence relation,
status, or kind; no agent autonomy, new tool execution, Safe Tool Gateway
work, model-output authority, network capability, or any authority/
budget/target/credential change of any kind.

Security invariants (unchanged, restated): hypothesis evidence attachment
must never execute a network request, spawn a process, run a tool, or
modify scope/credential/budget/target state. Program isolation must be
independently provable at the service layer for `attach_evidence`/
`transition_status`, not merely incidentally caught by the store's
fallback check. A hypothesis's supporting/contradicting evidence must
actually describe the hypothesis's own subject, not merely share its
program. MODEL OUTPUT != AUTHORITY; SUBAGENT OUTPUT != AUTHORITY;
`READY_FOR_VALIDATION` remains never a confirmed anything, untouched by
this milestone.

Acceptance criteria:
- `attach_evidence` refuses evidence whose `target_kind`/
  `target_canonical_value` differs from the hypothesis's own
  `subject_kind`/`subject_canonical_value`, for both `SUPPORTS` and
  `CONTRADICTS`; a matching-subject case, and every existing regression
  fixture (which already uses matching subjects throughout), continue to
  succeed unchanged.
- A mixed citation set in one call (one matching, one mismatched) is
  refused in full — proving "all must match," not "at least one."
- `attach_evidence`/`transition_status` called with a real hypothesis ID
  under the wrong program each raise the exact existing service-level
  error, independent of the store's fallback check.
- Full existing v0.3.415/v0.3.416/v0.3.417 regression suites unaffected;
  no existing accept/refuse outcome changes.

Test strategy: subject-mismatch negative tests for both relations
(`SUPPORTS`/`CONTRADICTS`) plus a mixed-citation-set negative test, added
to `AttachEvidenceTests`; the existing positive fixtures already exercise
the matching-subject path, so no new positive test is required; two new
`ProgramIsolationTests` cases (`attach_evidence`, `transition_status`)
asserting the precise service-level message; a differential run of every
existing v0.3.415/v0.3.416/v0.3.417 fixture proving no accept/refuse
outcome changes; impacted suites focused first, full canonical gates once
at release.

Mutation strategy: deliberate local mutants (via in-memory monkeypatching,
never written to disk, mirroring v0.3.417's own method) for at least —
remove the new subject-binding check from `attach_evidence`; allow a
mixed-citation set through; remove the service-level program check from
`attach_evidence`; remove it from `transition_status`. Every meaningful
mutant must be caught.

Affected architectural layers: `cognition` only (one application service's
authorization logic) — `research` types/records, persistence schema,
desktop panel, and Brain intent surface all untouched.

Rollback expectations: pure logic change over already-existing fields, no
schema/version bump, no persisted-data mutation; rollback is a plain
revert of the release commit with zero data-migration concern.

Deferred findings carried forward: F4 (lifecycle replay validation on
load) — design recommendation from hypatia-runtime's 2026-09-28 review:
"reject whole document" on any business-rule-invariant violation is
already the security-consistent, precedent-matching default (not an open
policy fork), but implementation requires a point-in-time evidence-gate
replay (not a final-state check), a research/cognition import-cycle-safe
way to share validation logic between the store and application service,
and a new characterization test proving replay-equivalence to the write
path — real engineering surface for its own dedicated future milestone,
not bundled here. Request-ID/correlation-ID persistence — rejected as
speculative, no live traceability problem found; revisit only if a real
replay/evaluation layer is ever actually proposed. The Windows
`ResourceWarning` test-hygiene debt remains untraced and out of scope.
`create_hypothesis`'s own residual spurious-`SUPPORTS`-link gap (found by
hypatia-epistemics's 2026-09-28 review, see Non-goals above) — same defect
class as this milestone's fix, deliberately deferred to keep this milestone
narrow; severity unaffected (still `SUPPORTS`-only, never `VALIDATES`).

Security review (hypatia-security, 2026-09-28): PASS, no findings. Confirmed
the bound-record lookup (`next(...)`, requiring both `hypothesis_id` and
`program_id`) precedes any subject/evidence work; confirmed the subject
check applies to both `SUPPORTS`/`CONTRADICTS` uniformly and reuses the
exact comparison already proven at `create_hypothesis` with a correctly
different, stricter aggregation; confirmed the two new program-isolation
tests assert the precise service-level message, textually distinct from
the store's own dangling-reference wording, making them non-vacuous;
confirmed no new I/O/subprocess/socket/tool surface, no schema/version
bump, and every stated non-goal held.

Epistemics review (hypatia-epistemics, 2026-09-28): PASS-with-caveats. Ran
the tests and traced the diff directly rather than accepting the ledger's
claims. Confirmed the "all must match" aggregation is genuinely
implemented and correctly reasoned; confirmed the severity characterization
(provenance-integrity, never authority-escalation) by independently
re-tracing `_carried_relation`'s exhaustive `SUPPORTS`/`CONTRADICTS`
mapping and the `VALIDATED` gate's `VALIDATES`-only requirement; confirmed
both new tests are genuinely non-vacuous (the old code had no subject-
comparison branch at all); confirmed no regression to F2/F3; confirmed
zero store diff. One caveat, already corrected above: found that
`create_hypothesis`'s own "at least one" check still lets a
mismatched-subject citation become a spurious `SUPPORTS` link at creation
time — the ledger's original "already correct" framing for that Non-goal
was inaccurate and has been rewritten to state it as a known, deliberately
deferred residual gap instead (severity unaffected either way).

QA review (hypatia-qa, 2026-09-28): PASS. Built a full acceptance-criterion
traceability table; ran the full 44-test module directly (`OK`) plus the
untouched 64-test Finding-side sibling as a cross-check (`OK`). Confirmed
the mixed-citation test is constructed to genuinely distinguish "all must
match" from "at least one" by fixture design, not merely by regex wording
— an "at least one" implementation would fail to raise on that fixture.
Confirmed the pre-existing looser `test_hypothesis_from_a_different_program_is_rejected`
test was preserved, not replaced; confirmed the two new program-isolation
messages are textually disjoint from the store's own error wording;
confirmed `tests/research/test_json_file_research_security_hypothesis_store.py`
shows zero diff.

Runtime review (hypatia-runtime, 2026-09-28): PASS, no caveats. Confirmed
zero diff in the store and in `Bootstrap.py`; confirmed the new check
reuses the single existing `_evidence_for_program` call, no second
evidence-loading path; grepped the whole `src/` tree for any other
independent subject/target comparison and found only display-only
formatting in the desktop panel and response composer, nothing needing
this fix; confirmed rollback safety (no new persisted field, plain revert
restores prior behavior exactly); re-ran `RestartReloadTests`, `OK`.

Mutation pass (2026-09-28, hypatia-lead): four targeted mutants applied via
in-memory monkeypatching, never written to any file on disk (mirroring
v0.3.417's own method) — remove the subject-binding check from
`attach_evidence`; allow a mixed-citation set through; remove the
service-level program check from `attach_evidence`; remove it from
`transition_status`. All four caught; all four control runs against the
real, unmutated code passed beforehand.

Release gates (2026-09-28, Windows canonical environment, hypatia-lead):
7452 tests, OK (skipped=3) — 4 net new tests over v0.3.417's 7448; Black,
Ruff, and MyPy (601 source files) clean; `git diff --check` clean (one
pre-existing CRLF-on-disk file unrelated to this diff, normalized by git
per `.gitattributes` on the next touch, as for every text file in this
repository — not introduced by this milestone). Linux exact-SHA CI pending
dispatch.

## Historical scope: v0.3.417 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Finding Lifecycle evidence-integrity hardening (Bug Bounty foundation, step 7 continued) |
| Base SHA | 223fb1b5ce7854604eb022cde3f9b8d75bc019d8 |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer (surgical, related-surface fix across two application services and two derived read models), plus mutation pass; hypatia-security: independent review, PASS, no findings above informational; hypatia-epistemics: independent review, PASS-with-caveats, two non-blocking documentation/epistemic notes, no defects; hypatia-qa: independent review, PASS, full acceptance-criterion traceability; hypatia-runtime: independent review, PASS, no missed derivation call sites, zero wiring/schema drift; hypatia-lead: release |
| Blockers | none |

Rationale: bounded continuation of roadmap item 7, closing deferred findings
from the delivered v0.3.416 Finding Lifecycle foundation's own security and
QA reviews (`docs/dev/MILESTONE.md`, "Historical scope: v0.3.416") without
opening any new authority, execution, or provenance surface. Four candidate
items were investigated read-only in parallel by hypatia-epistemics,
hypatia-security, hypatia-runtime, and hypatia-qa (2026-09-27) before this
lock: F1/F2 (evidence-integrity gaps in `ResearchSecurityFindingApplicationService`),
F3 (wall-clock-dependent status ordering, inherited from v0.3.415), F4
(no lifecycle-replay validation on load), the M21/M22 mutation-survivor
gap, agent-output trust boundaries, and Safe Tool Gateway groundwork. F4,
trust-class taxonomy, and tool-execution architecture were all found to
require either a real design decision or a real new capability that does
not yet exist, and are explicitly deferred (see Non-goals). F1/F2/F3 and
M21/M22 are small, mechanical, and precedented, and are locked here.

F3 scope decision (2026-09-27, hypatia-lead, direct code inspection — not
assumed from the deferred-finding prose): traced
`ResearchSecurityFindingApplicationService.create_finding`
(`src/cognition/ResearchSecurityFindingApplicationService.py:167-168`),
which gates finding creation on `hypothesis.status is
ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION`. `hypothesis.status`
is the v0.3.415 `ResearchSecurityHypothesis` derived read model's own
`_latest_status` (`src/research/ResearchSecurityHypothesis.py:131-139`),
which sorts transitions by `(entry.recorded_at, entry.transition_id)` —
byte-for-byte the same wall-clock/random-UUID-tiebreak defect described for
the Finding side, independently duplicated a third and fourth time in
`ResearchSecurityHypothesisApplicationService._current_status`
(`src/cognition/ResearchSecurityHypothesisApplicationService.py:641-655`).
Because `create_finding`'s own allow/deny gate reads this exact
Hypothesis-derived value, a wall-clock regression at the Hypothesis layer
can misorder its transitions and cause `create_finding` to see a stale
`status` — silently permitting promotion from a hypothesis whose true
latest state is not `READY_FOR_VALIDATION` (e.g. a later `REFUTED`
correction hidden behind an earlier-recorded `READY_FOR_VALIDATION`), or
wrongly refusing a legitimately ready one. Fixing only the Finding-side
derivation would leave this gate exposed to exactly the defect this
milestone exists to close. Per the user's own stated preference hierarchy
(correctness, then security invariants, then determinism, then minimal
scope, then architectural consistency), **Option B is chosen**: the
ordering fix is applied symmetrically to both derived read models
(`ResearchSecurityFinding._latest_status`/`ResearchSecurityHypothesis._latest_status`)
and both application services' internal `_current_status` helpers — four
call sites, one bug, no schema change in any of them. This was not a case
of two indistinguishable options, so no user check-in was needed.

Scope: a surgical, non-schema-changing hardening pass over the v0.3.416
Finding Lifecycle's evidence-attachment, finding-creation, and
status-derivation logic, extending into the two v0.3.415 Hypothesis-side
derivation call sites strictly for the F3 ordering fix identified above
(no other Hypothesis-side file, type, or behavior changes).

In scope:
- **F1** (Medium, from v0.3.416 security review): `ResearchSecurityFindingApplicationService.attach_evidence`
  gains a subject-binding check — reusing, not reinventing, the exact
  `target_kind`/`target_canonical_value`-vs-`subject_kind`/`subject_canonical_value`
  comparison already proven correct at hypothesis creation
  (`ResearchSecurityHypothesisApplicationService.create_hypothesis`,
  lines 166-174) — applied to all three relations
  (`SUPPORTS`/`CONTRADICTS`/`VALIDATES`), so evidence about a different
  subject in the same program can no longer support, contradict, or
  (critically) validate a finding it does not actually describe.
- **F2** (Low): `create_finding` independently re-verifies every
  evidence ID carried forward from the source hypothesis against the live
  HTTP evidence store for the same program before persisting the new
  finding document; a missing ID fails the whole creation closed (no
  partial/silent drop), and the source hypothesis itself is never mutated.
- **F3** (Low, inherited from v0.3.415; scope per the decision above):
  `ResearchSecurityFinding._latest_status`/its transitions-sort, and the
  matching helpers in `ResearchSecurityFindingApplicationService`,
  `ResearchSecurityHypothesis._latest_status`/its transitions-sort, and
  `ResearchSecurityHypothesisApplicationService._current_status` all switch
  from `(recorded_at, transition_id)` ordering to trusting the
  already-persisted append-only list/tuple position as the sole ordering
  signal (`recorded_at` remains a stored, displayed field — it is simply no
  longer used to compute *which* transition is latest). No schema version
  bump: this reads fields and positions that already exist on disk today.
- **M21/M22** (mutation-survivor gap, from v0.3.416's own mutation pass):
  two new regression tests proving `attach_evidence`/`transition_status`
  themselves — not merely the store's document-level fallback — refuse a
  real finding ID under the wrong `program_id`, with the exact service-level
  error message asserted. The store's existing dangling-reference check is
  kept exactly as-is (defense in depth, not redundancy to be removed).

Non-goals (exhaustive): no lifecycle replay validation on load (F4 —
deferred, needs a reject-vs-quarantine design decision this milestone does
not make); no persisted sequence-number field or schema/version change of
any kind (the F3 fix uses data already on disk); no change to
`ResearchSecurityHypothesisRecord`/`Status`/`Origin`/`EvidenceKind`/
`EvidenceRelation`/`create_hypothesis`/`attach_evidence`/`transition_status`
business logic (only the two narrow `_latest_status`/`_current_status`
ordering helpers are touched, strictly for F3); no agent autonomy, new tool
execution, Safe Tool Gateway generalization, model-output authority,
network capability, automatic exploitation, credential expansion, target
expansion, or budget expansion of any kind; no generic trust-class/
provenance-metadata taxonomy (`origin_agent`/`source_type`/`trust_class`/
`correlation_id`/`parent_action_id`) — no automatic finding/hypothesis
producer exists to warrant it; no broad correlation/replay architecture
(the dormant `src/tools/ToolExecutionOutcome` correlation-ID pattern stays
unwired); no unrelated cleanup; no Windows ResourceWarning fix (confirmed
by hypatia-qa's 2026-09-27 read-only review to originate outside the
Finding/Hypothesis store and test code, which are fully context-manager-safe) —
it is fixed here only if a test this milestone directly touches proves the
leak belongs to this feature, which is not expected.

Security invariants (unchanged, restated): MODEL OUTPUT != AUTHORITY;
SUBAGENT OUTPUT != AUTHORITY; a `VALIDATED` finding is never authority to
act (`means_confirmed_vulnerability` stays `False` for every status,
untouched by this milestone). Finding evidence attachment, finding
creation, and status transitions/derivation must never execute a network
request, spawn a process, run a tool, or modify scope/credential/budget/
target state — reasoning over already-recorded evidence and already-
persisted history only. Program isolation must be independently provable
at the service layer for `attach_evidence`/`transition_status`, not merely
incidentally caught by the store's fallback check. A finding's evidentiary
state (supporting/contradicting/validating) must actually describe the
finding's own subject, not merely share its program.

Acceptance criteria:
- `attach_evidence` refuses evidence whose `target_kind`/`target_canonical_value`
  differs from the finding's `subject_kind`/`subject_canonical_value`, for
  all three relations; a matching-subject case still succeeds unchanged.
- A finding cannot reach `VALIDATED` via subject-mismatched `VALIDATES`
  evidence even when relation/gate conditions otherwise hold.
- `create_finding` refuses when any carried-forward evidence ID no longer
  exists in the live evidence store for that program; succeeds unchanged
  when all exist; never mutates the source hypothesis.
- A transition sequence containing a later-appended, earlier-`recorded_at`
  entry (backward clock, or same-instant transitions) still derives the
  correct append-order latest status, identically for both
  `ResearchSecurityFinding` and `ResearchSecurityHypothesis`, and
  identically whether read via the derived model or the application
  service's own internal helper.
- `attach_evidence`/`transition_status` called with a real finding ID under
  the wrong program each raise the exact existing service-level error,
  independent of the store's fallback check.
- Full existing v0.3.415/v0.3.416 regression suites unaffected; no existing
  accept/refuse outcome changes.

Test strategy: positive/negative subject-binding tests for all three
evidence relations on `attach_evidence`, including a dedicated
subject-mismatched-`VALIDATES` negative case; a carried-evidence
existence-at-creation test (missing ID refused, all-present case
unaffected, source hypothesis unmutated); a dedicated backward-clock
regression test at each of the four touched derivation call sites
(delivered as an inline mutable-clock closure per test rather than a
shared named helper — a naming discrepancy from this section's original
"_regressing_clock helper" wording, flagged by hypatia-epistemics's review
as documentation-only, not a functional gap) exercising both subsystems'
derivation paths (derived-model and application-service helper) under a
backward clock step and under same-instant transitions;
two new `ProgramIsolationTests` cases for `attach_evidence`/
`transition_status` asserting the service-level error message directly;
a differential run of every existing v0.3.415/v0.3.416 fixture proving no
accept/refuse outcome changes; impacted suites focused first, full
canonical gates once at release.

Mutation strategy: deliberate local mutants (or equivalent targeted checks)
for at least — remove the service-level program check from
`attach_evidence`; remove it from `transition_status`; allow wrong-subject
evidence into any of the three relations; skip carried-evidence
revalidation in `create_finding`; accept a missing carried evidence ID;
accept cross-program carried evidence; restore `(recorded_at,
transition_id)` sorting in any of the four touched derivation call sites;
regress the clock ordering fix specifically. Every meaningful mutant must
be caught; if any survives due to genuine redundant defense in depth (as
M21/M22 did in v0.3.416), that must be proven with an explicit test and
documented as harmless, not silently accepted.

Affected architectural layers: `cognition` (both application services'
authorization/derivation logic) and `research` (both derived read models'
ordering) — persistence schema, desktop panels, and Brain intent surface
untouched.

Rollback expectations: every change is a pure logic change over
already-existing fields with no schema/version bump and no persisted-data
mutation; rollback is a plain revert of the release commit with zero
data-migration concern in either direction.

Deferred findings carried forward unchanged: F4 (lifecycle replay
validation on load — needs a reject-vs-quarantine design decision); the
symmetric F1-class subject-binding gap in
`ResearchSecurityHypothesisApplicationService.attach_evidence` (same defect
class as Finding's F1, confirmed present by hypatia-epistemics's 2026-09-27
review, deliberately left for a future, separately-scoped Hypothesis-side
milestone rather than bundled here) — that same review also noted one
downstream, fail-closed-direction consequence worth tracking alongside it:
a carried-forward `CONTRADICTS` link inherited from a hypothesis whose own
evidence was never subject-checked could, in principle, wrongly block a
finding from ever reaching `VALIDATED` (over-conservative, never a false
validation, so no acceptance criterion is violated by leaving it deferred);
request-ID/correlation-ID persistence
into research records; origin/trust-class taxonomy; Safe Tool Gateway
generalization; the Windows ResourceWarning test-hygiene debt.

Security review (hypatia-security, 2026-09-27): PASS, no findings above
informational. Confirmed program isolation is independently enforced at
the service layer for `attach_evidence`/`transition_status`; confirmed the
F1 subject-binding check applies unconditionally to all three relations
including `VALIDATES`, so a finding can never reach `VALIDATED` via
subject-mismatched evidence; confirmed F2 fails the whole `create_finding`
closed before any write and never mutates the source hypothesis; confirmed
the F3 ordering fix only re-derives which already-real, already-persisted
transition is "latest" and can never fabricate or drop a transition;
confirmed `JsonFileResearchSecurityFindingStore.save()`'s append-only
prefix-preservation check (which the F3 fix depends on) is unchanged;
confirmed no new I/O, subprocess, socket, or tool-execution surface
anywhere in the diff; confirmed every stated non-goal held (no schema/
version bump in either store, no correlation-ID/trust-class/tool-gateway
code, no change to Hypothesis-side business logic beyond the two ordering
helpers). One informational, non-blocking observation: a direct hand-edit
of a persisted JSON file that reorders `status_transitions` is undetected
under both the old and new ordering scheme alike — a pre-existing risk,
correctly deferred to F4, not worsened by this milestone.

Epistemics review (hypatia-epistemics, 2026-09-27): PASS-with-caveats.
Independently re-derived the append-only guarantee from both stores'
`save()` methods rather than trusting docstrings, confirming list position
is a legitimate causal-order proxy. Confirmed the F3 scope decision's
premise directly in code: `create_finding`'s `READY_FOR_VALIDATION` gate
reads `hypothesis.status`, which is exactly `ResearchSecurityHypothesis`'s
own (now-fixed) derivation. Confirmed carried evidence links can only ever
be `SUPPORTS`/`CONTRADICTS` — `ResearchSecurityHypothesisEvidenceRelation`
has no `VALIDATES` member at all — so a carried link can structurally
never satisfy the `VALIDATED` gate regardless of subject, closing the
highest-severity path by construction, not merely by convention. Traced
each backward-clock test against the real state-transition tables to
confirm the old `(recorded_at, transition_id)` sort would have produced a
different, wrong answer in every case (non-vacuous, not cosmetic). Two
caveats, both non-blocking, both folded into this section already: the
`_regressing_clock`-helper wording mismatch (Test strategy, above) and the
carried-`CONTRADICTS`-subject edge case (Deferred findings, above).

QA review (hypatia-qa, 2026-09-27): PASS. Built a full acceptance-criterion
traceability table; every criterion maps to a specific, run, passing test.
Independently ran the four impacted test modules (199 tests, OK) and
confirmed both `JsonFileResearchSecurityFindingStore`/
`JsonFileResearchSecurityHypothesisStore` test files show zero diff,
supporting the "no schema/store change" claim. Confirmed the M21/M22 tests
are genuinely discriminating by tracing what a mutant deleting only the
service-layer program check would actually produce (a different, non-
matching error message surfacing from a downstream check instead), not
merely inspecting the test in isolation. Confirmed all four F3 call sites
have their own dedicated backward-clock test, not one shared test standing
in for all four. Confirmed the two renamed ordering tests
(`test_derives_latest_status_by_append_order`,
`test_append_order_wins_over_transition_id_at_the_same_instant`) are
strictly stronger than what they replaced, not weaker.

Runtime review (hypatia-runtime, 2026-09-27): PASS. Grepped the full
`src/` tree for any other place deriving a "latest status" for either
subsystem and confirmed every other consumer (`ResponseComposer`,
`ResearchSecurityFindingPanel`) reads `status_history[-1]` from the same
already-fixed `transitions` tuple — no missed, independently-sorting call
site. Confirmed zero diff in both stores and in `Bootstrap.py` (no wiring,
schema, or constructor change of any kind). Confirmed F2 reuses the
existing `_evidence_for_program` helper rather than adding a second
evidence-loading path. Confirmed rollback safety: no new field is written
to any persisted document, so a plain revert of the four production files
fully restores prior behavior with no leftover incompatible state. One
informational note: `attach_evidence`'s "all cited evidence must match
subject" aggregation intentionally differs from `create_hypothesis`'s "at
least one must match" aggregation — appropriate to their different call
semantics (gating an addition vs. establishing initial subject), not an
inconsistency.

Mutation pass (2026-09-27, hypatia-lead): six targeted mutants applied via
in-memory monkeypatching, never written to any file on disk — this
workstation's own tooling guard correctly refused a transient on-disk edit
that removed a program-isolation check, confirming the guard itself is
live; the mutation pass was completed safely by monkeypatching the target
method onto the real class in a throwaway script instead. Mutants: M21
(service program check removed from `attach_evidence`), M22 (same, for
`transition_status`), F1 (subject-binding check removed), F2 (carried-
evidence revalidation removed), and F3 at both the derived-model and
application-service layers (old `(recorded_at, transition_id)` sort
restored). All six caught; all six control runs against the real,
unmutated code passed beforehand, confirming the harness itself was sound.

Release gates (2026-09-27, Windows canonical environment, hypatia-lead):
7448 tests, OK (skipped=3) — 9 net new tests over v0.3.416's 7439; Black,
Ruff, and MyPy (601 source files) clean; `git diff --check` clean (two
pre-existing CRLF-on-disk files unrelated to this diff, normalized by git
per `.gitattributes` on the next touch, exactly as for every text file in
this repository — not introduced by this milestone). Linux exact-SHA CI
pending dispatch.

## Historical scope: v0.3.416 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Finding Lifecycle foundation (Bug Bounty foundation, step 7) |
| Base SHA | 45252c1e9690cb7e8177d0357db3d6d30522fce7 |
| Status | delivered |
| Specialists | hypatia-epistemics: sole implementer, plus a bounded completion pass closing review- and mutation-found gaps; hypatia-security: independent review, yes-with-caveats, no Critical/High findings, deferred findings recorded; hypatia-qa: independent review, ready-with-caveats, no production-code defects, test gaps closed; hypatia-lead: release |
| Blockers | none |

Rationale: user-directed. Item 7 of the Bug Bounty Researcher roadmap,
directly after delivered v0.3.415 (Security Hypothesis model foundation).
Repository-grounded discovery (2026-09-26, hypatia-lead, direct file reads):
three pre-existing "Finding"/"Vulnerability"-named things exist and are all
confirmed unrelated, not reused, not touched. `src/security/SecurityFinding.py`/
`SecurityFindingKind.py` audit Hypatia's own persisted state for internal
integrity problems (e.g. a non-HTTPS source URL) — no target concept exists
in that type at all. `src/research/ReflectionFindingKind.py`/
`ResearchReflectionFinding.py` name bounded observations about how a
*research run's own process* went (failures, contradictions, weak evidence)
— meta-commentary on process quality, not a security claim about a target.
`src/security/VulnerabilityFamilyGraph.py`/`VulnerabilityRelation.py`/
`VulnerabilityRelationKind.py` is an authored, conceptual taxonomy graph of
weakness *classes* (e.g. "SSRF enables metadata access") with, by its own
docstring, "no node type for a system, no edge type for 'is vulnerable to',
and no way to attach a target" — it describes a body of knowledge, never an
attack surface, and has no `program_id`/subject/evidence concept whatsoever.
`ResearchVulnerabilityRecord`/`ResearchVulnerabilityMetric` hold structured
NVD/CVE provider metadata for research-source discovery candidates — "not
fetched, not evidence, not trusted, not a claim." None of the four is a
per-target, per-program finding record, and this milestone does not modify
any of them.

Scope: a new, `program_id`-scoped Finding Lifecycle sitting directly on top
of the delivered v0.3.415 Security Hypothesis foundation, named
`ResearchSecurityFinding*` to read as v0.3.415's sibling (same `research/`
module, same naming discipline) while staying textually distinct from the
unrelated `security.SecurityFinding`. Mirrors v0.3.415's exact architecture
(append-only founding record + append-only evidence-link records +
append-only status-transition records + a derived-only read model, modeled
on `ResearchAsset`'s type-plus-builder shape) — reusing, not duplicating,
`ResearchAssetKind`/`canonicalize_asset_value` for subject identity,
`ResearchSensitiveInputPolicy` for every free-text field, and
`ResearchAssetScopeResolutionView`/`ResearchTargetScope.resolve_hostname`/
`resolve_addresses` for live scope display.

New types in `src/research/`:
- `ResearchSecurityFindingStatus` (`StrEnum`): `CANDIDATE`,
  `VALIDATION_REQUIRED`, `VALIDATED`, `REFUTED`, `DUPLICATE`, `SUPERSEDED`.
  A `.terminal` property true for `REFUTED`/`DUPLICATE`/`SUPERSEDED` only. A
  `means_confirmed_vulnerability`-style property (name to match
  `ResearchSecurityHypothesisStatus.means_validated_vulnerability`'s exact
  discipline) that is `False` for every member, including `VALIDATED` — a
  validated finding is evidence-backed reasoning, never authority, and this
  milestone performs no active validation of any kind so nothing here could
  honestly claim confirmation of exploitability. A pure
  `is_valid_status_transition(current, new)` function implementing exactly:
  `CANDIDATE` -> `{VALIDATION_REQUIRED, VALIDATED, REFUTED, DUPLICATE,
  SUPERSEDED}`; `VALIDATION_REQUIRED` -> `{CANDIDATE, VALIDATED, REFUTED,
  DUPLICATE, SUPERSEDED}`; `VALIDATED` -> `{REFUTED, DUPLICATE, SUPERSEDED}`
  (never back to `CANDIDATE`/`VALIDATION_REQUIRED` — a corrected validation
  is explicitly re-refuted, not silently reopened); `REFUTED`/`DUPLICATE`/
  `SUPERSEDED` -> `{}` (terminal, mirroring `ResearchSecurityHypothesisStatus`'s
  `REFUTED`-is-terminal discipline exactly). A same-state transition is
  always invalid. The state-table function only knows the graph; the
  additional business rule that a transition *to* `VALIDATED` requires real
  validation evidence and zero unresolved contradicting evidence is enforced
  at the application-service layer, not baked into this pure function
  (mirroring how v0.3.415 keeps `is_valid_status_transition` pure and
  enforces its business rules in the service; correction recorded at
  release: v0.3.415's evidence floor applies when a hypothesis is created,
  not to its status transitions, which carry no evidence gate).
- `ResearchSecurityFindingOrigin` (`StrEnum`): exactly one member,
  `OPERATOR_AUTHORED` (mirrors `ResearchSecurityHypothesisOrigin`'s
  one-member-until-truly-needed discipline; no automatic/model-origin member
  is added this milestone).
- `ResearchSecurityFindingEvidenceKind` (`StrEnum`): exactly one member,
  `HTTP_EVIDENCE`. Deliberately its own enum, not a re-export of
  `ResearchSecurityHypothesisEvidenceKind` — this codebase's own convention
  (`ResearchAssetProvenanceKind` vs `ResearchHttpEvidenceProvenanceKind`)
  is that each record type owns its evidence/provenance vocabulary
  independently even where two enums currently hold the same one member, so
  the two subsystems' evidence vocabularies can evolve independently later.
- `ResearchSecurityFindingEvidenceRelation` (`StrEnum`): `SUPPORTS`,
  `CONTRADICTS`, `VALIDATES` — its own enum, not a widened
  `ResearchSecurityHypothesisEvidenceRelation` (which stays exactly
  `SUPPORTS`/`CONTRADICTS`, untouched, unmodified). `VALIDATES` evidence is
  the one and only real gate for the `VALIDATED` status.
- `ResearchSecurityFindingRecord` (frozen dataclass, the immutable founding
  fact): `finding_id`, `program_id`, `source_hypothesis_id`, `finding_kind:
  ResearchSecurityHypothesisKind` (reused unchanged — "may inherit from
  Security Hypothesis categories" per this milestone's own instruction; no
  new classification vocabulary), `subject_kind: ResearchAssetKind`,
  `subject_canonical_value`, `title` (bounded ~200 chars), `description`
  (bounded ~2,000 chars), `required_followup` (bounded ~1,000 chars,
  descriptive strategy only, never permission — same discipline as
  `required_validation`), `origin`, `created_at`. Never mutated after
  creation. No separate `disposition` field: `status` (on the derived read
  model) already names the disposition, and a second field asserting the
  same fact would only risk drifting from it.
- `ResearchSecurityFindingEvidenceLinkRecord` (frozen dataclass, append-only
  per citation): `link_id`, `finding_id`, `program_id`, `evidence_kind`,
  `evidence_id` (validated `is_http_evidence_id` shape), `relation`,
  `recorded_at`.
- `ResearchSecurityFindingStatusTransitionRecord` (frozen dataclass,
  append-only per status change): `transition_id`, `finding_id`,
  `program_id`, `status`, `reason` (bounded ~500 chars, sensitive-input
  checked, may be empty — mirrors the Hypothesis transition record exactly),
  `duplicate_of_finding_id: str | None` (populated exactly when `status is
  DUPLICATE`, `None` otherwise — fail-closed 1:1 binding, mirroring
  `ResearchAssetObservationRecord`'s `source_operation_digest`/`provenance`
  1:1-binding discipline), `superseded_by_finding_id: str | None`
  (populated exactly when `status is SUPERSEDED`, `None` otherwise, same
  1:1 binding), `recorded_at`.
- `ResearchSecurityFinding` (derived read model, no `Record` suffix,
  mirroring `ResearchAsset`/`ResearchSecurityHypothesis`'s own convention):
  assembled fresh on every read from the founding record plus its evidence
  links and status transitions — never persisted as a merged entity. Exposes
  `supporting_evidence`/`contradicting_evidence`/`validation_evidence`
  (three disjoint tuples, never netted against each other) and a derived
  `status` (the latest transition, or `CANDIDATE` if none has ever been
  recorded — mirroring `OPEN` as Hypothesis's zero-transition default).

New persistence: `JsonFileResearchSecurityFindingStore` (new store, schema
version 1), three flat lists (findings, evidence links, status transitions)
in one atomic file, modeled directly on
`JsonFileResearchSecurityHypothesisStore`'s shape — strict field-set
validation, bounded ceilings, globally-unique ID rejection per ID space,
dangling-reference rejection (an evidence link or status transition must
reference a finding already present in the same document), fail-closed on
malformed/truncated content.

New application service: `ResearchSecurityFindingApplicationService`
(`src/cognition/`, mirroring `ResearchSecurityHypothesisApplicationService`'s
shape exactly), taking the finding store, an HTTP-evidence reader, a narrow
`SecurityHypothesisReader` Protocol (`hypothesis_by_id(hypothesis_id,
program_id) -> ResearchSecurityHypothesis | None`, satisfied naturally by
`ResearchSecurityHypothesisApplicationService` itself — no import cycle, no
hard coupling, mirroring the existing `ActiveProgramScopeRevisionReader`/
`ResearchHttpEvidenceReader` Protocol-injection pattern), and the same
optional `program_scope_revision_store`.

- `create_finding(program_id, source_hypothesis_id, title, description,
  required_followup)`: validates the source hypothesis exists for this
  exact program via the injected reader; requires the hypothesis's current
  (derived) status to be exactly `READY_FOR_VALIDATION` (the hypothesis
  side's own explicit "an operator judges enough has been gathered" signal
  — promoting an `OPEN`/`NEEDS_EVIDENCE` hypothesis, or a `REFUTED` one,
  straight to a finding candidate would let a bare conjecture or a disproven
  one masquerade as something worth tracking as a finding); copies
  `finding_kind`/`subject_kind`/`subject_canonical_value` from the
  hypothesis (never independently operator-typed, so a finding's identity
  can never drift from the hypothesis that produced it); refuses a second
  finding for the same `source_hypothesis_id` (the dedup rule — one
  hypothesis maps to at most one finding lifecycle; the caller attaches
  further evidence or transitions the existing finding instead of creating
  a near-duplicate); carries the hypothesis's *current* supporting and
  contradicting evidence forward as the finding's own initial evidence links
  (same relation, same evidence IDs) — the finding starts from the same
  evidentiary state as its hypothesis, then diverges independently.
- `attach_evidence(finding_id, program_id, evidence_ids, relation)`:
  supporting, contradicting, or validating; same-program existence check
  against the HTTP evidence store, same-program finding-existence check;
  always allowed regardless of current status (append-only audit trail,
  mirroring the Hypothesis service's own unconditional `attach_evidence`).
- `transition_status(finding_id, program_id, new_status, reason,
  duplicate_of_finding_id=None, superseded_by_finding_id=None)`: validates
  the finding exists for this program, validates the pure state-table
  transition, and — only for a transition *to* `VALIDATED` — additionally
  requires at least one `VALIDATES`-relation evidence link and refuses if
  any `CONTRADICTS`-relation evidence link currently exists (the smallest
  safe rule for unresolved contradictions per this milestone's own
  instruction: a finding with live contradicting evidence simply cannot
  validate, full stop, rather than adjudicating whether the validation
  "outweighs" the contradiction); for a transition to `DUPLICATE` requires
  `duplicate_of_finding_id` to name a different, existing, same-program
  finding; for `SUPERSEDED` requires `superseded_by_finding_id` under the
  same rule; applies the sensitive-input policy to `reason`.
- `findings_for_program`/`finding_by_id`: derived read projections.
- `current_scope_resolution`: read-only, never-cached dispatch, identical
  shape to the Hypothesis service's own method, reusing
  `ResearchAssetScopeResolutionView` unchanged.
- Brain intents: `research_security_finding_create`,
  `research_security_finding_evidence_attach`,
  `research_security_finding_status_transition`,
  `research_security_finding_preview`, mirroring the exact dispatch/failure
  pattern `CognitiveEngine.py` already uses for the Hypothesis intents. Every
  response for a non-terminal-status finding states a fixed, literal
  disclaimer distinguishing a candidate from a validated finding and stating
  that even `VALIDATED` is not authority to act.

Desktop: a new "Findings" panel (`src/desktop/ResearchSecurityFindingPanel.py`),
mirroring `ResearchSecurityHypothesisPanel.py`'s exact widget idiom — list
findings per program (kind/subject/status/source hypothesis/created-at),
detail pane showing title/description/required follow-up/supporting,
contradicting, and validation evidence IDs/duplicate-or-superseded
linkage/provenance/full status-transition history/current live scope
resolution labelled "recomputed live from active policy, not stored". A
visually plain distinction between `CANDIDATE` and `VALIDATED` (text labels
only — no color/severity styling of any kind, since this milestone adds no
severity concept). Entry fields to create a finding, attach evidence, and
transition status.

Non-goals (exhaustive): no active validation engine, no Validation Recipes,
no Kali/Burp/browser/mouse-keyboard control, no shell/HTTP/network execution
of any kind, no exploitation, no automated CVSS/severity, no Impact
Reasoning, no Report Composer, no automatic root-cause correlation or fuzzy
duplicate inference, no vulnerability intelligence engine, no CVE
monitoring, no fuzzing, no business-logic state-machine engine, no
internal/cloud execution; no modification of
`ResearchSecurityHypothesisRecord`/`Status`/`Origin`/`EvidenceKind`/
`EvidenceRelation`/`ApplicationService`/`Panel` (v0.3.415, reused strictly
by reference/Protocol), `ResearchSensitiveInputPolicy`,
`ResearchHttpEvidenceRecord`, `ResearchAssetKind`/`canonicalize_asset_value`,
`SecurityFinding`/`SecurityFindingKind` (unrelated self-audit),
`ReflectionFindingKind`/`ResearchReflectionFinding`,
`VulnerabilityFamilyGraph`/`VulnerabilityRelation`/`VulnerabilityRelationKind`
(unrelated taxonomy graph), or `ResearchVulnerabilityRecord`/
`ResearchVulnerabilityMetric` (unrelated NVD candidate metadata); no
automatic/LLM-generated finding content or validation (origin is
`OPERATOR_AUTHORED` only); no new evidence kind beyond `HTTP_EVIDENCE`; no
cross-program finding or evidence reference of any kind; no fuzzy/LLM
similarity-based duplicate detection (deterministic
one-hypothesis-per-finding identity only); no new scope/target/credential/
budget primitive; no `disposition` field separate from `status`; no
automatic downgrade of `VALIDATED` when new contradicting evidence arrives
(attaching contradicting evidence is always allowed and always preserved,
but a status change remains a separate, explicit, operator-driven action).

Security invariants: finding creation, evidence attachment, and status
transitions must never execute a network request, spawn a process, run a
tool, or modify scope/credential/budget/target state — reasoning over
already-recorded evidence only, proved by a no-network/no-process test
mirroring v0.3.415's. `VALIDATED` never means permission to act — every
consumer of that status (Brain response, desktop render) must render the
fixed non-authority disclaimer. Program isolation is enforced on every
finding/evidence/hypothesis-reference operation. `ResearchSensitiveInputPolicy`
(unmodified) is applied to `title`, `description`, `required_followup`, and
transition `reason`. Untrusted evidence content can never reach a finding
field, status, or Brain response — the finding layer reads only evidence
IDs, never evidence content, exactly like the Hypothesis layer.

Test strategy: model construction/immutability/bounded-text/invalid-
enum tests; every valid and invalid status transition (all 6 states as both
source and target where the table allows, self-transition rejected for all
6, every terminal state's zero outgoing transitions verified); the
`VALIDATED` evidence gate (positive: validation evidence present and no
contradicting evidence; negative: no validation evidence; negative: live
contradicting evidence blocks validation even with validation evidence
present); `DUPLICATE`/`SUPERSEDED` linkage validation (missing reference
rejected, self-reference rejected, cross-program reference rejected);
hypothesis-gate tests (wrong hypothesis status rejected, specifically a
`REFUTED` hypothesis rejected, cross-program hypothesis rejected, evidence
carried forward correctly from the hypothesis at creation time); dedup (a
second finding for the same `source_hypothesis_id` refused); program
isolation across findings/evidence/hypotheses; sensitive-input refusal on
all four free-text fields; untrusted-evidence inertness; a no-network/
no-process authority proof; a restart/reload test proving the derived read
model (including computed status) survives identically; a realistic
end-to-end flow building two real `ResearchHttpEvidenceRecord` fixtures
(the object-ID-access scenario from this milestone's own instruction) and
both a validated and a refuted outcome, proving no request is issued and no
vulnerability is automatically declared confirmed; desktop reachability via
a real constructed-widget test, including full coverage of the
`DesktopController`/`CognitiveEngine`-dispatch/`Bootstrap`-wiring layer up
front this time (the exact gap class QA found and closed after the fact in
v0.3.415 — write these tests during initial implementation, not as a
follow-up pass); a small, high-value mutation-testing pass (3-5 mutations:
allow `VALIDATED` without validation evidence, allow cross-program evidence,
let untrusted/model text set status, bypass the sensitive-input guard, let
finding creation/transition touch scope or authority) — each caught, all
restored; impacted suites focused first, full canonical gates once at
release.

Security review (hypatia-security, 2026-09-26): yes-with-caveats, no
Critical or High findings. No path exists from finding state to tool,
network, process, scope, or authority: nothing reads a finding status as
permission, `means_confirmed_vulnerability` is `False` for every status, the
service requires real enum instances for status and relation, the finding
layer only tests evidence IDs for membership and never reads evidence
content, the sensitive-input policy covers all four free-text fields on
write and again on load, and program isolation holds on every write and read
path. Deferred, non-blocking findings (no production change in this
release): F1 (Medium) — `VALIDATES` evidence need only exist in the same
program, so it may reference a different host; a future design should model
explicit evidence-to-subject/scope relationships rather than assume hostname
equality. F2 (Low) — evidence IDs carried forward from the hypothesis are
not independently re-checked against the HTTP evidence store; defer to
provenance/store hardening. F3 (Low, inherited from v0.3.415) — status
order depends on wall-clock timestamps, so a clock step backwards can hide
a later transition. F4 (Low, inherited) — store load validates structure,
bounds, unique IDs, and dangling references but does not replay lifecycle
invariants (transition legality, the `VALIDATED` gate, linkage targets,
one-finding-per-hypothesis). F5-F10 are informational (no cross-process
lock; deep-nesting fails closed; the contradiction gate is per finding by
the spec's deterministic-identity choice; control characters allowed in
operator free text). F11: this section's claim that v0.3.415 enforced an
evidence floor on transitions was inaccurate and is corrected above.

QA review (hypatia-qa, 2026-09-26): ready-with-caveats, no production-code
defects. An 86-row acceptance-criterion traceability matrix found every
criterion implemented; the gaps were in test evidence (no Brain-level
`VALIDATED` disclaimer test, the 500-character reason bound, truncated JSON,
failed atomic write, no-automatic-downgrade, several panel detail lines) and
in the panel listing, which lacked the source hypothesis and created-at
columns this section requires.

Completion passes (approved by hypatia-lead, 2026-09-26):
each panel row now shows kind, subject, status, source hypothesis, and
created-at, and the detail pane shows created-at. The not-authority notice
is one canonical constant in `response.ResponseComposer`, imported by the
panel (`desktop` already depended on `response`; `response` never imports
`desktop`, so no new layer direction). Lead decisions: (1) any
`CONTRADICTS` link — including one carried from the hypothesis — blocks
`VALIDATED` for the life of the finding in this release, since links are
append-only and contradiction resolution is a separate future design,
pinned by a regression test; (2) no hostname-equality rule for `VALIDATES`
evidence (see F1); (3) the notice wording above, which superseded "a
candidate finding" phrasing so that a `VALIDATED` finding is never
mislabelled, is status-neutral: "Research finding only. This status does
not grant authority to act, execute tools, access systems, or expand
scope."; (4) F2 deferred. Fifteen tests were added across the two passes;
no production behaviour changed beyond the panel columns and the notice
wording.

Mutation pass (2026-09-26): 45 mutants plus an unmutated control (which
passed) across illegal transitions, the `VALIDATED` evidence gate,
contradicting-evidence handling, `DUPLICATE`/`SUPERSEDED` linkage,
cross-program isolation, one-finding-per-hypothesis, append-only history,
the sensitive-input guard, the authority notice, and execution surfaces.
43 caught. The first run left five meaningful survivors, each now caught by
a new test: M05 (service judging a transition against the earliest status),
M29 (append-only check ignoring status transitions), M35 (untrusted text
coerced into a status), M36 (notice dropped for `VALIDATED` only), and M44
(`os.system` inside `create_finding`). M21/M22 (the service's own program
check removed before attach/transition) survive only because the
lower-layer `ResearchSecurityFindingDocument` reference check still refuses
the cross-program write; this was verified directly against both mutants.

Release gates (2026-09-26): Linux, Python 3.14.7 — 7439 tests, 0 failures
(34 skipped). Windows canonical environment — 7439 tests, OK (skipped=3);
ResourceWarning output about unclosed file handles during the Windows run
is recorded as non-blocking test-hygiene debt, not addressed here. Ruff and
Black clean; MyPy 0 issues in 601 source files.

## Historical scope: v0.3.415 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Security Hypothesis model foundation (Bug Bounty foundation, step 6) |
| Base SHA | 6217535373fc9e7e01545b377c49fc9d56ef5175 |
| Status | delivered |
| Specialists | hypatia-epistemics: sole implementer, plus a second bounded pass closing QA-found test-coverage gaps; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, found and hypatia-epistemics closed one high and two moderate test-coverage gaps; hypatia-lead: release |
| Blockers | none |

Rationale: user-directed. Item 6 of the Bug Bounty Researcher roadmap
(`docs/Roadmap/Master_Roadmap.md`, recorded 2026-09-23). Items 1-5 are
delivered (Asset Inventory, recon ingestion, HTTP Evidence, session
contexts, secret-ingress boundary). Repository-grounded discovery
(2026-09-25, hypatia-lead, direct file reads, not assumed) found this is
**not** greenfield: a general-purpose `ResearchHypothesis` subsystem already
exists in `src/research/`/`src/cognition/`
(`ResearchHypothesis.py`/`HypothesisStatus.py`/`HypothesisApplicationService.py`/
`JsonFileHypothesisStore.py` and siblings) — but it is `run_id`-scoped
(a field on `ResearchRun`, the general deep-research Q&A engine), has no
`program_id`, and its `supporting_evidence_ids`/`opposing_evidence_ids` are
validated only against that same run's own `ResearchEvidenceRecord` tuple.
`ResearchRun` (confirmed by direct read of its field list) carries no
`program_id` field at all. The Bug Bounty vertical
(`ResearchAssetInventoryApplicationService`, `ResearchHttpEvidenceRecord`,
`ResearchSessionContextRecord`, `ResearchProgramScopeRevision`) is a
completely separate, parallel, `program_id`-scoped system that never
references `ResearchRun`/`run_id`. These two verticals do not currently
bridge. A security hypothesis about a bug-bounty program's target therefore
cannot honestly be represented by `ResearchHypothesis` without either
bolting a `program_id` onto the general research-run engine (widening an
unrelated subsystem) or building a new, `program_id`-scoped type that
mirrors the SAME falsifiability discipline `ResearchHypothesis` already
proves out (a required defeater/validation strategy, supporting vs. opposing
evidence kept in separate, never-netted collections, status derived rather
than declared as fact) inside the Bug Bounty vertical's own conventions.
This milestone takes the second path: a new type, not a modification of
`ResearchHypothesis`, `HypothesisStatus`, or anything under `src/security/`
(which is a distinct, unrelated self-audit subsystem —
`SecurityFinding`/`SecurityFindingKind`/`SecurityPostureAuditor` check
Hypatia's *own* persisted state for problems, e.g. a non-HTTPS source URL;
they have no concept of an external target and are not touched here).
Also confirmed by direct read: `ResearchHttpEvidenceRecord` already carries
`target_kind: ResearchAssetKind` (always `HOSTNAME`) and
`target_canonical_value: str` (already-canonical, via
`canonical_dns_hostname`) — the exact subject/target shape a hypothesis
needs, reusable without new machinery.

Scope: five new frozen types in `src/research/`, one new store, one new
application service, minimal desktop and Brain wiring — modeled directly on
the v0.3.407 Asset Inventory shape (append-only fact records plus a
derived-only read projection, never a persisted merged/mutated entity):

- `ResearchSecurityHypothesisKind` (`StrEnum`: `AUTHENTICATION`,
  `AUTHORIZATION`, `INPUT_HANDLING`, `SERVER_SIDE_INTERACTION`,
  `STATE_TRANSITION`, `CONFIGURATION`, `INFORMATION_EXPOSURE`, `UNKNOWN`) —
  broad security-mechanism categories, not a per-CVE/per-vulnerability-name
  enum; a specific vulnerability name is future knowledge-layer content, not
  a hypothesis-kind value.
- `ResearchSecurityHypothesisStatus` (`StrEnum`: `OPEN`, `NEEDS_EVIDENCE`,
  `READY_FOR_VALIDATION`, `REFUTED`, plus a `.terminal` property true only
  for `REFUTED`) — explicitly excludes any
  confirmed/validated/exploited/severity vocabulary; `REFUTED` is terminal
  (no transition out), everything else can move to `NEEDS_EVIDENCE`,
  `READY_FOR_VALIDATION`, or `REFUTED`, and a same-state transition is
  refused as a no-op. `.means_true`/equivalent is explicitly `False`
  everywhere, mirroring `HypothesisStatus.means_true`'s existing discipline
  of asserting this in a property (and a test) rather than a docstring.
- `ResearchSecurityHypothesisOrigin` (`StrEnum`: exactly one member,
  `OPERATOR_AUTHORED` — mirrors `ResearchAssetProvenanceKind`'s "exactly one
  member until a second is truly needed" discipline; no automatic/model
  origin kind is added since none is implemented this milestone).
- `ResearchSecurityHypothesisEvidenceKind` (`StrEnum`: exactly one member,
  `HTTP_EVIDENCE` — HTTP Evidence is "the first realistic subject" per this
  milestone's own scope; Asset observations / research evidence / session
  contexts are deferred, additive future members, not implemented now).
- `ResearchSecurityHypothesisEvidenceRelation` (`StrEnum`: `SUPPORTS`,
  `CONTRADICTS` — kept as two disjoint sets, never netted against each
  other, mirroring `ResearchHypothesis`'s own
  supporting/opposing-never-merged discipline).
- `ResearchSecurityHypothesisRecord` (frozen dataclass, the immutable
  founding fact): `hypothesis_id`, `program_id`, `hypothesis_kind`,
  `subject_kind: ResearchAssetKind` (restricted to `HOSTNAME`/`IP_ADDRESS`,
  reusing `ResearchAssetKind`/`canonicalize_asset_value` from Asset
  Inventory — no new subject-identity machinery), `subject_canonical_value`
  (must already be canonical, fail-closed re-validation exactly like
  `ResearchAssetObservationRecord`), `statement` (concise, bounded ~500
  chars — "what is inferred"), `rationale` (bounded ~2,000 chars — why the
  cited evidence suggests it, "what is observed" tied to "what is
  inferred"), `required_validation` (bounded ~1,000 chars — descriptive
  strategy only, "what must still be tested"; never itself permission),
  `origin`, `created_at`. Never mutated after creation.
- `ResearchSecurityHypothesisEvidenceLinkRecord` (frozen dataclass, one
  append-only fact per evidence citation): `link_id`, `hypothesis_id`,
  `program_id`, `evidence_kind`, `evidence_id`, `relation`, `recorded_at`.
  References evidence by stable identity only (`evidence_id`, validated as a
  real `is_http_evidence_id` shape and required to exist for the same
  `program_id` in the HTTP Evidence store) — never copies evidence content.
- `ResearchSecurityHypothesisStatusTransitionRecord` (frozen dataclass, one
  append-only fact per status change): `transition_id`, `hypothesis_id`,
  `program_id`, `status`, `reason` (bounded ~500 chars, sensitive-input
  checked), `recorded_at`.
- `ResearchSecurityHypothesis` (derived read model, no `Record` suffix,
  mirroring `ResearchAsset`'s own naming/derivation convention): assembled
  fresh on every read from one founding record plus its evidence-link and
  status-transition records for that `hypothesis_id` — never persisted as a
  merged entity. Exposes `supporting_evidence`/`contradicting_evidence`
  (deduplicated, ordered) and a derived `status` (the latest status
  transition, or `OPEN` if none has ever been recorded).

New persistence: `JsonFileResearchSecurityHypothesisStore` (new store,
schema version 1) holding three flat lists (hypotheses, evidence links,
status transitions) in one atomic file, modeled on
`JsonFileResearchAssetInventoryStore`'s shape — strict field-set validation,
bounded max counts, globally-unique ID rejection on save.

New application service: `ResearchSecurityHypothesisApplicationService`
(`src/cognition/`, mirroring `ResearchAssetInventoryApplicationService`'s
and `ResearchSessionContextApplicationService`'s shape): `create_hypothesis`
(validates program ID, applies `ResearchSensitiveInputPolicy` to
`statement`/`rationale`/`required_validation`, requires at least one
supporting evidence reference that exists for the same program, requires the
hypothesis's subject to match the `target_kind`/`target_canonical_value` of
at least one cited evidence record — a hypothesis can never cite evidence
about a different host than the one it names, closing an authority-adjacent
honesty gap the milestone brief did not explicitly name but that follows
directly from "evidence-first" — and refuses an exact-identity duplicate:
same `program_id`+`subject_kind`+`subject_canonical_value`+`hypothesis_kind`+
normalized `statement`, directing the caller to attach evidence to the
existing hypothesis instead of creating a near-duplicate); `attach_evidence`
(supporting or contradicting, same program/existence checks);
`transition_status` (validates the closed state machine, refuses a
self-transition, applies the sensitive-input policy to `reason`);
`hypotheses_for_program`/`hypothesis_by_id` (derived read projections); a
read-only, never-cached `current_scope_resolution` dispatching to the
unchanged `ResearchTargetScope.resolve_hostname`/`resolve_addresses` by
`subject_kind` against the caller-supplied *currently active*
`ResearchProgramScopeRevision` — exactly `ResearchAssetInventoryApplicationService`'s
own pattern, reusing its `ActiveProgramScopeRevisionReader` protocol shape.

Desktop: a new "Security Hypotheses" panel
(`src/desktop/ResearchSecurityHypothesisPanel.py`), reusing the exact
`ttk.Treeview`/entry-field/detail-pane idiom `ResearchAssetInventoryPanel.py`
already established — list hypotheses per program with
kind/subject/status/created-at, a detail pane showing statement, rationale,
required validation, supporting/contradicting evidence IDs, origin, and
current live scope resolution explicitly labelled "recomputed live from
active policy, not stored"; entry fields to create a hypothesis, attach
evidence, and transition status. No vulnerability dashboard, no severity
display, no confidence score.

Brain: new read/write intents mirroring the existing preview-then-record
pattern (`research_security_hypothesis_create`,
`research_security_hypothesis_evidence_attach`,
`research_security_hypothesis_status_transition`,
`research_security_hypothesis_preview` for a program listing) exposed
through `CognitiveEngine.py`/`DesktopController.py`. Responses answer "what
hypotheses are open", "what supports/contradicts this one", "what still
needs validation" descriptively; every rendered response for a non-`REFUTED`
hypothesis states explicitly that a hypothesis is not a finding.

Non-goals (exhaustive, matching the locked instruction): no active
validation, no Finding Lifecycle, no vulnerability confirmation, no CVSS or
severity, no exploitation, no sqlmap/Nuclei/ffuf/Burp/browser/Kali-gateway
execution of any kind, no generic shell execution, no vulnerability
intelligence engine or CVE monitoring, no autonomous source-research loop,
no business-logic state machine, no fuzzing, no report generation, no
cloud/internal/AD execution, no desktop mouse/keyboard operator, no
numeric/percentage confidence score of any kind, no `CONFIRMED`-flavoured
status value, no modification of `ResearchHypothesis`/`HypothesisStatus`/
anything under `src/security/`/`ResearchRun`/`ResearchClaimRecord`/
`ResearchClaimContradictionRecord`/`ResearchAssetObservationRecord`/
`ResearchAssetRelationRecord`/`ResearchHttpEvidenceRecord`/
`ResearchSessionContextRecord` (all reused strictly by reference, byte-for-
byte unchanged), no new evidence-kind beyond `HTTP_EVIDENCE`, no cross-
program hypothesis or evidence reference of any kind, no new scope/target/
credential/budget primitive, no automatic/LLM-generated hypothesis creation
(operator-authored only this milestone — a future automatic-origin member
is additive, not built now).

Security invariants: hypothesis creation, evidence attachment, and status
transition must never execute a network request, spawn a process, run a
tool, modify scope, modify credentials, grant authority, create a budget, or
enroll a target — this is reasoning/data only, proved by a no-network/
no-process test. Model output, if ever produced by a future milestone,
remains a proposal, never authority; this milestone adds no model-generated
content path at all (origin is `OPERATOR_AUTHORED` only). Untrusted text
embedded in evidence (header values, tool output, source prose) that looks
like an instruction must remain inert data — it cannot alter status, become
authority, or reach a Brain command; this hypothesis layer never reads
evidence content itself (only its stable ID), so an instruction-shaped
string inside an HTTP evidence header cannot reach the hypothesis layer at
all except as an opaque evidence reference. `ResearchSensitiveInputPolicy`
(unmodified) is applied to every operator-authored free-text field exactly
as v0.3.411-414 established. Program isolation is real: an evidence
reference, a status transition, or an evidence attachment must resolve to
the exact same `program_id` as the hypothesis itself, fail-closed otherwise.
`OUT_OF_SCOPE`/`UNCERTAIN` scope resolution remains purely a live, never-
cached display value — creating or reading a hypothesis about an
out-of-scope or unresolvable host executes nothing and authorizes nothing.

Test strategy (per the locked instruction's own enumeration): model
construction (valid hypothesis, immutability, invalid status/kind rejected,
bounded text, missing-evidence rejection); evidence linkage (supporting and
contradicting references work, nonexistent evidence rejected, cross-program
evidence rejected, multiple evidence records preserved, subject-evidence
consistency enforced); status transitions (valid transitions succeed,
invalid/self transitions fail closed, no state implies a validated
vulnerability); authority proof (hypothesis creation/evidence/transition
never execute a request, spawn a process, run a tool, or touch scope/
credential/budget/target primitives — a real no-network/no-process test, not
an assertion by inspection alone); sensitive-data handling (secret-shaped
rationale/statement/required_validation/reason refused, never reflected);
untrusted-data inertness (an instruction-shaped evidence reference stays
inert data); one realistic end-to-end flow building a hypothesis from real
`ResearchHttpEvidenceRecord` fixtures, asserting the recorded statement
never claims a confirmed vulnerability and no request is issued; a small,
high-value mutation-testing pass (~3-5 mutations: allow cross-program
evidence, let creation touch scope/authority, let instruction-shaped
evidence content leak through, bypass the sensitive-input guard, treat
`OPEN` as a confirmed finding) — each must be caught, all mutations
restored; desktop reachability via a real constructed-widget test; impacted
suites focused first, full canonical gates once at release.

Security review (hypatia-security, 2026-09-25): PASS, no findings. Traced
`create_hypothesis`/`attach_evidence`/`transition_status` line by line and
confirmed none open a network socket, spawn a process, or touch any
scope/credential/budget/authorization primitive — the only scope-related
call is the read-only `current_scope_resolution` dispatch, called only from
the preview path, never from a write path. Confirmed `ResearchSensitiveInputPolicy`
byte-for-byte unchanged and applied to every free-text field including the
status-transition `reason`; confirmed the hypothesis layer never reads
evidence content (only its ID), so an instruction-shaped string embedded in
evidence content structurally cannot reach a hypothesis field, verified by a
genuine test; confirmed program isolation is enforced on every method that
accepts both a hypothesis and program ID; confirmed the no-network/
no-process test genuinely patches real dangerous call sites across a full
create-attach-transition flow against a real temp-file store; confirmed
`ResearchHypothesis.py`/`HypothesisStatus.py`/everything under `src/security/`
are byte-for-byte unmodified.

QA review (hypatia-qa, 2026-09-25): found one high and two moderate
test-coverage gaps, no production-code defects. High: the new
`DesktopController` methods, `CognitiveEngine` dispatch branches (including
all four "service unavailable" fallback paths), and `Bootstrap` wiring had
zero test coverage anywhere, breaking this codebase's own established
per-file testing convention. Moderate: the exact-identity duplicate-rejection
check had no negative counterpart — QA proved by mutation testing that
removing the `hypothesis_kind` comparison from the dedup predicate left
every existing test green; and no restart/reload test proved the *derived*
`ResearchSecurityHypothesis` view (including computed `status`) survives a
genuine restart identically, unlike the Asset Inventory precedent this
milestone claims to mirror. hypatia-epistemics closed all three directly:
added 15 `DesktopController` tests, 8 `CognitiveEngine` dispatch tests (4
wired-success + 4 unwired-failure), 2 `Bootstrap` wiring tests, 3 dedup
negative tests, and 1 restart/reload test proving byte-identical derived
output across independent store/service instances. Re-verified QA's exact
mutation is now caught. Re-run after the fix: 494 focused tests across seven
impacted test modules, OK; `black`/`ruff`/`mypy`/`git diff --check` clean.

## Historical scope: v0.3.414 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Claim-contradiction preview secret-ingress boundary (Bug Bounty foundation, step 5 continued) |
| Base SHA | 37c756808a058d882583521bbfceeaf8ce3ed2d3 |
| Status | delivered |
| Specialists | hypatia-lead: sole implementer (single-function fix, per the constitution's "no subagent for trivial, single-file work"), release; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, PASS, no findings |
| Blockers | none |

Rationale: bounded continuation of roadmap item 5, "Credential + secret
boundary", after delivered v0.3.413. hypatia-security's v0.3.413 review
flagged one genuine, pre-existing, out-of-scope gap: repository-grounded
re-check (2026-09-25, hypatia-lead) confirms
`ResearchRunManager.preview_claim_contradiction_write` normalizes its `note`
argument via the shared static method `_normalize_claim_contradiction_note`
(length/emptiness only — no sensitivity check), then constructs a
`ResearchClaimContradictionWritePreview` carrying that raw note, which
`ResponseComposer.research_claim_contradiction_write_preview_success` embeds
verbatim as `f"User note: {preview.note}"` (`ResponseComposer.py:4991`) in
the rendered Brain response — before any confirmation, before the
`__post_init__`-level check v0.3.413 added to the persisted
`ResearchClaimContradictionRecord` ever runs. An operator previewing a
secret-shaped contradiction note today sees it echoed straight back in the
preview response, which is exactly what the v0.3.411 security invariant
("the candidate secret is never interpolated into an exception, Brain
response, log, or stored record") forbids elsewhere. Confirmed by direct
read: no equivalent preview object exists for evidence
(`add_evidence`/`ResearchEvidenceRecord` writes directly, no preview) or for
comparison reviews (`record_comparison_review` also writes directly, no
preview) — `ResearchClaimContradictionWritePreview` is the only note-carrying
preview object in the research-run model, so this is a single, complete fix,
not a partial one.

Scope: add the same `_refuse_sensitive_input` check (reusing the existing,
unmodified `ResearchSensitiveInputPolicy`) directly inside
`ResearchRunManager._normalize_claim_contradiction_note` — the one static
method already shared by both `preview_claim_contradiction_write` and
`record_claim_contradiction`, so a secret-shaped note is refused identically
and immediately for both, before a preview object can ever be constructed
with it. Add a test proving `preview_claim_contradiction_write` raises
`ResearchError` (never reflecting the candidate value) for a secret-shaped
note, to `ResearchRunManager`'s existing test file; add a cognition-layer
test proving the `research_claim_contradiction_write_preview` Brain intent
returns a failure response that never reflects the sentinel, to
`CognitiveEngine`'s existing test coverage for that intent.

Non-goals: no change to `ResearchSensitiveInputPolicy`,
`ResearchClaimContradictionRecord`, `ResearchComparisonReviewRecord`,
`ResearchEvidenceRecord`, or any other already-covered record; no change to
`ResearchClaimContradictionWritePreview.py` itself (the dataclass is
unchanged — it is simply never constructed with a refused note now); no
change to `CognitiveEngine.py`'s existing generic
`"Research claim contradiction could not be validated or saved."` catch-all
failure message (it already discards every contradiction-refusal reason
uniformly, including this one — verified, not assumed); no new preview type,
no widening to any other domain's preview object beyond the one confirmed to
exist; no secret storage, encryption, masking-and-keeping, credential
reference/use, login, network/process capability, or any authority/budget/
target/execution change.

Security invariants: identical to v0.3.411/v0.3.412/v0.3.413 — classification
stays deterministic, local, bounded, and side-effect-free; a refusal exposes
only its fixed category (or, at the `CognitiveEngine` layer, the existing
generic catch-all — never the candidate value) in the raised error or any
Brain response; `record_claim_contradiction` remains doubly protected (this
normalization check plus the existing `__post_init__` check on the persisted
record); benign notes remain unaffected at both the preview and record paths.

Test strategy: a manager-level test proving `preview_claim_contradiction_write`
refuses a secret-shaped note without constructing a preview and without
reflecting the candidate text; a differential test proving a benign note
still previews and records exactly as before; a cognition-layer test proving
the Brain-level preview intent returns a failure response without the
sentinel; confirm the existing v0.3.413 `record_claim_contradiction`
regression tests still pass unchanged (this milestone adds a second,
earlier check on the same value, so no existing accept/refuse outcome for
`record_claim_contradiction` should change); impacted suites focused first,
full canonical gates once at release.

Security review (hypatia-security, 2026-09-25): PASS, no findings. Confirmed
the production diff is exactly one import, one module-level policy instance,
and the new check inside `_normalize_claim_contradiction_note`; confirmed
both `preview_claim_contradiction_write` and `record_claim_contradiction`
call that one method; confirmed the raised error never carries the candidate
text; confirmed `record_claim_contradiction` is now doubly protected without
conflict; confirmed `CognitiveEngine.py`'s pre-existing generic catch-all for
this intent is unchanged and untouched by this diff; confirmed every
non-goal file (`ResearchSensitiveInputPolicy.py`,
`ResearchClaimContradictionRecord.py`, `ResearchComparisonReviewRecord.py`,
`ResearchEvidenceRecord.py`, `ResearchClaimContradictionWritePreview.py`) is
byte-for-byte unchanged.

QA review (hypatia-qa, 2026-09-25): PASS, no findings. Mutation testing on
the new check confirmed both new tests fail without it, and — empirically
validating the milestone's own "doubly protected" claim — the existing
v0.3.413 `record_claim_contradiction` test still passed under the same
mutation because the persisted record's `__post_init__` check independently
catches it downstream. Confirmed the benign-note accept path is unaffected,
confirmed the cognition-layer test's non-reflection assertion targets the
correct field with no coincidental substring risk, and confirmed no existing
test body was modified (pure insertions). Full focused run: 278 tests, OK;
`black`/`ruff`/`mypy`/`git diff --check` clean.

## Historical scope: v0.3.413 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Research-run note secret-ingress boundary (Bug Bounty foundation, step 5 continued) |
| Base SHA | acf37a351ed3338c2f807b88aa5500336baf5fd4 |
| Status | delivered |
| Specialists | hypatia-epistemics: sole implementer; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, found and hypatia-lead closed one moderate test-hygiene gap; hypatia-lead: release |
| Blockers | none |

Rationale: bounded continuation of roadmap item 5, "Credential + secret
boundary", after delivered v0.3.412. v0.3.412's own non-goals text explicitly
named six other `note: str` fields in `src/research/` as residual future
work, pending a scoping pass to separate genuinely operator-authored
persisted notes from transient authorization/preview objects. That scoping
pass (2026-09-25, hypatia-lead): `ResearchClaimContradictionRecord.note`
(persisted append-only, populated directly from a caller-supplied `note`
parameter in `ResearchRunManager.record_claim_contradiction`),
`ResearchComparisonReviewRecord.note` (persisted append-only, the operator's
authored reason for a supported/not-supported review decision), and
`ResearchEvidenceRecord.note` (persisted, populated from a caller-supplied
`note` parameter in `ResearchRunManager.add_evidence` — distinct from
`excerpt`, which is raw fetched source content, not operator input, and stays
out of scope exactly as `canonical_value` did in v0.3.412) are all genuinely
operator-authored persisted free text with no sensitive-input check today.
`ResearchContradictionAuthorization.note`, `ResearchEvidenceAuthorization.note`,
and `ResearchClaimContradictionWritePreview.note` are transient
authorization/preview objects, not persisted records: every value they carry
must still pass through one of the three constructors above before becoming
durable, so — mirroring v0.3.412's own reasoning for not touching
`*WritePreview` types — enforcing at the three persisted-record constructors
is the single interception point that covers every path (direct manager call
or plan-step-authorized delegated path) without needing a second check
upstream. All three record types are held on `ResearchRun` and round-trip
through the existing `JsonFileResearchRunStore`, so enforcing in
`__post_init__` again covers both the write and the load path in one place.

Scope: import the existing, unmodified, already-reviewed
`ResearchSensitiveInputPolicy` into `ResearchClaimContradictionRecord.py`,
`ResearchComparisonReviewRecord.py`, and `ResearchEvidenceRecord.py`; refuse
`note` in each record's `__post_init__`, exactly the same
`_refuse_sensitive_input` helper shape already used in
`ResearchSessionContextRecord.py`/`ResearchAssetObservationRecord.py`/
`ResearchAssetRelationRecord.py` (fixed category-only message, never the
candidate value); add normal/refusal/benign-near-miss regression tests to
each record's existing test file
(`tests/research/test_research_claim_contradiction_record.py`,
`tests/research/test_research_comparison_review_support.py`,
`tests/research/test_research_evidence_record.py`); add a
malicious-persisted-note-fails-closed-on-load fault-injection test to
`tests/research/test_json_file_research_run_store.py` for each of the three
record types; add a service-layer regression test (mirroring v0.3.411's
`test_secret_shaped_input_is_refused_without_write_or_reflection`) to
`ResearchRunManager`'s existing test coverage for `record_claim_contradiction`
and `add_evidence` up front, closing the exact gap class QA found in v0.3.412
before release rather than after.

Non-goals: no change to `ResearchSensitiveInputPolicy` itself; no change to
`ResearchContradictionAuthorization`, `ResearchEvidenceAuthorization`, or
`ResearchClaimContradictionWritePreview` (transient objects, covered
transitively — see Rationale); no change to `excerpt`, `chunk_sha256`,
`claim_ids`, `evidence_ids`, `document_id`, `chunk_index`, `review_id`,
`note_id`, `decision`, `supersedes_review_id`, or any other non-note field on
any of the three records; no change to `ResearchSessionContextRecord`,
`ResearchAssetObservationRecord`, or `ResearchAssetRelationRecord` (already
covered); no comment/review-composition Brain-response wording changes beyond
what a refusal already requires; no secret storage, encryption, hashing,
masking-and-keeping, credential reference/use, login, network/process
capability, or any authority/budget/target/execution change. Whether any
`note: str` field exists outside `src/research/` (e.g. in `src/security/` or
elsewhere) is explicitly not investigated by this milestone — a separate
future scoping pass, not assumed absent.

Security invariants: identical to v0.3.411/v0.3.412 — classification stays
deterministic, local, bounded, and side-effect-free, invoked before
persistence on both the write and load paths; a refusal exposes only its
fixed category, never the candidate value, in the raised error, any Brain
response, or any log; a malicious persisted run document (a note containing a
sentinel secret written directly to the store's file) must fail closed on
load with the store's existing typed error; benign notes that merely discuss
credentials descriptively remain valid.

Test strategy: reuse the exact category/case/whitespace/benign-near-miss test
shapes already proven for the four fields covered so far, applied to all
three new note fields; a differential test proving every existing
fixture's accept/refuse outcome for non-note fields on all three records is
unchanged; three malicious-persisted-note-fails-closed-on-load tests on
`JsonFileResearchRunStore` (one per record type embedded in a run); two
service-layer regression tests on `ResearchRunManager`
(`record_claim_contradiction`, `add_evidence`) proving a secret-shaped note
is refused without a write and without reflection; impacted suites focused
first, full canonical gates once at release.

Security review (hypatia-security, 2026-09-25): PASS, no findings. Traced the
write path (`ResearchRunManager.record_claim_contradiction`, `add_evidence`,
`record_comparison_review`) and the load path
(`JsonFileResearchRunStore._parse_claim_contradiction`/`_parse_comparison_review`/
`_parse_evidence`) and confirmed the refusal is unconditionally reached on
both, `excerpt` remains completely unclassified, no other field was touched,
the raised error never carries the candidate text, and every delegated
authorization/preview path (`ClaimContradictionStepOperation`,
`EvidenceRecordingStepOperation`) funnels through the same checked
constructors with no alternate persistence route. Flagged one pre-existing,
out-of-scope observation for future work: `ResearchClaimContradictionWritePreview`
already echoes an unclassified note verbatim into a Brain response
(`ResponseComposer.research_claim_contradiction_write_preview_success`) —
unrelated to and unchanged by this diff, but a genuine gap for a future
`*WritePreview` scoping pass under item 5.

QA review (hypatia-qa, 2026-09-25): found one moderate hygiene gap recurring
from v0.3.412 — two of the three "non-note fields unaffected" differential
tests (`ResearchComparisonReviewRecord`, `ResearchEvidenceRecord`) reused
each file's shared default fixture unmodified rather than proving a
non-default value round-trips correctly with the new check active (the
`ResearchClaimContradictionRecord` version of this test already did this
correctly). Mutation testing on all three `_refuse_sensitive_input` call
sites confirmed every category/benign-near-miss/store/service test is
non-vacuous. hypatia-lead closed the gap directly: both tests now construct
with distinct non-default field values and assert those exact values round
trip. Re-run after the fix: 129 focused tests across the five impacted test
modules, OK; `black`/`ruff`/`mypy`/`git diff --check` clean.

## Historical scope: v0.3.412 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Asset Inventory note secret-ingress boundary (Bug Bounty foundation, step 5 continued) |
| Base SHA | eb3219f302b09f67354e81e07a0bb0df8eb41b72 |
| Status | delivered |
| Specialists | hypatia-epistemics: sole implementer; hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, found and hypatia-lead closed one moderate test-coverage gap; hypatia-lead: release |
| Blockers | none |

Rationale: bounded continuation of roadmap item 5, "Credential + secret
boundary", after delivered v0.3.411. v0.3.411 enforced
`ResearchSensitiveInputPolicy` on every operator-authored free-text field of
`ResearchSessionContextRecord` (the newest persistence surface at the time),
but explicitly scoped no further. Repository-grounded re-check (2026-09-25,
hypatia-lead): `ResearchSensitiveInputPolicy` is imported in exactly one file
(`ResearchSessionContextRecord.py`). Two older, still-live operator-authored
free-text `note` fields predate that boundary and remain completely
unclassified: `ResearchAssetObservationRecord.note` and
`ResearchAssetRelationRecord.note` (both from v0.3.407, both bounded to 2,000
characters — identical to the policy's own
`MAX_RESEARCH_SENSITIVE_INPUT_CHARACTERS` ceiling). An operator recording an
asset observation or relation can paste a real credential into either note
today with zero refusal, exactly the gap item 5 exists to close. Both fields
are validated in `__post_init__`, on the same record classes the asset
inventory store already round-trips through on save and load, so enforcing
here automatically covers both the write path and the malicious-persisted-
document-on-load path, mirroring v0.3.411's own discipline.

Scope: import the existing, unmodified, already-reviewed
`ResearchSensitiveInputPolicy` into `ResearchAssetObservationRecord.py` and
`ResearchAssetRelationRecord.py`; refuse `note` in each record's
`__post_init__` exactly as `ResearchSessionContextRecord` already refuses its
own free-text fields (fixed category-only message, never the candidate
value); add a one-line "never enter a secret" caption to
`src/desktop/ResearchAssetInventoryPanel.py` near its observation/relation
note entry fields, mirroring the existing Session Contexts panel caption; add
normal/refusal/persistence(load)/service regression tests to
`tests/research/test_research_asset_inventory.py` and
`tests/research/test_json_file_research_asset_inventory_store.py`.

Non-goals: no change to `ResearchSensitiveInputPolicy` itself (reused
byte-for-byte, no new category, no pattern change); no change to
`canonical_value`, `observation_id`, `program_id`, `relation_id`, or any
non-note field on either record (a canonical hostname/IP cannot syntactically
carry a secret past `canonicalize_asset_value`, so classifying it would be
inert ceremony, not a real boundary); no change to
`ResearchSessionContextRecord` (already covered); no widening to the other
`note: str` fields found elsewhere in `src/research/`
(`ResearchClaimContradictionRecord`, `ResearchClaimContradictionWritePreview`,
`ResearchComparisonReviewRecord`, `ResearchContradictionAuthorization`,
`ResearchEvidenceAuthorization`, `ResearchEvidenceRecord`) — these are a
mixed set of authorization records and derived/auto-populated fields that
need their own scoping pass, not a mechanical copy of this milestone's
pattern, and are recorded here as explicit residual future work under item 5.
No secret storage, encryption, hashing, masking-and-keeping, credential
reference/use, login, network/process capability, or any authority/budget/
target/execution change.

Security invariants: classification stays deterministic, local, bounded, and
side-effect-free, invoked before persistence on both the write and load
paths. A refusal exposes only its fixed category, never the candidate value,
in the raised error, any Brain response, or any log. A malicious persisted
asset-inventory document (a note containing a sentinel secret written
directly to the store's file, bypassing the service) must fail closed on
load with the same typed error the store already raises for other malformed
content — never a partial or fabricated asset. Benign asset/relation notes
that merely discuss credentials descriptively (e.g. "no auth header was
sent") must remain valid, matching the existing benign-near-miss discipline.

Test strategy: reuse the exact category/case/whitespace/benign-near-miss test
shapes already proven in `tests/research/test_research_session_context*`
(construction access confirmed, not assumed) against both
`ResearchAssetObservationRecord.note` and `ResearchAssetRelationRecord.note`;
a differential test proving every existing asset-inventory record/service/
store fixture's accept/refuse outcome for non-note fields is unchanged; a
save-a-malicious-note-directly-to-disk-then-load fail-closed test on
`JsonFileResearchAssetInventoryStore`, modeled on v0.3.411's own store-level
test; a desktop-reachability check that the new caption text is present on
the panel; impacted suites focused first, full canonical gates once at
release.

Security review (hypatia-security, 2026-09-25): PASS, no findings.
Independently confirmed `ResearchSensitiveInputPolicy.py` is byte-for-byte
unmodified; the refusal fires only on `note` in both records' `__post_init__`
(every other field's validation traced and confirmed unchanged); the raised
`ResearchError` carries only the fixed category label, never the candidate
text, matching `ResearchSessionContextRecord`'s existing pattern exactly; the
refusal is unconditionally reached on both the service write path and the
store's load-time reconstruction path; no code path reflects a refused note
value into a Brain response or log; the new store fault-injection tests write
raw bytes to disk bypassing the service, a genuine test; no authority, scope,
target, budget, or credential primitive was touched; the desktop change is
label-text-only.

QA review (hypatia-qa, 2026-09-25): found one moderate gap — the locked scope
promised a service-layer regression test mirroring v0.3.411's own
`test_secret_shaped_input_is_refused_without_write_or_reflection`, and none
had been added to `tests/cognition/test_research_asset_inventory_application_service.py`.
Mutation testing on both record files (temporarily disabling each
`_refuse_sensitive_input` call) proved the existing record-level tests are
non-vacuous; all five explicit `ResearchSensitiveInputClass` categories are
genuinely exercised for both fields; the benign near-miss and store
fault-injection tests are real. hypatia-lead closed the gap directly: added
`SensitiveInputRefusalPersistsNothingTests` (two tests, mirroring the
v0.3.411 service-test pattern exactly) to the application-service test file,
and a desktop-reachability assertion for the new caption text to
`tests/desktop/test_research_asset_inventory_panel.py` (the second,
cosmetic gap QA also named). Re-run after the fix: 143 focused tests across
the four impacted test modules, OK; `black`/`ruff`/`mypy`/`git diff --check`
clean on all seven changed files.

## Historical scope: v0.3.411 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Research session-context secret-ingress boundary foundation (Bug Bounty foundation, step 6) |
| Base SHA | 2d2ac281768a4739911b00f5e6eed4bc79c12519 |
| Status | delivered |
| Specialists | Codex: bounded implementation, security/QA review, gates, exact-SHA and PR CI, standard merge, and post-merge reconciliation |
| Blockers | none |

Rationale: bounded continuation after delivered v0.3.410 and roadmap item 5,
"Credential + secret boundary". The first honest boundary is at the only new
operator-authored authentication-context persistence surface: reject a small,
explicit set of high-confidence secret-bearing input forms before they can be
stored, rendered, logged, or returned in an error. The classifier reports only
a bounded category; it never returns or interpolates the candidate value.

Scope: one pure bounded sensitive-input classifier with explicit categories
for credential-bearing URLs, authorization/cookie header forms, private-key
material, secret assignments, and high-confidence token formats; enforce it
inside `ResearchSessionContextRecord` for every operator-authored free-text
field; keep refusal messages category-only; update the desktop warning and add
normal/refusal/persistence/service regression tests. Document this as a
conservative floor rather than complete secret detection.

Non-goals: no secret value storage, encryption, hashing, masking-and-keeping,
OS keychain/credential-manager integration, credential reference or scope,
credential use/audit/rotation, login/session establishment, environment or
file scanning, entropy detection, configurable patterns, override, network or
process capability, and no authority/budget/target/execution change.

Security invariants: classification must be deterministic, local, bounded,
side-effect-free, and operate before persistence. A refusal exposes only its
fixed category. Reloading a malicious store fails closed without reflecting
the secret. Benign discussion such as "no password was used" remains valid;
the policy must not claim completeness or turn descriptive context into
credential authority.

Test strategy: each explicit sensitive category; case and whitespace variants;
benign near-misses; identity/program/note enforcement; fixed non-reflective
error text; no write on service refusal; malicious persisted document fails
closed; existing session-context normal/restart/UI behavior; impacted suites;
then full canonical gates once at release.

Security review (Codex, 2026-09-25): PASS after one completeness fix. The
initial credential-bearing URL rule required `user:password@host` and would
have allowed a URL whose userinfo itself was a token (`token@host`). The rule
now refuses any non-empty URL userinfo, with a regression test. All classifiers
are bounded and side-effect-free; categories carry no candidate text; model,
service, persistence-load, and rendered failure paths were verified not to
reflect the sentinel secret. No credential or authority path was introduced.

QA review (Codex, 2026-09-25): verified every explicit category, case and
whitespace forms, benign near-misses, fixed category wording, exact field
enforcement, no-write service refusal, malicious-store fail-closed behavior,
existing round-trip/append-only behavior, desktop reachability, and version
consistency. Focused impacted suite: 45 tests, OK. Full canonical gates: 7079
tests, OK (skipped=3); Black, Ruff, MyPy, and `git diff --check` clean.

## Historical scope: v0.3.407 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Bug Bounty asset inventory: canonical asset identity (Bug Bounty foundation, step 2) |
| Base SHA | be1d13b274c88bf7b7e3e32398397dec43b2ce41 |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics: sole implementer; hypatia-security: independent review complete (no authority widening; one medium zone-scoped-address identity/scope divergence defect plus four low/informational findings, all fixed); hypatia-qa: independent review complete (three high-severity test gaps — window reachability, Bootstrap wiring, behavioral scope freshness — plus medium gaps, all closed); Lead verified the new tests with seven mutations, all caught; hypatia-release: delivering v0.3.407 |
| Blockers | none |

Rationale: continuing the bounded Bug Bounty Researcher roadmap immediately
after v0.3.406 (tri-state scope resolution). Two parallel read-only
discovery specialists (hypatia-runtime: existing target/URL/asset
representations, persistence and desktop UI precedents; hypatia-epistemics:
provenance/identity/relationship semantics) confirmed, with file:line
citations, that **no asset entity of any kind exists anywhere in `src/`
today** — every hostname/IP/URL representation found is either
`ResearchTargetScope`/`TargetHostRule` (scope-authorization policy, not a
discovered-asset record) or a bare `str` field on an unrelated value object
(research-source citation URLs, transport parameters, Kali operation
preview inputs). The two existing Kali operation kinds
(`DNS_RECORD_LOOKUP`/`HTTPS_HEADER_LOOKUP`) produce only raw, unparsed
`stdout_lines`/`candidate_lines` text — no structured resolved-address or
header data exists anywhere to seed an asset record from. This confirms
recon-result ingestion (the roadmap's next step) has nothing to ingest
into yet, and that this milestone's only honest population path is
operator-authored entry, mirroring how `ResearchTargetScope` itself is
already desktop-authored today.

Discovery also found the two strongest reusable precedents: (1)
`src/research/ResearchSourceTemporalHistory.py` — a canonical
`resource_identity: str` field kept structurally separate from a tuple of
dated, independently-recorded observations, derived fresh from already-
recorded data on every read and never itself persisted as a merged/mutated
entity (`temporal_history_for()`); this is the exact identity/observation
split this milestone adopts. (2) `ResearchAuthorizer`'s own docstring
discipline against adding an enum member "for symmetry" before a real
capability needs it — directly applied to the new provenance vocabulary
below (exactly one member, not a speculative set). Discovery further
confirmed `program_id` is a purely opaque, unregistered `str` everywhere
in this codebase (no `Program` entity exists to extend or duplicate), and
that `SourceIdentity.identity_of`'s `www.`-stripping/resource-identity
normalization is the wrong tool for hostname identity (it is calibrated
for "same research document," not "same network host") — hostname
canonicalization instead reuses `ResearchTargetScope`'s own tested
`_dns_name` normalization directly, so asset identity and scope-matching
can never silently drift apart.

Scope: five new frozen types in `src/research/`:
- `ResearchAssetKind` (`StrEnum`: `HOSTNAME`, `IP_ADDRESS` only — `URL`/
  `SERVICE`/`ENDPOINT` explicitly deferred, since no structured data exists
  yet to populate them honestly, and a URL asset kind risks conflating with
  the existing, conceptually distinct `ResearchSourceRecord.url` citation
  field without a dedicated design pass).
- `ResearchAssetProvenanceKind` (`StrEnum`: exactly one member,
  `OPERATOR_AUTHORED` — no `IMPORTED_TOOL_RESULT`/`PASSIVE_DISCOVERY`
  member yet, since nothing in this codebase produces that data; extending
  this enum is explicitly recon-result-ingestion's job, a later milestone).
- `ResearchAssetRelationKind` (`StrEnum`: exactly one member,
  `RESOLVES_TO` — directional, hostname-to-address only).
- `ResearchAssetObservationRecord` (frozen dataclass: `observation_id`,
  `program_id`, `kind`, `canonical_value`, `provenance`, `note`,
  `recorded_at`) — one immutable, append-only fact. `canonical_value` must
  already be canonical at construction (fail-closed `__post_init__`
  re-validation via the kind-appropriate canonicalizer — never silently
  normalized/fixed up).
- `ResearchAssetRelationRecord` (frozen dataclass: `relation_id`,
  `program_id`, `source_kind`, `source_value`, `related_kind`,
  `related_value`, `kind`, `note`, `recorded_at`) — references assets by
  `(kind, canonical_value)`, not a synthetic asset ID (matching the
  derived-projection identity model below); self-relation rejected.
- `ResearchAsset` (frozen dataclass, the derived read-model: `program_id`,
  `kind`, `canonical_value`, `observations: tuple[ResearchAssetObservationRecord, ...]`,
  `first_seen`/`last_seen` derived as min/max of its observations'
  `recorded_at`) plus a pure `assets_for_program(program_id, observations)
  -> tuple[ResearchAsset, ...]` builder in the same file, grouping the flat
  observation list by `(program_id, kind, canonical_value)` — modeled
  directly on `ResearchSourceTemporalHistory.py`'s type-plus-builder shape.
  **Never persisted as a merged entity** — recomputed fresh from the raw
  observation list on every read, so there is no "find an existing asset
  and mutate it" persistence logic anywhere.

One new public function on the existing `ResearchTargetScope.py` (zero
changes to any existing function, class, or line — purely additive, same
discipline as v0.3.406): a public wrapper exposing `_dns_name`'s
normalization for reuse by the new asset-identity module, so hostname
canonicalization and scope-hostname-matching normalization can never
silently diverge. IP canonicalization reuses the stdlib
`ipaddress.ip_address(value)` directly (already used elsewhere in this
codebase), no new function needed.

New persistence: `JsonFileResearchAssetInventoryStore` (`src/research/`) —
one atomic file holding two flat lists (`ResearchAssetObservationRecord`,
`ResearchAssetRelationRecord`), schema version 1 (a brand-new store, no
legacy version to carry), strict field-set validation, bounded max counts,
globally-unique `observation_id`/`relation_id` rejection on save — modeled
on `JsonFileFailureLessonStore`'s simpler flat-list-atomic-store shape
(not `JsonFileResearchProgramScopeRevisionStore`'s stricter forced-
append-only-history constraint, which is specific to that store's
revocation semantics and not needed here since observations are already
inherently append-only by construction).

New service layer: `ResearchAssetInventoryApplicationService`
(`src/cognition/`, mirroring `ResearchProgramScopeEnrollmentService`'s
shape rather than the heavier `ResearchRunManager`) — validates
canonicalization, enforces program isolation (an asset/relation belongs to
exactly one `program_id`; relations may only reference two assets already
observed in that same program — fail closed on cross-program references),
records observations/relations, and derives `assets_for_program`/
`relations_for_program` read projections. New read-only scope-integration
function: given one `ResearchAsset` and the *currently active*
`ResearchProgramScopeRevision` for its program (looked up fresh, never
cached), dispatch to the existing v0.3.406 `resolve_hostname`/
`resolve_addresses` by `asset.kind` and return the tri-state
`ResearchTargetScopeResolution` — never persisted, always recomputed.

Desktop: a new "Asset Inventory" panel reusing the exact `ttk.Treeview` +
scrollbar + `<<TreeviewSelect>>` + `iid -> detail-text` dict pattern
already established by the v0.3.399 mission-audit traceability view (no
new widget-construction idiom introduced), listing assets per program with
kind/canonical value/observation count/first-last-seen and a "current
scope resolution (recomputed live from active policy)" column explicitly
labelled as such — never a stored/stale label. Simple entry fields for an
operator to record a new observation (kind + value + note) and a new
relation (two known assets + kind + note), wired through new Brain
intents mirroring the existing preview-then-record pattern used throughout
this codebase.

Non-goals: no active recon of any kind (no Nmap/httpx/ffuf/feroxbuster/
Nuclei/subfinder/amass execution, no DNS brute force, no HTTP probing, no
port scanning, no fuzzing, no exploitation, no automatic validation) — this
milestone only builds the model recon-result ingestion will later populate.
No `URL`/`SERVICE`/`ENDPOINT` asset kinds (deferred). No relationship kinds
beyond `RESOLVES_TO` (no `HAS_SUBDOMAIN`/`EXPOSES_SERVICE`/`HOSTED_ON`/
`OBSERVED_REDIRECT_TO` yet — deferred, each needs its own asset-kind
prerequisite this milestone doesn't build). No provenance kind beyond
`OPERATOR_AUTHORED`. No global, cross-program asset graph — assets and
relations are strictly program-scoped by field, matching
`ResearchProgramScopeRevision`'s own opaque-`program_id` convention, not a
new `Program` entity. No change to `ResearchTargetScope.py`'s existing
`require_hostname`/`require_addresses`/`resolve_hostname`/
`resolve_addresses`/`TargetHostRule`/`_dns_name` behavior — the only
change to that file is one new additive public wrapper function. No change
to `ResearchProgramScopeEnrollmentService`'s create/revoke workflow, to
`SourceIdentity`, or to any authorization/execution gate. Persisted scope
resolution as durable authority is explicitly forbidden — every rendered
scope status is recomputed live, and a restart/reload must never let an
old `IN_SCOPE` reading substitute for a fresh check against the active
revision. No new authority, budget, target, or credential primitive.

Acceptance criteria: canonical hostname identity is case-normalized,
trailing-dot-normalized, and validated via the same `_dns_name` logic
`ResearchTargetScope` already uses (proven by a differential test showing
the wrapper's output is byte-identical to calling the existing scope
matching path); sibling hosts (`api.example.com`/`www.example.com`) and
suffix-trick lookalikes (`attackerexample.com` vs `example.com`) never
collapse into the same canonical identity; repeated observations of the
same `(program_id, kind, canonical_value)` produce one derived `ResearchAsset`
with multiple preserved observations, never a duplicate asset; IP
canonicalization is deterministic for both IPv4 and IPv6 (where the
existing engine already supports IPv6); a `RESOLVES_TO` relation can only
be recorded between two assets already observed in the same program
(fail-closed cross-program/cross-observation rejection); asset existence
alone never appears anywhere as sufficient grounds for a resolve-to-`IN_SCOPE`
claim — scope resolution is always a fresh call into the unchanged
v0.3.406 resolver against the currently active revision; a
CNAME/vendor/redirect-style relationship never widens or implies scope
(structurally true here since `RESOLVES_TO` carries no scope semantics of
its own — proven by a differential/inertness test mirroring v0.3.405/
v0.3.406's pattern); restart/reload produces identical derived assets from
the same persisted observation list, and never fabricates a fresher scope
reading than a live check would produce; malformed/duplicate/cross-program
observation or relation writes fail closed; full canonical gates green.

Specialist ownership: hypatia-epistemics is the sole implementer (matches
this milestone's domain — identity/provenance/relationship semantics —
and avoids the dual-writer file-conflict risk). hypatia-security is the
primary independent reviewer, given the asset-existence-is-not-authority
invariant is the central safety property of this milestone; hypatia-qa
reviews independently afterward; hypatia-release delivers only after both
reviews and full canonical gates are green.

Security implications: the critical property is that no code path anywhere
treats asset existence, an asset relationship, or a persisted observation
as sufficient grounds for an active action or a scope grant. hypatia-security
must independently verify: recorded assets/relations never feed
`ResearchTargetScope`/`ResearchClaimCalibrator`/any authorization path
except through the unchanged, always-live `resolve_hostname`/
`resolve_addresses` calls; a `RESOLVES_TO` relation cannot be read as
"the related address is now authorized"; program isolation is real (no
code path can read one program's asset/relation records while resolving
another program's scope); restart/reload cannot make a stale resolution
substitute for a fresh one; malformed canonical values fail closed rather
than silently coercing into a plausible-looking hostname/address.

Epistemic implications: this is the core of the milestone. Canonical
identity must never conflate genuinely distinct hosts (siblings, suffix
lookalikes, apex-vs-subdomain) and must never silently merge two
observations that only coincidentally share surface text. Provenance
(`OPERATOR_AUTHORED`) must be literal and attributable, never inferred or
model-generated on the asset's behalf. Discovery is not authority: nothing
about recording, linking, or re-observing an asset may itself imply
current-world truth or testing permission, mirroring this file's existing
"historical observation != current-world truth" and "revalidation !=
freshness" invariants.

Persistence implications: one new store, schema version 1 (new store, not
a version bump on an existing one); strictly append-only observation/
relation records; no mutation-in-place of any persisted record; derived
`ResearchAsset` projections are never themselves written to disk.

Restart/replay implications: the derived-projection design makes this
structurally safe — `assets_for_program` recomputes identical output from
the same persisted observation list on every call, and the scope-
resolution dispatch always re-queries the active program-scope revision
live, so a restart can neither fabricate a new asset nor resurrect a stale
`IN_SCOPE` reading as current authority.

Authority/budget/target/credential implications: none created, widened,
or restored. This milestone adds a purely descriptive inventory layer over
already-existing, already-reviewed scope-authorization infrastructure; the
only real authority gates (`require_hostname`/`require_addresses`, program-
scope revision validity) remain completely untouched.

Test strategy: canonicalization tests (hostname case/trailing-dot
normalization matching `ResearchTargetScope`'s own behavior exactly via a
differential test; sibling-host and suffix-trick non-collapse; IPv4/IPv6
canonicalization); dedup tests (repeated observation of the same identity
produces one derived asset with growing, order-preserved observations, not
a duplicate); relation tests (`RESOLVES_TO` creation, self-relation
rejection, cross-program rejection, reference-to-unobserved-asset
rejection); scope-integration tests (known asset + `IN_SCOPE` policy ->
current resolution `IN_SCOPE`; + explicit exclusion -> `OUT_OF_SCOPE`; + no
matching policy -> `UNCERTAIN`; persisted asset does not become authorized
on restart; a `RESOLVES_TO` relation never moves the resolution); an
inertness/differential test proving asset inventory data never changes
`ResearchClaimCalibrator`/`EvidenceSupportProfile`/any existing consumer's
output (mirroring the v0.3.405/v0.3.406 pattern); persistence tests
(round-trip, malformed-state fail-closed, duplicate-ID rejection, bounded
size ceilings); a real constructed-widget desktop reachability test for
the new panel, including a non-default value proven to survive end-to-end
(learning directly from the exact gap QA found and closed in v0.3.405).

## Historical scope: v0.3.406 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Explicit tri-state target-scope resolution (Bug Bounty foundation, step 1) |
| Base SHA | ad7de6cce455f8a931459190b18849de05bd5826 |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics: sole implementer (avoided the dual-writer file-conflict risk); hypatia-security: independent review, PASS, no findings, traced every consumer of the new tri-state type and confirmed no path lets `UNCERTAIN`/bare `IN_SCOPE` reach an active action; hypatia-qa: independent review, PASS, extensive mutation testing on unaddressed-host defaulting/exclusion-precedence/subdomain-suffix-matching/unmatched-address handling (all mutations caught), found two minor test-coverage gaps (one fixed with a new wildcard-suffix-trick test, independently verified non-vacuous; one confirmed already accurately scoped, no change needed); hypatia-release delivered v0.3.406 |
| Blockers | none |

Rationale: user-directed pivot. The user explicitly redirected product
direction away from the previously-planned pairwise source-relation
milestone (not implemented this session — recorded as a valid future
epistemics milestone, not discarded) toward the start of a bounded "Bug
Bounty Researcher" roadmap, whose stated first required foundation is a
scope-policy model with the invariant: the operator explicitly defines
authorized scope; Hypatia may actively interact only with `IN_SCOPE`
targets; `OUT_OF_SCOPE` targets must never receive active testing;
`UNCERTAIN` scope must fail closed and require operator clarification.

Repository-grounded discovery (three parallel read-only investigations, an
Explore-then-Plan design pass, plus a targeted follow-up check, all
2026-09-23) found this is not greenfield work: a substantial, tested
bug-bounty program-scope backbone already exists —
`src/research/ResearchTargetScope.py` (`TargetHostRule` exact/subdomain-only
host matching + CIDR `allowed_networks`/`excluded_networks`, exclusions
always win, "not explicitly allowed" already fails closed via
`require_hostname()`/`require_addresses()`); `ResearchProgramScopeRevision.py`
(its own docstring: "One immutable, human-confirmed bug-bounty program scope
revision" — digest-bound, ≤1-hour-validity-ceilinged, one-way
human-only revocation, single-active-revision-per-`program_id` succession);
`ResearchProgramScopeExecutionPolicy.py` (permitted check classes/ports/
rate/request/time budgets, digest-bound alongside scope);
`ResearchProgramScopeEnrollmentService.py` (two-phase preview→confirm→
revoke, persist-before-publish). Enforced at three real call sites:
`ScopedPublicHttpsUrlValidator` (research source fetch, pre- and
post-DNS-resolution re-checks, literal-IP consistency verification),
`TargetResearchDraft` (desktop single-source-URL authoring),
`KaliOperationPreviewApplicationService` (inert Kali preview gating, no
process execution). Desktop reachability already exists via
`TkinterDesktopWindow.py`'s "Kali" tab reading
`program_scope_enrollment_service.revisions`.

The one confirmed genuinely missing piece: no `IN_SCOPE`/`OUT_OF_SCOPE`/
`UNCERTAIN` tri-state exists anywhere. Matching today is strictly boolean —
`require_hostname`/`require_addresses` raise identically whether a host is
explicitly excluded or simply not addressed by any rule, collapsing two
operator-meaningfully-different outcomes into one refusal. This is exactly
the distinction the stated invariant requires, and `require_*` cannot
express it today (it only ever succeeds or raises).

Presented this finding to the user via a clarifying question (given the
scale of pre-existing infrastructure materially reframes "the smallest
substantial milestone") with three framings: (a) add the tri-state resolver
only, reusing all existing matching/persistence/enforcement unchanged; (b)
the resolver plus extending program-enrollment desktop authoring if it
proved thinner than needed; (c) something else. User selected (a), the
smallest option.

Scope: two new frozen types — `src/research/ResearchTargetScopeResolutionStatus.py`
(a `StrEnum`: `IN_SCOPE`/`OUT_OF_SCOPE`/`UNCERTAIN`, plus a `.settles`
property, modeled on `ResearchAttemptResolution.py`'s fail-closed-on-
ambiguity discipline — the strongest existing precedent found for a true
tri-state security-decision enum, not the merely-descriptive `UNKNOWN`
members on assessment dimensions like `ResearchSourceApplicability`) and
`src/research/ResearchTargetScopeResolution.py` (a frozen dataclass:
`status`, `target`, `matched_rule: str | None` — `None` exactly when
`UNCERTAIN`, non-empty otherwise — `reason: str`, all bounded and validated
in `__post_init__`). Two new pure, additive methods on the existing
`ResearchTargetScope` (same file): `resolve_hostname(hostname)` and
`resolve_addresses(addresses)`, reusing the exact same normalization/
matching primitives (`_dns_name`, `TargetHostRule.matches`, `_in_networks`)
`require_hostname`/`require_addresses` already use, in the same
exclusion-checked-first order, returning a typed result instead of raising.
No schema or persistence change — `ResearchTargetScope` itself gains no new
field, so no store/codec/digest change, no schema-version bump; backward
compatibility is automatic since the resolver is a pure function over
already-persisted, already-tested scope state.

Visibility, kept narrow: (1) `KaliOperationPreviewApplicationService.py`
additionally calls the new resolver when a preview is refused, to include
the `OUT_OF_SCOPE` vs `UNCERTAIN` distinction in the refusal detail text —
without changing whether the preview is refused (both statuses still
refuse identically; explanation only, mirroring the v0.3.402/v0.3.403
refusal-explanation discipline); (2) `TargetResearchDraft.py` and its
`TkinterDesktopWindow.py` dialog counterpart show the tri-state resolution
for a drafted source URL's hostname; (3) one new read-only Brain intent
(e.g. `research_target_scope_resolution_preview`) exposing the resolver
directly through `CognitiveEngine.py`/`DesktopController.py`, matching the
existing preview-intent pattern, for checking a hostname against a scope
with zero side effects.

Non-goals: no change to `require_hostname`/`require_addresses` themselves,
`ScopedPublicHttpsUrlValidator`, `KaliOperationAuthorizationApplicationService`,
any authorization/execution gate, or `ResearchProgramScopeEnrollmentService`'s
create/revoke workflow. No new program/engagement entity beyond the
existing `program_id` string. No new desktop program-scope-enrollment
authoring UI. No wildcard/CIDR matching-algorithm changes. No automatic
scope inference of any kind (nothing widens scope from a redirect, CNAME,
discovered asset, or certificate-transparency result — already true today;
this milestone adds regression tests locking that in, not new behavior).
No recon, tool execution, vulnerability scanning, or active-testing
automation of any kind.

Acceptance criteria: `resolve_hostname`/`resolve_addresses` correctly
classify — exact host match, subdomain-only wildcard match (apex not
auto-included), suffix-trick non-match (`attackerexample.com` vs
`example.com`), lookalike-domain non-match, literal-IP/CIDR allow and
exclude, exclusion-precedence-over-inclusion, and the core new case (a host
addressed by no rule at all resolves `UNCERTAIN`, never `OUT_OF_SCOPE`);
redirect/CNAME/CDN/third-party-API/certificate-transparency-style
"discovered but never authored into a rule" scenarios all resolve
`UNCERTAIN`, proving discovery never implies scope; restart/reload and
legacy (v1-schema) persisted state produce identical resolutions, proving
no session-derived state leaks in; a differential test proves every
existing `ScopedPublicHttpsUrlValidator`/`KaliOperationPreviewApplicationService`
test fixture's actual accept/refuse outcome is byte-for-byte unchanged
before and after this milestone; full canonical gates green.

Specialist ownership: hypatia-epistemics is the sole implementer, to avoid
the dual-writer file-conflict risk this constitution warns against (both
specialists would otherwise touch the same `src/research/` files).
hypatia-security is the primary independent reviewer for this milestone
given its subject matter (authority-adjacent explanatory surface over a
real security boundary, even though it changes no enforcement);
hypatia-qa reviews independently afterward; hypatia-release delivers only
after both reviews and full canonical gates are green.

Security implications: the critical property is that this milestone adds
zero new authority — `IN_SCOPE` from the new resolver must never be
readable as, or substitutable for, an actual execution grant; only the
unchanged `require_hostname`/`require_addresses` gates and further
upstream authorization records (`ResearchKaliOperationAuthorization`,
program-scope revisions) create real execution authority. hypatia-security
must independently verify `require_hostname`/`require_addresses`,
`ScopedPublicHttpsUrlValidator`, and
`KaliOperationAuthorizationApplicationService` are byte-for-byte unchanged,
and that no code path anywhere treats a bare `resolve_*` result as
sufficient to proceed with a fetch or operation.

Epistemic implications: the tri-state distinction is itself an
epistemic/explainability improvement — `UNCERTAIN` is an honest "this
policy does not address this target" answer, never silently folded into
either confident state. `matched_rule`/`reason` must cite only literal,
already-persisted rule data, never inferred or model-generated text.

Persistence implications: none — no schema, store, or codec change of any
kind; the resolver is a pure read over the existing `ResearchTargetScope`
shape.

Restart/replay implications: none — resolution is a stateless pure
function recomputed fresh from persisted scope data on every call; a test
proves identical results across a fresh process reload.

Authority implications: none created, widened, or restored. Discovery vs.
active-testing authority stays structurally separated exactly as today:
resolving a hostname is a side-effect-free read that grants nothing by
itself.

Budget implications: none — no budget primitive touched.

Target implications: none — no target identity semantics changed; the
resolver only classifies an already-given hostname/address against an
already-persisted scope, never selects or substitutes a target.

Credential implications: none — no credential primitive touched.

Provenance requirements: `matched_rule`/`reason` must be literal citations
of the exact persisted rule (or its absence) that produced the result —
never inferred, paraphrased, or model-generated — mirroring this file's
existing goal-explanation discipline (`ResearchMissionGoalExplanation`'s
"does not interpret source/model prose" invariant).

Test strategy: exhaustive adversarial matching cases (see acceptance
criteria) in a new test class colocated with
`tests/research/test_research_target_scope_store.py`'s existing
convention; a `resolve_addresses` mirror of the network-only cases; a
`KaliOperationPreviewApplicationService` refusal-detail differential test
proving unchanged accept/refuse behavior; a desktop-reachability test for
the `TargetResearchDraft` integration using this session's established
real-constructed-widget pattern.

## Historical scope: v0.3.405 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Primary-vs-secondary source evidence type: a fifth operator-authored assessment dimension |
| Base SHA | 06564ff12eb3a708a6288091125a59bc1459eaf5 |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics: discovery (full fan-out map of the 4 existing dimensions, cited file:line) + implementation (new `ResearchSourceEvidenceType` enum threaded through 12 `src/` files) + one follow-up fix closing a QA-found desktop test-coverage gap; hypatia-security: independent review, PASS, no findings, independently confirmed inertness by repo-wide grep and re-read of `ResearchClaimCalibrator`/`EvidenceSupportProfile`/`AssessmentWarningRules`; hypatia-qa: independent review, found one real narrow gap (no end-to-end desktop test proved a non-default `evidence_type` survived the UI→controller call), fixed and independently re-verified non-vacuous via temporary mutation testing; hypatia-release delivered v0.3.405 |
| Blockers | none |

Rationale: no milestone was open (v0.3.404 delivered and merged to
`origin/main`; HEAD was a docs-only ledger reconciliation commit). Selected
from `docs/Roadmap/Master_Roadmap.md`'s "Future direction" section,
candidate C ("Epistemic (not numeric) source comparison"). The roadmap's
own text names a concretely missing, safely-boundable slice of that
candidate: "Adding these as new *operator-authored* fields (citation, not
inference) would fit the existing discipline" — distinguishing this from
the auto-*inferring* half of candidate C, which explicitly "must not be
built without a separate, explicit design pass" and is out of scope here.
Directly matches this session's product-direction priorities: "primary/
original evidence should be preferred where appropriate."

Re-verified directly against current code before locking (hypatia-lead +
hypatia-epistemics discovery, 2026-09-23): `ResearchSourceAssessmentRecord`
already carries 4 operator-authored closed-vocabulary dimensions
(`usefulness`, `applicability`, `independence`, `publication_status`), all
added together in v0.3.195 (schema version 11; current
`JsonFileResearchRunStore._SCHEMA_VERSION` is 20). The roadmap's claim that
"directness of evidence" is absent is stale — `applicability`
(DIRECT/PARTIAL/BACKGROUND_ONLY/UNRELATED) already covers it. What remains
genuinely absent, confirmed by a repository-wide grep with zero matches:
any field distinguishing a firsthand/primary source from a secondary
report of one or a tertiary summary of those.

Fan-out discovery (hypatia-epistemics, read-only, cited file:line):
`independence` is the one existing dimension with a large, entangled
footprint (98 occurrences/26 files) because it feeds
`EvidenceSupportProfile.independence_confirmed`, which changes the claim-
calibration ceiling (`ResearchClaimCalibrator.py:291-298`), and has
dedicated consumers in `HypothesisSupportCorrection.py`,
`ResearchFailureLessonDeriver.py`, `ResearchHypothesisAppraiser.py`,
`ResearchKnowledgeGapDetector.py`, `ResearchEvidenceCompletionEvaluation.py`
and its own desktop review module. `publication_status` (36 occurrences/12
files, all real touch points, zero prose false positives) is the smallest,
purely presentational existing dimension: stored/validated field, one
display line per renderer, one entry in the shared symmetric
`AssessmentWarningRules` table (advisory-only, mutates no canonical
state), one count-dict in the read-only provider-quality report. The new
field is modeled on `publication_status`'s footprint, explicitly not on
`independence`'s.

Scope: a new `src/research/ResearchSourceEvidenceType.py` — a frozen
`StrEnum` (`UNKNOWN` default, `PRIMARY`/`SECONDARY`/`TERTIARY`) — and a new
`evidence_type: ResearchSourceEvidenceType = ResearchSourceEvidenceType.UNKNOWN`
field threaded through exactly the same touch points `publication_status`
uses today: `ResearchSourceAssessmentRecord.py` (field + `__post_init__`
isinstance check), `ResearchSourceAssessmentWritePreview.py` (mirrored
field + check), `ResearchRunManager.py` (`preview_source_assessment_write`,
`record_source_assessment`, `_normalize_source_judgement`,
`_identical_assessment` — add as a 5th element of the judgement tuple),
`JsonFileResearchRunStore.py` (schema version 20 -> 21,
`_ASSESSMENT_FIELDS_V21 = _ASSESSMENT_FIELDS_V11 | {"evidence_type"}`, one
more `elif schema_version < 21` branch in `_parse_assessment`'s cascade,
serialization line), `ResearchRunMarkdownRenderer.py` (one more bullet
line), `ResearchReflectionGenerator.py`'s `_assessment_revision_detail`
(one more tuple entry), `ResearchProviderQualityProfile.py` +
`ResearchProviderQualityEvaluator.py` (one more count-dict field, named
`evidence_type` to match the field name), `CognitiveEngine.py`'s
`_research_source_assessment_write_values` (one more
`research_source_evidence_type` metadata key, defaulting to `"unknown"`
exactly like the other 4), `DesktopController.py` (`evidence_type` param
threaded through `preview_research_source_assessment_write`,
`record_research_source_assessment`,
`_research_source_assessment_write_metadata`), `TkinterDesktopWindow.py`
(one more `tk.StringVar`, one more tuple entry in the existing
label/variable/vocabulary loop that already builds a `ttk.Label` +
readonly `ttk.Combobox` generically, the fixed-row label below the loop
bumped by one row, one more display line in the assessment-history/
current-state f-strings, one more `.get()` feeding the controller call).

`_parse_judgement`'s current single hardcoded `if schema_version < 11`
threshold (shared by all 4 existing fields because they share a birth
version) must become per-field-aware — add a `min_version` parameter,
called with `11` for the 4 existing fields and `21` for `evidence_type` —
this is the one piece of genuinely new code shape in this milestone, not a
copy-paste of the existing pattern.

Non-goals: no change to `EvidenceSupportProfile`, `ResearchClaimCalibrator`'s
ceiling computation, `AssessmentWarningRules` (no new warning-rule entry —
adding one would mean deciding what combination of primary/secondary/
tertiary and other state deserves a warning, which is a judgement call
this milestone deliberately does not make), the reputation ledger, or any
of `HypothesisSupportCorrection.py`, `ResearchFailureLessonDeriver.py`,
`ResearchHypothesisAppraiser.py`, `ResearchKnowledgeGapDetector.py`,
`ResearchEvidenceCompletionEvaluation.py`, `MissionSourceIndependenceReview.py`
(the last already forward-carries the other dimensions unchanged when
writing an independence-only revision — `evidence_type` joins that
unchanged-carry-forward set, not a new special case). No automatic or
inferred classification of any kind — this is a citation-only field,
exactly like the 4 that already exist; a build that guessed `primary` from
a domain name or date would be inventing a judgement nobody made. No
extension of `SourceAssessmentStepOperation.py`/plan-authored assessments
— that operation already does not thread any of the 4 existing structured
dimensions (only `information_trust`), so `evidence_type` inherits the
same pre-existing gap; extending it is a separate scope decision, not a
mechanical copy of this milestone's pattern, and is recorded as residual/
future work. No change to `information_trust`, `usefulness`,
`applicability`, `independence`, or `publication_status` themselves. No
new authority, budget, target, or credential primitive of any kind.

Affected modules: `src/research/ResearchSourceEvidenceType.py` (new),
`ResearchSourceAssessmentRecord.py`, `ResearchSourceAssessmentWritePreview.py`,
`ResearchRunManager.py`, `JsonFileResearchRunStore.py`,
`ResearchRunMarkdownRenderer.py`, `ResearchReflectionGenerator.py`,
`ResearchProviderQualityProfile.py`, `ResearchProviderQualityEvaluator.py`,
`src/cognition/CognitiveEngine.py`, `src/desktop/DesktopController.py`,
`src/desktop/TkinterDesktopWindow.py`, plus their corresponding test files.

User-visible outcome: an operator recording a source assessment from the
desktop's existing assessment-recording panel sees a 5th dropdown —
primary / secondary / tertiary / unknown — beside the existing usefulness/
applicability/independence/publication-status dropdowns, using the exact
same widget pattern. The value is purely descriptive: it appears in the
assessment display, the assessment-history list, the run's Markdown
export, and the read-only provider-quality report; it changes no ranking,
no reputation, no claim, no confidence, and no calibration ceiling.

Acceptance criteria: `ResearchSourceEvidenceType` has exactly 4 values
(`UNKNOWN` default plus the 3 named above); every one of the touch points
listed in Scope reflects the new field symmetrically with the existing 4;
a pre-v21 run store record decodes `evidence_type` as `UNKNOWN` with no
backfill or inference (legacy-load test, modeled on
`tests/research/test_json_file_research_run_store.py`'s existing v10/v11
pattern); an unrecognised `evidence_type` value at v21 fails closed; a
record missing the `evidence_type` key at exactly v21 fails closed; a
full save/load round trip is lossless; the desktop combobox is reachable
through a real constructed `Tk` widget test, not merely a controller-level
check; `ResearchClaimCalibrator`'s computed warnings/ceilings are
regression-tested to be byte-for-byte identical with and without a
non-`UNKNOWN` `evidence_type` on otherwise-identical fixtures, proving the
field is genuinely inert to calibration; `MissionSourceIndependenceReview`
carries a non-default `evidence_type` forward unchanged when only
`independence` is revised; full canonical gates green.

Specialist ownership: hypatia-epistemics owns the full implementation
(type design already drafted during discovery; the touch points span
`src/research/` and the `src/desktop/`+`src/cognition/` wiring layer, but
form one cohesive feature with heavy file overlap across nearly every
touch point, so a single implementer avoids the multi-writer conflict risk
this constitution warns against). hypatia-security and hypatia-qa review
independently after integration. hypatia-release delivers only after both
reviews and full canonical gates are green.

Test strategy: schema-boundary tests (pre-v21 legacy load, v21 missing-
key fail-closed, unrecognised-value fail-closed) modeled directly on the
existing v10/v11 tests; a full round-trip save/load test; a real
constructed-`Tk`-widget desktop reachability test for the new combobox
(not a controller-only check); a `ResearchClaimCalibrator`
non-interaction/inertness regression test (differential, not a substring
check); a `ResearchReflectionGenerator` revision-detail test naming
`evidence_type` when it changes; a `ResearchProviderQualityEvaluator`
count-dict test; a `MissionSourceIndependenceReview` carry-forward test;
`CognitiveEngine`/`DesktopController` metadata-threading tests mirroring
the existing 4-dimension pattern.

Security implications: the critical property is that `evidence_type`
never becomes load-bearing by accident — hypatia-security must
independently confirm it is not read by `EvidenceSupportProfile`,
`ResearchClaimCalibrator`'s ceiling logic, the reputation ledger, or any
authorization/budget/execution path, and that no new warning-rule entry
was added. Also confirm the new metadata key in `CognitiveEngine.py`
follows the same untrusted-input handling as the existing 4 (defaults to
`"unknown"` on anything unrecognised, never raises on malformed desktop
input, never accepts a value that bypasses the enum's closed vocabulary).

Epistemic implications: this is the core of the milestone. `evidence_type`
must remain a pure citation (a human saying what kind of witness a source
is), never an inference from source text, domain name, publication date,
or any automated heuristic. It must not be conflated with `independence`
(which answers whether two sources are one witness or two) — a primary
source that is also the only source is still exactly one source, and
recording `PRIMARY` must never itself imply, suggest, or contribute to an
independence or corroboration judgement.

Persistence implications: one new optional-with-default field, additive
only; `JsonFileResearchRunStore` schema version 20 -> 21; strict
`set(document) == expected_fields` validation at load, matching the
existing fail-closed discipline exactly; no backfill or inference for
pre-v21 records.

Restart/replay implications: none — `evidence_type` carries no status
transition and is not read by any execution/replay path; it is decoded
identically on every load regardless of restart history.

Authority/budget/target/credential implications: none — no primitive of
any kind is created, restored, or altered; this milestone only adds one
more citation-only descriptive field to an existing, already-reviewed
operator-authored record.

Provenance requirements: `evidence_type` is always attributed to the
operator who recorded the assessment (via the existing assessment
record's `assessment_id`/`recorded_at`), never inferred or attributed to a
model, source, or automated process; superseded assessments preserve
their own `evidence_type` value exactly as they do for the other 4
dimensions today (no rewriting of history).

## Historical scope: v0.3.404 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Truncated-valid-prefix-on-load fault-injection coverage for every durable JSON store |
| Base SHA | 4c0288476510258d5efcc1bb04e0976187bb3b5d |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-runtime: implementation, 18 new tests across all 18 `JsonFile*Store` classes, no `src/` change needed (every store already failed closed); hypatia-security: independent review, PASS, no findings, independently re-read all three authority/budget-bearing stores' `load()` paths and their downstream consumers; hypatia-qa: independent review, PASS, no findings, verified non-vacuous via temporary mutation testing (reverted a store's fail-closed raise to `return []`, confirmed the new test failed, restored the file, confirmed `git diff` clean); hypatia-release delivered v0.3.404 |
| Blockers | none |

Rationale: selected from `docs/Roadmap/Master_Roadmap.md`'s own "Default
development order". Item 1 (Evaluate -> Adapt) is delivered, v2 explicitly
blocked on a human cross-mission authority/budget decision. Item 3 (Tool
registry + policy engine) is explicitly flagged authority-adjacent and
requiring a human check-in before autonomous implementation — excluded per
standing instructions. Item 2 (persistence/concurrency/cancellation
hardening) is the next legitimate item: the roadmap's own Phase 7 entry
names one still-open, precisely bounded residual — "Corrupted/truncated
state handling on **load**" — with the exact wording: existing tests cover
hand-written malformed content (`"{ not json"` style strings), but "the
specific truncated-valid-prefix fixture itself is confirmed absent across
every `JsonFile*Store` test file checked, not merely undocumented."

Re-verified directly against current code before locking (hypatia-lead,
2026-09-23): 18 `JsonFile*Store` classes exist in `src/` (`grep -rl "class
JsonFile.*Store" src/`): `JsonFileResearchExecutionStore`,
`JsonFileResearchRunStore`, `JsonFileResearchSourceContentStore`,
`JsonFileResearchKaliOperationAuthorizationStore`,
`JsonFileDeferredExecutionGrantStore`, `JsonFileResearchPlanAuthorizationStore`,
`JsonFileOneShotDeferredExecutionScheduleStore`, `JsonFileBackgroundTaskStore`,
`JsonFileHypothesisStore`, `JsonFileFailureLessonStore`,
`JsonFileReflectionReportStore`, `JsonFileCuriosityQuestionStore`,
`JsonFileVulnerabilityGraphStore`, `JsonFileResearchTargetScopeStore`,
`JsonFileResearchProgramScopeRevisionStore`, `JsonFileMemoryStore`,
`JsonFileSessionStore`, `JsonFileKnowledgeRelationStore`. Every one already
fails closed on unreadable/malformed content with its own typed error
(`ResearchError`, `MemoryError`, `SessionError`, or `KnowledgeError`,
confirmed by direct inspection of each `load()`), but
`tests/integration/test_research_execution_restart.py::test_corrupted_store_refuses_rather_than_fabricating_state`
and its siblings across the 16 dedicated per-store unit test files (plus
`tests/research/test_research_target_scope_store.py` and
`tests/research/test_research_program_scope_revision_store.py` for the two
stores without a `test_json_file_*_store.py`-named file) all construct
malformed content by hand rather than by truncating a real, previously
valid, saved document's actual bytes — exactly the gap the roadmap names,
and exactly the scenario a genuine crash mid-write on a non-atomic path or
a partially flushed filesystem would produce.

Scope: for each of the 18 stores listed above, add one new test to its
existing dedicated test file that (1) builds a real, non-trivial, valid
document through the store's own `save()` path using that file's existing
fixture/builder helpers, (2) reads the resulting bytes directly off disk,
(3) truncates them at an arbitrary interior cut point that leaves a
non-empty prefix that is not well-formed JSON, (4) writes the truncated
bytes back to the same path, and (5) asserts `load()` raises the store's
own existing typed error rather than returning an empty, partial, or
otherwise fabricated result. No new store, no new persistence mechanism,
no schema-version bump, and no change to `save()`/atomic-write behavior is
anticipated — the existing `except (UnicodeDecodeError, json.JSONDecodeError)`
plus required-field validation already present in every `load()` is
expected to already refuse a truncated prefix in most cases. If a specific
store is found during implementation to NOT fail closed on a truncated
prefix (for example, a cut point that happens to leave syntactically valid
but semantically incomplete JSON that passes today's validation), fixing
that store's `load()` to refuse it is in-scope per standing instructions
("ordinary bugs inside the locked milestone: fix them without asking"),
not scope creep.

Non-goals: the roadmap's other bundled Phase 7 residual — WSL in-guest
process-tree cleanup on Kali operation timeout — is deliberately excluded
from this milestone. That item requires real WSL-guest process-management
verification (asserting no orphaned process survives inside the Linux
namespace), which cannot be safely bounded or deterministically tested
unattended in this session and is a materially different engineering
problem (subprocess/process-group lifecycle, not load-time fault
injection) from what this milestone scopes; it remains a separate future
residual, not discarded. No change to any authority, budget, scope,
target, or credential field on any store's schema; no change to `save()`'s
already-hardened (v0.3.397/v0.3.398) mid-write-failure atomicity; no
change to what any store's `load()` accepts as *valid* content, only
confirmation/hardening of what it refuses when content is truncated.

Acceptance criteria: all 18 stores have a new truncation-fixture test in
their existing test file; each new test is a genuine fault-injection test
(real bytes physically truncated after a real successful save, not a
hand-written malformed string); every new test passes against the final
code; if any store required a `load()` fix to fail closed, a
characterization run proves the new test would have failed before the fix;
full canonical gates green (focused tests first, full suite once); no
existing test's behavior or assertions weakened.

Affected modules: the 18 `src/*/JsonFile*Store.py` files listed above
(read-only unless a genuine refusal-gap fix is required in one) and their
corresponding 18 test files under `tests/`.

Security implications: three of the eighteen stores are authority/budget-
bearing (`JsonFileResearchKaliOperationAuthorizationStore`,
`JsonFileDeferredExecutionGrantStore`, `JsonFileResearchPlanAuthorizationStore`).
hypatia-security must independently verify that a truncated authorization
or grant document is refused outright with no partial trust, and — the
critical property — that a refused load can never be read downstream as a
default-permissive or default-authorized state (fail-closed, not merely
fail-noisy). Also verify no test in this milestone changes any store's
`save()` write path, since that is exactly the boundary v0.3.397/v0.3.398
already hardened and reviewed.

Epistemic implications: none — this is fault-injection testing of an
existing fail-closed load path; it introduces no new evidence, claim, or
provenance semantics and asserts no new epistemic state.

Persistence implications: none structural (no schema change on any
store); the milestone only adds load-time fault-injection coverage to
already-existing schemas.

Restart/replay implications: directly on-point — this is precisely the
"restart encounters corrupted durable state" scenario across every
persisted store in the codebase. The milestone proves restart never
fabricates a partial or successful load from a truncated document for any
of the 18 stores, reinforcing this file's "malformed, missing, stale,
inconsistent, or ambiguous authority-bearing state fails closed" invariant
uniformly rather than store-by-store.

Authority/budget/target/credential implications: none created, widened, or
restored by this milestone; it only adds test coverage proving existing
refusal behavior holds under a fault (truncation) it was not previously
exercised against, including for the three authority/budget-bearing
stores named above.

Test strategy: one new fault-injection test per store (18 total), each a
real save-then-truncate-then-load round trip added to that store's
existing test file; focused tests run per store during implementation;
full canonical suite (unittest discover, Black, Ruff, MyPy, `git diff
--check`) run once at the milestone boundary per this constitution's
resource policy.

## Historical scope: v0.3.403 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Deterministic gap-closing guidance on the mission goal explanation |
| Base SHA | 201b1af345f9b853b522bd3f219b886d9c719415 |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics-scope work performed directly by hypatia-lead (single-file, narrowly-bounded literal mapping); hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, PASS, all seven required test behaviors verified with real differential/equality assertions, full 133-test integration suite re-run clean; hypatia-release delivered v0.3.403 |
| Blockers | none |

Rationale: user-directed. The user approved the prior turn's read-only
reconnaissance of `docs/Roadmap/Master_Roadmap.md`'s "Future direction:
bounded delegated research & evidence-quality completion" as the design
basis, and explicitly locked candidate D ("Confidence and uncertainty made
visible") as this milestone, explicitly excluding candidate A ("Bounded
delegated research continuation") because its authority-policy boundary
still requires a human design decision. Ground truth was re-verified
against the live checkout immediately before implementation (HEAD/upstream
unchanged at `201b1af`, the `ResearchEvidenceCompletionLimitation` enum
still exactly 8 values, `ResearchMissionGoalExplanation.summary()`
unchanged) before locking the milestone, per the user's instruction.

Scope: a private literal `_LIMITATION_GUIDANCE` mapping in
`src/research/ResearchMissionGoalExplanation.py` from each of the 8
existing `ResearchEvidenceCompletionLimitation` values to one bounded,
hand-written guidance sentence describing what recorded evidence gap it
names — no new enum value, no model-generated text, no confidence score.
A new additive `limitations: tuple[ResearchEvidenceCompletionLimitation,
...] = ()` field on the frozen `ResearchMissionGoalExplanation` dataclass,
validated in `__post_init__` exactly like the existing `caveats` field
(type/membership/uniqueness only), populated unchanged from the
already-computed `ResearchEvidenceCompletionEvaluation.limitations` inside
`explain_mission_goal_satisfaction`. `summary()` appends one further
sentence — explicitly labelled "(explanatory only; not a pending action or
a grant of budget/authority)" — only when limitations are non-empty, in
the same order the limitations tuple already carries.

Investigated and confirmed during implementation: this text was already
reachable through two existing, unmodified read paths with zero new
surface needed. `ResearchTeachingReport.teaching_report()` already
embeds `goal_explanation.summary()` verbatim (`ResearchTeachingReport.py:131`);
`ResearchMissionAudit.py`'s `build_mission_audit` already sets its
`report`/`teaching_report` field to that same `teaching_report(...)` call
unmodified (`ResearchMissionAudit.py:174`), and its markdown `_preview()`
quotes that field verbatim in a "## Teaching Report" section
(`ResearchMissionAudit.py:639-650`). So no new Brain intent and no new
desktop widget were added — confirmed necessary by hypatia-qa's
independent re-reading of that call chain, not merely assumed.

Non-goals: no change to `ResearchEvidenceCompletionLimitation` or any
other enum; no automatic/inferred/model-generated guidance text; no
numeric confidence score or percentage (the roadmap's own candidate D
explicitly forbids fabricated percentages without a defensible model); no
new Brain intent; no new desktop widget; no change to
`ResearchEvidenceCompletionEvaluation`, `evaluate_evidence_completion`, or
any authority/budget/target/credential primitive; does not implement
candidate A (bounded delegated research continuation), which remains
explicitly blocked on a human authority-policy decision.

Acceptance criteria (all independently verified by hypatia-qa against a
real test run, not merely read): every one of the 8
`ResearchEvidenceCompletionLimitation` values maps to exactly one
deterministic guidance statement; an empty/sufficiently-supported
`limitations` tuple adds no gap-closing text; multiple simultaneous
limitations render their guidance in the same stable order as the
existing limitations tuple; `ResearchTeachingReport` output changes only
by the appended guidance text (proved by a `dataclasses.replace(...,
limitations=())` differential, not a substring check); `ResearchMissionAudit`
output changes only by the same appended text (proved by construction,
since its `report` field is the same `teaching_report(...)` string
unmodified); existing summary content is byte-for-byte unchanged except
for the new appended section; the guidance path performs no model,
network, execution, persistence, budget, authorization, target, or
credential side effect; full canonical gates green (6620 tests, `OK
(skipped=3)`; Black, Ruff, MyPy, `git diff --check` all clean); the
pre-existing 133-test `tests/integration/test_learning_research_journey.py`
suite re-run clean and unmodified.

Security implications: verified by independent hypatia-security review —
the guidance path is read-only by construction (pure dict lookup plus
string join, no I/O); the new `limitations` field is inert typed metadata
that no other code path branches on to change what executes (grepped
every `.limitations` read repo-wide); all 8 guidance strings are literal,
hand-written text with no interpolation of source/model/note prose; the
file's own "does not interpret source/model prose... does not grant any
new authority" docstring invariant is preserved, reinforced by the new
sentence's own explicit "(explanatory only...)" qualifier.

Epistemic implications: none new — the guidance is a pure presentation
layer over already-computed, already-typed limitation state; it does not
assert that closing a named gap would produce a true or complete answer,
only names what recorded condition is absent, exactly matching this
file's existing reason/caveat rendering discipline.

Persistence/replay/restart implications: none — `ResearchMissionGoalExplanation`
is a derived, non-persisted projection recomputed on demand from canonical
state; the new field carries no status transition and is not written to
any store.

Authority/budget/target/credential implications: none — no primitive of
any kind is created, restored, or altered; this milestone only makes an
existing gap more legible to an operator.

Product-direction compatibility: this is explanation of a recorded
evidence gap, not an epistemic completion decision, a saturation
judgement, or a numeric confidence claim. Candidate A (bounded delegated
research continuation) remains explicitly out of scope and blocked on a
human authority-policy decision, per the user's instruction for this
milestone.

## Historical scope: v0.3.402 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Persist budget-refusal reasons across a status refresh |
| Base SHA | 32d8376fc18a09d5f4beaa60a0fa9e230cbe529c |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-runtime: implementation complete, including the critical anti-stranding safety design (rejecting the naive `block_step` reuse that would have permanently stranded refused executions); independent review (security/QA) surfaced three real findings during the implementation cycle — refusal reason not restored across `restored()`, a possible uncaught exception when the execution isn't cleanly running, and possible interference with an actively-running step — all three verified fixed directly against final code by hypatia-lead; hypatia-release delivered v0.3.402 (plus a follow-up test-fixture correction commit) |
| Blockers | none |

Rationale (repository archaeology, 2026-09-22): two candidates were
investigated fresh and in parallel before this milestone was chosen.

**Candidate A (chosen): budget-refusal-reason persistence.** Confirmed
still accurate against current code (hypatia-runtime): in
`ResearchPlanExecutionApplicationService.process_advance()`, the two
budget-refusal branches (`research_plan_execution_budget_refused`, lines
1293 and 1331) never call `state.block_step` or any other durable-state
mutation before returning — the refusal reason exists only in that one
response's `.message`, built from ephemeral in-memory data (the live
allowance). A subsequent `research_plan_execution_status` refresh on the
same execution shows the step still `pending` with no trace an advance
was attempted and declined. Zero existing test coverage of this gap
(confirmed by grep across `tests/` for `budget_refused`/"advance
refused" — the two existing tests that exercise this path,
`tests/integration/test_foreground_execution_control.py::test_an_exhausted_advance_budget_attempts_nothing`
and `::test_a_refusal_before_the_attempt_charges_nothing`, only assert
the one-shot response and allowance numbers, never a subsequent
`status()` call).

**Critical design correction found during investigation**: the naive fix
(reuse the existing `block_step`/`BLOCKED` mechanism genuine capability
failures already use) would be UNSAFE, not merely redundant. `block_step`
sets both the step AND the whole execution to `BLOCKED`, and the only
recovery path, `recover_blocked_step`, accepts exclusively a step whose
`resolution` is `PERFORMED_RESULT_UNKNOWN` — a budget refusal's step
never reaches that resolution (it was never attempted), so reusing
`block_step` would permanently strand the execution with no way back to
`RUNNING`, even after more budget is approved. This is a real behavioral
regression the milestone must not introduce. The correct shape is a NEW,
narrower, additive mechanism that records a step id + reason string
without touching `status`/`step.status` at all, so `_require_running()`
and `next_pending_step_id` keep working exactly as today and the very
next approved allowance lets the step proceed normally.

**Candidate B (investigated, not chosen this cycle): richer
replanning/continuation diff.** Confirmed real but narrower and lower
blast-radius (hypatia-epistemics): a genuinely honest "diff" can only
ever be flat, same-field juxtaposition (`ResearchMissionContinuationProposal`'s
own docstring: "cites... nothing else" — no structural diff primitive
exists anywhere, `plan_digest` is a pure content hash, not a comparator).
Worse, nothing durably records that a new mission originated from a
given proposal — `_use_continuation_proposal_question` is deliberately a
pure client-side `StringVar` mutation with no Brain/persistence call
(v0.3.400's own design), so a genuinely useful "diff" is only honestly
derivable in a SESSION-SCOPED form (juxtapose already-live origin and
new-mission data immediately after the operator completes
preview -> authorize -> start in the same desktop session). A durable
"find it later" comparison would need one new citation-only field on
`ResearchPlanExecutionSnapshot` — confirmed a separate prerequisite
milestone, not something to fold into a "pure presentation, no schema
change" scope without misrepresenting its size/risk. Recorded as
residual/future work below, not discarded.

Also re-confirmed excluded, unchanged since the last check: Evaluate ->
Adapt v2 (still blocked on human cross-mission authority/budget design);
Tool registry + policy engine (still authority-adjacent per
`docs/Roadmap/Master_Roadmap.md`'s "Default development order").

Scope: a new state-transition method on `ResearchPlanExecutionState`
(e.g. `refuse_advance(step_id, detail)`) that records a bounded reason
string tied to the exact step and capability that was refused, WITHOUT
changing `status` or `step.status` — the execution stays exactly as
advanceable as it was before the refusal. A new optional field on
`ResearchPlanExecutionSnapshot` (and the matching field on
`ResearchPlanExecutionState`) following the exact `None`-default /
`.get(key, default)` legacy-load pattern already used for
`mission_stop_reason`/`revalidation_plan_digest` — no schema-version
bump needed, matching this codebase's established convention that
purely-additive-optional fields don't require one. The two budget-refusal
branches in `process_advance()` (lines 1293, 1331 at time of archaeology
— re-locate exact current lines before editing) call the new method
through the same commit/persist plumbing `_blocked()` already uses, and
attach `research_plan_execution=state` to the response (mirroring
`research_plan_execution_status`) so the retained reason renders on the
next status refresh. The field is cleared on the next successful
`start_step` so it never reads as stale. No desktop changes needed: the
existing `_append_response`/transcript path already renders whatever
`research_plan_execution_status.message` composes, so the retained
reason appears automatically once the response layer includes it.

Non-goals: no change to `block_step`/`BLOCKED`/`recover_blocked_step`
semantics; no change to how genuine capability-failure blocks behave;
does NOT extend to the broader, heterogeneous `research_plan_execution_rejected`
call sites (mission-authority mismatch, scope refusal, delivery-ready
refusal, interrupted-step refusal, no-pending-step) — several of those
fire BEFORE a step is even resolved, so "attach to a step" doesn't apply
uniformly, and deciding whether plan-level refusals belong on the
execution record vs. a step record is a separate, larger design question
explicitly deferred, not silently generalized into this milestone; no
new budget/authority/target/credential semantics of any kind; no change
to allowance accounting, `next_pending_step_id`, or the interrupted-step
replay-refusal check; does not implement Candidate B (session-scoped or
durable), which remains residual/future work.

Acceptance criteria: a test proving that BEFORE this fix,
`tests/integration/test_foreground_execution_control.py`'s existing
budget-refusal tests show no persisted trace of the refusal on a
subsequent `status()` call (characterizing the gap), and AFTER this fix,
the same subsequent `status()` call shows the retained reason; a test
proving the field is correctly `None`/absent on legacy snapshots that
predate it (no backfill, no inference); a test proving the field is
cleared on the next successful `start_step`; a test proving `status`
after a refusal remains exactly as advanceable as before (the step is
still `pending`, `next_pending_step_id` still resolves it, a subsequent
approved-allowance advance still succeeds normally) — this is the
regression test for the "would strand the execution" risk the naive fix
would have introduced; a restart/reload test proving the field survives
a `restored()` pass unchanged (or is reasonably cleared, matching
whichever behavior is chosen and documented) without affecting step
status reinterpretation; full canonical gates green.

Security implications: the critical property to verify is that this
field can NEVER be read as authority, budget, or a status signal by any
other code path — it must be provably inert metadata. Confirm nothing
downstream (recovery logic, replay logic, another consumer) branches on
its presence/absence in a way that could change what executes.

Epistemic implications: none — this is execution-state bookkeeping, not
research/evidence/provenance semantics; the reason string must remain a
literal citation of the refusal that occurred (capability, step id,
shortfall), never an inferred narrative about why the mission overall
failed or what should be done next.

Persistence implications: one new optional field, additive-only, no
schema-version bump per established convention; encode/decode follows
the exact pattern already used for `mission_stop_reason`.

Replay/restart implications: none — confirmed by construction: the new
field carries no status transition, so `restored()`'s existing
RUNNING-becomes-INTERRUPTED reinterpretation and all budget/allowance
accounting are completely unaffected. This is the one property every
review pass must re-verify independently, since the entire safety case
for the milestone rests on it.

Authority/budget/target/credential implications: none — no primitive of
any kind is created, restored, or altered. A refused advance remains
exactly as un-executed after this fix as before it; only the explanatory
record of the refusal becomes durable.

Product-direction compatibility: this record explains an execution refusal;
it is not an epistemic completion decision. Resource limits do not establish
evidence sufficiency or research saturation. Delegated continuation, source
independence, primary-source preference, contradiction analysis and uncertainty
remain existing or future concerns outside this milestone's locked scope.

## Historical scope: v0.3.401 (delivered)

The following retained scope is historical context, not part of the current
budget-refusal milestone.

Rationale (repository archaeology, 2026-09-22): v0.3.400's own residual list
named this as the strongest remaining candidate. Confirmed fresh, not
assumed: `SourceRevalidationStepBinding(...)` is still constructed nowhere
in `src/` outside its own module and three test files (grep re-run against
current HEAD) — the v0.3.393 `source_revalidation` capability remains
genuinely, completely unreachable from the desktop.

A dedicated read-only investigation (hypatia-runtime) resolved the one real
open question before scoping: source revalidation is not "one more step in
an in-progress multi-step plan draft" — it is a bounded, standalone,
single-purpose plan/approval/execution authored AFTER a source is already
accepted (by any earlier means), bound by `research_run_id` to that
pre-existing run, naming the source's real `observation_id`. This is
directly proven by `tests/integration/test_bounded_source_revalidation.py`'s
own scenario shape (accept a source into an existing run, then author a
SEPARATE one-step revalidation plan/approval/execution against that same
run). Critically, this is not a new mechanism to invent: the desktop
already does exactly this shape of work for a different capability — the
existing "Acquisition" feature (`src/desktop/AcquisitionResearchDraft.py`,
`src/research/ResearchAcquisitionBatchDraft.py::preview_acquisition_batch`)
already builds a new plan of steps bound to an already-existing,
already-populated run, and the generic four-call desktop flow
(`preview_research_plan_draft` -> `preview_plan_authorization` ->
`confirm_plan_authorization` -> `start_authorized_execution`, all in
`DesktopController.py`) already threads an explicit `research_run_id`
end-to-end and already accepts a typed `opening_draft` object to carry
richer `ResearchPlanStepDraftInput` values the free-text "Plan draft"
editor cannot express (confirmed: its legacy tuple format caps at 6
positional fields, `MAX_LEGACY_DRAFT_TUPLE_LENGTH = 6` in
`ResearchPlanStepDraftInput.py`, short of `source_revalidation_binding`).

Other v0.3.400 residuals were re-considered and not chosen: the
budget-refusal-reason-persistence gap touches execution state transitions
and needs more care about idempotency/restart-safety than this milestone's
budget allows; a richer "replanning diff" beyond already-shown proposal
provenance is a smaller, less user-visible increment; Evaluate -> Adapt v2
remains blocked on a human cross-mission authority/budget design decision
(unchanged since the last check); Tool registry + policy engine remains
authority-adjacent (unchanged since the last check, per
`docs/Roadmap/Master_Roadmap.md`'s "Default development order" item 3).

Scope: mirror `AcquisitionResearchDraft.py`'s exact shape for a new
`src/desktop/RevalidationResearchDraft.py` — a frozen, self-validating
dataclass built from `(run, prior_observation_id)` that revalidates itself
against canonical state via `plan_digest` equality (so a stale draft
against a run whose source count changed since preview is rejected, not
silently over-authorized) and exposes the single-step
`ResearchPlanStepDraftInput(capability="source_revalidation",
source_revalidation_binding=SourceRevalidationStepBinding(run.run_id,
prior_observation_id, requested_url, max_sources=len(run.sources) + 1))`.
A small pure builder analogous to `preview_acquisition_batch`. Mechanical
widening of the `QuestionResearchDraft | AcquisitionResearchDraft` union
to include the new draft type at its few call sites in
`DesktopController.py`/`TkinterDesktopWindow.py`. Desktop UI: an
eligible-source picker over the run's existing accepted-sources catalog
(`self._research_source_catalog`), filtering out any `ResearchSourceRecord`
with `observation_id is None` or `requested_url is None` (legacy/back-compat
records — binding them would fail `SourceRevalidationStepBinding`'s own
validation, so the UI pre-filters rather than surfacing an opaque refusal),
feeding the chosen source into the existing preview -> authorize -> start
sequence unchanged. The UI surfaces `SourceRevalidationStepBinding.lines()`'s
existing, already-reviewed wording verbatim ("one explicitly approved
re-fetch only", "not a freshness conclusion") rather than inventing new
copy.

Non-goals: no change to `SourceRevalidationStepOperation`,
`SourceRevalidationStepBinding`, `ResearchRunManager`, or any
authority/budget/execution semantics — all reused byte-for-byte; no
cross-run revalidation (same-run-only stays a hard structural constraint,
unchanged); no automatic or scheduled revalidation; no new eligibility
rule beyond the existing binding validation and the desktop's own
legacy-record pre-filter; no change to Evaluate -> Adapt, cancellation, or
persistence-store code; does not implement the budget-refusal-reason
persistence gap or a richer replanning diff (both remain residual/future
work, not discarded).

Acceptance criteria: the new draft type's `.metadata(...)` output produces
a `ResearchPlanStepDraftInput` that, when threaded through the existing
authorization/execution chain, behaves identically to a hand-constructed
one in `test_bounded_source_revalidation.py` (equality-tested at the
binding/step level); a stale draft (source count or observation state
changed since preview) is rejected via `plan_digest` mismatch, mirroring
`AcquisitionResearchDraft`'s own self-check; the eligible-source picker
never offers a source with a null `observation_id`/`requested_url`; the
desktop path performs a genuine end-to-end revalidation reachable only
through the full manual preview -> authorize -> start chain — no
convenience action skips or shortcuts approval; cross-run attempts (a
binding naming a different run than the one currently selected) are
refused by the existing, unchanged `SourceRevalidationStepOperation.run()`
check, exercised through the new desktop path; full canonical gates green.

Security implications: this is the first desktop feature that lets an
operator directly select a specific PRIOR OBSERVATION to bind into a new
plan step (as opposed to picking a fresh discovery candidate) — the
critical property to verify is that the desktop draft cannot construct a
binding naming an observation/run the operator didn't actually select
(source-identity substitution), and that the entire flow still requires
the full manual authorize/start walk, never auto-executing a revalidation
merely because a source was selected in a picker.

Epistemic implications: none new — revalidation's existing "content
relation, not a freshness conclusion" discipline
(`SourceRevalidationStepBinding.lines()`, `SourceRevalidationStepOperation`'s
own docstring) is unchanged and must be preserved verbatim in any new UI
copy, not paraphrased into something that could read as a freshness
verdict.

Persistence implications: none — no new store, no schema change; the
existing `source_revalidations()`/`recorded_revalidation(...)` durable
record path is unchanged and reused as-is.

Replay/restart implications: none new — `SourceRevalidationStepOperation`'s
existing `recorded_result` idempotency (a restarted execution recognizes
its own already-committed revalidation without refetching) is unchanged
and untouched by this milestone; the desktop draft itself is ephemeral,
nothing persisted.

Authority/budget/target/credential implications: none — no new primitive;
same-run-only enforcement is unchanged and structural (three independent
existing layers, per the prior milestone's archaeology); the ordinary
plan-step network/budget slot is reused exactly as `SourceRevalidationStepBinding`
already declares (`declared_cost=ResearchOperationCost(network_operations=1)`,
subject to the existing cumulative allowance, never a separate budget).

## Historical scope: v0.3.400 (delivered)

Rationale (repository archaeology, 2026-09-22): with Evaluate -> Adapt v1,
Phase 7 hardening and v0.3.399 all settled (see the prior documentation
reconciliation commit `f5710aa`), the roadmap's own "Default development
order" flags item 3 (Tool registry + policy engine) as authority-adjacent
and requiring an explicit human check-in before autonomous work — so it
was not picked. Two parallel investigations (hypatia-runtime,
hypatia-epistemics) evidenced two safely-boundable candidates instead:

1. A desktop-visible source-revalidation flow (Phase 5's "[ ] User-facing
   revalidation workflow"): confirmed genuinely, completely unreachable
   from the desktop today (not merely buried — `SourceRevalidationStepBinding`
   is constructed nowhere in `src/` outside its own plumbing and three test
   files), reusing 100% existing same-run authority/budget.
2. Wiring the already-delivered, already-tested Evaluate -> Adapt v1
   continuation-proposal mechanism (v0.3.396) into the desktop: confirmed
   `ResearchMissionAuditApplicationService.proposal_for` "is not wired to
   any `BrainRequest` intent or desktop action" (grep across `src/desktop`
   returns no matches for `proposal_for`/`ContinuationProposal`/
   `seed_question`), and CHANGELOG.md's own v0.3.396 entry says so
   explicitly: "No new desktop UI; this is a backend/service-layer seam
   only." Hypatia's current top-level roadmap priority (Phase 6) is
   therefore, today, completely unusable by an actual operator through the
   product — it exists only as a backend service plus an end-to-end test.

Chosen: **(2)**. It closes the more foundational gap — the flagship
capability of the current phase has zero access path — while (1) remains
a strong, independently-valid future candidate (recorded below as
residual/future work, not discarded).

Scope: (1) a new read-only Brain intent (e.g.
`research_mission_continuation_proposal_preview`) that calls the EXISTING,
UNMODIFIED `ResearchMissionAuditApplicationService.proposal_for(plan_id)`
for a selected closed mission and returns either the proposal (with its
existing provenance fields: `origin_run_id`, `origin_plan_digest`,
`origin_stop_reason`, `origin_goal_status`, `origin_evidence_status`,
`origin_evidence_limitations`, `seed_question`) or an explicit,
accurate "not eligible" explanation — never a fabricated proposal, never a
guessed reason; (2) a `DesktopController` method mirroring the existing
`preview_mission_audit_export`/`preview_plan_authorization` read-only
pattern; (3) a "View continuation proposal" button beside the existing
mission-audit controls in "3 Authored analysis" -> "Plan draft" (same
panel as v0.3.399's traceability view, for the same reason: that's where
an operator already reviews a closed mission's result) showing the
proposal read-only; (4) one convenience action, "Use this proposal's
question," that does nothing except `self._research_question.set(seed_question)`
on the desktop's existing question `StringVar` (the exact field
`_preview_question_plan`/`_start_research_goal`/`_select_question_plan`
already read from for manual entry) — zero Brain/network/authorization
calls of its own. After that, the operator walks the entire existing,
byte-for-byte-unmodified preview -> authorize -> start chain themselves,
exactly as if they had typed the question by hand.

Non-goals: no new authority/budget primitive; no auto-approval or
auto-start of a proposal — approving still requires the full manual
preview -> authorize -> start walk, unchanged; no new eligibility rule
(reuses `proposal_for`'s existing `unresolved`/`partially_satisfied`-only
gate exactly as-is; `blocked`/`budget_limited` stay ineligible, matching
the v0.3.396 product decision); no "replanning diff" computation beyond
showing the proposal's own already-existing provenance fields — no new
comparison/judgment logic invented; no change to
`ResearchMissionContinuationProposal`, `continuation_proposal_for`, or
`proposal_for` themselves; no change to Evaluate -> Adapt v2, revalidation,
cancellation, or persistence-store code; does not implement the
budget-refusal-reason-persistence gap or the desktop-visible
source-revalidation flow found during archaeology (both recorded as
residual/future work below, not discarded).

Acceptance criteria: for an eligible closed mission, the new intent
returns a proposal identical to calling `proposal_for(plan_id)` directly
(equality-tested, same idiom as v0.3.399's traceability-graph equivalence
test); for an ineligible mission, an explicit accurate explanation, never
a crash or a fabricated proposal; the convenience button triggers zero
Brain/network calls and, after it fires, the existing preview -> authorize
-> start chain behaves byte-for-byte identically to manual entry
(extending `tests/e2e/test_continuation_proposal_reentry.py`'s existing
proof to the desktop path); no existing Brain intent, `DesktopController`
method, or `TkinterDesktopWindow` behavior changes; full canonical gates
green.

Security implications: the new surface renders a proposal's
`seed_question` (verbatim operator-authored text from the ORIGIN mission,
not external/untrusted content) and typed provenance IDs — no new
untrusted-content-rendering surface beyond what v0.3.399 already
established a pattern for. The convenience button must be proven to make
no Brain call itself (pure `StringVar` population) — this is the one
specific thing hypatia-security must independently trace.

Epistemic implications: none new — `proposal_for`'s existing fail-closed
eligibility gate is reused unchanged; this milestone must not add a
second eligibility check that could disagree with it.

Persistence/replay/restart implications: none — the new intent is a pure
read reusing `proposal_for`'s existing pure-function, nothing-persisted
derivation; nothing new is written, so restart/replay is unaffected by
construction.

Authority/budget/target/credential implications: none — no new primitive
of any kind; the only executable path remains the existing, unmodified
authorization chain, reached only through the operator's own explicit
manual walk-through, exactly as today.

## Historical scope: v0.3.399 (delivered)

Rationale (repository archaeology, 2026-09-22): Master_Roadmap.md was
reconciled at v0.3.395 and is stale relative to v0.3.396-398. Two apparent
"next in order" candidates were investigated and ruled out with evidence
before this milestone was chosen.

Evaluate -> Adapt v2 (bounded source-revalidation proposal): the fetch-based
`source_revalidation` plan step (v0.3.393) is a hard single-run construct at
three independent layers (`SourceRevalidationStepBinding`'s single
`research_run_id` field, `SourceRevalidationStepOperation.run()`'s explicit
same-run refusal, `ResearchRunManager`'s hardcoded
`earlier_run_id=later_run_id=run.run_id`), with a dedicated refusing test
(`tests/research/test_source_revalidation_step_operation.py::test_cross_run_provenance_is_refused_without_authority`).
Real cross-mission revalidation linking requires new cross-mission
authority/budget-boundary design — out of scope for autonomous execution
per this constitution's stop conditions.

Phase 7 persistence/cancellation/timeout hardening: confirmed already
substantially implemented and tested (`src/core/CancellationSignal.py`,
`ResearchPlanExecutionApplicationService.process_cancel`, distinct
`CANCELLED`/`INTERRUPTED` statuses, `cancelled != failed` and
`interrupted != failed` both directly proven by
`tests/research/test_research_plan_execution_state.py`,
`tests/research/test_concurrent_execution_state.py`,
`tests/research/test_research_plan_execution_snapshot.py`; real per-request
LLM/HTTP/Kali timeouts already exist). Master_Roadmap.md's Phase 7
"confirmed absent" language is wrong and should be corrected in a future
documentation pass. The only genuinely open residuals (WSL in-guest
process-tree cleanup on Kali timeout; a truncated-valid-prefix-on-load test
fixture) are each too narrow for a milestone alone, and a real unified
error taxonomy is either decorative or architecturally large (2,300+ raise
sites) — neither is a bounded next milestone.

Direct inspection of `src/research/ResearchMissionAudit.py` found a real,
still-open gap instead, matching Master_Roadmap.md Phase 4's `[ ]`
"Provenance visualization": `build_mission_audit`'s `_traceability()`
function already computes a complete provenance graph (claim -> evidence ->
source observation -> discovery candidate; contradiction -> claims ->
evidence; comparison review -> note -> evidence -> sources; revalidation ->
paired observations), but `ResearchMissionAuditApplicationService` only
exposes it through a 24,000-character-truncated flat Markdown preview
(`MAX_MISSION_AUDIT_PREVIEW_CHARACTERS`) and a two-file export-to-disk
action (`TkinterDesktopWindow.py`, no structured in-app traceability
browsing exists anywhere at milestone-lock time).
An operator must leave the app and open the exported files to see a
mission's actual provenance structure.

Scope: (1) a new typed, frozen, Tkinter-independent graph read-model type in
`src/research/` (hypatia-epistemics) that re-shapes `_traceability()`'s
existing output into explicit nodes/edges — zero new relations, zero new
inference, unresolved references stay explicitly unresolved exactly as
`_traceability()` already reports them; (2) a new read-only Brain intent on
`ResearchMissionAuditApplicationService` (hypatia-runtime) built from the
exact same `build_mission_audit(...)` call `render()`/`_preview()` already
use — no new computation path, no mutation, no network/model/provider call;
(3) a new read-only `ttk.Treeview` widget in the desktop app (hypatia-runtime)
letting an operator expand claim/evidence/source/contradiction/comparison-
review/revalidation chains in-app, reusing existing safe-text normalization
for untrusted source titles/URLs. Existing preview/save export behavior is
completely unchanged (strictly additive third way to see the same
already-computed data). Landed placement (confirmed during implementation):
the "3 Authored analysis" -> "Plan draft" sub-tab, directly beside the
pre-existing mission-audit export buttons it was scoped against — not
"4 Review & export" as originally assumed when this milestone was locked;
see CHANGELOG.md/PROJECT_STATUS.md v0.3.399 for the corrected location.

Non-goals: no new inference (no automatic independence/freshness/mirror/
syndication detection); no change to `build_mission_audit`'s computed
semantics or the existing Markdown/JSON export format; no new persistence,
store or schema version; no new authority/budget/approval primitive; no
cross-mission graph; no canvas/force-directed rendering (`ttk.Treeview` is
sufficient and avoids new rendering-security surface); no changes to
Evaluate -> Adapt, revalidation, cancellation or persistence-store code.

Permanent invariants affected: none. This is a pure read-only presentation
layer over already-computed, already-tested canonical data; it introduces
no authority, no budget, no target, no credential and no inferred
provenance.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.424: reproduction record foundation |
| SHA | 8f2eec0dbdc5776f2bbedc9c4c750d537288cf0f |
| Linux desktop CI (exact-SHA) | success (run 36546347086) |
| Windows desktop CI (exact-SHA) | success (run 36546351357) |
| Linux desktop CI (PR-triggered) | success (run 36546878414) |
| Windows desktop CI (PR-triggered) | success (run 36546878485) |
| Status | delivered |
| PR | #403, MERGED 2026-09-29T09:08:54Z, standard merge commit `3cd6bfefd70be02a2eb1b1aaca48c8f6ee1a05de` |
| origin/main reachability | verified: `git merge-base --is-ancestor 8f2eec0d origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`3b138d3`, `8f2eec0`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-29, hypatia-lead): see the "Historical
scope: v0.3.424 (delivered)" entry above for the full PR-diff and CI
verification this pointer summarizes.

Deferred, non-blocking findings carried forward (candidates for a future
milestone, not fixed in this release): the CONTRADICTS-side of the
`VALIDATED` evidence gate is deliberately not replayable at load time (no
persisted interleaving between `evidence_links` and `status_transitions`
proves whether a `CONTRADICTS` link was attached before or after a
`VALIDATED` transition; see v0.3.425's own ledger entry). Request-ID/
correlation-ID persistence into research records — rejected as
speculative, no live traceability problem found. The Windows
`ResourceWarning` test-hygiene debt remains untraced and out of scope.

## Historical scope: v0.3.418 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.418: hypothesis evidence subject-binding symmetry |
| SHA | ac7b62c1f5b505bf2e66b719e2d3bd9ebd59c129 |
| Linux desktop CI (exact-SHA) | success (run 36351608455) |
| Windows desktop CI (exact-SHA) | success (run 36351611189) |
| Linux desktop CI (PR-triggered) | success (run 36351590932) |
| Windows desktop CI (PR-triggered) | success (run 36351590942) |
| Status | delivered |
| PR | #397, MERGED 2026-09-28T07:04:17Z, standard merge commit `ef15e431dc3956ec759de1d9b5a200a131c38d35` |
| origin/main reachability | verified: `git merge-base --is-ancestor ac7b62c origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`b318203`, `ac7b62c`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-28, hypatia-lead): PR #397 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (the v0.3.417 ledger reconciliation `b4a4f25`, the
v0.3.418 milestone lock `b9589a6`, and release commit `ac7b62c`) across
exactly 7 changed files. It was `MERGEABLE`/`CLEAN`, and both PR-triggered
`test-build-smoke` checks passed against the release SHA on both runners
(completed 2026-09-27T21:26:16Z / 21:29:26Z), independently of the two
manually dispatched exact-SHA `workflow_dispatch` runs above (also
confirmed against the exact release SHA individually, not assumed from
recency). The standard merge commit is on `origin/main`; all three carried
commits are reachable from it; author/committer identity is unchanged
(Songül Kızılay via GitHub noreply email); the working tree was clean
except this ledger reconciliation.

Note: this bounded release closes the symmetric F1-class subject-binding
gap on the Hypothesis side, deferred explicitly by v0.3.417's own ledger.
`ResearchSecurityHypothesisApplicationService.attach_evidence` now uses a
bound-record lookup (mirroring the Finding-side `next(...)` pattern) and
refuses any cited evidence — for both `SUPPORTS` and `CONTRADICTS` — whose
`target_kind`/`target_canonical_value` differs from the matched
hypothesis's own `subject_kind`/`subject_canonical_value`, with "all cited
evidence in one call must match" aggregation (not "at least one"), proven
by a dedicated mixed-citation-set negative test. Two new
`ProgramIsolationTests` cases close a same-file coverage gap QA identified
(`attach_evidence`/`transition_status` under the wrong `program_id`, M22-
equivalent). No schema or on-disk document change of any kind; no new
evidence relation, status, or kind. Security review: PASS, no findings.
Epistemics review: PASS-with-caveats, one accurate residual-gap finding
folded into the ledger's own Non-goals (no defect in delivered code). QA
review: PASS, full acceptance-criterion traceability. Runtime review:
PASS, no caveats. Mutation pass: 4/4 targeted mutants caught (remove the
subject-binding check; allow a mixed-citation set through; remove the
service-level program check from `attach_evidence`; remove it from
`transition_status`) via in-memory monkeypatching, verified without ever
writing a weakened file to disk. Full canonical gates (Windows canonical
environment): 7452 tests OK (skipped=3) — 4 net new tests over v0.3.417's
7448; Black, Ruff, MyPy (601 source files), and `git diff --check` clean.

Deferred, non-blocking findings carried forward (candidates for a future
milestone, not fixed in this release): F4 (lifecycle replay validation on
load) — "reject whole document" on any business-rule-invariant violation
is the security-consistent, precedent-matching default, but implementation
needs a point-in-time evidence-gate replay (not a final-state check), an
import-cycle-safe way to share validation logic between the store and
application service, and a characterization test proving replay-
equivalence to the write path; real engineering surface for its own
dedicated milestone. `create_hypothesis`'s own residual spurious-`SUPPORTS`-
link gap (same defect class as this milestone's fix — once at least one
citation matches, every `supporting_evidence_ids` entry still becomes a
`SUPPORTS` link including mismatched ones — deliberately deferred to keep
this milestone narrow; severity unaffected, still `SUPPORTS`-only,
structurally incapable of reaching `VALIDATES`). Request-ID/correlation-ID
persistence into research records — rejected as speculative in this
milestone's own investigation, no live traceability problem found. The
Windows `ResourceWarning` test-hygiene debt remains untraced and out of
scope.

## Historical scope: v0.3.417 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.417: finding lifecycle evidence-integrity hardening |
| SHA | 828ba0f374a0a3d8228135ce2c77e90a65a967cb |
| Linux desktop CI (exact-SHA) | success (run 36348936351) |
| Windows desktop CI (exact-SHA) | success (run 36348938189) |
| Status | delivered |
| PR | #396, MERGED 2026-09-27T21:04:01Z, standard merge commit `b318203168479e9b8a53bfb65acbe7b42482a866` |
| origin/main reachability | verified: `git merge-base --is-ancestor 828ba0f origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`8d998c7`, `828ba0f`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-27, hypatia-lead): PR #396 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (the v0.3.416 ledger reconciliation `223fb1b`, the
v0.3.417 milestone lock `3e8f98b`, and release commit `828ba0f`) across
exactly 13 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered
`test-build-smoke` checks passed against the release SHA on both runners
(completed 2026-09-27T20:42:38Z / 20:46:00Z), independently of the two
manually dispatched exact-SHA workflow_dispatch runs above (also confirmed
against the exact release SHA individually, not assumed from recency). The
standard merge commit is on `origin/main`; all three carried commits are
reachable from it; author/committer identity is unchanged (Songül Kızılay
via GitHub noreply email); the working tree was clean except this ledger
reconciliation.

Note: this bounded release closes three findings deferred by v0.3.416's own
security and QA review, on the same Finding Lifecycle foundation. F1
(Medium): `attach_evidence` now refuses evidence whose subject does not
match the finding's own subject, for all three relations
(`SUPPORTS`/`CONTRADICTS`/`VALIDATES`) — closing the path by which a
`VALIDATES` citation about an unrelated host could validate a finding it
did not describe. F2 (Low): `create_finding` independently re-verifies
every carried-forward evidence ID against the live evidence store before
persisting, failing the whole creation closed on any missing reference,
never mutating the source hypothesis. F3 (Low, inherited from v0.3.415):
status derivation for both `ResearchSecurityFinding` and
`ResearchSecurityHypothesis` (four call sites) now trusts each store's own
append-only write order instead of `(recorded_at, transition_id)`, applied
symmetrically to the Hypothesis side because `create_finding`'s own
`READY_FOR_VALIDATION` gate reads `hypothesis.status` directly (verified in
code). No schema or on-disk document change of any kind. M21/M22: new
regression tests prove the Finding service's own program-isolation guard
independently refuses a cross-program operation, closing the named
mutation-testing gap. Security review: PASS, no findings above
informational. Epistemics review: PASS-with-caveats, two non-blocking
notes, no defects. QA review: PASS, full acceptance-criterion traceability.
Runtime review: PASS, no missed derivation call sites, zero wiring/schema
drift. Mutation pass: 6/6 targeted mutants caught (M21, M22, F1, F2, F3 at
both the derived-model and application-service layers) via in-memory
monkeypatching, verified without ever writing a weakened file to disk.
Full canonical gates (Windows canonical environment): 7448 tests OK
(skipped=3) — 9 net new tests over v0.3.416's 7439; Black, Ruff, MyPy (601
source files), and `git diff --check` clean.

Deferred, non-blocking findings carried forward (candidates for a future
milestone, not fixed in this release): F4 (Low, inherited) — store load
validates structure, bounds, unique IDs, and dangling references but does
not replay lifecycle invariants (transition legality, the `VALIDATED`
gate, linkage targets, one-finding-per-hypothesis) on load; closing this
needs a reject-vs-quarantine design decision, not yet made. The symmetric
F1-class subject-binding gap in
`ResearchSecurityHypothesisApplicationService.attach_evidence` (confirmed
present, deliberately left for a future, separately-scoped Hypothesis-side
milestone) — with one downstream, fail-closed-direction consequence noted
alongside it: a carried-forward `CONTRADICTS` link inherited from a
hypothesis whose own evidence was never subject-checked could, in
principle, wrongly block a finding from ever reaching `VALIDATED`
(over-conservative, never a false validation). Request-ID/correlation-ID
persistence into research records (a mature, already-built but completely
unwired pattern exists in `src/tools/ToolExecutionOutcome`/
`ToolExecutionService` that should be reused as the template if this is
ever pursued, rather than inventing a new one). Non-blocking test-hygiene
debt: a Windows-only `ResourceWarning` about unclosed file handles was
observed across the full test run in both v0.3.416 and v0.3.417; confirmed
(hypatia-qa read-only review) not sourced in the Finding/Hypothesis store
or test code, which are fully context-manager-safe — the warning's origin
elsewhere in the suite remains untraced and out of scope for the Finding
Lifecycle line of work.

## Historical scope: v0.3.416 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.416: finding lifecycle foundation |
| SHA | 0462a4c43731c7e56f51871152f47cd605004e32 |
| Linux desktop CI (exact-SHA) | success (run 36344330230) |
| Windows desktop CI (exact-SHA) | success (run 36344332295) |
| Status | delivered |
| PR | #395, MERGED 2026-09-27T20:10:22Z, standard merge commit `8d998c7ec1a179e927d1b1008fe1fdf34caa6768` |
| origin/main reachability | verified: `git merge-base --is-ancestor 0462a4c origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`db88f94`, `0462a4c`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-27, hypatia-lead): PR #395 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (the v0.3.415 ledger reconciliation `45252c1`, the v0.3.416 milestone
lock `53c96e7`, and release commit `0462a4c`) across exactly 30 expected
files. It was `MERGEABLE/CLEAN`, and both PR-triggered `test-build-smoke`
checks passed against the release SHA on both runners, independently of the
two manually dispatched exact-SHA workflow_dispatch runs above (also
confirmed against the exact release SHA individually, not assumed from
recency). The standard merge commit is on `origin/main`; all three carried
commits are reachable from it; the release author remains Songül Kızılay via
GitHub noreply email; the working tree was clean except this ledger
reconciliation.

Note: this bounded release adds a new, program_id-scoped Finding Lifecycle
(`ResearchSecurityFinding*`) sitting directly on top of the delivered
v0.3.415 Security Hypothesis foundation — an immutable founding record plus
append-only evidence-link and status-transition records, with a
derived-only read model assembled fresh on every read. `VALIDATED` is never
authority to act (`means_confirmed_vulnerability` is `False` for every
status); any `CONTRADICTS` link blocks `VALIDATED` for the life of a
finding. Finding creation, evidence attachment, and status transitions
perform no network request, process, tool execution, or scope/credential/
budget/target change of any kind. Security review: yes-with-caveats, no
Critical/High findings. QA review: ready-with-caveats, no production-code
defects (test-coverage gaps only, closed). Mutation pass: 45 mutants plus an
unmutated control, 43 caught; the 2 survivors (M21/M22) are caught anyway by
a redundant lower-layer program-isolation check, not a live gap. Full
canonical gates: Linux 7439 tests OK (34 skipped); Windows 7439 tests OK (3
skipped); Black, Ruff, MyPy, and `git diff --check` clean.

Deferred, non-blocking findings carried forward (candidates for v0.3.417 or
later, not fixed in this release): F1 (Medium) — `VALIDATES` evidence need
only exist in the same program, so it may reference a different host; no
explicit evidence-to-subject/scope relationship is enforced today. F2 (Low)
— evidence IDs carried forward from the hypothesis at finding creation are
not independently re-checked against the live HTTP evidence store. F3 (Low,
inherited from v0.3.415) — status order is derived from
`(recorded_at, transition_id)` rather than persisted append order, so a
wall-clock regression (or same-instant transitions, tie-broken by a random
UUID) can misorder the derived `status`. F4 (Low, inherited) — store load
validates structure, bounds, unique IDs, and dangling references but does
not replay lifecycle invariants (transition legality, the `VALIDATED` gate,
linkage targets, one-finding-per-hypothesis) on load. Non-blocking test-
hygiene debt: a Windows-only `ResourceWarning` about unclosed file handles
was observed across the full 7439-test Windows run; confirmed (2026-09-27,
hypatia-qa read-only review) not sourced in the Finding/Hypothesis store or
test code, which are fully context-manager-safe — the warning's origin
elsewhere in the suite remains untraced and is out of scope for the Finding
Lifecycle line of work.

## Historical scope: v0.3.415 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.415: security hypothesis model foundation |
| SHA | 379884ffa661d07d8cca2db1b65a1e0b974bac19 |
| Linux desktop CI (exact-SHA) | success (run 36185129132) |
| Windows desktop CI (exact-SHA) | success (run 36185133690) |
| Status | delivered |
| PR | #394, MERGED 2026-09-25T20:40:04Z, standard merge commit `db88f94989d2ff29eec90ec499a11f68a7cafbca` |
| origin/main reachability | verified: `git merge-base --is-ancestor 379884f origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`742ab84`, `379884f`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, hypatia-lead): PR #394 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (v0.3.414's documentation-only ledger reconciliation `6217535`, the
v0.3.415 milestone lock `0c4cc2b`, and release commit `379884f`) across
exactly 31 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered
checks passed against the release SHA (`test-build-smoke` on both runners).
The standard merge commit is on `origin/main`; all three carried commits are
reachable from it; the release author remains Songül Kızılay via GitHub
noreply email; the working tree is clean except this ledger reconciliation.

Note: this bounded release adds a new, program_id-scoped
`ResearchSecurityHypothesisRecord` foundation (Bug Bounty Researcher roadmap
item 6), distinct from the pre-existing, unrelated run_id-scoped
`ResearchHypothesis` (general research falsifiability tracker) and the
`src/security/` `SecurityFinding` self-audit subsystem, both untouched.
Every hypothesis requires at least one cited HTTP Evidence reference for the
same program, with its subject matching at least one citation's target. A
closed status state machine (`OPEN`/`NEEDS_EVIDENCE`/`READY_FOR_VALIDATION`/
`REFUTED`) tracks the operator's own evidence judgement; no status asserts a
validated vulnerability. Hypothesis creation, evidence attachment, and
status transitions perform no network request, process, tool execution, or
scope/credential/budget/target change of any kind. Security review found no
findings; QA found one high (zero test coverage for the new
`DesktopController`/`CognitiveEngine`/`Bootstrap` wiring) and two moderate
(dedup missing a negative case; no restart/reload proof for the derived read
model) test-coverage gaps, all closed with 29 new tests, re-verified via
mutation testing. Full canonical gates: 7244 tests, OK (skipped=3); Black,
Ruff, MyPy, and `git diff --check` clean.

## Historical scope: v0.3.414 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.414: claim-contradiction preview secret boundary |
| SHA | 528a49ee58f733dbdd95e19e9da4b5044dff3420 |
| Linux desktop CI (exact-SHA) | success (run 36162047327) |
| Windows desktop CI (exact-SHA) | success (run 36162051082) |
| Status | delivered |
| PR | #393, MERGED 2026-09-25T16:49:58Z, standard merge commit `742ab846a4e6680069053130fdfc3d1a7344eb21` |
| origin/main reachability | verified: `git merge-base --is-ancestor 528a49e origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`cdc0125`, `528a49e`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, hypatia-lead): PR #393 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (v0.3.413's documentation-only ledger reconciliation `37c7568`, the
v0.3.414 milestone lock `b7cb2fd`, and release commit `528a49e`) across
exactly 8 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered
checks passed against the release SHA (`test-build-smoke` on both runners).
The standard merge commit is on `origin/main`; all three carried commits are
reachable from it; the release author remains Songül Kızılay via GitHub
noreply email; the working tree is clean except this ledger reconciliation.

Note: this bounded release closes a gap hypatia-security flagged during
v0.3.413's review — a secret-shaped claim-contradiction note was echoed
verbatim into a preview Brain response before any sensitivity check ran.
The existing, unmodified `ResearchSensitiveInputPolicy` now runs inside
`ResearchRunManager._normalize_claim_contradiction_note`, the one
normalization step shared by both the preview and record paths, so both
refuse identically before a preview can be constructed with a secret-shaped
note. `record_claim_contradiction` is now doubly protected. Implemented
directly by hypatia-lead as single-function, single-file work. Security and
QA review both PASS with no findings; QA's mutation testing empirically
confirmed the double-protection claim. Full canonical gates: 7105 tests, OK
(skipped=3); Black, Ruff, MyPy, and `git diff --check` clean.

## Historical scope: v0.3.413 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.413: research-run note secret boundary |
| SHA | 29c78805e8384fb1d74d6c1d8ebbccea1fbe6ec2 |
| Linux desktop CI (exact-SHA) | success (run 36158436587) |
| Windows desktop CI (exact-SHA) | success (run 36158440256) |
| Status | delivered |
| PR | #392, MERGED 2026-09-25T16:14:33Z, standard merge commit `cdc0125a070b00abf9e1b49e1204ab32f3af862a` |
| origin/main reachability | verified: `git merge-base --is-ancestor 29c7880 origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`3e4cb4d`, `29c7880`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, hypatia-lead): PR #392 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (v0.3.412's documentation-only ledger reconciliation `acf37a3`, the
v0.3.413 milestone lock `27f0c4f`, and release commit `29c7880`) across
exactly 13 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered
checks passed against the release SHA (`test-build-smoke` on both runners).
The standard merge commit is on `origin/main`; all three carried commits are
reachable from it; the release author remains Songül Kızılay via GitHub
noreply email; the working tree is clean except this ledger reconciliation.

Note: this bounded release widens the existing, unmodified
`ResearchSensitiveInputPolicy` (v0.3.411) to three more operator-authored
free-text `note` fields on the research-run model
(`ResearchClaimContradictionRecord`, `ResearchComparisonReviewRecord`,
`ResearchEvidenceRecord`), closing the residual list named when v0.3.412
shipped. `ResearchEvidenceRecord.excerpt` (raw fetched source content) stays
deliberately unclassified. Refusals expose only fixed categories and never
echo the candidate value; a malicious persisted note fails closed on load.
It introduces no secret storage, credential use, login, network/process
capability, or scope, target, budget, credential, or execution authority.
Security review found no findings (one pre-existing, out-of-scope
observation recorded for future work); QA found one moderate test-hygiene
gap recurring from v0.3.412, closed by hypatia-lead and verified non-vacuous
by QA's mutation testing. Full canonical gates: 7103 tests, OK (skipped=3);
Black, Ruff, MyPy, and `git diff --check` clean.

## Historical scope: v0.3.412 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.412: asset inventory note secret boundary |
| SHA | 089443a80bdba6694e22eb35ade0d9512eef3049 |
| Linux desktop CI (exact-SHA) | success (run 36154333982) |
| Windows desktop CI (exact-SHA) | success (run 36154337786) |
| Status | delivered |
| PR | #391, MERGED 2026-09-25T15:36:55Z, standard merge commit `3e4cb4d98630c08eb5252aa1cecd7a9f693516fb` |
| origin/main reachability | verified: `git merge-base --is-ancestor 089443a origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`a2f0918`, `089443a`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, hypatia-lead): PR #391 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (v0.3.411's documentation-only ledger reconciliation `eb3219f`, the
v0.3.412 milestone lock `bb333ab`, and release commit `089443a`) across
exactly 12 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered
checks passed against the release SHA (`test-build-smoke` on both runners).
The standard merge commit is on `origin/main`; all three carried commits are
reachable from it; the release author remains Songül Kızılay via GitHub
noreply email; the working tree is clean except this ledger reconciliation.

Note: this bounded release widens the existing, unmodified
`ResearchSensitiveInputPolicy` (v0.3.411) to the two operator-authored
free-text `note` fields in the Bug Bounty Asset Inventory
(`ResearchAssetObservationRecord`, `ResearchAssetRelationRecord`, v0.3.407)
that predated the secret-ingress boundary. Refusals expose only fixed
categories and never echo the candidate value; a malicious persisted note
fails closed on load. It introduces no secret storage, credential use,
login, network/process capability, or scope, target, budget, credential, or
execution authority. Security review found no findings; QA found one
moderate service-layer test-coverage gap plus one cosmetic desktop-caption
gap against this milestone's own locked test strategy, both closed by
hypatia-lead with new tests verified non-vacuous by QA's mutation testing.
Full canonical gates: 7088 tests, OK (skipped=3); Black, Ruff, MyPy, and
`git diff --check` clean.

## Historical scope: v0.3.411 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.411: research session-context secret-ingress boundary foundation |
| SHA | c5ab6ce3aa7304636fe8c23cda1b080d15c11891 |
| Linux desktop CI (exact-SHA) | success (run 36111047175) |
| Windows desktop CI (exact-SHA) | success (run 36111051142) |
| Status | delivered |
| PR | #390, MERGED 2026-09-25T08:16:19Z, standard merge commit `a2f0918a90fe2ce8766c0625b627ad5224ee3bd6` |
| origin/main reachability | verified: `git merge-base --is-ancestor c5ab6ce origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`980e508`, `c5ab6ce`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, Codex): PR #390 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 3
commits (v0.3.410's documentation-only ledger reconciliation `2d2ac28`, the
v0.3.411 milestone lock `4972dbb`, and release commit `c5ab6ce`) across exactly
13 expected files. It was `MERGEABLE/CLEAN`, and both PR-triggered checks
passed against the release SHA (Linux run 36111594883, Windows run
36111594992). The standard merge commit is on `origin/main`; all three carried
commits are reachable from it; the release author remains Songül Kızılay via
GitHub noreply email; the working tree is clean except this ledger
reconciliation.

Note: this bounded release rejects a conservative, explicit set of
high-confidence secret-bearing forms before research session-context
persistence. Refusals expose only fixed categories and never echo the
candidate value. It introduces no secret storage, credential use, login,
network/process capability, or scope, target, budget, credential, or execution
authority. Security review found and fixed one credential-bearing URL
completeness gap; QA verified all categories, benign near misses, no-write
refusal, malicious-store fail-closed behavior, restart behavior, and desktop
reachability. Full canonical gates: 7079 tests, OK (skipped=3); Black, Ruff,
MyPy, and `git diff --check` clean.

## Historical scope: v0.3.410 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.410: research session context foundation |
| SHA | cf49a931daff46e460c54e6fd2d8e6d8d4066b39 |
| Linux desktop CI (exact-SHA) | success (run 36108321606) |
| Windows desktop CI (exact-SHA) | success (run 36108324229) |
| Status | delivered |
| PR | #389, MERGED 2026-09-25T07:44:36Z, standard merge commit `980e508b18aec8c724f8a4eab28bdaeb6aefe0a4` |
| origin/main reachability | verified: `git merge-base --is-ancestor cf49a93 origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`679a24f`, `cf49a93`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, Codex): PR #389 base `main`, head
`feature/structured-learned-memory-extraction-v0.3.118`, carried exactly 2
commits (v0.3.409's documentation-only ledger reconciliation `86727d0` and
v0.3.410's release commit `cf49a93`), was `MERGEABLE/CLEAN`, and both
PR-triggered checks passed (Linux run 36108774238, Windows run 36108774287).
Merged with a standard merge commit. The merge commit is on `origin/main`;
both carried commits are reachable from it; release-commit author and
committer remain Songül Kızılay via GitHub noreply email; the working tree is
clean except this ledger reconciliation.

Note: this bounded roadmap slice adds descriptive historical authentication
state over already-recorded same-program HTTP evidence. Records are frozen,
strictly bounded, append-only, restart-safe, and exposed through Brain and a
dedicated desktop panel. They contain no credential or reusable live session,
perform no login/request, never inspect or copy HTTP header values, and create
no scope, target, budget, credential, or execution authority. Security review
found and fixed a rendered-line-forgery gap in identifier/program input; QA
verified model, persistence, service, Brain, Bootstrap, controller, and desktop
paths. Full canonical gates: 7067 tests, OK (skipped=3); Black, Ruff, MyPy, and
`git diff --check` clean.

## Historical scope: v0.3.409 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.409: HTTP evidence model foundation |
| SHA | 66e9479a68233469e93be30cd5c1adc6482f59ac |
| Linux desktop CI (exact-SHA) | success (run 36087477607) |
| Windows desktop CI (exact-SHA) | success (run 36087479733) |
| Status | delivered |
| PR | #388, MERGED 2026-09-25T02:55:25Z, standard merge commit `679a24fdf09f054a651c76503e66ad04827eaa0b` |
| origin/main reachability | verified: `git merge-base --is-ancestor 66e9479 origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`8821844`, `66e9479`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-25, hypatia-lead): PR #388 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (the documentation-only ledger-reconciliation commit
`8d9ad59`, the documentation-only milestone-lock commit `50e06c6`, and
v0.3.409's release commit `66e9479`), `mergeStateStatus: CLEAN`, both
PR-triggered checks `pass` (Linux run 36087861821, Windows run 36087861850).
Merged with `gh pr merge 388 --merge --subject "..."` — no interactive
confirmation prompt. Author/committer identity on the release commit
confirmed unchanged (Songül Kızılay via GitHub noreply email). Working tree
clean after merge except this ledger edit.

Note: step 4 of the bounded Bug Bounty Researcher roadmap (HTTP evidence
model). The Lead ran direct ground-truth discovery (confirmed
`HTTPS_HEADER_LOOKUP`'s exact reviewed `curl --head` argv shape, and
directly executed `curl --head` once to ground the parser design in real
output), locked a bounded slice (one producer, no body capture, no new
asset/relation kinds, no redirect following), and dispatched hypatia-runtime
as sole implementer. Delivered: `ResearchHttpEvidenceProvenanceKind`
(exactly one member, `KALI_OPERATION_RESULT`); a fail-closed evidence
record with hard-pinned `request_headers_observed`/`response_body_observed`
booleans so "not observed" can never read as "observed and empty"; a
deterministic, content-derived `evidence_id` (`http_evidence_id`, mirroring
`kali_operation_preview_digest`'s digest pattern) making replay-safety
structural rather than a separate dedup pass; a pure parser that re-derives
hostname/port from the reviewed command plan's argv rather than trusting a
cached field; a new atomic store; an application service with a
side-effect-free preview and an idempotent-on-exact-replay record path; and
desktop/Brain wiring mirroring v0.3.408's ingestion discipline exactly, with
sensitive header values redacted at every render site. Independent
hypatia-security review: PASS on all 8 reviewed properties, no
authority-widening defect, but flagged two completeness/coverage gaps — live
scope resolution wasn't threaded through the ingestion preview/record flow
(a named item in the locked scope), and no test proved sensitive-header
redaction actually survives into the rendered `BrainResponse.message` text
(only the desktop dialog's separate redaction path was tested). The Lead
fixed both directly: added a required `scope` field to the ingestion
preview/result types, computed fresh on every call, rendered in both
messages; added an integration test proving redaction survives into the
message. Independent hypatia-qa review then found the Lead's own new
scope-line test was itself vacuous (would pass even if the rendered line
were hardcoded, mutation-confirmed) and that the parser's `--resolve`/URL-
hostname validation had zero test coverage (mutation-confirmed: deleting the
check left the whole suite green). The Lead fixed both directly with a
second-scenario freshness test (revoke the active revision mid-test,
require the rendered line to change) and three new parser tests
(malformed `--resolve` value, wrong port, URL/hostname mismatch),
mutation-verifying each fix personally before re-running the full milestone
test set. Full canonical gates on the integrated tree: 7047 tests, `OK
(skipped=3)`, Black, Ruff, MyPy, `git diff --check` all clean.

## Historical scope: v0.3.408 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.408: bug bounty recon result ingestion + normalization foundation |
| SHA | 1a4848cfbcc1618ad3b6f12343e7bc0e4607929b |
| Linux desktop CI (exact-SHA) | success (run 36065535503) |
| Windows desktop CI (exact-SHA) | success (run 36065539096) |
| Status | delivered |
| PR | #387, MERGED 2026-09-24T22:17:33Z, standard merge commit `8821844120b01fd61545b1423d90206df0b48e42` |
| origin/main reachability | verified: `git merge-base --is-ancestor 1a4848c origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`4b82d71`, `1a4848c`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-24, hypatia-lead): PR #387 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (the documentation-only ledger-reconciliation commit
`45cc713`, the documentation-only milestone-lock commit `8611955`, and
v0.3.408's release commit `1a4848c`), 25 files, `mergeStateStatus: CLEAN`,
both PR-triggered checks `pass` (Linux run 36066052863, Windows run
36066052904). Merged with `gh pr merge 387 --merge --subject "..."` — no
interactive confirmation prompt. Author/committer identity on the release
commit confirmed unchanged (Songül Kızılay via GitHub noreply email).
Working tree clean after merge except this ledger edit.

Note: step 3 of the bounded Bug Bounty Researcher roadmap (recon result
ingestion). The Lead discovered that Hypatia's existing `DNS_RECORD_LOOKUP`
Kali operation (`dig +short`) was the only existing result producer
structured enough to ingest honestly, locked a bounded slice (A/AAAA only,
no CNAME, no `HTTPS_HEADER_LOOKUP`), and dispatched hypatia-epistemics as
sole implementer. That implementation agent was interrupted mid-verification
(an accidental ESC) after substantially completing the full slice — new
`KALI_OPERATION_RESULT` provenance kind, a fail-closed 1:1
provenance/digest-forgery binding shared by observations and relations, a
store schema v1->v2 bump with honest legacy decode, a pure DNS-result parser,
service/Brain/desktop wiring, and 172 passing tests. The Lead inspected the
full diff directly (not re-derived), ran two of its own mutation checks
(forged-provenance-digest binding, disabled IP-version check; both caught),
then continued the lifecycle. Independent hypatia-security review found no
authority widening across all 8 reviewed properties (scope reachability,
provenance forgery, program isolation, untrusted-tool-output handling, no
new execution/network capability, replay/restart, schema/persistence,
no new credential/budget/target primitive) — zero defects. Independent
hypatia-qa review mutation-tested 3 of 12 checklist points and found two
genuine test-coverage gaps: no multi-address test proved the hostname
observation is recorded exactly once per run rather than once per resolved
address (a named milestone acceptance criterion), and the parser's `argv`
shape guard was untested dead code from a test-coverage perspective. Both
were closed by the Lead directly with new mutation-verified tests (174
tests passing afterward). Full canonical gates on the integrated tree: 6929
tests, `OK (skipped=3)`, Black (2 files reformatted first), Ruff, MyPy,
`git diff --check` all clean.

## Historical scope: v0.3.407 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.407: bug bounty asset inventory canonical identity |
| SHA | 2d55e762ca43a5eb9884544c2d86aa0c9ba26f89 |
| Linux desktop CI (exact-SHA) | success (run 36037376068) |
| Windows desktop CI (exact-SHA) | success (run 36037379943) |
| Status | delivered |
| PR | #386, MERGED 2026-09-24T18:06:17Z, standard merge commit `4b82d71cba2e2a0f8cb6b530522a1314898c4c33` |
| origin/main reachability | verified: `git merge-base --is-ancestor 2d55e76 origin/main` succeeds; `origin/main` HEAD is the merge commit itself, whose two parents (`08c8f0e`, `2d55e76`) prove a true merge rather than a squash or rebase |

Post-merge verification (2026-09-24, hypatia-lead): PR #386 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 2 commits (the documentation-only ledger/roadmap commit `be1d13b`
and v0.3.407's release commit `2d55e76`), 31 files, `mergeStateStatus:
CLEAN`, both PR-triggered checks `SUCCESS` (Linux run 36038289241, Windows
run 36038289320). Merged with `gh pr merge 386 --merge --subject "..."` —
no interactive confirmation prompt. Author/committer identity on both
carried commits confirmed unchanged (Songül Kızılay via GitHub noreply
email). Working tree clean after merge except this ledger edit.

Note: step 2 of the bounded Bug Bounty Researcher roadmap. The work was
already implemented in the working tree when this session resumed; the Lead
verified it against this file's own locked scope rather than re-deriving it,
then ran the milestone's remaining lifecycle. Two formatting findings (Black
on two files, one 89-character line) were fixed first. Independent
hypatia-security review found no authority widening and verified nine safety
properties with file:line evidence, plus one medium defect — a zone-scoped
address (`fe80::1%eth0`) was accepted as asset identity while
`ResearchTargetScope` refuses every address containing "%", so an
append-only record could have wedged a program's whole inventory read path
irrecoverably — now refused at canonicalization, and four low/informational
findings (read/write revision-store type narrowed to a read-only reader
protocol; provenance pinned to `OPERATOR_AUTHORED` instead of read from
request metadata; the kind dispatch names `IP_ADDRESS` explicitly and raises
otherwise, with `ResearchAsset` validating its own `StrEnum` kind; note text
rendered on a single line so it cannot forge `Provenance:`/`Recorded at:`
field lines), all fixed. Independent hypatia-qa review found no weakened
pins but three high-severity gaps where the implementation could have been
wrong with the whole suite green — the panel was never proven reachable from
the application window, Bootstrap wiring was untested, and scope freshness
was asserted structurally (a `__dataclass_fields__` name check) rather than
behaviorally — plus medium gaps (no "nothing was persisted" assertion after
a refused write, preview entries never checked per-asset, a persisted
non-canonical value never proven to fail closed, thin restart determinism, a
vacuous panel failure-path test); all were closed with roughly 25 new tests.
The store file was renamed to `research_asset_inventory.json` for the
`research_*` sibling convention before any release existed to carry the old
name. The Lead then mutation-verified the new tests: seven deliberate
breakages (cached scope readings; the window never building the panel;
Bootstrap dropping the store; the store normalizing values on load; the
preview reusing the first asset's reading; scoped addresses accepted again;
provenance read from metadata) were each caught by a failing test. Two of
the first mutation attempts were themselves faulty (one read a cache it
never populated) and were corrected rather than counted as passes. Full
canonical gates on the integrated tree: 6846 tests, `OK (skipped=3)`,
Black/Ruff/MyPy clean, `git diff --check` clean.

## Historical scope: v0.3.406 (delivered)

| Field | Value |
| --- | --- |
| Milestone | v0.3.406: explicit tri-state target-scope resolution |
| SHA | bfc0a3c23736d722f44cc394342e1974c7b27d1f |
| Linux desktop CI (exact-SHA) | success (run 35894553832) |
| Windows desktop CI (exact-SHA) | success (run 35894559568) |
| Status | delivered |
| PR | #385, MERGED 2026-09-23T17:27:37Z, standard merge commit `08c8f0ec041146807a5bb9831f5c9ad8827b18a5` |
| origin/main reachability | verified: `git merge-base --is-ancestor bfc0a3c origin/main` succeeds; `origin/main` HEAD is the merge commit itself |

Post-merge verification (2026-09-23, hypatia-lead): PR #385 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 2 commits (the documentation-only ledger-reconciliation commit
`ad7de6c` and v0.3.406's release commit `bfc0a3c`), 21 files (4 doc/version
files, 11 `src/` files including 3 new files — `ResearchTargetScopeResolutionStatus.py`,
`ResearchTargetScopeResolution.py`, `ResearchTargetScopeResolutionApplicationService.py`
— and 6 test files including 2 new files, matching the locked scope
exactly), `mergeStateStatus: CLEAN`, both PR-triggered `test-build-smoke`
checks `pass`. Merged with `gh pr merge 385 --merge` — no interactive
confirmation prompt. Author/committer identity on both carried commits
confirmed unchanged (Songül Kızılay via GitHub noreply email, Claude
Sonnet 5 co-author trailer preserved). Working tree clean after merge.

Note: this is step 1 of Hypatia's bounded Bug Bounty Researcher roadmap.
Repository-grounded discovery found a substantial, tested bug-bounty
program-scope backbone already existed (`ResearchTargetScope`,
`ResearchProgramScopeRevision`, `ResearchProgramScopeExecutionPolicy`,
`ResearchProgramScopeEnrollmentService`); the one confirmed gap was that
matching was strictly boolean, so an explicitly excluded host and an
unaddressed host produced an identical refusal. This milestone added a
purely additive `IN_SCOPE`/`OUT_OF_SCOPE`/`UNCERTAIN` tri-state read
(`ResearchTargetScopeResolutionStatus`/`ResearchTargetScopeResolution`,
`resolve_hostname`/`resolve_addresses` on the existing `ResearchTargetScope`)
without modifying `require_hostname`/`require_addresses` at all — proven
byte-for-byte unchanged by a differential test. Implementation was
delegated to hypatia-epistemics as sole implementer (avoiding the
dual-writer file-conflict risk). Independent hypatia-security review
(PASS, no findings — traced every consumer of the new type and confirmed
no path lets `UNCERTAIN`/bare `IN_SCOPE` reach an active action) and
independent hypatia-qa review (PASS — extensive mutation testing on every
key branch, all caught; found and closed one real test-coverage gap, a
missing wildcard-suffix-trick regression test, independently re-verified
non-vacuous) both ran as specialist subagents. hypatia-lead ran the full
canonical gate suite directly on the integrated diff before release: 6690
tests, `OK (skipped=3)` (325.4s), Black/Ruff/MyPy all clean, `git diff
--check` clean (only pre-existing CRLF-normalization advisories, no
whitespace errors).

Note: v0.3.406 (SHA `bfc0a3c23736d722f44cc394342e1974c7b27d1f`), v0.3.405
(SHA `922d1d3ed8c893c61fc561336a71c709886c9cf3`), v0.3.404
(SHA `cfa8fb7e9b859cc38b63bbc7234c152dd6974178`), v0.3.403
(SHA `848b37d23437a3adb038ef924fb1ca0a4c56455c`), v0.3.402 (SHA
`793b5d70147438cad4a6a38590e61128a00aaa46`), v0.3.401 (SHA
`32d8376fc18a09d5f4beaa60a0fa9e230cbe529c`), v0.3.400 (SHA
`ec1a6f0bc2f6c5b8d1a609b789c8c836d91fffd4`), v0.3.399 (SHA
`650bfe486bb326635ea8aa4dd9c3b80dbc746c5b`), v0.3.398 (SHA
`3cf726a6c16b181bf26ae4d67cea690e84f2ce9a`), and v0.3.397 (SHA
`aeff7713a8fea7efd247892272c78a80b9d16176`) all remain reachable from
`origin/main` as ancestors of v0.3.406 (this row), which is now the
current last-delivered product milestone.

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
