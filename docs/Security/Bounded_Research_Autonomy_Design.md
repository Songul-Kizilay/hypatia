# Bounded Research Autonomy — Security Design

**Status: DESIGN, WITH OPERATOR-CONTROLLED FOREGROUND EXECUTION IMPLEMENTED.**
Discovery results are ranked deterministically before a person chooses among
them, a person can record what they concluded about a source after reading it,
calibration reports when a claim rests on a source they distrusted, research can
reach vulnerability records rather than only scholarly papers, and the record of
how each provider's assessed samples turned out can be described. All five
changed what research knows without changing what it may do — the provider a
plan will contact is bound into the approval that authorizes it, and measuring
provider performance is deliberately not the same thing as choosing a provider,
and the operator can now put one question to both providers as two ordinary
approved steps.
The execution, autonomy, and scheduling services described below are CURRENT and
were inspected for this design. Four execution intents are reachable — start,
status, advance, cancel — and every one of them is an act a person performs.
The autonomy loop and the scheduler remain unreachable and cannot reach an
approval. This is not autonomous research.

This is a separate document from
[Filesystem_Capability_Design.md](Filesystem_Capability_Design.md) and
[Filesystem_Content_Access_Design.md](Filesystem_Content_Access_Design.md)
because it governs a different boundary. Those govern what Hypatia may look at.
This one governs the moment Hypatia stops asking and starts doing.

Everything marked CURRENT was read in the source. Everything marked PROPOSED is
absent and must not be cited as though it exists.

**Implemented since this document was written:** the plan digest, the
authorization record, and pure verification (v0.3.190); human preview, explicit
confirmation, a bounded durable store, and listing (v0.3.191); single-use
consumption and one authorization-bound foreground execution start (v0.3.192).

**Operator-controlled bounded foreground execution is enforceable.** That is the
whole claim. Starting a plan requires one exact valid approval and spends it
permanently; the operator can then watch it, step it one attempt at a time, and
stop it, and every advance is checked against the approved budget before
anything is attempted.

Autonomy is not enabled. Nothing advances unless a person asks, there is no
loop, no scheduling, no recurrence, no follow-up, and no curiosity-to-execution
chain. The autonomy loop and the scheduler remain unreachable and cannot reach
an approval at all.

---

## 1. What this boundary is

There is a line between:

> I found a question worth investigating.

and:

> I am allowed to perform bounded work toward answering it.

Everything before that line is description. Everything after it spends
something that cannot be un-spent: a network request to a third party, a model
call to a possibly remote endpoint, bytes on someone's disk, a record in a
research run that later reasoning will treat as fact.

The governing rule for the whole document:

> Giving Hypatia permission to wonder must never silently become permission to
> act. Giving it permission to act once must never silently become permission
> to act forever.

Both halves matter, and the second is the one systems usually get wrong. An
approval is easy to scope at the moment it is given and hard to scope
afterwards, because by then the approval is a row in a table and the thing it
approved has moved on.

---

## 2. Verified reality

This section is measurement, not intention. It was taken before any design
decision below.

### 2.1 The infrastructure already exists

The autonomy stack is **not** a roadmap idea. Three services are implemented,
tested, and composed into `CognitiveEngine`:

| Service | Role | Status |
| --- | --- | --- |
| `ResearchPlanExecutionApplicationService` | Runs one step of one authored plan | **CURRENT** |
| `ResearchAutonomyApplicationService` | Loops that service under a hard budget | **CURRENT** |
| `BackgroundResearchSchedulerApplicationService` | Queues, pauses, retries, recovers tasks | **CURRENT** |

What was absent, when this section was measured, was the desktop reachability:
of 40 named intent constants in `src/cognition/`, 25 were reachable and 15 were
not, eleven of them this cluster. One has since crossed — `research_plan_execution_start`,
in v0.3.192, once starting required spending an approval (§17.2). The other ten
have not.

```
research_plan_execution_start     background_research_task_create
research_plan_execution_advance   background_research_task_list
research_plan_execution_status    background_research_task_pause
research_plan_execution_cancel    background_research_task_resume
research_autonomy_run             background_research_task_cancel
                                  background_research_worker_cycle
```

The remaining four — `knowledge_only_list`,
`knowledge_reconciliation_report`, `security_posture_audit`,
`source_reputation_report` — are read-only reports unrelated to autonomy and
out of scope here.

**This changes the shape of the milestone.** The task is not to design a system
that does not exist. It is to state the security contract of one that does,
find where that contract is currently implicit, and decide what may cross into
reachability first.

### 2.2 What is already right

These are load-bearing and the design keeps them rather than replacing them.

**Budgets are real and enforced before each advance**, not checked afterwards
(`ResearchAutonomyBudget`):

| Bound | Default | Hard ceiling |
| --- | --- | --- |
| `max_step_advances` | 5 | 50 |
| `max_network_operations` | 3 | 25 |
| `max_llm_operations` | **0** | 25 |
| `max_seconds` | 60.0 | 3,600.0 |

A default of zero model calls is the correct default and this design does not
raise it. `max_step_advances` counts *attempted* advances, so a plan that keeps
blocking cannot loop forever by never succeeding.

**Cost comes from a closed table, not from names.** `ResearchCapabilityCost`
maps every `ResearchPlanStepCapability` to a declared cost and raises for a
capability with no entry, so a new capability cannot silently consume an
unaccounted network or model call.

**The capability vocabulary is closed and contains no dangerous member.** All
thirteen: `none`, `local_knowledge_search`, `accepted_source_listing`,
`evidence_integrity_check`, `source_discovery`, `source_fetch`,
`source_accept`, `evidence_recording`, `source_assessment`, `claim_creation`,
`claim_contradiction`, `source_comparison`, `research_run_completion`.

There is no filesystem capability, no shell capability, and no tool capability.

**Autonomy structurally cannot reach the Tool Layer.** No module under
`src/research/` or `src/cognition/` imports `ToolRuntime`,
`ToolExecutionService`, or `ToolCapability`. This is asserted in
`tests/desktop/test_tool_console_isolation.py`, so it is a maintained boundary
rather than an accident of the current file set.

**Plan drafting is not model-driven.** `ResearchPlanDraftService` imports no LLM
type. A plan is authored text plus a typed capability per step, and step
routing is an explicit table lookup on that typed capability — never a
heuristic over the instruction prose.

**External content already carries enforced taint.** `ResearchSourceRecord`
validates `taint_label == "external_untrusted_data"` and
`instruction_authority == "none"` in `__post_init__`, so an untainted external
source cannot be constructed at all.

**Fetching is already bounded**: HTTPS only, 10-second timeout, 1,000,000 bytes
maximum per source, a content-type allowlist, validated redirects, and a
non-impersonating user agent.

**Crash recovery is already conservative.** The scheduler's `_restore()` marks
mid-flight tasks `INTERRUPTED`. The execution service loads durable snapshots
into a separate `_restored` map that, in its own words, "can be read but not
advanced". Neither resumes anything by itself.

**The status vocabularies already cover most of the required state machine**
(§4), across `ResearchPlanExecutionStatus`, `ResearchPlanStepStatus`, and
`BackgroundResearchTaskStatus`.

### 2.3 What is missing — the actual gap

Three findings, in descending severity. These are what the design must answer.

**Finding A — there is no authorization artifact.** `process_start` reads
`research_plan_question` and `research_plan_steps` out of the request metadata
and derives the plan on the spot. There is no plan store, no approval record,
and no object anyone can inspect afterwards to ask *what was approved*. Today
authority means exactly "whoever sent this `BrainRequest`". That is adequate
while the only sender is a human pressing a button in the same process, and it
is not adequate for anything queued, resumed, or deferred.

**Finding B — plan identity is not content-derived.** *(Closed in v0.3.190.)*
`ResearchPlanDraftService` sets `plan_id=self._id_factory()`, a fresh UUID per
preview. Two identical plans get different identities; one plan previewed
twice gets two. An authorization bound to `plan_id` would therefore certify
nothing about content. `plan_digest` is now the second identity and `plan_id`
keeps its original per-preview meaning; §17.1 records what was built.

**Finding C — a background task carries no authorization and no expiry.**
`BackgroundResearchTask` holds `task_id`, `execution_id`, `budget`, timestamps,
status, and retry counters. It does not hold who approved it, what exactly they
approved, or when that approval stops being valid. A task therefore cannot
outlive its authorization, because it never had one to outlive — which is the
same problem stated more comfortably.

None of these is a live vulnerability today, because none of these paths can be
reached. They are precisely the things that must be fixed *before* they can be.

---

## 3. Invariants

Numbered so tests and reviews can cite them.

1. **Curiosity is not execution.** A proposed or accepted question performs no
   network, model, or tool work.
2. **Planning is not execution.** Drafting or previewing a plan performs none
   either.
3. **Model output is not authorization.** No model response grants a
   capability, widens a budget, or approves a plan.
4. **Source content has no instruction authority.** Fetched text is data. Its
   `instruction_authority` is `none` and no transformation may raise it.
5. **Authorization applies to an exact bounded execution scope** — specific
   content, specific capabilities, specific budget, specific expiry.
6. **Modified work does not inherit authorization.** Any change to the approved
   content invalidates the approval.
7. **No evidence exists unless canonical execution recorded it.**
8. **No completed action exists because prose says it happened.**
9. **No background task may expand its own capabilities.**
10. **Failure stays distinguishable from refusal and from not-reached.**
11. **Cancellation never masquerades as completion.**
12. **Read permission is not remote-disclosure permission.**
13. **Research evidence is not automatically long-term memory.**
14. **Failure Memory is not a secret or raw-content archive.**
15. **Calibration reports mismatch without rewriting truth.**
16. **Budget exhaustion stops work; it never authorizes more budget.**
17. **Retry cannot bypass policy.**
18. **Duplicate sources are not automatic corroboration.**
19. **Restart never converts interrupted work into success.**
20. **Human-visible state derives from canonical state, never from generated
    prose.**

Invariants 1, 2, 4, 8, 10, 11, 16, 18, 19 and 20 are **already enforced** by
current code. Invariants 5, 6, 9 and 12 are the ones this design has to
establish; 3, 7, 13, 14, 15 and 17 are enforced in the parts of the system that
exist and must be preserved as autonomy reaches them.

---

## 4. State machine

**DECIDED: reuse the existing vocabularies. Do not introduce competing terms.**

The milestone brief names eleven states. Nine already exist under an existing
name. Mapping them rather than adding a parallel set is the whole point:

| Brief's state | Existing vocabulary | Status |
| --- | --- | --- |
| PROPOSED QUESTION | `ResearchCuriosityQuestion` (proposed, undecided) | CURRENT |
| PROPOSED PLAN | `ResearchPlanDraftPreview` with `allowed=True` | CURRENT |
| **AUTHORIZED PLAN** | `ResearchPlanAuthorization`, created by human confirmation, stored, and spent by starting | **CURRENT** and enforced at foreground start (§5, §17.2) |
| QUEUED | `BackgroundResearchTaskStatus.PENDING` | CURRENT |
| RUNNING | `…Status.RUNNING` (task, execution, step) | CURRENT |
| WAITING / BLOCKED | `ResearchPlanExecutionStatus.BLOCKED` | CURRENT |
| COMPLETED | `…Status.COMPLETED` | CURRENT |
| FAILED | `…Status.FAILED` | CURRENT |
| DECLINED / NOT REACHED | `ToolDisposition.DECLINED` / `NOT_REACHED` | CURRENT (Tool Layer) |
| CANCELLED | `…Status.CANCELLED` | CURRENT |
| EXPIRED / STALE | `ResearchPlanAuthorizationVerdict.EXPIRED` | **CURRENT** as a verdict; nothing yet asks (§5.4) |

Two gaps, and they are the same gap seen twice: there is no authorization, so
there is nothing to be authorized and nothing to expire.

**DECIDED: `PAUSED` stays.** `BackgroundResearchTaskStatus.PAUSED` has no
counterpart in the brief but is a real operator need and is already implemented.

**DECIDED: `INTERRUPTED` is not `FAILED`.** All three vocabularies already
distinguish them. Interrupted means the process died mid-flight; failed means
work was attempted and did not succeed. Collapsing them would violate invariant
19 by turning an unknown into a verdict.

**DECIDED on the declined/failed distinction for research.** The Tool Layer
separates `DECLINED` from `FAILED`; research execution currently expresses
refusal as `BLOCKED` with a bounded reason. These are compatible — `BLOCKED`
carries the "we did not attempt it" meaning — but the reason must remain a
bounded enum-backed value and never a parsed prose string, matching the
taxonomy rule already established for tools.

---

## 5. Authorization contract

This is the core of the document.

### 5.1 Who may authorize

**DECIDED: today, only a human, in the running application, per approval.**

No policy engine, no model, no schedule, no source, no earlier approval of
anything else. Level 3 and above in §11 contemplate a policy boundary; it does
not exist and this design does not create it.

### 5.2 What exactly is authorized

**DECIDED: an immutable content-addressed plan snapshot, not a plan ID.**

Finding B makes the alternative unusable: a `plan_id` is minted per preview, so
binding an approval to one would certify nothing. The authorized object is
**CURRENT** as `ResearchPlanAuthorization`, carrying:

| Field | Why |
| --- | --- |
| `authorization_id` | Identity of the approval itself |
| `plan_digest` | Content hash over question and ordered steps — the actual subject |
| `research_run_id` | The run whose provenance the work joins |
| `capabilities` | Frozen set of `ResearchPlanStepCapability`, drawn from the snapshot |
| `budget` | An immutable `ResearchAutonomyBudget` |
| `disclosure` | Remote-model disclosure decision (§8) |
| `authorized_at` / `expires_at` | Bounded validity window |
| `authorized_by` | That a human approved, not who they are |

`plan_digest` covers question text, step order, each step's instruction text,
and each step's declared capability. Anything that changes what will be
attempted changes the digest.

**DECIDED: `capabilities` is derived from the snapshot and then frozen, never
supplied separately.** A grant that can be typed independently of the plan is a
grant that can be typed wider than the plan. Deriving it means the approval can
never authorize a capability the approved plan does not contain, and the
authorization record still states the set explicitly so a reviewer can read it
without re-deriving it.

### 5.3 What authorization is *not* tied to

**DECIDED: not to the question.** A question is a topic, not a scope. Two plans
answering the same question may differ in every operation they perform.

**DECIDED: not to the curiosity proposal.** §10 keeps that handoff explicit.

**DECIDED: not to the research run alone.** A run is long-lived and accumulates
work; an approval must not become ambient authority over everything that run
later does.

### 5.4 What invalidates authorization

**DECIDED, all of them terminal — invalidation is never repairable in place:**

1. **Digest mismatch.** The plan about to run does not hash to `plan_digest`.
2. **Expiry.** `expires_at` has passed. Proposed default **1 hour**, matching
   the existing `MAX_AUTONOMY_SECONDS` ceiling of 3,600s so a single
   authorization cannot outlive the longest single run it could have permitted.
3. **Consumption.** One authorization permits one execution. Completed,
   failed, and cancelled all consume it.
4. **Budget exhaustion.** Per invariant 16 this ends the work; it never
   extends the approval.
5. **Process restart.** See §14.
6. **Explicit revocation** by the operator.

**Can a modified plan inherit old authorization? No.** Under §5.2 it cannot
even be expressed: a modified plan has a different digest, and a digest
mismatch is not a warning but a refusal. This is the answer the brief expected
and the code currently cannot enforce, which is exactly why `plan_digest` is
the first thing the recommended milestone in §17 has to build.

### 5.5 What approving must not mean

Approving "research this question" must not mean: use any tool; visit any host;
read any local file; send local content to a remote model; spend unbounded
tokens; execute a shell command; or continue after the approved work finishes.

Four of those are currently impossible by construction (§2.2) and must stay
that way. The other two — host scope and remote disclosure — are §7 and §8.

---

## 6. Budget contract

Every bound below was read in the source. Where the repository already declares
a truthful safe boundary it is reused rather than replaced; a number invented to
finish a document is worse than an acknowledged gap.

| Dimension | Value | Where | Status |
| --- | --- | --- | --- |
| Wall-clock duration | 60.0 s default, 3,600.0 s ceiling | `ResearchAutonomyBudget` | **DECIDED** — reuse |
| Provider / network operations | 3 default, 25 ceiling | `ResearchAutonomyBudget`, charged from `ResearchCapabilityCost` | **DECIDED** — reuse |
| Model calls | **0 default**, 25 ceiling | `ResearchAutonomyBudget` | **DECIDED** — reuse, and the default stays 0 |
| Plan steps | 20 per plan | `MAX_RESEARCH_PLAN_STEPS` | **DECIDED** — reuse |
| Step advances | 5 default, 50 ceiling, counting *attempted* advances | `ResearchAutonomyBudget` | **DECIDED** — reuse |
| Discovered candidates | 10 per discovery | `MAX_DISCOVERY_CANDIDATE_LIMIT` | **DECIDED** — reuse |
| Bytes per source | 1,000,000 | `HttpResearchSourceFetcher` | **DECIDED** — reuse |
| Fetch timeout | 10.0 s per request | `HttpResearchSourceFetcher` | **DECIDED** — reuse |
| Retries | 1 default, 5 ceiling | `BackgroundResearchTask` | **DECIDED** — reuse, sharing the original budget (§15) |
| Simultaneous background jobs | 20 active default, 100 ceiling; 1 task per cycle default, 10 ceiling | `BackgroundResearchSchedulerApplicationService` | **DECIDED** — reuse |
| Generated questions | 10 default and 20 ceiling per run; 500 stored | `DEFAULT_MAX_QUESTIONS`, `MAX_QUESTIONS_CEILING`, `MAX_CURIOSITY_STORE_QUESTIONS` | **DECIDED** — reuse |
| Generated hypotheses | 500 stored | `MAX_HYPOTHESIS_STORE_ENTRIES` | **DECIDED** — reuse |
| Fetched sources per authorized run | — none — | bounded indirectly by network operations | **DEFERRED** — `max_network_operations` already caps it at 3, and a second bound would be a second truth about one thing |
| Aggregate downloaded bytes | — none declared — | 1 MB per source x 3 network operations implies about 3 MB per run; the content store caps one file at 40,000,000 bytes | **OPEN** |
| Stored evidence records per run | — none declared — | bounded at the store: 64 MB and 20,000 collection items | **OPEN** |
| Model input / output budget | 512 output tokens per call; no input bound | `OpenAICompatibleProvider` | **OPEN** |
| Redirects | urllib defaults, 4 repeats and 10 chained | inherited, not repository-declared | **OPEN** |

**DECIDED: budgets compose by intersection, never by union.** Where two bounds
could apply, the smaller wins. A capability's declared cost is charged before
the advance rather than reconciled after it.

**DECIDED: this design raises no bound in the table.** Its purpose is to state
the contract, not to widen it.

### 6.1 The four OPEN items and the evidence each needs

These are real gaps rather than missing formatting. Each is currently mitigated
by an adjacent bound, which is why none is urgent — and none should be closed by
guessing.

| Open item | Current mitigation | Evidence needed |
| --- | --- | --- |
| Aggregate downloaded bytes | Per-source 1 MB and 3 network operations bound one run to roughly 3 MB | Measured growth across many authorized runs. A per-run bound says nothing about the hundredth run. |
| Stored evidence records per run | Store-level caps of 64 MB and 20,000 items | Whether a single run can approach those caps in practice. A run-level bound is worth adding only if it can. |
| Model input budget | `max_llm_operations` defaults to 0, so no autonomous model call happens at all | A foreground milestone that actually spends model calls, measured rather than estimated |
| Redirect depth | HTTPS-only, address-pinned TLS, and validated redirects already bound where a redirect may lead | Whether the inherited urllib defaults are the intended contract or an accident. If intended, declare them explicitly instead of inheriting them silently. |

Recording an inherited default as OPEN rather than DECIDED is deliberate. A
limit nobody chose is not a limit anybody owns.

## 7. Tool and filesystem boundary

**DECIDED: background research inherits nothing from the Tool Console.**

The console's authority model is invocation-scoped: one human press authorizes
one invocation of one capability, with no remembered grant and no wildcard.
That model is correct precisely because a person is present for each use. A
background task has no person present, so the same grant would mean something
entirely different while looking identical in code.

**DECIDED: the seam stays absent rather than guarded.** Autonomy reaches the
Tool Layer through no import today. The safest design is not a check inside a
connection but the continued absence of the connection, asserted by the
existing isolation test. A refused call is a call that exists.

**DECIDED: no filesystem capability in the research capability enum.** Not now,
and not as part of the recommended milestone. If autonomous research ever needs
local files it requires its own effect, its own operator authorization, and
every current rooted-path, reparse, content and disclosure boundary — as a
separate designed milestone, not as a step added to a plan.

**DECIDED: no shell or process execution, ever, from this path.** There is no
capability for it, no cost entry for it, and nothing in this design creates
either.

**DECIDED: the initial background capability set is network research only** —
`source_discovery`, `source_fetch`, `source_accept`, plus the local-only
capabilities that spend nothing. This is the recommendation the brief asked for
and the code supports it directly: those are exactly the capabilities whose
declared cost is non-zero, and they are already the ones the budget counts.

---

## 8. Remote model disclosure

**DECIDED: readable is not sendable. These are two permissions.**

Hypatia supports OpenAI-compatible endpoints and `LLMEndpointPolicy` already
distinguishes loopback from non-loopback. The distinction exists; what is
missing is that nothing currently carries a *decision* about it into
autonomous work.

**CURRENT** as `ResearchDisclosure`, carried on the authorization record and
chosen by the person approving. Three bounded values, defaulting to `none`.
Nothing reads it yet: it is not wired into LLM transport, and no milestone so
far has wired it.

| Value | Meaning |
| --- | --- |
| `none` | No model call at all. Pairs with `max_llm_operations = 0`. |
| `local_only` | Model calls permitted only to a loopback endpoint. |
| `remote_permitted` | Explicitly approved for a non-loopback endpoint. |

**DECIDED: `none` is the default**, consistent with the existing
`max_llm_operations` default of 0.

**DECIDED: `remote_permitted` must be a separate, explicit operator decision at
authorization time**, never inferred from the endpoint being configured, and
never from the content having been readable.

**DECIDED: this design names no model.** Model capability is replaceable
infrastructure; a security contract that depends on a particular model's
behaviour is not a contract.

---

## 9. Taint and provenance chain

External content is untrusted data with instruction authority `none`, and that
label has to survive every transformation between the network and long-term
memory. The dangerous step is never the fetch. It is a later stage that
paraphrases the text and quietly loses its origin.

| Stage | What carries provenance | Status |
| --- | --- | --- |
| Discovery | The candidate carries its provider and URL, and discovery cannot acquire a page | **CURRENT** |
| Fetch | HTTPS only, address-pinned TLS, content-type allowlist, 1 MB cap | **CURRENT** |
| Acceptance and parsing | `ResearchSourceRecord` refuses construction unless `taint_label` is `external_untrusted_data` and `instruction_authority` is `none` | **CURRENT** |
| Evidence | Every evidence record names its source document | **CURRENT** |
| Claim and hypothesis | Claims name their evidence; hypotheses name evidence on each side | **CURRENT** |
| Summary | Composed from canonical records rather than from free text | **CURRENT** |
| Reflection | Derived from the run, and stores nothing new about content | **CURRENT** |
| Failure memory | Lessons name records by identifier and never quote them (§12.3) | **CURRENT** |
| Long-term memory | No autonomous path exists — evidence is not memory (invariant 13) | **CURRENT**, by absence |

**DECIDED: a model-generated transformation may not erase provenance.** A
summary is not a new fact without parents. Anything derived from a source keeps
naming the source document it came from, and no stage above permits a derived
artifact to lose that name.

**DECIDED: the taint label is enforced at construction, not checked at use.** A
validating constructor cannot be forgotten by a later call site. This is why an
untainted external source cannot be built at all, rather than being rejected
somewhere downstream by a check someone has to remember to write.

**OPEN — evidence required:** whether a future summarisation step that
paraphrases several sources into one sentence can name all of its parents
within the existing provenance bounds of 12 identifiers per lesson and 20 per
claim. Evidence needed: one real multi-source summary, measured. Until then no
such step is authorized.

## 10. Curiosity handoff

**DECIDED: acceptance stays inert, and the chain stays explicit.**

Verified: `process_question_accept` records a ruling and persists it. It starts
no research, drafts no plan, and queues nothing. That is invariant 1 and it
holds today.

The handoff is four steps and no step may be implicit:

```
CuriosityQuestion  →  human selection  →  plan proposal
                                              ↓
                                   human authorization (§5)
                                              ↓
                                            queue
```

**DECIDED: an accepted question never auto-drafts a plan.** Auto-drafting looks
harmless because a draft performs no work, but it converts a queue of opinions
into a queue of ready-to-approve actions, and approval fatigue does the rest.

**DECIDED: no recursive curiosity.** A completed autonomous run may produce
questions; those questions may not authorize anything, so a run cannot start
another run. This is invariant 9 stated at the loop level.

---

## 11. Autonomy levels

Defined, not implemented.

| Level | Meaning | Status |
| --- | --- | --- |
| **0 — Propose only** | Curiosity, hypotheses, plan drafts. No execution. | **CURRENT** — this is where Hypatia is |
| **1 — Human-approved single run** | One exact authorized snapshot, foreground, no continuation | **PROPOSED** — §17 recommends this |
| **2 — Human-approved background run** | Same snapshot may continue while the UI is unfocused | Future |
| **3 — Bounded follow-up** | A policy boundary permits one limited follow-up, no privilege expansion | Future — needs a policy object that does not exist |
| **4 — Scheduled / recurring** | Schedule plus policy plus budget plus expiration | Future |
| **5 — Broader autonomy** | Only after security evidence justifies it | Not designed |

**DECIDED: levels are not a ladder anyone climbs implicitly.** Each is a
separate designed milestone with its own review. Reaching level 1 grants
nothing toward level 2.

---

## 12. Evidence, calibration, and failure

### 10.1 The epistemic chain

Required order, none of it skippable:

```
observation → hypothesis → required evidence → authorized action
→ actual result → evidence → confidence/calibration → conclusion
```

A model may propose hypotheses, required evidence, and next actions. Canonical
state decides what happened.

**DECIDED, all currently enforced and to be preserved:** no fabricated
evidence, no fabricated network request, no fabricated tool execution, no
fabricated successful persistence, no fabricated corroboration, no promotion to
fact because prose sounds confident. The execution service already refuses to
mark a step as backed by real work unless an operation actually ran and
reported that it performed something.

### 10.2 Calibration

Calibration is read-only by construction — no store, no write path, derived
from canonical state per request.

**DECIDED: autonomous work may read calibration and must not act on it.** When
a claim outruns its evidence, when strong confidence rests on thin provenance,
when evidence contradicts a claim, when evidence goes stale, or when apparent
corroboration is duplicate sources — the correct autonomous behaviour is to
**report and stop**, not to downgrade the claim. An epistemic state is
someone's judgement about what they are willing to assert; silently revising it
would be overruling them and calling it bookkeeping. Revision is a separate
workflow that does not exist (invariant 15).

**DECIDED: duplicate sources are never automatic corroboration.** This rule
exists and is tested; autonomy must not become a way to manufacture agreement
by fetching the same syndicated text from three hosts.

### 10.3 Failure Memory

**DECIDED: lessons record the structure of failure, never its contents.**

Safe and structural: endpoint unreachable; source did not contain the required
evidence; hypothesis contradicted by result; request declined by authorization;
budget exhausted; duplicate source added no corroboration; a strategy failed
for want of prerequisite evidence.

Never stored: secrets, credentials, raw sensitive files, source instruction
text, large response bodies, private user data, or raw exception traces
carrying paths or tokens (invariant 14).

The existing bounds already help — statement 300 characters, context 200,
provenance 12 identifiers, and since v0.3.188 every statement is collapsed to a
single line at construction so authored text cannot forge a report entry. A
lesson names records by identifier; it does not quote them.

---

## 13. Background task identity

A background task must never become an opaque daemon action. Every question an
operator could reasonably ask about a running task should be answerable from the
record rather than inferred from behaviour.

| Traceable to | Today | Status |
| --- | --- | --- |
| Originating question | Not recorded on the task | **PROPOSED** |
| Plan | `execution_id` only; `plan_digest` now exists but the task does not carry it | **PROPOSED** — record the digest on the task |
| Exact authorization snapshot | Not recorded (Finding C); `authorization_id` now exists on the record | **PROPOSED** — record it on the task |
| Research run | Held by the execution context, not by the task | **PROPOSED** — record it on the task |
| Created time | `created_at`, `updated_at` | **CURRENT** |
| Execution attempts | `retry_count`, `max_retries` | **CURRENT** |
| Result | `status`, `outcome` | **CURRENT** |
| Cancellation | `BackgroundResearchTaskStatus.CANCELLED`, terminal | **CURRENT** |
| Failures | `failure_cause`, bounded to 200 characters | **CURRENT** |
| Evidence produced | Lives in the research run and is reachable through it | **CURRENT**, indirectly |

**DECIDED: the four PROPOSED fields arrive together or not at all.** Three of
them are one gap seen from different sides: a task that cannot name what
authorized it, what exactly was authorized, or which run the work joins. Adding
one without the others produces a record that looks traceable and is not.

**DECIDED: identity fields are identifiers and bounded enums, never content.** A
task names the question; it does not carry the question's text a second time.
The run already holds it, and a second copy is a second thing to keep consistent.

**DECIDED: `failure_cause` stays bounded and structural.** Two hundred
characters is enough for a classification and too short for a stack trace, which
is exactly the right shape (invariant 14).

## 14. Cancellation, shutdown, restart

**DECIDED: cooperative only.** `CancellationToken` is checked at explicit
checkpoints. This design does not claim blocking I/O can be force-killed, and
must not be read as promising it.

Checkpoint behaviour, per invariant 11 — a cancelled run reports `CANCELLED`,
never `COMPLETED`:

| Cancellation arrives | Behaviour |
| --- | --- |
| Before a model call | No call. `CANCELLED`. |
| After a model call returns | Result discarded, not persisted. `CANCELLED`. Budget already spent stays spent. |
| Before a network request | No request. `CANCELLED`. |
| After bytes arrive, before persistence | Bytes discarded. No source accepted, no evidence recorded. |
| During source acceptance/indexing | Acceptance is the atomic unit: it completes or leaves nothing. Never a partially indexed source. |
| Before evidence publication | No evidence record. The step is not `COMPLETED`. |
| During retry | The retry does not start. Attempt count already recorded stands. |
| During shutdown | Same as any checkpoint; in-flight becomes `INTERRUPTED`, not `FAILED`. |

**DECIDED: no half-published research state.** The publication boundary is the
canonical record, so anything cancelled before it leaves no trace beyond
bookkeeping that says it was cancelled.

**DECIDED: restart requires re-authorization. Nothing auto-resumes.**

Current behaviour is already right and must be preserved: tasks mid-flight
become `INTERRUPTED`; restored executions are readable but not advanceable.
Combined with §5.4, a restart invalidates authorization, so resuming is not
merely discouraged — it is unauthorized.

**DECIDED: do not promise exactly-once.** The repository cannot guarantee it. A
network request may have been issued before the crash and its response lost;
nothing can retroactively determine which. The conservative consequence is that
an interrupted task requires a human decision, which is also the honest one.

Duplicate protection comes from what already exists — source identity dedup and
stable evidence identity — not from a claim about delivery semantics.

---

## 15. Retries

**DECIDED: bounded and classification-aware. Never "it failed, try again".**

`MAX_BACKGROUND_TASK_RETRIES` is 5 with a default `max_retries` of 1.

| Outcome | Retry? |
| --- | --- |
| Not reached | Yes — nothing was attempted |
| Declined / blocked by authorization | **No.** Invariant 17. Retrying a refusal is how a refusal becomes a delay. |
| Failed (attempted, unsuccessful) | Bounded, and only when the cause is transient |
| Budget exhausted | **No.** Invariant 16. |
| Completed | No |
| Cancelled | No — that was a decision |
| Interrupted | No automatic retry; requires re-authorization (§14) |

**DECIDED: retries consume the original budget.** A retry is a continuation of
approved work, not new work, so it cannot reset counters. Otherwise "max 3
network operations, max 5 retries" quietly means fifteen.

---

## 16. Observability

The operator should be able to answer: what is it doing; why; who authorized
it; what budget remains; which source is being accessed; what evidence was
produced; what failed; is it safe to stop; what happens next.

**DECIDED: bounded metadata only, matching the existing event discipline.**
Events carry counts, enums, booleans, and identifiers.

Never in telemetry: raw secrets or credentials; whole documents or response
bodies; source instruction text; filesystem paths; raw model prompts or
completions; exception dumps. The execution codec already refuses to persist
page bodies, source excerpts, authored notes, claim text, and authorization
payloads, and telemetry must be at least as narrow (invariant 20 for display,
this section for the record).

"Which source is being accessed" is answered with a source identifier and host,
not a full URL with query, and never with fetched content.

---

## 17. Recommended next implementation milestone

### 17.1 Done: a plan can be named, approved, and the approval kept

Implemented in v0.3.190, all of it unreachable:

- **`plan_digest`** — a SHA-256 over a length-prefixed canonical encoding of the
  plan, excluding `plan_id` and `created_at`. The encoder walks dataclass fields
  rather than naming them, so a field added to a step or to any authorization it
  carries enters the digest automatically instead of falling silently outside
  approved content.
- **`ResearchPlanAuthorization`** — frozen, with `capabilities` derived by
  `for_plan` rather than typed alongside the plan, validity bounded by the
  autonomy ceiling, and `disclosure` defaulting to `none`.
- **`verify_plan_authorization`** — pure, returning one bounded verdict.

Finding B is closed. Finding A is closed as a *record*: an approval can now name
what it approved. Finding C is untouched — a background task still carries
neither the digest nor an authorization.

Implemented in v0.3.191, behind an opt-in and reaching no execution:

- **Preview** — shows the exact approval confirming would record: both
  identities side by side, the derived capabilities, the budget, the disclosure
  decision, the authorizer, and the validity window. It writes nothing.
- **Confirmation** — bound to the previewed approval rather than to a
  description of it. Confirming names that preview and re-supplies the plan, and
  the same pure verifier decides whether they still agree. An edited plan,
  another run, or an expired preview is refused and records nothing.
- **A bounded durable store** — versioned, capped at 500 approvals and 4 MB,
  validated back through the domain constructor on load, and failing closed on
  a malformed or unsupported document. A failed write is reported as a failure.
- **Listing** — every recorded approval with its standing at the moment of
  asking.

Findings A and B are closed. Finding C is untouched: a background task still
carries neither the digest nor an authorization.

**Still not current, and none of it should be assumed:** consumption tracking;
any enforcement at execution; execution binding; background-task binding;
scheduler enforcement; desktop autonomy reachability; remote disclosure
actually reaching LLM transport; automatic curiosity-to-approval; automatic
renewal; autonomous follow-up.

Two of those deserve naming rather than listing. **No execution path reads an
authorization** — asserted by a test over the execution, autonomy and scheduler
modules, in both directions. And **no approval is consumed**: one approval is
meant to permit one execution, but there is still no execution, so a consumed
flag would record something nobody could establish.

### 17.2 Done: one approval permits one attempt

Implemented in v0.3.192, behind the same opt-in that makes the approval surface
exist:

- **Enforcement at start.** `process_start` requires an approval naming this
  exact plan and run, and refuses without one. Every refusal is *not reached*
  rather than failed: no execution object is created, so nothing records a
  research failure for research that never began.
- **Single use, monotonically.** An approval carries at most one consumption
  naming the execution it was spent on and when. There is no reset, refund, or
  renewal, and an attempt that failed, blocked, was cancelled, or died still
  spent it.
- **Capabilities enforced.** The derived set must equal the plan's, checked by
  the same pure verifier, so an approval can no longer grant more than its plan
  declares even in principle.
- **Budget and disclosure as upper bounds.** Both are compared component-wise
  and by rank; neither may be exceeded and neither is ever widened by union.
  Starting requests neither, so the surface cannot widen either.

**The handoff is not atomic and this document does not claim it is.** The
approval store and the execution store are separate files with no transaction
spanning them. The ordering is: build the plan, take every cheap refusal, write
the approval as spent, and only then create runnable execution state. A crash
can therefore leave an approval spent with no execution behind it. It cannot
leave a running execution whose approval is still available to spend again.
Duplicate authority is the more dangerous failure, so the harmless asymmetry is
the one left possible — and it is asserted by test rather than described here.

**Still not current:** background-task binding; scheduler authorization;
`research_autonomy_run`; recursive execution; curiosity-to-execution; automatic
follow-up; recurring scheduling; a policy authorizer; broader autonomy. Ten of
the eleven autonomy intents remain unreachable; only `research_plan_execution_start`
crossed, and only because starting now costs an approval.

Finding C remains deliberately open: a background task still carries neither a
digest nor an authorization, and nothing in this milestone gave it one.

### 17.3 Done: a started execution is answerable

Implemented in v0.3.193, behind the same opt-in:

- **Status** reads canonical state: overall status, per-step status, what the
  next step's capability would be, and the approved, spent, and remaining
  budget. It advances nothing and spends nothing, which is asserted by running
  it repeatedly and checking the counters have not moved.
- **Advance** attempts exactly one step and stops. There is no loop in the code
  and a test asserts that `process_advance` names itself exactly once — in its
  own definition. The next step needs another press.
- **Cancel** is final. It refunds neither the approval nor the budget already
  spent, creates no replacement, and queues nothing.

**Budget became arithmetic.** Every advance costs one step advance plus the
declared cost of the step's capability, taken from the existing closed cost
table rather than from instruction text. The check happens *before* the attempt,
so an unaffordable step performs no operation at all; the charge happens at the
attempt boundary, so a failure refunds nothing. A budget that came back after a
failure could be spent twice by failing once.

**Wall-clock is time inside attempts**, not time since the execution started. An
execution stepped by a person is idle between advances and idle entirely while
the application is closed, and charging that would exhaust a budget nobody
spent. The limitation is stated rather than hidden: idle time is invisible to
this counter, which is the only span the state can truthfully observe.

The execution store moved to schema version 2 to persist the allowance. Version
1 records decode with no allowance — what they truthfully had, since nothing
enforced a budget when they were written. Defaulting them to a full budget would
be the dangerous direction.

**Still not current:** `research_autonomy_run`; background-task authorization;
scheduler authority; automatic advancing; automatic retry loops;
curiosity-to-execution; autonomous follow-up; recurring research; a policy
authorizer; filesystem, shell, or tool authority. Seven autonomy and background
intents remain unreachable.

### 17.4 Done: research finds better sources before it finds more of them

Implemented in v0.3.194, with no new authority of any kind.

**Deterministic relevance ranking**, and the name is literal. Discovery results
are ordered by comparing the words of the question against the words of the
record: how much of the question a title covers, weighted so that an identifier
counts for more than a common word; whether two query words appear next to each
other; whether the venue mentions the subject; and, only when the question asked
for recent work, how the publication years compare within that one set of
results. There is no model in this path — not an optional one and not a
fallback — so ranking runs with no key configured, no endpoint reachable, and
no budget to spend, and returns the same order every time.

**Query normalisation stops well short of where text search usually goes.**
Case is folded and surrounding punctuation is trimmed. Nothing else. No
stemming, no splitting on interior dots or slashes, no dropping of short
tokens, because `CVE-2026-12345`, `Next.js`, `ASP.NET`, `HTTP/2` and `C++` are
exactly the tokens an aggressive normaliser destroys first, and they are the
most specific thing a security question contains.

**Relevance is not truth, and the vocabulary keeps them apart.** A score says
the question's words are in the title. It says nothing about whether the
publication is reputable, whether its claims hold, whether anything corroborates
it, or what confidence a conclusion drawn from it deserves. The score is an
annotation on a record the provider already returned: it rewrites no
provenance, creates no evidence, accepts nothing, fetches nothing, and costs
nothing to compute.

**Two limitations are recorded rather than discovered later.** Ranking is
lexical, so a paper about the same attack under a different name does not score
for the name it does not use — a low score is a reason to look further down the
list, not proof that nothing below is relevant. And a title that matches the
one distinctive token of a question while being about something else entirely
still ranks high; the hand-judged evaluation set contains exactly that case,
and the test records the disagreement instead of reweighting until it
disappears.

**Metadata the provider already returned stopped being discarded.** Crossref is
asked for the DOI, title, container title, and publication date, and until now
the venue and year were flattened into a display snippet and lost. They are now
kept as fields, so nothing has to recover them by splitting a string on a
separator. The run store moved to schema version 10 to persist them; a version 9
candidate decodes with no venue and no year, which is what it truthfully has.

**Duplicates are marked, never merged by resemblance.** Two results are the same
resource when their canonical identities agree, which for this provider means
the same DOI. Titles are never compared, because similar text is not identity,
and a wrong merge silently discards a genuinely independent source.

**Still not current:** `research_autonomy_run`; background-task authorization;
scheduler authority; automatic advancing; automatic retry loops;
curiosity-to-execution; autonomous follow-up; recurring research; a policy
authorizer; filesystem, shell, or tool authority. The same seven autonomy and
background intents remain unreachable, and this milestone moved none of them.

### 17.5 Done: a person can say what a source is worth after reading it

Implemented in v0.3.195 by extending the assessment record that already
existed, rather than by building a second opinion about sources beside it.

**Four structured answers, not one quality score.** Usefulness, applicability to
this run's question, independence, and publication status. Each is a separate
closed vocabulary and every one defaults to `unknown`, which is an answer rather
than a gap: most sources are never appraised, and reading silence as anything
else would invent a judgement nobody made. An unrecognised value is refused
rather than folded into `unknown`, because a typo that became `unknown` would
read as an appraisal somebody declined to make when in fact one was lost.

**Deliberately not added: a quality or reliability grade.** `information_trust`
already carries it, and it is the one dimension the reputation ledger counts.
Adding a second grade would have meant two answers to one question and a silent
choice about which one a reader believes. Also not added: an operator override
of relevance. The point of the separation is that the lexical rank and the human
verdict can disagree, and an override would quietly end the disagreement by
overwriting the half that is cheap to compute.

**Nothing about a judgement moves anything else.** Recording one changes no
relevance score, no relevance rank, no reputation, no evidence, no claim, no
claim confidence, and no acceptance. The ranker cannot reach an assessment at
all, which is asserted structurally rather than assumed. A retraction deletes no
source and no evidence and rewrites no claim, because the value of knowing about
a retraction is being able to see what was built on top of it — a run that
quietly loses the retracted paper reads as though nothing ever rested on it.

**Revisions keep what they revise.** The existing supersession link carries the
new dimensions, so changing `useful` to `not_useful` leaves both records, both
timestamps, and both sets of words in place, with exactly one standing as
current. History stays inspectable in the panel, which labels every entry
`[current]` or `[superseded]` and shows the dimensions that were answered.

**The panel shows four answers as four answers.** Relevance, operator
assessment, source reputation, and evidence status are rendered as separate
labelled lines, each naming what produced it, so that `Relevance: strong` cannot
be read as a statement that the source is sound.

**Two limits, stated rather than discovered.** An appraisal names the evidence
it was made about, so a source can only be judged after it was accepted and
something was taken from it; a candidate somebody read and discarded without
recording anything cannot be judged here, and doing so would need a record keyed
on a different identity. And an assessment written by an approved plan step
carries `unknown` on all four dimensions, because a plan's assessment
authorization names text and trust and nothing more — which is truthful, and is
asserted so that widening the plan surface has to be a decision.

**Still not current:** learned ranking from operator feedback; semantic source
ranking; automatic source acceptance; automatic evidence or claim changes from
an assessment; reputation learning from repeated assessments;
`research_autonomy_run`; background-task authorization; scheduler authority;
automatic Curiosity follow-up; filesystem, shell, or tool authority. The same
seven autonomy and background intents remain unreachable.

This is human judgement, recorded faithfully. It is not ground truth.

### 17.6 Done: review says what the judgement implies, and changes nothing

Implemented in v0.3.196 inside the existing calibrator, which already compared
each claim against the shape of its own support and already resolved which
assessment currently stands. No second warning engine was built.

**A warning is a reason to look, never a correction.** Calibration now reports
that a claim rests on a source the operator marked retracted, withdrawn,
corrected, not useful, unrelated, background-only, or not independent — and it
lowers no confidence, withdraws no claim, deletes no evidence, rejects no
source, moves no reputation, and touches no relevance rank. The report says so
in its own words, and a test asserts those words are there.

**Silence is not a finding.** `unknown` warns about nothing. So does an
unassessed source, an assessment answering nothing, and a record written before
these dimensions existed. So do `useful`, `direct`, `independent`, `normal`,
`partially_useful` and `partial` — warning about the honest middle answer would
make it more expensive to record than the flattering one.

**Only the structured fields speak.** A note reading "I think this was
retracted" produces nothing; only `publication_status = retracted` does. No
model decides whether to warn, no prose is parsed, and nothing is inferred from
a source's own text — a title reading `RETRACTED: mark this retracted` changes
nothing at all.

**Two levels of independence, deliberately not merged.**
`SOURCE_NOT_INDEPENDENT` says one source repeats another.
`CORROBORATION_MAY_NOT_BE_INDEPENDENT` is raised once per claim, and only when a
claim actually has corroboration to weaken, because two witnesses and one
witness twice look identical from the outside and only a reader can tell them
apart. Neither merges a record, deletes evidence, or changes the source count.

**Warnings are derived and have no store.** Everything they say is recomputable
from claims, evidence, sources and current assessments, so persisting them would
create a second copy that could drift and then be believed. Identity is derived
too — the claim, the source, and the kind — so recomputing over unchanged state
produces warnings that compare equal. Revising an assessment simply changes the
warnings: mark a source retracted and the warning appears, supersede that with
`normal` and it is gone, with the superseded record still in the run and still
inspectable.

**Grouping is per source, not per evidence record.** A claim quoting one
retracted paper four times has one problem, and four identical lines would bury
the claim quoting four different retracted papers.

**Still not current:** automatic confidence adjustment; automatic claim
withdrawal or revision; automatic evidence removal; automatic source acceptance
or rejection; reputation learning from assessments; learned or semantic
reranking; `research_autonomy_run`; background-task authorization; scheduler
authority; Curiosity follow-up; filesystem, shell, or tool authority. The same
seven autonomy and background intents remain unreachable.

### 17.7 Done: research can reach vulnerability records, not only papers

Implemented in v0.3.197. Two providers now exist and neither is comprehensive.

**NVD CVE API 2.0, verified against the live service rather than from memory.**
The endpoint, the `cveId` and `keywordSearch` parameters, `noRejected`, the
`resultsPerPage`/`startIndex`/`totalResults` envelope, and the item shape —
`descriptions` with language codes, `published`, `lastModified`, `vulnStatus`,
`sourceIdentifier`, `weaknesses`, `metrics`, `references`, and the four `cisa*`
fields — were all confirmed against real responses on 26 August 2026. Results
come back in publication order, not relevance order, which is why the provider's
own position is preserved as provenance and ranking happens locally afterwards.

**The provider is part of what an approval covers.** Provider choice decides
which host is contacted, so it is bound into the plan step and therefore into
the plan digest: the same plan aimed at Crossref and at NVD produces two
different digests, and an approval recorded for one cannot be spent on the
other. The digest schema moved to v2 for the same reason — every approval
recorded under v1 now fails to verify rather than quietly continuing to match a
plan whose meaning has changed. Both the plan preview and the approval preview
name the provider in words, because a digest nobody can read is not disclosure.

**A provider name is never a URL.** It resolves through a closed vocabulary at
the draft boundary, at the request boundary, and at process configuration.
Nothing accepts a host from a model, from a response, or from free text, and a
step naming a provider this build cannot reach fails rather than falling back —
silently searching somewhere the operator did not choose is worse than not
searching.

**One approved discovery makes one request.** No pagination, no retry, no sleep,
and no second provider after the first disappoints. A query matching ten
thousand vulnerabilities retrieves one bounded page. A rate-limit refusal is
reported as one, because a retry inside a single advance would be a network
operation the approved budget never accounted for.

**References are inert.** A CVE lists where it was discussed, and that list
arrives from the network in exactly the shape of a request to go somewhere.
Discovery never fetches one, never follows a redirect to one, and grants a later
fetch no authority it would not otherwise have had. A reference reading
`http://169.254.169.254/` is stored, displayed, and left alone.

**Severity is not relevance, and known exploitation is not either.** Every CVSS
metric is kept with its own version and its own scorer rather than collapsed
into a maximum called "the CVSS", because those numbers disagree by design.
Entries that carry no score — the live response includes `ssvcV203` — are
skipped rather than defaulted. Nothing about a score, a CISA listing, or the
provider's institutional standing moves a relevance rank, a source reputation,
an operator assessment, or a claim's confidence.

**Provider data is not operator judgement.** NVD's `vulnStatus` says what NIST
concluded about its own record; the operator's publication status says what a
person concluded after reading the source. They are deliberately not mapped onto
each other, and a rejected CVE stays visible and stays labelled rather than
being dropped.

The research run store moved to schema 12 to persist the structured record.
Bounded fields only — never the provider's raw document — and a candidate
written before version 12 decodes with no vulnerability record, which is what it
has.

**Still not current:** automatic multi-provider research; a CISA KEV provider; a
GitHub Security Advisories provider; vendor advisory providers; semantic or
learned reranking; learned provider selection; automatic source acceptance;
autonomous discovery; background research; scheduler authority; recursive
follow-up. The same seven autonomy and background intents remain unreachable.

Two providers are not comprehensive vulnerability intelligence, and this
document does not claim otherwise.

### 17.8 Done: provider experience can be described, and still not obeyed

Implemented in v0.3.198 as a derived report with no store and no write path.

**The join was the whole problem.** Both halves were already recorded — a
discovery names the provider that produced it, an assessment names what a person
concluded after reading a source — and nothing connected them, because no
accepted source carries a foreign key back to the discovery that proposed it.
The bridge is canonical resource identity, `identity_of(candidate.url)` against
`identity_of(source.url)`: not a domain guess and not invented here, but the same
function the panel already uses to decide whether a discovered candidate was
accepted. From the accepted source onward the join is by exact document
identifier.

**What cannot be attributed is counted apart rather than guessed.** A resource
both providers returned has no single provider to credit and is excluded from
every profile; an assessed source no discovery proposed was added by hand and is
excluded too. Both counts are reported.

**The funnel is reported, never divided across.** Discovery operations,
candidates discovered, accepted sources, sources with evidence, and assessed
sources are five different populations. A usefulness rate is taken over assessed
sources and says so; assessment coverage is reported as `assessed / evidence
bearing` beside it, so a high percentage over two sources cannot be mistaken for
a finding.

**Silence never becomes a negative vote.** An unassessed source is missing data,
not a bad source. `unknown` on a dimension means the question was not answered:
it is counted and shown, and excluded from the rate. Zero assessed samples
renders as `No assessed provider samples yet`, never as 0%.

**There is no provider score, and no winner.** No field names a better provider,
a preferred provider, or a recommendation, and a test asserts that no such name
exists in the report's code. Every ratio carries its numerator and denominator,
and every profile carries a sample band — `no_data`, `very_small`, `limited`,
`descriptive` — whose largest value is still called descriptive.

**Query category is decided from the question, never from the provider.** A
question naming exactly one well-formed CVE is an exact lookup; everything else
is a keyword search, judged by the same strict parser the NVD provider uses. A
`security keyword` category was considered and rejected: nothing here can tell
one deterministically, and the invented list would end up deciding the
statistics. The split earns its place because the providers differ sharply
across it, and averaging them would hide the only thing the data shows.

**These figures are observational and selection-biased, and say so in their own
text.** The operator chose which provider to ask, which candidate to open, which
source to accept, and which of those to appraise. This is descriptive evidence
from actual use. It does not establish causal provider quality and does not
claim to.

**Nothing reads it to decide anything.** The report changes no provider default,
no plan draft, no ranking, no ranking weight, no reputation, no assessment, no
claim and no confidence; it opens no socket, calls no model, advances no
execution and spends no budget. A test enumerates every file that so much as
mentions the report type, and the list is five: the response that carries it, the
events that count it, the evaluator that builds it, the module that defines it,
and the composer that renders it.

**Still not current:** automatic or learned provider selection; provider routing
policy; provider reputation learning; ranking weight adaptation; semantic
reranking; unbiased benchmarking; autonomous multi-provider research; background
research; scheduler authority. The same seven autonomy and background intents
remain unreachable.

### 17.9 Done: the operator can put one question to both providers

Implemented in v0.3.199, and the notable result is how little it required.

**A comparison turned out to be two ordinary discovery steps in one plan.** The
question already belongs to the research run rather than to a step, so two
discovery steps in one run ask the same question by construction — there is no
arrangement in which one side quietly searches for something else, and nothing
had to enforce it. The provider has been bound into the plan digest since
v0.3.197. A discovery step has always cost one network operation. One advance has
always attempted exactly one step. So no comparison execution engine exists,
because none was needed, and a test asserts that no such module was created.

**Two steps, two approvals under one digest, two charges, two presses.** The
digest covers both provider steps: swapping the providers, changing the
question, dropping a side, or replacing one provider all change it, so an
approval for Crossref-then-NVD cannot be spent on anything else. The pair costs
two network operations because each step costs one, and nothing in the
comparison path can widen a budget. Advancing runs one provider; the second
needs another press.

**The Compare button reaches a preview and nothing else.** It drafts the
two-step plan and hands it to the ordinary preview, which names both providers
and the shared question in words. Approval and two advances still stand between
pressing it and any request, and a test reads the handler's actual calls rather
than its prose to prove it.

**Side by side, never merged.** Each provider's candidates are ranked by the
common ranker within that provider only. There is no rank across providers,
because a number one spanning both would be a verdict about providers wearing a
sort order. Provider rank travels alongside relevance rank on every row, and
provider-specific metadata stays on the side that has it: a vulnerability record
appears under NVD and no empty CVE column appears beside a scholarly paper.

**Partial is reported as partial.** One side complete and the other pending is
the ordinary state between two advances, and a pending side says so rather than
rendering an empty result — being asked and answering nothing is a finding,
while not being asked is not. Re-asking a provider replaces its side rather than
adding a column; the older discovery stays in the run and stays auditable.

**One limitation is stated rather than left to be found.** A failed discovery is
recorded against the run without naming which provider failed, so a side that
was attempted and errored is indistinguishable here from one nobody advanced.
Both read as pending, the run's failed-discovery count is reported separately,
and no failure is attributed to a side. Overloading an existing audit field to
make one test pass would have satisfied the test rather than the record.

**Nothing decides.** No winner field, no preferred or recommended provider, no
provider score; the report says in its own text that neither provider was judged
better and that no default changed. Viewing a comparison contacts nobody, calls
no model, spends nothing, writes nothing, and creates no assessment — the
service holds no provider and has no write path. Only the operator's own action
builds a comparison request: a test enumerates every file that mentions the type
and finds exactly two.

This is an operator-driven paired comparison. It is not a controlled benchmark,
and the sources on either side are still ones a person chose to accept and
appraise.

**Still not current:** automatic provider selection; automatic dual-provider
discovery; learned provider routing; provider winner scoring; global
cross-provider relevance ranking; semantic reranking; a CISA provider; a GitHub
Advisory provider; background autonomy; scheduler authority. The same seven
autonomy and background intents remain unreachable.

### 17.10 Done: measure the paired comparisons the operator actually ran

**Exactly one: paired-comparison evaluation from recorded operator assessments.**

The provider-quality report describes each provider over whatever questions it
happened to be asked, and that was its stated limit. Pairing now removes the
cause: when both providers answer one question, the two samples finally line up,
and the operator's own appraisals of the sources on each side are directly
comparable in a way they have never been.

Nothing reads them that way yet. The quality report sees the new discoveries
because they are ordinary records, which is right, but it still aggregates them
into per-provider profiles across unrelated questions — so the one genuinely
comparable slice of the data is averaged away with everything else.

Implemented in v0.3.200. It stays descriptive and stays read-only: the report
shows, per paired question, what the operator concluded about each side, with
both denominators and the sample band visible, and without ever producing a
winner.

**Alignment is proved from canonical text, not inferred from provider presence.**
A run qualifies only when Crossref and NVD each hold a discovery whose exact
recorded query equals the run's canonical question. Two provider names beside
different queries are not presented as a pair.

**The old attribution rules remain intact inside each pair.** A resource both
providers returned is excluded from both funnels rather than credited by
execution order, and an assessed source no discovery proposed is reported as
unattributed. Superseded assessments remain history rather than extra samples.

**The view is bounded without hiding the denominator.** At most 40 paired
questions are rendered, in deterministic run order, while the report carries
the complete number of eligible pairs. Telemetry carries only eligible-pair,
reported-pair, and assessed-sample counts; it carries no question, provider
result, document identity, or judgement content.

**Question alignment is not a benchmark.** The operator still chose which
candidates to accept, which accepted sources became evidence, and which sources
to assess. The report says so next to the numbers. Nothing reads the result to
select a provider, draft a plan, change a default, alter a ranking, or update a
reputation.

**Explicitly not in it:** provider selection or routing; reranking; reputation
learning; new providers; background scheduling; `research_autonomy_run`;
filesystem, shell, or tool authority.

---

## 18. Threat model

| # | Threat | Boundary | Preventive control | Detection | Residual risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Prompt injection in fetched source | Source → reasoning | `instruction_authority = none` enforced at construction; capability routing is a typed table lookup, never prose parsing | Source identity recorded with every evidence record | A person reading a summary may still be persuaded by quoted text |
| 2 | Malicious plan text | Plan → execution | Step routing uses declared capability only; instruction text is never parsed for authority | Declared capability visible in the approval | A human may approve a plan they misread |
| 3 | Model attempts privilege expansion | Model → authorization | Model output is not authorization (inv. 3); capabilities derived from snapshot, not from a response | Budget and capability set recorded per authorization | None material while `max_llm_operations` defaults to 0 |
| 4 | Source asks for tool use | Source → Tool Layer | No import path exists; asserted by isolation test | Test failure on any new import | None while the test holds |
| 5 | Source asks for memory persistence | Source → memory | Evidence is not memory (inv. 13); no autonomous memory write | Memory writes remain explicit and separately surfaced | None |
| 6 | Source asks for secrets or local files | Source → filesystem | No filesystem capability in the research enum; no cost entry | Capability enum is closed and tested | None |
| 7 | Model invents evidence | Model → canonical state | Only a real operation reporting performed work may complete a step | `work_performed` never inferred at load | None structural |
| 8 | Model invents completed actions | Model → status | Canonical status is derived from execution, not prose (inv. 8, 20) | Status/prose divergence visible in the record | Prose may still read misleadingly to a human |
| 9 | Infinite planning loop | Planner | Plans are authored and finite; drafting performs no work | Step count bounded per plan | None |
| 10 | Infinite curiosity loop | Curiosity → execution | Acceptance is inert; no auto-draft; no recursive follow-up (§10) | Ruling recorded without side effect | None while §10 holds |
| 11 | Recursive follow-up research | Run → run | One authorization, one execution; consumption is terminal (§5.4) | Authorization state per task | Requires §17 to be enforceable |
| 12 | Retry storm | Scheduler | `max_retries` default 1, ceiling 5; retries share the original budget | Attempt count on the task | None |
| 13 | Network request storm | Autonomy | `max_network_operations` default 3, ceiling 25, charged from the cost table | Per-run operation counts | None |
| 14 | Token / model-cost exhaustion | Autonomy | `max_llm_operations` default 0, ceiling 25 | Per-run counts | None at default |
| 15 | Storage exhaustion | Persistence | Per-source 1 MB cap; bounded stores for lessons, questions, reports, tasks | Store sizes bounded and refused past cap | Many small runs still accumulate |
| 16 | Duplicate-source pseudo-corroboration | Evidence | Duplicate ≠ corroboration, enforced and tested | Source identity dedup | Syndicated text from distinct hosts may still look independent |
| 17 | Stale authorization | Time | `expires_at`, proposed 1 hour | Expiry checked at use, not at creation | Requires §17 |
| 18 | Plan changed after authorization | Content | `plan_digest` mismatch is a refusal, not a warning | Digest recomputed at use | Requires §17 |
| 19 | Restart during execution | Process | Tasks → `INTERRUPTED`; restored executions readable, not advanceable; re-authorization required | Status distinguishes interrupted from failed | A network request already issued may have taken effect unobserved |
| 20 | Cancellation race | Concurrency | Cooperative checkpoints; publication is the atomic boundary | Cancelled status is terminal and distinct | A model or network call already in flight still completes and is discarded |
| 21 | Partial persistence | Storage | Atomic replace; acceptance completes or leaves nothing | Failed writes reported, never swallowed | None known after v0.3.189 |
| 22 | Source changes between fetch and use | Time | Evidence names the accepted source document it came from | Fetch time recorded | The live page may no longer say what the evidence says |
| 23 | Remote model receives undisclosed data | Disclosure | `disclosure` defaults to `none`; `remote_permitted` is a separate decision (§8) | Disclosure recorded on the authorization | Requires §17; today mitigated by 0 model calls |
| 24 | Telemetry leaks secrets | Observability | Bounded counts and identifiers only; codec already excludes bodies and payloads | Event payload shapes are asserted in tests | A source identifier still reveals interest in a topic |
| 25 | Task outlives its authorization | Time | Consumption plus expiry plus restart invalidation (§5.4) | Authorization state inspectable per task | Requires §17 |
| 26 | Console capability inherited by background work | Tool Layer | No import path; invocation-scoped grants are not transferable | Isolation test | None while §7 holds |

---

## 19. Test plan

To be written when the code they describe exists. Listed so the milestone in
§17 cannot quietly ship without them.

**Authorization** — a digest changes when the question, a step's text, a step's
capability, or step order changes; an unchanged plan digests identically across
processes; an expired authorization is refused; a consumed one is refused; a
modified plan is refused rather than re-approved; capabilities never exceed
those the snapshot declares.

**Inertness** — accepting a curiosity question performs zero network, model,
and tool operations; plan preview performs zero execution; drafting a plan
writes nothing.

**Refusal semantics** — unauthorized execution is not-reached rather than
failed; authorization denial is not retried; budget exhaustion does not extend
a budget.

**Model containment** — a model response saying a tool executed changes no
execution state; a response saying evidence was confirmed creates no evidence;
prompt injection in a fetched source changes neither plan nor capability set.

**Budgets and limits** — each bound in §6 stops work at its stated value; a
retry consumes the original budget rather than resetting it; the retry ceiling
is enforced; exceeding a bound stops the run rather than extending it; two
sources carrying the same content do not count as independent corroboration
without an explicit human assessment.

**Provenance** — every stage in §9 preserves the source document a record came
from; a derived summary names its parents; an external source cannot be
constructed without its taint label and instruction authority.

**Boundaries** — filesystem content is unreachable without separate
authorization; no shell or process capability exists; remote model disclosure
is separately gated; a completed run cannot start another; curiosity cannot
form an execution loop.

**Truthfulness** — cancellation before publication leaves no evidence;
reflection cannot invent execution history; calibration cannot mutate a claim
by reporting it; a failed persistence write is reported as failed; restart
behaviour is deterministic and conservative; telemetry carries no raw sensitive
material.

---

## 20. Decision register

**DECIDED** — reuse existing state vocabularies; authorization is an immutable
content-addressed snapshot; capabilities derived from the snapshot and frozen;
authorization is single-use, expiring, and non-inheritable; restart requires
re-authorization; no Tool Layer seam; no filesystem or shell capability;
initial background capability set is network research only; disclosure defaults
to `none`; retries are classification-aware and share the original budget;
calibration reports without mutating; failure memory records structure only;
telemetry is bounded; autonomy levels are separately gated; every budget in §6
is reused rather than raised; budgets compose by intersection; provenance
survives every stage in §9 and no model transformation may erase it; the four
proposed task-identity fields in §13 arrive together or not at all; the next
milestone is plan identity and authorization *without* reachability.

**DEFERRED** — the queue surface (level 2); policy-boundary authorization
(level 3); scheduling and recurrence (level 4); a claim-revision workflow;
allowed-host scoping beyond the existing HTTPS and content-type rules;
per-operator authorization identity beyond "a human approved"; a separate cap on
fetched sources per run, which `max_network_operations` already bounds.

**OPEN — evidence required**

| Question | Evidence needed |
| --- | --- |
| Is a 1-hour expiry right? | Observed duration of real approved runs. Chosen to match `MAX_AUTONOMY_SECONDS`; that is reasoning, not measurement. |
| Do current per-source and per-run caps bound aggregate storage adequately across many runs? | Store growth measured over a realistic run history. Per-item caps are verified; aggregate is not. |
| Should `max_llm_operations` ever exceed 0 for background work? | A disclosure model proven in a foreground milestone first. |
| Can syndicated duplicate content be detected across distinct hosts? | Measurement on real sources. Identity dedup catches same-document reuse, not republication. |
| Is `BLOCKED` sufficient, or does research execution need an explicit declined/failed split like the Tool Layer? | Observed block reasons from real executions. |
| Should aggregate downloaded bytes have their own bound? | Growth measured across many authorized runs (§6.1). |
| Should stored evidence records be bounded per run rather than only per store? | Whether one run can approach 64 MB or 20,000 items in practice (§6.1). |
| Is there an input-token budget, not only the 512-token output cap? | A foreground milestone that actually spends model calls (§6.1). |
| Are the inherited urllib redirect defaults the intended contract? | A decision, then an explicit declaration replacing the inheritance (§6.1). |
| Can a multi-source summary name all its parents within existing provenance bounds? | One real multi-source summary, measured (§9). |

---

## 21. What stays unreachable

All eleven autonomy intents remain unreachable from the desktop after this
document, and the milestone in §17 keeps them unreachable.

That is the point. An unreachable dangerous capability is safer than a
prematurely reachable one, and the reachability count is not a score to
improve. The eleven become reachable when the authorization object exists,
holds, and has been reviewed — not before, and not to make a number smaller.
