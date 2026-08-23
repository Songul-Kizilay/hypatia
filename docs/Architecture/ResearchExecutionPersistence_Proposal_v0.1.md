# Research Execution Persistence — Design Proposal v0.1

Status: **proposal only. Not implemented. Requires approval before any code.**

Runtime at time of writing: `v0.3.137 (Genesis)`.

This document exists because research-plan execution state is currently
ephemeral, and making it durable requires a persisted-schema change. Under the
project's engineering rules a schema migration is not performed autonomously, so
the design is written down and the implementation is deferred.

---

## 1. What is actually ephemeral today

`ResearchPlanExecutionApplicationService` holds three in-memory dictionaries
keyed by plan ID:

- `_executions` — the immutable `ResearchPlanExecutionState`
- `_plans` — the authored `ResearchPlan`
- `_contexts` — the `ResearchPlanExecutionContext`

All three are lost when the process exits. The service reports this honestly:
every status message ends with `Execution state: in-memory only, lost when
Hypatia exits`, and an unknown plan is reported as absent rather than resumable.

**What is already durable.** Everything the research chain *produces* is
persisted by `ResearchRunManager`: discoveries, accepted sources, evidence,
assessments, claims, contradictions, comparison notes, failures, and run status.
A process restart therefore loses the *bookkeeping of which step ran*, never the
research results themselves.

That distinction matters for prioritisation. Persistence buys resumability and
auditability of execution, not recovery of lost research.

---

## 2. Why this needs a migration

`ResearchRun` is a frozen dataclass persisted through `JsonFileResearchRunStore`.
Its loader validates the document shape. Adding execution state to `ResearchRun`
would change what a valid persisted run looks like, and an older Hypatia reading
a newer file, or the reverse, would need defined behavior.

There is currently no schema version marker in the research store, which is the
first thing any migration has to address.

---

## 3. Options considered

### Option A — embed execution inside `ResearchRun`

Add an `executions` field to `ResearchRun`.

- Natural ownership: an execution belongs to a run.
- But it changes the most load-bearing persisted type in the research subsystem,
  and executions are not bound to a run one-to-one — a plan may run with no run
  bound at all.

Rejected as the first step: highest blast radius.

### Option B — a separate execution store (recommended)

A new `JsonFileResearchExecutionStore` alongside the existing run store, holding
its own versioned document.

- `ResearchRun` and its schema are untouched, so every existing snapshot stays
  valid and no migration of existing data is required.
- A missing execution file simply means "no persisted executions", which is
  exactly today's behavior.
- The store can carry `schema_version` from its first release, so future changes
  are versioned rather than guessed.
- Cleanly revertible: delete the file, delete the wiring, and behavior returns to
  ephemeral.

This is additive rather than migrating, which is why it is recommended.

### Option C — leave ephemeral, persist nothing

Still viable. Execution state is bookkeeping; results are already durable.

---

## 4. Recommended shape (Option B)

```
{
  "schema_version": 1,
  "executions": [
    {
      "plan_id": "...",
      "status": "running",
      "detail": "",
      "research_run_id": "...",
      "recorded_at": "2026-08-23T...+00:00",
      "plan": { "question": "...", "steps": [ ... ] },
      "steps": [
        {
          "step_id": "step-1",
          "status": "completed",
          "detail": "...",
          "work_performed": true,
          "operation": "source_accept"
        }
      ]
    }
  ]
}
```

Notes on the shape:

- `work_performed` and `operation` persist together, preserving the existing
  invariant that recorded work must name the operation that produced it.
- The authored `plan` is stored because a resumed execution must not invent step
  instructions or capability authorizations it never had.
- `cancellation_token` is deliberately absent. It is per-request runtime state,
  not durable data.

---

## 5. Honesty rules that must survive persistence

These are the rules the current implementation is tested against. Persistence
must not weaken any of them.

1. A restored execution is **not** a running one. Restoring bookkeeping is not
   resuming work.
2. A restored `running` plan whose step was mid-flight must be reported as
   **interrupted**, not as still running. The operation did not survive the
   restart, so its outcome is unknown.
3. `work_performed` must never be inferred at load time. It is persisted exactly
   as recorded, or the record is invalid.
4. A terminal execution stays terminal across a restart.
5. A persisted execution referencing an unknown run must be loadable and
   reported, never silently dropped — dropping it would hide history.
6. Restoring must perform no research work, no network call, and no LLM call.

Rule 2 is the one most likely to be got wrong. It probably needs a new
non-terminal `INTERRUPTED` execution status rather than reusing `BLOCKED`, since
blocked means "a human must decide", while interrupted means "we do not know what
happened".

---

## 6. Staged implementation plan

Each stage is independently testable and revertible.

**Stage 1 — codec only.** Pure encode/decode between
`ResearchPlanExecutionState` and its document form. No store, no wiring. Tests:
round-trip fidelity, rejection of malformed documents, refusal to load a
`work_performed` record with no operation.

**Stage 2 — versioned store.** `JsonFileResearchExecutionStore` with atomic
replace, matching the existing store conventions. Tests: missing file, empty
file, corrupt file, unknown `schema_version`, bounded record count.

**Stage 3 — opt-in wiring.** Behind an explicit environment flag, default off,
following the precedent set by `HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED`. With the
flag absent, behavior is byte-identical to today.

**Stage 4 — restore and interrupted reporting.** Load at startup, mark
mid-flight steps interrupted, and report restored executions honestly. Tests:
restart with a completed execution, a terminal execution, and a mid-flight
execution.

**Stage 5 — resume.** Only after restore is proven. Resume means advancing the
next pending step of a restored plan, never re-running a completed one.

---

## 7. What is explicitly out of scope

- Migrating existing `ResearchRun` snapshots. Option B avoids it entirely.
- Any change to `ResearchRun`, its store, or its validation.
- Crash-safety guarantees beyond the atomic-replace behavior the existing stores
  already provide.
- Background or automatic resumption. Resume must stay user-initiated until a
  scheduler exists with its own bounds.

---

## 8. Recommendation

Adopt Option B, implement Stages 1 and 2 first, and keep the wiring opt-in and
default off. Nothing here should be built until the shape in section 4 and the
`INTERRUPTED` status question in section 5 are reviewed, because both are
persisted decisions that are expensive to change later.

Until then the honest position stands: execution state is ephemeral, Hypatia
says so, and no resume is faked.
