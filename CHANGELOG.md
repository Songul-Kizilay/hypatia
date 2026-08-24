# Changelog

All notable project changes are recorded here.

## [0.3.166] - 2026-08-24

### Added

- `ToolEffect.COMPUTES_LOCALLY`, so a tool that only transforms data it was
  handed can declare that truthfully instead of borrowing an effect it does not
  have.

### Changed

- `ToolInvocation` and `ToolResult` now check that argument and value pairs are
  actually strings. A length bound alone admitted an empty list or dict, because
  both have a length.

### Safety

- The blank-declaration guard in `ToolDescriptor` is kept, not relaxed. An empty
  effect set is a subset of every grant, so making it legal would turn the
  declaration nobody filled in into the only one no authorisation could refuse.
- Declaring purity explicitly keeps "authorise nothing" and "authorise pure
  computation" different sentences. A pure tool is refused under an empty grant.
- `COMPUTES_LOCALLY` is neither irreversible nor observable outside the machine,
  so a tool declaring only it is read-only and reaches nothing.
- Granting computation grants nothing else: a clock tool declaring
  `READS_LOCAL_STATE` is refused under a computation-only grant.
- Rejecting a non-string argument is a construction-time refusal, so a
  mistyped value never reaches a tool and is never coerced into text.

### Verification

- The package-aware full local suite contains 2,664 passing automated tests.
- Fourteen new tests cover the retained empty-set refusal, the new effect's
  authorization behaviour in both directions, the closed empty-container hole,
  non-string names and values on both the argument and result side, and the
  still-valid empty string.

## [0.3.165] - 2026-08-24

### Added

- `ClockReadTool`, the one concrete tool of this milestone. It reports the
  current UTC time as four structured values through the full tool path.

### Removed

- `ToolFailureKind.INVALID_ARGUMENTS`, which had no producer. Malformed
  arguments are refused when the invocation is constructed, and unsupported ones
  are a tool discovering by looking, which is a failure rather than a refusal.

### Safety

- The tool declares exactly what it does: it reads local state and nothing else.
  Tests assert each absent effect individually — no write, no network, no model.
- It touches no network, no filesystem, no process, and no model, and mutates
  nothing.
- The clock is injected, so no test depends on the second it ran in. A naive
  datetime from the clock source is refused rather than guessed at, and a
  non-UTC one is normalised.
- It accepts no arguments. An unsupported argument yields a
  performed-but-unsuccessful result, because the tool was reached and declined.
- The clock tool is not exempt from the gate. A test invokes it with an empty
  grant and asserts it is refused before starting, since a trusted-tool shortcut
  for something harmless is the shortcut a later tool would inherit.
- Only `clock_read` is registered. No filesystem, terminal, process, browser,
  network, or generic execution capability exists, and nothing is wired into
  ordinary chat.

### Verification

- The package-aware full local suite contains 2,650 passing automated tests.
- Eighteen new tests cover the descriptor and its truthful effects, injected and
  normalised clocks, refused ambiguous times, argument rejection, and the
  end-to-end path including lifecycle order, the gate applying to the clock
  tool, cancellation, unknown capabilities, and telemetry carrying no time
  value.
- An application-level run confirms the path: granted, it emits requested,
  authorized, started, completed and returns the injected time; ungranted, it
  emits requested and failed with `unauthorized_effect` and never reaches the
  tool.

## [0.3.164] - 2026-08-24

### Added

- `ToolEvents` publishes six lifecycle events on the existing event bus:
  `tool.requested`, `tool.authorized`, `tool.started`, `tool.completed`,
  `tool.failed`, and `tool.cancelled`. No second event system was created.

### Safety

- The events are required to be true. `authorized` is emitted only after the
  gate allowed the call and `started` only when the implementation is about to
  run, so a refused invocation produces neither — tests assert the absence of
  both, since those are the two events that would make a refusal read as a run.
- A cancelled invocation reports cancellation rather than failure, and a tool
  that ran and failed reports failure after starting with `performed` true.
- Payloads are bounded now, while the only tool reads a clock. Arguments and
  returned values are counted, never carried. Tests plant a secret in an
  argument, a returned value, and a raised error, and assert none of the three
  appears in any payload.
- What is carried: a request id correlating one invocation, the capability, the
  declared and authorized effects, `performed`, `succeeded`, and a bounded
  failure kind.

### Verification

- The package-aware full local suite contains 2,632 passing automated tests.
- Nineteen new tests cover the exact event order for success, unknown
  capability, unauthorized effects, cancellation, a raising tool and a failing
  tool, once-only emission, request correlation, a service without a bus, and
  the bounded-payload rules.

## [0.3.163] - 2026-08-24

### Added

- `ToolRegistry` binds each invocable capability to exactly one tool, reading
  the capability from the tool's own descriptor.
- `ToolExecutionService`, the single seam every invocation passes through:
  resolve, authorize, invoke, report.
- `ToolFailureKind` and `ToolExecutionOutcome`, which keep refusals and failures
  apart and carry resolution and authorization alongside the result.
- The existing Tool Layer abstractions — `ToolCapability`, `ToolEffect`,
  `ToolDescriptor`, `ToolInvocation`, `ToolResult`, and the `Tool` protocol —
  are adopted unchanged as the foundation.

### Safety

- Authorization is central and fail-closed. A tool never checks its own grant;
  the service compares declared effects against the invocation's authorized
  effects before the implementation is reached.
- There is no bypass, no trusted-tool shortcut, and no ambient permission. A
  grant applies to one invocation and does not carry into the next.
- The registry has no fallback. An unregistered capability resolves to `None`,
  never to a similar tool, and the registry cannot invoke anything itself.
- A refused invocation never reaches the implementation, proven by a tool that
  counts its calls rather than by inspecting the returned result.
- Failure kinds are bounded and a raised error becomes `TOOL_FAILED` with a
  fixed sentence, so no exception text reaches a consumer.
- The outcome refuses to disagree with itself: no performed work without
  authorization, no performed work after a pre-execution refusal, and no
  failure kind on a successful result.
- No concrete tool is registered, nothing is wired into ordinary chat, and no
  filesystem, process, network, or model capability exists.

### Verification

- The package-aware full local suite contains 2,613 passing automated tests.
- Twenty-five new tests cover registration, duplicates, `NONE`, unknown
  capabilities, the absence of fallback, determinism, exact and partial
  authorization, empty grants, unreached implementations, cancellation, bounded
  failure kinds, the performed/succeeded distinction, and the absence of bypass
  methods.

## [0.3.162] - 2026-08-24

### Added

- Knowledge reconciliation classifies every indexed resource as attached,
  knowledge-only, or a broken reference, and reports counts for resources,
  documents, and each classification.
- `knowledge_reconciliation_report` and `knowledge_only_list` intents, and one
  bounded `knowledge_reconciliation.reported` event.

### Safety

- Read only. There is no delete, prune, or garbage-collect path, and tests
  assert neither the reconciler nor the service exposes a method whose name
  contains one, and that the run store and index are byte-unchanged after
  repeated reconciliation.
- Knowledge-only is presented as a normal state rather than a cleanup list. The
  user-facing report never calls it an orphan; that word is reserved for a run
  naming a document the index does not hold, which is the only genuine
  structural breakage here.
- Resources are keyed by identity, so the same page stored twice is one resource
  holding two documents rather than two resources.
- A record cannot contradict its classification: an attached resource must name
  its runs, a knowledge-only one must name none, and a broken reference names a
  run but no document.
- Event payloads carry counts plus explicit `documents_removed` and
  `references_repaired` zeroes, and deliberately no identity or title.

### Verification

- The package-aware full local suite contains 2,588 passing automated tests.
- Twenty-eight new tests cover the vocabulary and its consistency rules, empty
  machines, attached and knowledge-only classification, duplicated resources,
  broken references and their exclusion from indexed counts, shared resources
  across runs, read-only behaviour, the absence of removal methods,
  presentation, events, and engine routing with and without research
  persistence.

## [0.3.161] - 2026-08-24

### Fixed

- Displayed research counts did not refresh after a source was accepted. The
  interface now re-reads the affected run when the event bus reports canonical
  acceptance.

### Added

- `ResearchStateRefreshSignal` records which runs changed canonically and never
  records a count. It is thread-safe, because events arrive on the worker thread
  while the interface drains on its own event-loop thread.

### Safety

- The event says which run changed; every number shown is read back from the
  store. A payload can never put a count on screen that the store does not hold.
- Only canonical acceptance marks a run. A local index, a refused attachment,
  and a cancellation change no run, so none of them refresh anything — tests
  assert each case leaves the displayed count unchanged.
- The `attached_to_run` flag is checked as well as the event name, so a payload
  that does not claim acceptance cannot trigger a refresh under an acceptance
  name.
- Draining is destructive and idempotent, so a retry after a failed attachment
  refreshes exactly once and a duplicate load does not double-count.
- No polling was added. The existing Tk event-loop poll drains the signal.

### Changed

- Two tests encoded obsolete proxies rather than guarantees. One built bare
  windows through `object.__new__`; the signal is now declared at class level so
  focused tests stay safe. The other asserted exactly one container resolution;
  it now asserts the Brain and the event bus both come from the same container.

### Verification

- The package-aware full local suite contains 2,560 passing automated tests.
- Sixteen new tests cover signal semantics, self-subscription, and the full
  chain driven through the real ingestion pipeline: zero to one, index-only,
  failed attachment, retry, duplicate load, two acceptances, and a replay
  asserting no event order can show a count the store lacks.

## [0.3.160] - 2026-08-24

### Added

- `SourceIngestionEvents` publishes every real transition of a source load:
  validation, fetch, index, and research-run attachment each start and complete,
  and a stop is announced as cancelled or failed.
- Every event of one load shares an attempt identifier, so a subscriber can
  follow a single ingestion without inferring which events belong to it.

### Safety

- The stage vocabulary is reused, not duplicated. Events carry `SourceLoadStage`
  values, so the stream cannot drift from the transaction it describes.
- An event fires only after the transition it names, except the `*_started`
  events, which claim nothing about outcome.
- The payload is machine-readable only: identifiers, a stage, a status,
  booleans, and a bounded failure kind. No prose, no translation, no exception
  message.
- Indexed locally still does not mean accepted into a run. The two facts are
  separate fields, only `ACCEPTED_INTO_RUN` carries `attached_to_run`, and a
  test asserts no event of an index-only load claims attachment.
- Safe-failure metadata reports what happened: a refused fetch with a bound run
  reports the recorded failure, and the same refusal without a run reports that
  none was recorded.
- Evidence recording is deliberately outside this pipeline. It is a separate
  authored transaction, and announcing it here would invent progress.

### Changed

- One existing test asserted zero events as a proxy for "no side effects". It
  now asserts the guarantee it meant — no conversation, memory, or model work —
  by requiring the absence of `brain.*` events and that every emitted event
  belongs to the ingestion subsystem.

### Verification

- The package-aware full local suite contains 2,544 passing automated tests.
- Twenty-five new tests cover the full successful order, exactly-once emission,
  attempt correlation, index-only distinctness, refused fetch, index failure,
  attach failure, duplicate documents, cancellation, retry, safe-failure
  reporting, payload shape, and a service constructed without a bus.

## [0.3.159] - 2026-08-24

### Added

- `HYPATIA_RESEARCH_USER_AGENT_CONTACT` lets an operator append their own
  contact to the research agent string, for sites that ask non-browser clients
  to name one. Hypatia does not invent a contact on anyone's behalf.

### Safety

- The override cannot impersonate a browser. A value containing a browser marker
  is refused, as are overlong values and anything carrying a line break, so the
  header cannot be used for injection either.
- The default agent string was inspected and left unchanged: it names the
  product and version, carries no browser marker, no tracking, and no machine or
  user identity. A 403 remains a 403; no anti-bot control is bypassed.

### Verification

- The package-aware full local suite contains 2,519 passing automated tests.
- Eight new tests cover the default string, the absence of impersonation and
  identity, contact appending, blank contacts, browser impersonation, overlong
  values, and header injection.
- Live network validation, run against the real internet rather than doubles: a
  direct public HTTPS page travelled the whole ingestion path — validation,
  fetch of 32,585 characters, local index, canonical acceptance, evidence
  record — ending at one accepted source, with assessment and claim correctly
  unperformed. Crossref discovery returned five real candidates including a 2026
  paper.
- Crossref's `link` metadata was checked against the live API rather than
  assumed. It returns plain-HTTP PDF URLs, which the HTTPS and content-type
  boundaries refuse, so exposing it would not make DOI loading work under the
  current safety policy and was deliberately not added.

## [0.3.158] - 2026-08-24

### Fixed

- The same resource stored under two document IDs read as two independent
  sources to everything that counted support, so a claim resting on one page
  could satisfy the corroboration ceiling and a hypothesis could look supported
  by sources it did not have. Support is now counted over resource identities.

### Added

- `SourceIdentity`, a conservative canonical identity for a source URL:
  lowercased scheme and host, dropped default port, dropped `www.` prefix, one
  dropped trailing slash. The query string is kept, path case is kept, and
  titles are never compared.

### Safety

- Storage stays history-preserving. No record is merged, rewritten, or deleted;
  only counting changed. A test asserts both records and both evidence entries
  survive.
- Normalisation is conservative because the errors are asymmetric: a missed
  merge overcounts support, which the audit flags, while a wrong merge silently
  discards a genuinely independent source, which nothing would flag.
- Claim calibration, hypothesis appraisal, and thin-claim detection count
  resources. Two different pages on one host still corroborate; the same page
  twice does not.
- Source reputation counts a resource once toward its standing, so a duplicate
  cannot reach a standing on its own. Accepted-record counts stay as stored.
- The audit's duplicate finding stays and now matches on identity rather than
  exact URL. It is redundant with the protection above, which is why it is worth
  keeping: a check that is redundant today is the one that notices a regression.

### Verification

- The package-aware full local suite contains 2,511 passing automated tests.
- Twenty-one new tests cover identity equivalence and non-equivalence
  table-driven, calibration and hypothesis corroboration for duplicated versus
  distinct pages, thin-claim detection, reputation sample counting and standing
  thresholds, audit detection of equivalent forms, and the preservation of every
  stored record.

## [0.3.157] - 2026-08-24

### Fixed

- An evidence reply printed "Sources accepted: 0" and then said "Sources exist
  but no evidence record does". The branch tested whether anything at all had
  been recorded, so a run with no sources fell past the empty case. The prose is
  now chosen from the same two counters the reply prints.
- Deterministic honesty responses were composed in English regardless of the
  question, so a Turkish request received a wall of English that read like a
  developer diagnostic. The sentences are now looked up per language, with the
  plain statement first and the counters under a details heading.
- Asked whether it could reach a URL, ordinary chat let the model answer and the
  model claimed the page was not accessible — a claim about someone else's server
  made without contacting it. Such a message is now recognised and answered
  deterministically.

### Added

- `ResponseLanguage` and `detect_response_language`, a bounded hint table with
  English as the fallback.
- `HonestyPhrasebook`, the fixed honesty sentences per language, with a missing
  key falling back to English rather than being approximated.
- `LiveInformationRequestKind.URL_ACCESS`, matched only when a message contains
  a URL *and* asks about reaching it.

### Safety

- The honesty statements remain composed in code and are never phrased by a
  model. Only their translation is looked up.
- The URL reply says three separate things: the link was not opened in this
  turn, whether the site is reachable is unknown because nothing tried, and the
  Research workflow is how to check. A test asserts no phrase in any language
  contains inaccessible, unavailable, offline, blocked, or their Turkish
  equivalents.
- Both signals are required before a turn is treated as a URL request. A pasted
  link used as context is not hijacked, and tests cover both directions.
- Ordinary chat still reaches no network; the new kind changes what is said, not
  what is done.
- Language hints are restricted to tokens absent from the other language, after
  an early version turned English questions containing "site" or "var" into
  Turkish answers.

### Verification

- The package-aware full local suite contains 2,490 passing automated tests.
- Twenty-eight new tests cover language detection including the shared-word
  regression, phrasebook completeness and fallback, the five evidence-state
  combinations table-driven, URL access detection in both languages, the
  refusal to judge reachability, and statement-before-counters ordering.

## [0.3.156] - 2026-08-24

### Fixed

- A source load with no research run bound indexed the document into local
  knowledge and reported "Research source loaded" with a real document ID, while
  the run's canonical state correctly showed zero accepted sources and zero safe
  failures. Nothing had failed; one word was covering two different outcomes.
  Every load now reports the stage it reached, and an indexed-only load says
  plainly that no research run accepted it.

### Added

- `SourceLoadStage` names how far a load got: fetch refused, index failed,
  content persist failed, run attach failed, indexed without run, accepted into
  run, cancelled. It distinguishes a stage that created a local document, one
  that rolled its work back, and the single stage that means the run accepted
  the source.
- `ResearchSourceAcceptanceResult.stage` and `attached_to_run`, which is the
  question callers asking "was it accepted?" actually mean.
- `BrainResponse.source_load_stage`, so a caller can branch on the stage rather
  than parse prose.

### Safety

- The acceptance result refuses a stage that disagrees with it: reporting
  acceptance into a run without a run, carrying a run without the accepted
  stage, or naming an indexed document that does not exist.
- The reply leads with the stage rather than the presence of a document. An
  indexed-only load is headed "Indexed locally, but NOT accepted into a research
  run", labels the identifier as a local document ID, and states that no
  evidence can be recorded from it.
- Partial transaction points are covered end to end: index succeeds and
  attachment fails leaves the run byte-honest and rolls the local document back;
  content persistence failure names its own stage; a retry after a failed
  attachment still succeeds exactly once.
- A test asserts no evidence can be recorded against a run from a document that
  was only indexed.
- The desktop guard that selects an accepted source only when the returned run
  confirms it now has a regression test.

### Verification

- The package-aware full local suite contains 2,462 passing automated tests.
- Thirty new tests cover the stage vocabulary, result consistency, every partial
  transaction point, reporting for each successful and failed stage, and the
  desktop capture guard.

## [0.3.155] - 2026-08-23

### Added

- Security agent. `SecurityPostureAuditor` checks Hypatia's own persisted
  research state against eight bounded properties and reports findings with a
  bounded `SecurityFindingSeverity`.
- `SecurityFinding`, `SecurityPostureReport`,
  `SecurityAgentApplicationService` with an audit intent, and one bounded
  `security_agent.posture_audited` event.

### Safety

- The agent audits this system and has no vocabulary to audit another. There is
  no scan intent, no probe intent, no target parameter, and no field for an
  external system. Tests assert those method names are absent and that the audit
  opens no socket, by making every socket call raise.
- The address check is literal rather than resolved, so the audit never becomes
  a network client. The resolution that mattered happened at the fetch boundary,
  where it was pinned.
- Checks cover what the domain types do not already guarantee. Referential
  integrity is enforced by `ResearchRun` at construction, so it is not audited
  again; a test asserts the type refuses those states rather than the auditor
  claiming credit for them. The two taint checks are declared as defence in
  depth via `covered_by_a_type`.
- A newly detected class of problem: the same URL accepted twice. Two records
  sharing a URL read as independent corroboration to calibration and to the
  hypothesis appraiser, and no type checked for it.
- Every report states its scope alongside its findings, and a clean report says
  explicitly that specific properties held just now rather than that the system
  is safe.
- Nothing is repaired. Tests assert the run store is byte-identical after
  repeated audits and that no file is created.
- Event payloads carry counts, bounded kinds, and the worst severity, plus
  explicit `external_systems_contacted: 0` and `records_modified: 0`. Tests
  assert no URL or research question appears in any payload.

### Verification

- The package-aware full local suite contains 2,432 passing automated tests.
- Forty new tests cover each check and its severity, loopback and private
  address forms, public addresses not being misreported, duplicate and distinct
  URLs, content types, timestamp ordering, worst-first ordering, empty scope,
  the socket assertion, inertness, bounded events, and production composition
  wiring.

## [0.3.154] - 2026-08-23

### Added

- Vulnerability family graph. `VulnerabilityFamily` records one class of
  weakness with a prevention note, `VulnerabilityRelation` records one authored
  edge with its reasoning, and `VulnerabilityFamilyGraph` answers bounded
  neighbourhood and ancestor queries.
- `JsonFileVulnerabilityGraphStore`, `VulnerabilityGraphApplicationService` with
  record, relate, neighbourhood, and list intents, and three bounded
  `vulnerability_graph.*` events.
- `HYPATIA_VULNERABILITY_GRAPH_ENABLED` opts into keeping the taxonomy, default
  off.

### Safety

- The safety property is structural, not filtered. Neither a family nor a
  relation has a field for a target, host, URL, payload, proof of concept,
  affected version, or CVE, and tests assert those field names are absent from
  both the domain types and the persisted document.
- A family describes a concept and never a system. `describes_a_target` and
  `asserts_exposure` are asserted false for every family and every relation
  kind, and every response repeats that recording or relating one says nothing
  about whether any system, product, or person is affected.
- The neighbourhood response says explicitly that its suggestions are about what
  to read next, not what to attack.
- Edges are authored and require a rationale. An unexplained edge is refused at
  construction and again on load.
- `specializes` is kept acyclic so the taxonomy stays one, and a hand-edited
  file introducing a cycle, a self-relation, or an edge to a family that does
  not exist is refused on load because loading replays the same checks.
- `enables` is directional and only followed forwards; a test asserts it is not
  read backwards into the reverse claim.
- Traversal is bounded in both depth and result count.
- Event payloads carry identifiers, bounded kinds, and counts only. Tests assert
  no family summary, prevention note, or relation rationale appears in any
  payload.

### Verification

- The package-aware full local suite contains 2,392 passing automated tests.
- Fifty-one new tests cover the absent-target schema shape, rationale
  enforcement, self-relations, duplicate families and edges, acyclic
  specialisation, symmetric versus directional traversal, depth and kind
  filtering, ancestor chains, persistence and restart, hand-edited documents,
  bounded events, and production composition wiring.

## [0.3.153] - 2026-08-23

### Added

- Hypothesis engine. `ResearchHypothesis` records one authored conjecture, the
  observation that would count against it, and the evidence entered on each
  side; `ResearchHypothesisAppraiser` derives a bounded `HypothesisStatus`.
- `JsonFileHypothesisStore`, `HypothesisApplicationService` with propose,
  support, oppose, withdraw, and list intents, and three bounded `hypothesis.*`
  events.
- `HYPATIA_HYPOTHESIS_ENABLED` opts into keeping hypotheses, default off.

### Safety

- A hypothesis without a discriminating test is refused at construction and
  again on load. A conjecture that names nothing capable of counting against it
  is a belief, and a stored one that lost its defeater would be
  indistinguishable from a belief.
- There is no confirm intent and no status meaning true. `HypothesisStatus`
  contains no confirmed, proven, true, or false value, `means_true` is asserted
  false for every status, and the service is asserted to expose no confirm
  method.
- Supporting and opposing evidence are never netted. Both counts are reported
  separately, the same evidence cannot be entered on both sides, and all
  evidence must already be recorded in the run.
- The status rules are asymmetric: any opposing evidence moves a hypothesis off
  the supported track, while support requires more than one source. A test
  asserts one opposing source weakens two supporting ones rather than being
  outvoted.
- Status is derived, never stored, so it cannot disagree with the evidence
  beside it. A test asserts no status field is written to the document.
- A hypothesis creates no claim and changes no run.
- Event payloads carry identifiers, bounded statuses, and per-side counts, plus
  an explicit `asserts_truth: false`. Tests assert the statement, its defeater,
  the research question, and URLs appear in no payload.

### Verification

- The package-aware full local suite contains 2,341 passing automated tests.
- Forty-nine new tests cover defeater enforcement, evidence on both sides,
  withdrawal, every status rule and its asymmetry, separate counting,
  persistence and restart including the defeater surviving, unknown hypotheses,
  unrecorded evidence, bounded events, store validation including a stripped
  defeater, and production composition wiring.

## [0.3.152] - 2026-08-23

### Added

- Source reputation. `SourceReputationLedger` aggregates authored assessments by
  origin across every run, and `SourceReputation` reports the counts with a
  bounded `SourceStanding` — unknown, provisional, mixed, consistently low, or
  consistently trusted.
- `SourceOrigin` normalises a URL host minimally: lowercase, no leading `www.`,
  no port, and no public-suffix guessing, so subdomains stay separate.
- `SourceReputationApplicationService` with a report intent for all origins or
  one named origin, and one bounded `source_reputation.reported` event.

### Safety

- Reputation gates nothing. A low standing refuses no fetch, discounts no
  evidence, pre-assesses no new source, and changes no assessment. Tests assert
  a later source from a consistently-low origin is still accepted and still
  arrives unassessed, and `SourceStanding.decides_anything` is asserted false
  for every value rather than merely intended in a comment.
- There is no store and no write path. The ledger is rebuilt from assessments on
  every request, so revising an assessment revises the reputation; a test
  asserts exactly that.
- There is no score. Counts per trust label stay separate so the sample is
  visible, rather than compressed into a number that looks precise and cannot be
  argued with.
- Below three assessments the standing is `provisional`. Two low assessments
  produce provisional, not consistently low.
- Only authored assessments count. Acceptance alone leaves the standing unknown,
  and superseded assessments stop counting.
- Event payloads carry counts and bounded standing categories but deliberately
  never an origin name, since a log line pairing a host with a low standing gets
  quoted later without its sample size.

### Verification

- The package-aware full local suite contains 2,292 passing automated tests.
- Thirty-nine new tests cover origin normalisation, every standing rule and its
  threshold, aggregation across runs, superseded assessments, acceptance without
  judgement, ordering, single-origin lookup, the absence of gating, derivation
  rather than storage, bounded events, and production composition wiring.

## [0.3.151] - 2026-08-23

### Added

- Claim calibration. `ResearchClaimCalibrator` builds an `EvidenceSupportProfile`
  for each active claim — distinct sources, evidence records, how many sources
  carry an assessment, the lowest and highest trust, and whether anything
  contradicts it — and compares the authored state and confidence against the
  ceilings that structure supports.
- `CalibrationVerdict`, `ResearchClaimCalibration`, `ResearchCalibrationReport`,
  `CalibrationApplicationService` with a report intent, and one bounded
  `calibration.reported` event.

### Safety

- Calibration never edits a claim. An epistemic state is the author's judgement
  about what they are willing to assert, and quietly adjusting it would overrule
  that judgement while presenting the change as bookkeeping. Tests assert an
  overstated claim keeps its authored state and confidence, and that the run
  store is byte-identical across repeated calibration.
- There is no calibration store and no write path. The report is derived on
  every request, so it cannot drift from the record it describes.
- The ceilings are stated rules, not a score, and nothing supports `fact`. No
  configuration of sources in our own record makes a claim a fact.
- Overstatement is reported; understatement is not treated as a problem. Being
  more careful than the record requires is never an error, and calibration does
  not nudge anyone toward more confidence.
- A ceiling is explicitly not a verdict on truth, and the response says so:
  meeting it does not make a claim true, exceeding it does not make one false.
- Superseded claims are excluded, and a contradicted claim supports nothing
  until the contradiction is resolved.
- The event payload carries the run identifier, bounded verdict counts, and a
  `claims_modified` count that is always zero. Tests assert no claim text,
  research question, or URL appears in it.

### Verification

- The package-aware full local suite contains 2,253 passing automated tests.
- Thirty-one new tests cover every ceiling rule, contradiction, understatement,
  superseded claims, empty runs, profile validation, verdict properties,
  inertness over claims and the run store, derivation rather than storage,
  bounded events, and production composition wiring.

## [0.3.150] - 2026-08-23

### Added

- Failure memory. `ResearchFailureLessonDeriver` reads a persisted run and
  derives seven bounded lesson kinds — disproving evidence, failed hypothesis,
  invalid assumption, false positive, confidence change, ineffective strategy,
  and operation failure — each naming the records it came from.
- `ResearchFailureLesson`, `JsonFileFailureLessonStore`, `FailureMemoryAdvisor`,
  `FailureMemoryApplicationService` with preview, store, list, and recall
  intents, and three bounded `failure_memory.*` events.
- `HYPATIA_FAILURE_MEMORY_ENABLED` opts into remembering lessons, default off.

### Safety

- A lesson without provenance is refused at construction and again on load, so
  no opinion can outlive the reasoning behind it. Repeated and empty provenance
  entries are refused too.
- The templates never overstate. A superseded hypothesis is recorded as
  abandoned rather than disproved, a contradiction leaves open which claim
  survives, and a barren search is a result about that query rather than a
  verdict on the provider.
- Recall is advisory and enforces nothing. It blocks no plan, refuses no
  capability, downgrades no claim, and edits no run, and the response says so
  explicitly. Tests assert research state is byte-identical after recall.
- Matching is deterministic word overlap weighted by lesson kind, not a model
  deciding which past failures apply to present work.
- Deriving, storing, listing, and recalling all leave every run byte-identical.
  Lesson identities are stable, so re-deriving remembers nothing new.
- Event payloads carry identifiers, bounded kind counts, and provenance counts
  only — never a lesson statement, research question, claim text, or URL. The
  provenance is counted, never listed.
- Persistence follows the proven atomic pattern, with unknown schema versions,
  unknown kinds, duplicate IDs, stripped provenance, and oversized documents
  refused, and a failed write leaving the previous document byte-identical.

### Verification

- The package-aware full local suite contains 2,222 passing automated tests.
- Fifty-nine new tests cover provenance enforcement, each lesson kind, the cases
  that correctly produce no lesson, weight ordering, identity stability, bounded
  counts, advisory recall and its bounds, chat-free inertness over research
  state, bounded events, store validation including stripped provenance, and
  production composition wiring.

## [0.3.149] - 2026-08-23

### Added

- Bounded reflection. `ResearchReflectionGenerator` reads a persisted run and
  reports eight bounded finding kinds — failed, contradiction, revised belief,
  weak evidence, uncertain, unused effort, worked, and next question — ordered
  with problems before successes.
- `ResearchReflectionReport`, `ResearchReflectionFinding`,
  `JsonFileReflectionReportStore`, `ReflectionApplicationService` with preview,
  store, and list intents, and two bounded `reflection.*` events.
- `HYPATIA_REFLECTION_ENABLED` opts into durable reflection history, default
  off.

### Safety

- Every finding describes the process, never the subject. Reflection reports
  that a claim rests on one source; it has no way to report that a claim is
  true. Tests assert an uncertain claim is still uncertain afterwards and that
  the run store is byte-identical across repeated reflection.
- There is no recursive reflection. The generator accepts a research run and
  nothing else; passing a report raises, and reflecting on a stored report ID is
  refused as an unknown run. Both are asserted.
- Generation is deterministic and template-driven rather than model authored, so
  a reflection cannot narrate work it did not inspect.
- Reflection reuses curiosity for the questions it proposes and the gap detector
  for thin-record findings, rather than adding a second engine. It reports those
  questions without storing them.
- Successes and proposed questions are excluded from lessons, so a run with
  nothing to learn from reports nothing to learn from, and an empty run reports
  no success at all.
- Event payloads carry identifiers, bounded kind counts, and canonical counts
  only. Tests assert no claim text, finding detail, research question, or URL
  appears in any payload.
- Persistence follows the proven atomic pattern, with unknown schema versions,
  unknown finding kinds, duplicate report IDs, and oversized documents refused,
  and a failed write leaving the previous document byte-identical.

### Verification

- The package-aware full local suite contains 2,163 passing automated tests.
- Forty-six new tests cover each finding kind, report ordering, bounded counts,
  reflection inertness, the recursion guard, preview without storing,
  persistence and restart, repeated reflection, listing, disabled persistence,
  failed writes, bounded events, store validation, and production composition
  wiring.

## [0.3.148] - 2026-08-23

### Fixed

- The desktop transcript displayed raw Markdown markers, so a reply containing
  a bolded word showed the asterisks around it. Bold, italic, and inline code
  are now drawn with Tk text tags and the markers are removed.

### Added

- `MarkdownTextSegments` splits a reply into styled segments. It imports no Tk,
  makes no rendering decision beyond which span carries which style, and is
  fully testable without a display.

### Safety

- Presentation cannot change content. Stripping the marker characters from the
  input and from the rendered text yields the same string, asserted over every
  sample, so no character of a reply can be lost to styling.
- The parser is conservative by design: it never spans a line break, and an
  unclosed marker, an empty span, or an underscore inside an identifier is left
  literal rather than guessed at. Showing a stray asterisk is preferable to
  swallowing text.
- Styling degrades rather than fails. If the platform cannot derive a bold or
  italic font the tags are simply not configured and the transcript reads
  exactly as it did before. No browser or webview dependency was added.

### Verification

- The package-aware full local suite contains 2,117 passing automated tests.
- Thirteen new tests cover content preservation across every sample, bold,
  italic with either marker, inline code left unparsed, bold winning over
  italic, unclosed and empty spans, identifiers keeping their underscores, spans
  never crossing a line break, and empty or invalid input.

## [0.3.147] - 2026-08-23

### Added

- `tools/diagnostics/research_pipeline_check.py` walks the real research
  pipeline and reports each stage separately: network request, candidate
  discovery, discovery record, explicit selection, HTTPS fetch, acceptance, and
  evidence. Nothing is promoted automatically and each stage runs only when
  named by flag. Assessments and claims are never produced by the diagnostic.
- `tools/diagnostics/durable_memory_check.py` gained a third stage that asks in
  a session created empty. The same-session result is now labelled weak, because
  that session's transcript already contains the taught fact; only the
  empty-transcript result is evidence of durable learned memory.

### Verification

- Live validation now covers the research pipeline end to end, not only
  deterministic doubles. A real Crossref discovery request returned five
  candidates; a real HTTPS fetch, acceptance, and evidence record completed; and
  assessment and claim correctly remained unperformed.
- Two real-world boundary observations from that run, both correct behaviour: a
  Crossref DOI candidate was refused at the HTTPS boundary because the publisher
  redirect was plain HTTP, and Wikipedia refused Hypatia's user agent with HTTP
  403. Both fail honestly rather than retrying or degrading.
- Seven new tests separate same-session recall from durable learned-memory
  recall, asserting that a fresh session carries an empty transcript and that
  the fact still reaches the model through injected learned-memory context. A
  negative control asserts that without a learned record no channel carries it.
- The package-aware full local suite contains 2,104 passing automated tests.

## [0.3.146] - 2026-08-23

### Fixed

- Ordinary chat could answer a request for live web information as though
  research had happened, inventing authors, journals, outlets, and dates, and
  could then describe those inventions as collected evidence. Both are now
  structurally prevented rather than discouraged.
- The default conversation instruction told the model to always answer in
  English and never in Turkish, which produced mixed and malformed output for
  users writing in Turkish. It now asks for the language the user wrote in,
  forbids mixing languages, asks for proportionate answers, and states that
  browsing is unavailable. No language is hardcoded.
- Conversation history was unbounded when `HYPATIA_LLM_HISTORY_MAX_TURNS` was
  unset. With a small local context window that pushes the newest message toward
  the truncation edge, so history is now bounded to twelve turns by default. The
  literal `unbounded` restores the previous behaviour.

### Added

- `LiveInformationRequestDetector` and `LiveInformationRequestKind` classify a
  plain chat message against a fixed phrase table in English and Turkish. The
  classification authorizes nothing.
- `ResearchHonestyApplicationService` answers such requests deterministically,
  without calling any model, and answers evidence questions from
  `CanonicalResearchSummary` counts derived from persisted runs.
- `ConversationResearchClaimGuard` annotates a generated reply that claims
  research in the first person with a bounded correction naming the canonical
  counts. It never deletes the model output.

### Safety

- A detected live-information request never reaches the language model, so
  there is nothing left that could fabricate a source. Tests assert zero
  provider calls across the real failing prompts.
- Detection cannot become an authorization path: it is gated on the absence of a
  declared intent, it returns only a category, and no capability, plan, run, or
  network operation follows from it.
- Evidence questions are answered only from persisted state, with discoveries,
  acceptances, evidence, assessments, claims, and contradictions counted
  separately so no stage is collapsed into another.
- Ordinary chat provably mutates no research state. Tests assert the run store
  is byte-identical after talking about evidence, sources, claims, and
  contradictions.
- The unsafe-URL boundary is now exercised end to end rather than only at the
  validator. Tests drive the real fetcher and the real authorized-fetch step
  with a recording opener and assert loopback, `127.0.0.1:11434`, private
  ranges, link-local metadata, embedded credentials, plain HTTP, non-standard
  ports, and non-HTTPS schemes are all refused before any connection is opened,
  and that a refusal records no source, evidence, or claim and leaks no
  credential.

### Verification

- The package-aware full local suite contains 2,097 passing automated tests.
- Fifty-two new tests cover live-information detection on the real failing
  prompts and on ordinary conversation, refusal without a model call, canonical
  evidence reporting, the post-generation guard, chat inertness over research
  state, the end-to-end fetch boundary, and bounded conversation history.

## [0.3.145] - 2026-08-23

### Added

- Bounded curiosity. `ResearchKnowledgeGapDetector` reads a research run and
  reports seven bounded gap kinds; `ResearchCuriosityQuestionGenerator` turns
  each gap into one ranked question; `CuriosityApplicationService` exposes
  detect, preview, store, list, accept, and dismiss intents.
- `JsonFileCuriosityQuestionStore` and `HYPATIA_CURIOSITY_ENABLED`, default off.
- Five bounded `curiosity.*` events.

### Safety

- Curiosity notices and proposes; it never acts. No curiosity intent starts
  research, drafts a plan, queues a background task, or spends a network or
  model operation, and accepting a question records intent only. Tests assert
  the run is unchanged after every intent.
- Detection is pure reading of persisted state. A gap reports what our own
  record is missing, never what is true: an unassessed source is not a bad
  source and an unresolved claim is not a wrong claim.
- Question generation is deterministic and template-driven rather than model
  authored, so a proposal cannot smuggle in an assertion. Every generated
  string is interrogative.
- Ranking is a stated formula: declared gap severity dominates and recorded
  claim confidence breaks ties. Gap and question identities are stable, so
  re-detecting proposes the same thing rather than duplicating it, and storing
  never reopens a question a human already decided.
- Superseded claims and superseded assessments are excluded, so a replaced
  record cannot resurface as a gap.
- Event payloads carry identifiers, bounded kinds, counts, and integer ranks
  only. Tests assert no claim text, question text, research question, or URL
  appears in any payload.

### Verification

- The package-aware full local suite contains 2,045 passing automated tests.
- Fifty-seven new tests cover each gap kind, severity ordering, bounded counts,
  superseded records, identity stability, question generation and ranking,
  preview-without-storing, persistence and restart, idempotent storing,
  decision transitions, unknown runs and questions, bounded events, disabled
  persistence, malformed and oversized stores, atomic write failure, and
  production composition wiring.

## [0.3.144] - 2026-08-23

### Added

- Background research scheduling. `BackgroundResearchTask` and its status
  domain, `JsonFileBackgroundTaskStore`, and
  `BackgroundResearchSchedulerApplicationService` with create, pause, resume,
  cancel, list, and worker-cycle intents.
- `BackgroundTaskOutcome` classifies each autonomy stop reason, and nine bounded
  `background_task.*` events.
- `HYPATIA_BACKGROUND_RESEARCH_ENABLED` opts into durable task storage, default
  off.

### Safety

- The scheduler owns queueing only. Every cycle drives the existing autonomy
  service, which drives the existing execution service; there is still one
  research-driving loop and this is not it. Tests assert an instruction naming
  fetch and accept completes no step and performs no research work.
- Budgets pass through unweakened. A task carries a `ResearchAutonomyBudget` and
  a test asserts a two-step budget completes exactly two steps.
- Retries are typed from the stop-reason enum, never from exception messages.
  Only budget exhaustion is retryable; blocked, failed, interrupted, and
  cancelled runs are never retried. The classification table is exhaustive, so a
  new stop reason without a declared outcome raises rather than defaulting to a
  retry.
- Work is synchronous and demand-driven: one cycle runs a bounded number of
  tasks and returns, with no thread, polling, or busy loop. Task selection is
  oldest-first so a retried task cannot starve the queue.
- A cancelled task never restarts and a completed task is never re-run; both are
  refused at the domain level.
- On restart a running task becomes `interrupted` and is not replayed.
  `INTERRUPTED`, `PAUSED`, and `BLOCKED` remain distinct.
- Persistence follows the proven atomic pattern: bounded temporary file, fsync,
  and `os.replace`, with a failed write leaving the previous document
  byte-identical. Unknown schema versions, malformed documents, duplicate task
  IDs, and oversized task counts are all refused.
- Stored documents and event payloads carry identifiers, statuses, counters, and
  an exception class name only. Tests assert the research question and authored
  instruction appear in neither.

### Verification

- The package-aware full local suite contains 1,988 passing automated tests.
- Thirty-one new tests cover task creation and persistence, a completed worker
  cycle, no re-running of completed tasks, pause and resume, cancellation and
  refusal to resume, bounded retry, the retry limit, non-retryable failure,
  budget pass-through, per-cycle and active-task bounds, cycle cancellation,
  restart interruption, no auto-replay, capability invention, bounded events,
  disabled persistence, malformed stores, atomic write failure, schema and
  duplicate rejection, task-count limits, absence of research content, the
  exhaustive outcome table, and production composition wiring.

## [0.3.143] - 2026-08-23

### Added

- Bounded autonomous research. `ResearchAutonomyApplicationService` loops over
  the existing execution service through the exact structured
  `research_autonomy_run` intent; no second execution engine exists.
- `ResearchAutonomyBudget` bounds step advances, network operations, LLM
  operations, and wall-clock seconds, each with a hard ceiling.
  `ResearchAutonomyResult` reports the stop reason, counters, and elapsed time.
- `ResearchOperationCost` and an exhaustive `CAPABILITY_COSTS` table declaring
  each capability's network and model cost.
- Two bounded events, `research.autonomy.started` and `.stopped`, emitted only at
  the boundaries of a run.

### Safety

- Autonomy runs only steps a human already authored and authorized, advanced
  through the same `process_advance` path, registry, operations, and run manager.
  It cannot invent a capability, infer one from instruction text, rewrite a plan,
  fabricate an authorization, accept a source, promote trust, promote a claim, or
  resolve a contradiction. Tests assert an instruction naming search and fetch
  still blocks, and that a discovery run leaves sources, evidence, assessments,
  claims, and contradictions empty.
- Network and model accounting come from the declared capability cost table, not
  from operation names or authored text. A test asserts exactly which
  capabilities declare network cost, so a new capability cannot quietly consume
  an unaccounted call.
- Budgets are enforced before each advance, never after. A zero network budget
  performs no network operation at all, and a zero step budget attempts nothing.
- `max_step_advances` counts attempted advances rather than successes, so a plan
  that keeps blocking cannot loop forever by never succeeding.
- Stopping is not failure. Step-level reasons are reported ahead of the generic
  terminal reason, so a failed, blocked, or interrupted step explains itself
  rather than being flattened into "terminal".
- Time comes from an injected clock; no test sleeps.
- A restored execution cannot be driven by autonomy, and a missing live execution
  is refused rather than started.
- Autonomy telemetry carries identifiers, declared budgets, counters, and a stop
  category only. A test asserts the authored instruction and the research
  question never appear.

### Verification

- The package-aware full local suite contains 1,957 passing automated tests.
- Twenty-one new tests cover completion within budget, exact step-budget
  stopping, network-budget stopping, zero network and zero step budgets, LLM
  accounting from declared cost, injected-clock time exhaustion, cancellation,
  blocked and failed steps, capability invention, absence of source acceptance
  and claim promotion, absence of duplicate side effects, unchanged manual
  execution, refusal without a live execution, bounded events, budget validation,
  and exhaustive capability-cost declaration.

## [0.3.142] - 2026-08-23

### Added

- Stages 3 and 4 of research-execution persistence. `Bootstrap` creates a
  `JsonFileResearchExecutionStore` beside the research-run store when
  `HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED` is exactly `true`, and the
  execution service owns loading, restoring, and writing.
- `research.plan.execution.restored` and
  `research.plan.execution.persistence_failed` events, both bounded.
- A restored-execution response that reports durable state without implying a
  resumable run.

### Safety

- Default off. With the flag absent or set to any other value, no store is
  created and behavior is identical to a runtime without persistence; a test
  asserts no file is written and status still reports ephemeral loss.
- Restoring is inspection, never resumption. A step recorded as running becomes
  `interrupted`, completed steps stay completed, and pending steps stay pending.
  Authorizations are deliberately not persisted, so a restored execution cannot
  be advanced and no completed operation is replayed. A test asserts the research
  run is unchanged after attempting to advance a restored execution.
- A corrupt store raises at startup rather than being replaced by an empty one,
  because silently discarding it would erase execution history on the next write.
- A failed write never erases live state: the in-memory execution continues and a
  bounded `persistence_failed` event reports the cause class.
- Persisted content is bookkeeping only. A test asserts the stored document
  contains neither the authored step instruction nor any source content.
- `CognitiveEngine` receives the store and forwards it, and gained no persistence
  logic.

### Verification

- The package-aware full local suite contains 1,936 passing automated tests.
- Thirteen new integration tests cover completed work surviving a restart without
  replay, a mid-flight step restoring as interrupted, the bounded restore event,
  refusal to advance a restored execution, terminal and cancelled executions
  surviving, disabled persistence keeping ephemeral behavior, a corrupt store
  refusing, duplicate identifiers refusing, a failed write preserving live state,
  the stored document duplicating no research content, and the Bootstrap flag
  requiring an exact value.

## [0.3.141] - 2026-08-23

### Added

- Stage 2 of research-execution persistence: `JsonFileResearchExecutionStore`, a
  dedicated versioned store for execution snapshots.

### Safety

- Deliberately separate from the research-run store. `ResearchRun` and its schema
  are untouched, every existing snapshot stays valid, and no migration of
  existing data is required. Deleting the execution file returns the runtime to
  purely ephemeral behavior.
- Writes follow the existing run-store discipline exactly: a bounded temporary
  file in the destination directory, flushed and fsynced, then moved into place
  with `os.replace`. A failed replace, a failed encode, and an oversized document
  all leave the previous snapshot byte-identical, and no temporary file is left
  behind.
- An absent file means no persisted executions, matching a runtime with
  persistence disabled. A malformed or unreadable file raises rather than being
  silently treated as empty, because discarding it would hide execution history.
- The document is versioned and an unknown `schema_version` is rejected outright.
  Unexpected or missing document fields, non-list executions, malformed entries,
  oversized files, too many executions, and duplicate execution IDs are all
  refused on load and on save.
- The stored document carries execution bookkeeping only. A test asserts it holds
  no excerpt, claim, or instruction content, so research facts are never
  duplicated out of the research run.
- Nothing is wired into the runtime yet; execution state remains ephemeral.

### Verification

- The package-aware full local suite contains 1,923 passing automated tests.
- Twenty-one new tests cover the absent file, lossless round trips, interrupted
  round trip, clearing the document, schema versioning, corrupted JSON, unknown
  schema version, invalid documents, oversized files, execution-count limits on
  load and save, duplicate identifiers on load and save, non-snapshot values,
  malformed entries, failed replace preserving the previous document, no
  temporary file left behind, no partial document when encoding fails, parent
  directory creation, and absence of research content in the stored document.

## [0.3.140] - 2026-08-23

### Added

- Stage 1 of research-execution persistence: a pure codec. `ResearchPlanExecutionSnapshot`
  is the durable record and `ResearchPlanExecutionCodec` converts it to and from
  its document form. No file access, no runtime wiring, and no restore policy
  yet.
- `INTERRUPTED` step and execution statuses, distinct from `BLOCKED`. Blocked
  means a human must decide; interrupted means the process died mid-flight and
  what the operation did is unknown. Neither is terminal.

### Safety

- A snapshot records what happened, never a running execution. `restored()`
  turns a step recorded as running into interrupted, never completed, so a
  mid-flight operation can never be fabricated as finished after a restart.
  Completed steps stay completed and pending steps stay pending.
- Terminal executions stay terminal across a restore, and restoring is
  idempotent.
- `work_performed` is never inferred at load time. A record claiming performed
  work without naming its operation is rejected by both the value object and the
  decoder.
- The document is deliberately narrow: step identity, declared capability,
  status, operation identity, work flag, bounded detail, the plan question, and
  the bound run identity. Authored step instructions, fetched page bodies, source
  excerpts, notes, claim text, and authorization payloads are never written, so
  no research fact is duplicated out of the research run.
- Malformed documents are refused rather than repaired: unknown or missing
  fields, empty or oversized step lists, unknown enum values, naive timestamps,
  and non-string identifiers all raise.

### Verification

- The package-aware full local suite contains 1,902 passing automated tests.
- Fifteen new tests cover capability pairing, work and operation preservation,
  interrupted restore, completed and pending steps surviving, terminal
  executions, restore idempotence, the blocked/interrupted distinction, lossless
  round trips with and without a bound run, absence of authored instructions in
  the document, rejection of work without an operation, and malformed execution
  and step documents.

## [0.3.139] - 2026-08-23

### Added

- Bounded observability for research-plan execution. `ResearchPlanExecutionEvents`
  publishes `research.plan.execution.started`, `.step_started`, `.step_completed`,
  `.step_failed`, `.step_blocked`, and `.cancelled` from one focused emitter that
  owns the event names and payload bounds.
- `ExecutionBlockReason` gives a blocked step a bounded category rather than free
  text: `no_declared_capability`, `unregistered_capability`, or
  `operation_performed_nothing`.

### Safety

- Visibility only. No event changes behavior, and an absent event bus makes every
  emitter call a no-op, so execution runs identically without observability. A
  test drives the same plan through an observed and an unobserved engine and
  asserts identical execution snapshots.
- Payloads carry safe identifiers, capability and operation names, counts, and
  booleans. A test asserts the authored instruction, the authorized URL, the
  research question, and the fetched source body never appear in any payload.
- A bound research run is reported as a boolean, not as an identifier.
- A failed step reports its exception class name, never the exception message.
- A step that genuinely ran without succeeding is distinguished from one that
  never ran, through the `work_performed` field on the failure event.

### Verification

- The package-aware full local suite contains 1,887 passing automated tests.
- Ten new tests cover the started-then-completed sequence with exact payloads,
  absence of authored content, boolean run binding, both block reasons, failure
  cause without message, cancellation reporting surviving progress, behavioral
  equivalence without an event bus, and bounded block categories.

## [0.3.138] - 2026-08-23

### Added

- One end-to-end explicit research-execution scenario driving the whole chain
  through the real `CognitiveEngine` composition path in a single narrative:
  question, discovery, explicit authorization, fetch, acceptance, evidence,
  assessment, two conflicting claims, contradiction, comparison, and honest
  closure.
- A research-execution persistence design proposal documenting why execution
  state stays ephemeral, what a migration would require, and a staged additive
  plan. It is a proposal only; nothing was implemented and no schema changed.

### Safety

- The scenario uses deterministic doubles only for the discovery provider and
  source fetcher, so no network is required. Every other component is real,
  including the run manager, knowledge engine, acceptance transaction, and
  epistemic domain.
- It asserts the chain's boundaries hold together, not merely that each step
  passes: discovery accepts nothing and fetches nothing, acquisition accepts
  nothing, only authorized URLs are ever contacted, recording a contradiction
  leaves both claims byte-identical, and both claims remain hypotheses with
  unassessed confidence at the end.
- The closed run retains its unresolved claims and its contradiction, and the
  completion detail reports them rather than implying resolution.
- Research execution writes no conversation memory.

### Verification

- The package-aware full local suite contains 1,877 passing automated tests.
- Black, Ruff, and MyPy pass for all 407 Python source and test files.
- Live-model and live-network validation remain separate manual diagnostics and
  are still pending.

## [0.3.137] - 2026-08-23

### Added

- `RESEARCH_RUN_COMPLETION` capability and `ResearchRunCompletionStepOperation`,
  closing a run through the existing `transition_status` path.
- `ResearchCompletionAuthorization` carries the one explicitly declared terminal
  status and rejects a non-terminal target.

### Fixed

- The draft service did not carry `completion_authorization` through to the
  plan step, so the capability was unreachable from an authored draft. The
  composition test caught it before release; the passthrough is now covered.

### Safety

- The operation defines no completion rule of its own. Every condition comes
  from the existing lifecycle: completion requires at least one accepted source
  and at least one evidence record, a failed run requires a failure record, and a
  closed run cannot change status. A refused transition is reported as performed
  work that did not succeed, with the run left open.
- Reaching the last execution step never closes a run. A composition test
  advances an execution to `completed` and asserts the run is still
  `collecting`.
- Closing a run resolves nothing. Unresolved claims held as hypothesis,
  speculation, unknown, or contradicted, together with contradictions and
  failures, survive into the final state and are counted in the reported detail.
  The detail states plainly that closing verifies no claim, settles no
  contradiction, and asserts no certainty.
- Missing authorization, an unknown run, a missing run binding, and cancellation
  all close nothing.

### Verification

- The package-aware full local suite contains 1,876 passing automated tests.
- Thirteen new operation tests cover domain-enforced refusal for missing sources
  and evidence, successful closure, reporting and preservation of unresolved
  claims and failures, contradictions surviving closure, the failure-record rule,
  refusal to reclose, missing authorization, cancellation, unknown and unbound
  runs, bounded detail, and authorization validation.
- The composition suite now covers twelve capabilities, and proves that finishing
  execution leaves the run open, that the capability respects domain rules
  through real wiring, and that a closed run retains its unresolved hypothesis.

## [0.3.136] - 2026-08-23

### Added

- `CLAIM_CONTRADICTION` capability and `ClaimContradictionStepOperation`,
  recording one confirmed contradiction through the existing
  `record_claim_contradiction` path.
- `SOURCE_COMPARISON` capability and `SourceComparisonStepOperation`, recording
  one authored comparison note through the existing
  `record_source_comparison_note` path.
- `ResearchContradictionAuthorization` and `ResearchComparisonAuthorization`,
  both arriving as named fields on `ResearchPlanStepDraftInput`. No positional
  draft element was added.

### Safety

- A proposal is never a contradiction. Previewing a contradiction persists
  nothing, and a suggestion, including a language-model one, stays a proposal
  until a human authorizes it through the canonical path.
- Recording a contradiction never rewrites either claim. A test captures both
  claims before and after and asserts they are byte-identical, with their
  epistemic states unchanged, so the contradiction never decides which claim is
  true.
- Exactly two distinct current claims from the bound run are required. Foreign
  and non-existent claim references are rejected with no mutation, and a
  duplicate relationship for the same pair is refused.
- Comparison is a description, not a verdict. It selects no winner, produces no
  ranking, promotes no trust, and verifies no claim; a test asserts assessments
  and claims are unchanged and contradictions stay empty afterwards.
- The existing 2-to-5 accepted-source bound is preserved rather than replaced,
  and evidence and assessment references must belong to the run.
- Authored notes and comparison text stay bounded, and user-facing detail stays
  within the bounded operation limit.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing for both capabilities.

### Verification

- The package-aware full local suite contains 1,860 passing automated tests.
- Seventeen new operation tests cover confirmed recording, claims left
  unrewritten, proposals persisting nothing, duplicate refusal, foreign and stale
  references, source-count bounds, trust and claim state left untouched, missing
  authorization, cancellation, closed and unknown runs, bounded detail, and
  authorization validation for both capabilities.
- The composition suite now covers eleven capabilities with production route
  tests for both new ones.

## [0.3.135] - 2026-08-23

### Added

- `CLAIM_CREATION` capability and `ClaimCreationStepOperation`, recording one
  authored claim through the existing `ResearchRunManager.record_claim` path. No
  second claim implementation exists.
- `ResearchClaimAuthorization` carries the exact evidence a claim rests on, the
  authored claim text, an explicit epistemic state, an explicit categorical
  confidence, and an optional superseded claim.
- `ResearchPlanStepDraftInput` gains a named `claim_authorization` field; no
  positional draft element was added.

### Safety

- Epistemic state and confidence are authored, never inferred. Completing the
  operation promotes nothing: a claim is recorded in exactly the state a human
  declared. A test records every one of the seven epistemic states and asserts
  each is stored verbatim.
- A high-trust assessment does not raise a claim. A composition test records a
  high-trust assessment and then a hypothesis, and asserts the claim stays a
  hypothesis with unassessed confidence.
- The existing domain requires at least one evidence reference for every claim,
  including a hypothesis or speculation. That exact rule is preserved rather than
  replaced, so no claim can exist without evidence.
- Evidence must belong to the bound run. Foreign and non-existent evidence
  references are rejected with no mutation.
- Claim text stays bounded, evidence references stay unique and bounded, and
  confidence remains categorical with no fabricated number.
- Supersession history is preserved: the superseded claim remains in its original
  state and the replacement records the exact predecessor identity.
- Existing contradiction state is untouched; recording a claim never resolves or
  clears a contradiction.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.

### Verification

- The package-aware full local suite contains 1,840 passing automated tests.
- Fifteen new operation tests cover authored recording, non-promotion of a
  hypothesis, verbatim recording of every epistemic state, the evidence
  requirement for speculation, rejection of foreign and stale evidence,
  supersession history, untouched contradictions, missing authorization,
  cancellation, closed and unknown runs, bounded detail, and authorization
  validation.
- The composition suite now covers nine capabilities and drives the complete
  chain through real `CognitiveEngine` wiring: acceptance, evidence, assessment,
  and claim.

## [0.3.134] - 2026-08-23

### Changed

- Authored plan-step drafts now normalize through the named immutable
  `ResearchPlanStepDraftInput`, replacing a widening positional tuple whose
  fifth element could only be understood by counting. Legacy positional tuples
  are still accepted unchanged, so existing callers, the desktop adapter, and the
  plan domain are unaffected and no persisted schema changed.

### Added

- `SOURCE_ASSESSMENT` capability and `SourceAssessmentStepOperation`, recording
  one authored assessment through the existing
  `ResearchRunManager.record_source_assessment` path. No second assessment
  implementation exists.
- `ResearchAssessmentAuthorization` carries one exact accepted-source document,
  its evidence references, the authored assessment text, an authored
  information-trust label, and an optional superseded assessment.

### Safety

- Assessment text and information trust are authored, never derived. Nothing
  about a successful fetch, a successful acceptance, or a completed operation can
  set them, and no language model participates in this milestone.
- At least one evidence reference is required, matching the existing domain rule,
  so an assessment is always grounded in recorded evidence and can never rest on
  a successful fetch alone.
- The source must already be accepted on the bound run; a source accepted on a
  different run is rejected, as is a foreign evidence reference.
- Supersession history is preserved: the superseded assessment remains, and the
  replacement records the exact predecessor identity.
- Information trust describes confidence in what a source says. It is not
  evidence, not claim verification, not proof the source is correct, and it never
  grants the source's text instruction authority.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.

### Verification

- The package-aware full local suite contains 1,822 passing automated tests.
- Fourteen new operation tests cover authored recording, absence of evidence or
  claim creation, unassessed trust defaulting, supersession history, rejection of
  unaccepted sources and foreign evidence, missing authorization, cancellation,
  closed and unknown runs, bounded detail, normalization, evidence grounding, and
  authorization validation.
- The composition suite now covers eight capabilities, proves the named draft
  input works through real wiring alongside legacy tuples, and drives the chain
  from source acceptance through evidence recording to assessment.

## [0.3.133] - 2026-08-23

### Added

- `EVIDENCE_RECORDING` capability and `EvidenceRecordingStepOperation`, recording
  one evidence entry through the existing `ResearchRunManager.add_evidence`
  path. No second evidence domain exists.
- `ResearchEvidenceAuthorization` groups one exact document ID, one exact chunk
  index, and one authored note, so capability-specific authorization stays
  cohesive instead of spreading across flat step fields. Draft steps accept it
  as an optional fifth element.

### Safety

- Evidence text is never supplied by a caller. The operation resolves a real
  `Chunk` by exact document ID and chunk index, and the existing evidence domain
  computes the excerpt, chunk identity, and hash from that chunk. A caller may
  authorize which chunk and what a human noted about it, never the excerpt, so
  evidence cannot be fabricated.
- No language model is involved at any point.
- A fetched-but-unaccepted source cannot produce evidence: the run manager
  independently requires the chunk's document to belong to an accepted source. A
  composition test drives fetch-without-accept and confirms the recording fails.
- An unknown document or chunk index is refused rather than guessed or
  approximated to a nearby chunk.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.
- Recording evidence establishes evidence only. It performs no assessment, forms
  no claim, elevates no epistemic state, and makes no source trustworthy; tests
  assert assessments, claims, and contradictions all stay empty.
- Excerpt truncation is reported rather than hidden, and user-facing detail stays
  within the bounded operation limit even with a maximum-length note.

### Verification

- The package-aware full local suite contains 1,805 passing automated tests.
- Twelve new operation tests cover recording from an accepted chunk, provenance
  computed from the real chunk, absence of assessment or claim, refusal for
  unaccepted sources and unknown chunks, missing authorization, cancellation,
  closed and unknown runs, bounded detail, and authorization validation.
- The composition suite now covers seven capabilities and proves the full
  production chain: `SOURCE_ACCEPT` then `EVIDENCE_RECORDING` through real
  `CognitiveEngine` wiring, plus the fetched-but-unaccepted refusal.

## [0.3.132] - 2026-08-23

### Changed

- The canonical source-acceptance transaction is extracted from
  `CognitiveEngine._process_research_source_load` into
  `ResearchSourceAcceptanceService`. The extraction is behavior-preserving: the
  same indexing, content persistence, `add_source`, and layered rollback flow
  runs, and every existing failure message is byte-identical. `CognitiveEngine`
  shrinks by 73 net lines and now delegates instead of owning the transaction.
  Exactly one acceptance implementation exists.

### Added

- `SOURCE_ACCEPT` capability and `SourceAcceptStepOperation`, fetching the one
  authorized URL through the canonical fetcher and then running the extracted
  acceptance transaction.
- `ResearchSourceAcceptanceResult` reports `accepted` and
  `transaction_attempted` as separate flags, and refuses to represent an
  accepted source that was never attempted.
- `AcceptsResearchSource` is the research-layer protocol for the transaction, so
  research operations never import the cognition layer.
- `ResearchPlanStepOperationResult.succeeded` distinguishes an operation that
  genuinely ran from one that achieved its outcome, and
  `ResearchPlanExecutionState.fail_step` can now record performed work on a
  failed step.

### Safety

- A transaction that runs and does not accept is recorded as performed work on a
  failed step, never rendered as a successful acceptance. The detail states that
  no source was added to the run.
- Authorization stays explicit. The URL comes only from the step's
  `authorized_source_url`; discovery metadata alone never authorizes acceptance,
  and instruction text remains inert. Tests assert zero fetches in both cases.
- No second content channel exists. Content flows only through the canonical
  knowledge engine and source-content store, and no page content enters the
  execution context.
- Cancellation before the fetch prevents all work; cancellation after the fetch
  prevents every acceptance mutation, leaving knowledge, content, and run state
  untouched.
- Rollback guarantees are unchanged and now directly tested: content failure
  rolls back indexing, `add_source` failure rolls back content and indexing, and
  a failed content rollback is reported precisely rather than glossed over.
- Duplicate sources remain deterministic, surfacing as an indexing error with no
  partial state, exactly as before.
- Accepted means accepted into the run's source set only. No evidence,
  assessment, claim, trust, or conclusion follows, and tests assert those
  collections stay empty.

### Verification

- The package-aware full local suite contains 1,790 passing automated tests.
- Ten acceptance-service tests cover success, all rollback branches, duplicate
  handling, unknown runs, indexing failure, and knowledge-only acceptance.
- Eleven operation tests cover authorized-only acceptance, attempted-but-not-
  accepted reporting, refusal of unauthorized and discovery-only sources,
  cancellation before and after the fetch, audited fetch and indexing failures,
  closed and unknown runs, and detail that never dumps content.
- The composition suite now covers six capabilities and additionally proves the
  existing source-load route and the `SOURCE_ACCEPT` operation share one
  acceptance service instance, and that the legacy route still accepts a source.

## [0.3.131] - 2026-08-23

### Added

- `SOURCE_FETCH` capability and `SourceFetchStepOperation`, reusing the canonical
  `ResearchSourceFetcher` pipeline. No second HTTP path was added.
- `ResearchPlanStep.authorized_source_url` is the one exact source a step may
  acquire, bounded to 2,048 characters and rejecting embedded control
  characters. Draft steps accept it as an optional fourth element.

### Safety

- The URL is never chosen by the operation. It comes only from the step's
  explicit authorization: never inferred from instruction text, never taken from
  a discovery result, never guessed from ranking. Tests assert zero network calls
  when a URL appears only in instruction text or only in a discovery record.
- Every existing protection stays in force through the reused pipeline: public
  HTTPS only, credential rejection, port restrictions, DNS and IP validation,
  public-address enforcement, redirect validation, TLS and hostname validation,
  response-size, content-type, and encoding bounds. A composition test drives the
  real `HttpResearchSourceFetcher` and confirms plain HTTP, a loopback address,
  and embedded credentials are all still rejected.
- The operation is acquisition-only. It performs no acceptance: nothing is
  indexed, no accepted-source record is written, no content snapshot is stored,
  and no evidence, assessment, or claim is created. Accepting a source remains a
  separate explicit contract.
- Because nothing is persisted, cancellation after bytes arrive leaves no partial
  research state. Cancellation before the fetch prevents any network call.
- A closed run, unknown run ID, or missing run binding is rejected before any
  network call.
- Blank content never becomes a successful fetch; the domain rejects it at
  `ResearchSource` construction and the operation guards it again.
- Fetched content is untrusted data with no instruction authority and is never
  sent to a language model here. User-facing detail reports only the bounded URL,
  content type, and character count, never source contents.

### Verification

- The package-aware full local suite contains 1,764 passing automated tests.
- Fifteen new operation tests cover authorized-only fetching, refusal of
  instruction-text and discovery URLs, cancellation before and after the fetch,
  acceptance of nothing, audited pipeline rejection, blank-content refusal at
  both layers, closed and unknown runs, content never appearing in detail,
  bounded hostile URLs, and step-level URL validation.
- The standing composition table now covers five capabilities.

## [0.3.130] - 2026-08-23

### Added

- `SOURCE_DISCOVERY` capability and `SourceDiscoveryStepOperation`, reusing the
  existing `ResearchSourceDiscoveryProvider` abstraction and the
  `ResearchRunManager` discovery audit path. No second discovery engine exists.
- `ResearchPlanExecutionContext.cancellation_token` carries the request's
  cooperative cancellation signal as per-execution state. The application
  service forwards the current request's token on every advance.

### Safety

- One step performs exactly one bounded provider query: no retry, no crawling,
  no link following, and no unbounded concurrency. A test asserts the provider
  is contacted exactly once even when it fails.
- Cancellation is checked before the query and again before the audit write.
  Cancelling first prevents provider contact entirely; cancelling during the
  query prevents the discovery record from being written.
- A closed run, an unknown run ID, and a missing run binding are all rejected
  before the provider is contacted.
- Provider results are validated for type and count. An oversized or malformed
  result is rejected and no discovery record is written.
- Provider failure records a `source_discovery` failure in the run audit and
  re-raises, so the step fails honestly rather than reporting partial success.
  No substitute provider is ever used; when no provider is configured the
  capability stays unregistered and a declaring step blocks.
- Candidates are persisted only as an unaccepted, provenance-preserving audit
  record. Nothing is accepted, fetched, turned into evidence, or turned into a
  claim. Every detail states that candidates are not accepted sources, not
  evidence, not trusted, and not a conclusion, and a composition test asserts
  that sources, evidence, claims, and assessments all remain empty afterwards.
- Zero candidates is a performed discovery, not a failure.

### Verification

- The package-aware full local suite contains 1,745 passing automated tests.
- Fourteen new operation tests cover the stable name, unaccepted candidate
  recording, zero-candidate completion, bounded query parameters, single-query
  behavior, failure auditing, oversized and malformed result rejection,
  cancellation before and after the query, closed and unknown runs, limit
  validation, and bounded detail.
- The standing composition table now covers four capabilities, with route tests
  proving discovery runs through real `CognitiveEngine` wiring, accepts nothing,
  and stays unregistered without a provider.

## [0.3.129] - 2026-08-23

### Added

- `EVIDENCE_INTEGRITY_CHECK` capability and `EvidenceIntegrityCheckStepOperation`,
  running the existing `ResearchEvidenceIntegrityAuditor` against the bound run
  through constructor-injected collaborators.

### Safety

- The check is local, read-only, and deterministic: no network, no LLM, no
  persistence mutation, and no event emitted. Repeated runs return an identical
  result, and the run is byte-identical afterwards.
- Only the bound run is audited, never the whole catalog.
- A completed check proves only that the integrity operation ran and returned
  its result. Every rendered detail states that it does not establish truth,
  verify a claim, or make a source trustworthy. Matched, missing, and changed
  counts describe structural and provenance consistency only.
- Zero evidence records still complete the audit, reporting that no evidence
  records were available to inspect.
- An `unavailable` audit is reported as a performed operation with an explicit
  state and no fabricated counts.
- An unknown run ID or a missing run binding fails the step safely with
  `work_performed` left false.
- The capability is registered only when both a run manager and an integrity
  auditor exist; otherwise it stays unregistered and a declaring step blocks.
- Detail stays within the bounded 500-character operation limit.

### Verification

- The package-aware full local suite contains 1,728 passing automated tests.
- Ten new operation tests cover the stable name, zero-evidence completion,
  reconciliation counts, single-run scoping, unavailable reporting, unknown-run
  and missing-binding failure, absence of mutation, bounded detail, and
  determinism.
- The standing composition table now covers three capabilities, with new route
  tests proving the check runs through real `CognitiveEngine` wiring, fails
  safely without a run, and stays unregistered without an auditor.

## [0.3.128] - 2026-08-23

### Added

- `ResearchPlanExecutionContext` is the smallest explicit typed context for one
  execution, currently one optional bounded `research_run_id`. It is passed
  through the application-service boundary to an operation.
- `ResearchPlanStepOperation.run` now receives that context. Collaborators stay
  constructor-injected at composition time, so an operation never reaches a
  global, service locator, dependency container, `CognitiveEngine`, or an
  unrelated store.
- `ACCEPTED_SOURCE_LISTING` capability and `AcceptedSourceListingStepOperation`,
  reading accepted sources from the canonical `ResearchRunManager` state.
- The start request accepts an optional explicit `research_run_id` binding.

### Safety

- Listing is read-only: no network, no LLM, no persistence mutation, and no
  event emitted. A test asserts the run is byte-identical afterwards.
- Zero accepted sources is a successfully performed listing, not a failure.
- The detail states explicitly that no source content was read and no evidence
  was established. Listing establishes neither evidence, nor trustworthiness,
  nor a verified claim; those remain in the existing research pipeline.
- Reported document identifiers are capped at three with a remainder count, so a
  large accepted-source catalog is never dumped into step detail.
- An unknown or stale run ID, and a missing run binding, fail the step safely
  with `work_performed` left false.
- The capability is registered only when a run manager exists. Without one it
  stays unregistered and a declaring step blocks rather than failing obscurely.
- Capability authorization stays separate from execution context: the step
  declares what it may run, the context describes what it runs against.

### Verification

- The package-aware full local suite contains 1,715 passing automated tests.
- Sixteen new tests cover the stable operation name, zero-source listing,
  identifier-only reporting, bounded large catalogs, unknown-run and
  missing-binding failure, absence of mutation, and context validation.
- A new composition-level suite proves every registered capability is actually
  reachable through the real `CognitiveEngine` wiring, covering the 0.3.126
  bug class where a capability worked in a directly constructed service while
  production wiring silently lacked it. This check is now required for every
  newly connected capability.

## [0.3.127] - 2026-08-23

### Added

- `ResearchPlanStepCapability` is the explicit typed authorization a plan step
  may declare, defaulting to `none`. `ResearchPlanStep.capability` keeps that
  authorization separate from the authored instruction text.
- `ResearchPlanOperationRegistry` binds each executable capability to exactly one
  operation. Selection is a table lookup, never a heuristic over instruction
  text, and `CognitiveEngine` registers the local knowledge search explicitly
  rather than growing conditional routing.
- `ResearchPlanStepState.operation` records which operation ran, so a completed
  step can always answer which operation was selected and what produced it.
- `ResearchPlanDraftService` accepts an optional explicit capability name as a
  third draft element. Two-element drafts remain valid and declare no capability.
- `ResearchPlanExecutionState.snapshot()` returns a minimal deterministic
  inspection tuple of step id, status, operation, and work flag.

### Fixed

- The 0.3.126 engine wiring for the local knowledge search silently did not
  apply, so the advance route reached no operation. The registry is now wired and
  covered by a test that drives the route through `CognitiveEngine`.

### Safety

- A step declaring no capability, or declaring a capability with no registered
  operation, is blocked with a bounded reason. Neither falls back to another
  operation.
- Instruction wording never selects a capability. A step whose instruction says
  "run a local knowledge search" still blocks unless the capability is declared.
- Recorded work now requires a recorded operation name: constructing a step state
  with `work_performed` true and no operation is rejected.
- Rendering states that a completed operation means the operation ran, and that
  it is neither evidence nor a verified claim. Evidence, assessment, and claims
  are not established by execution and remain in the existing research pipeline.
- Registering the `none` capability, registering a capability twice, or passing a
  non-capability value is rejected.
- The snapshot is an inspection aid only. It is not persistence and cannot resume
  an execution.

### Verification

- The package-aware full local suite contains 1,699 passing automated tests.
- Fifteen new tests cover capability defaults and validation, registry
  resolution, rejection of `none` and duplicate registration, blocking for
  undeclared and unregistered capabilities, instruction text never selecting a
  capability, recorded operation identity, draft capability parsing and
  rejection, and deterministic snapshots.
- Black, Ruff, and MyPy pass for all 372 Python source and test files.

## [0.3.126] - 2026-08-23

### Added

- Stage 3 of research-plan execution connects the first real research
  capability. `ResearchPlanStepOperation` is the structural boundary for one
  bounded operation, `ResearchPlanStepOperationResult` reports whether work
  actually ran plus one bounded 500-character summary, and
  `LocalKnowledgeSearchStepOperation` runs the existing deterministic local
  knowledge search for an authored step instruction.
- The exact structured `research_plan_execution_advance` Brain intent advances
  the next pending step by running that one operation.

### Safety

- Only an operation that actually executed can mark a step as backed by real
  work. When no operation is connected, or a connected operation reports that it
  performed nothing, the step is blocked with a bounded reason instead of being
  reported as completed research.
- A failing operation fails the step and the plan, leaves `work_performed` false,
  and preserves earlier completed steps.
- One advance request runs at most one operation for one step, in authored
  order. Advancing past the last pending step is rejected.
- A zero-result search is reported honestly as a performed search that matched
  nothing, so a step never implies evidence that was not located.
- The connected operation reads only already loaded local knowledge. Source
  discovery, source fetching, evidence extraction, assessment, and claims remain
  unconnected, and no network, LLM, or persistence path is used.
- Reported document identifiers are capped at three with an explicit remainder
  count.

### Verification

- The package-aware full local suite contains 1,684 passing automated tests.
- Thirteen new tests cover the stable operation name, real findings, honest
  zero-result reporting, bounded detail, result validation, blocking when no
  operation is connected, running one operation per step, blocking when an
  operation performed nothing, failure handling, completing a plan across
  advances, rejection past the last step, and advancing an unknown plan.
- Black, Ruff, and MyPy pass for all 369 Python source and test files.

## [0.3.125] - 2026-08-23

### Added

- Stage 2 of research-plan execution: `ResearchPlanExecutionApplicationService`
  owns ephemeral per-process execution state and exposes exact structured
  `research_plan_execution_start`, `research_plan_execution_status`, and
  `research_plan_execution_cancel` Brain intents.
- `ResearchPlanStepState.work_performed` records whether a real research
  operation backed a transition. `ResearchPlanExecutionState` adds
  `steps_with_research_work` and `performed_research_work`.
- `BrainResponse.research_plan_execution` carries the complete immutable state.

### Safety

- No research work runs in this stage. Starting a plan records that execution
  began and advances no step. Source discovery, fetching, evidence, assessment,
  and claims are not performed, and the rendered message says so.
- `work_performed` defaults to false and never becomes true on its own, so a
  bare state-machine advance can never be presented as completed research. A
  step completed without a backing operation is reported with
  `Research operations performed: 0` and an explicit no-research-ran line.
- Execution state lives in the application service, never in `CognitiveEngine`,
  which only routes.
- State is in-memory and per-process. Every status message states that it is
  lost when Hypatia exits, and an unknown plan reports absent state that is not
  resumed after a restart rather than inventing a resumable run.
- Duplicate start requests are rejected deterministically and leave existing
  state untouched. Active executions are capped at 20 per process.
- Terminal executions reject further transitions, and cancellation preserves
  completed-step history including its work flag.
- No persistence, schema change, second `ResearchRun` store, network call, or
  LLM call. Execution routes write no memory record.

### Verification

- The package-aware full local suite contains 1,671 passing automated tests.
- Seventeen new tests cover intent recognition, start without step advance,
  absence of reported research work, the ephemeral-boundary message,
  deterministic duplicate-start rejection, absent-state reporting, cancellation
  of unfinished steps, preservation of completed history, a manual advance being
  reported as no research, terminal rejection, invalid drafts leaving no state,
  missing plan IDs, bounded capacity, fresh-process statelessness, engine
  routing without owning state, and execution routes writing no memory.
- Black, Ruff, and MyPy pass for all 365 Python source and test files.

## [0.3.124] - 2026-08-23

### Added

- Stage 1 of research-plan execution: a pure immutable state machine. New
  `ResearchPlanExecutionStatus` (ready, running, completed, failed, cancelled,
  blocked) and `ResearchPlanStepStatus` (pending, running, completed, failed,
  cancelled, blocked) follow the existing `ResearchRunStatus` convention with an
  explicit `terminal` property.
- `ResearchPlanStepState` carries one step identity, its bounded status, and one
  bounded 500-character detail. `ResearchPlanExecutionState` tracks the whole
  plan and exposes `prepare`, `start`, `start_step`, `complete_step`,
  `fail_step`, `block_step`, and `cancel`.

### Safety

- Every transition returns a new immutable state and never mutates its input.
- A plan reaches completed only when every step reached completed. Constructing a
  completed state with unfinished steps is rejected, so partial or failed work
  can never present itself as finished.
- Steps run in exact authored order, and only one step may run at a time. Both
  are enforced at construction and at transition.
- Failure and cancellation preserve already-completed steps rather than rewriting
  history. Cancellation touches only unfinished steps.
- Blocked is deliberately non-terminal and carries a bounded reason for review.
- Terminal states reject all further transitions. Unknown step IDs, invalid
  statuses, duplicate step IDs, empty step tuples, and over-long details are
  rejected with one bounded `ResearchError`.
- Stage 1 is domain-only: no network, LLM, provider, persistence, event-bus,
  `ResearchRun`, Brain, or desktop integration, and no schema change. Execution
  cannot yet be started by any user-reachable route.

### Verification

- The package-aware full local suite contains 1,654 passing automated tests.
- Twenty-four new tests cover terminal-status membership, inert preparation,
  authored ordering, single-running-step enforcement, full success, fabricated
  completion rejection, failure preserving progress, terminal immutability,
  blocking and cancelling a blocked plan, cancellation preserving finished steps,
  non-mutation of prior states, unknown steps, transitions outside a running
  plan, and bounded detail.
- Black, Ruff, and MyPy pass for all 363 Python source and test files.

## [0.3.123] - 2026-08-23

### Added

- `DesktopController.audit_learned_memory` issues the existing structured
  `learned_memory_audit` intent as one read-only request, so the desktop adapter
  can surface learned-memory health without new runtime behavior.

### Safety

- The adapter adds no persistence, provider, network, LLM, or mutation path. It
  is a thin pass-through to the Brain route added in 0.3.122.
- The Tkinter window is unchanged in this increment; the bounded report is
  already fully rendered in the Brain response message.

### Verification

- The package-aware full local suite contains 1,630 passing automated tests.
- One new test locks the exact structured message, source, and metadata.
- Black, Ruff, and MyPy pass for all 357 Python source and test files.

## [0.3.122] - 2026-08-23

### Added

- A read-only learned-memory audit. `LearnedMemoryAuditor` computes deterministic
  bounded metrics from learned-memory records: total records, active and
  superseded counts, superseded share, distinct identities, identities with
  history, maximum versions for one identity, conflicting-history identities, and
  duplicate value candidates.
- `LearnedMemoryAuditReport` carries those metrics plus bounded samples capped at
  10 entries each, with an explicit `samples_truncated` flag.
- `LearnedMemoryAuditApplicationService` exposes the audit through the exact
  structured `learned_memory_audit` Brain intent, following the established
  no-write preview routing pattern.
- `BrainResponse.learned_memory_audit` carries the complete immutable report.

### Safety

- The audit is strictly read-only. It never deletes, merges, compacts, rewrites,
  normalizes, or reorders stored memories, and performs no persistence mutation
  or schema change.
- Duplicate value candidates are derived only from exact value equality between
  active identities. Equal text is never asserted to mean equivalent meaning, and
  nothing is merged. The rendered message states that no equivalence was decided.
- Superseded values never produce duplicate candidates, so historical records
  cannot inflate review noise.
- The rendered message reports kinds, keys, and counts only. It never includes a
  stored learned-memory value.
- The audit issues no LLM call, no semantic query, and no network request. It
  runs only on an explicit structured request, never on an ordinary chat turn.
- Repeated audits over unchanged records return identical reports and emit no
  events.

### Verification

- The package-aware full local suite contains 1,629 passing automated tests.
- Eighteen new tests cover the empty store, active-only stores, single and
  repeated corrections, repeated identical values as history without conflict,
  same-value-different-key candidates, superseded values excluded from
  candidates, bounded truncated samples, determinism, input immutability,
  exclusion of ordinary conversation records, absence of writes and events,
  structured-intent recognition, value omission from the message, and absence of
  LLM or semantic-runtime calls on the audit route.
- Black, Ruff, and MyPy pass for all 357 Python source and test files.

## [0.3.121] - 2026-08-23

### Added

- Optional semantic relevance in ordinary chat behind
  `HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED=true`, off by default and inert unless
  the semantic-memory runtime is also enabled. A semantically related question
  can now recover a durable memory whose wording differs from the message.
- `LearnedMemoryContextService` owns learned-memory context selection for one
  user turn. `CognitiveEngine` delegates to it instead of branching inline over
  selector and limit combinations.
- One bounded `brain.chat_semantic_memory.query_failed` event reports a failed
  semantic query, carrying only the request ID and the cause class name.

### Safety

- With the flag absent, ordinary chat delegates to the existing deterministic
  loaders unchanged and issues no semantic query or embedding call.
- One user turn performs at most one semantic query. The conversation path never
  starts an index rebuild.
- No second semantic index, store, or cache exists. The service reuses
  `SemanticMemoryIndexRuntime` and `HybridSemanticMemoryRanker`.
- A semantic hit on a superseded learned-memory record is rejected, so latest-wins
  correction behavior is preserved and stale values are never resurrected.
- Absent, rebuilding, stopped, or failing semantic retrieval falls back to the
  deterministic bounded path and the conversation still succeeds.
- The fused context is deduplicated by learned-memory identity and bounded by
  `HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` or 8 when that is unset.
- Retrieval performs no memory write. Explicit lexical recall and explicit
  semantic recall are unchanged. No persisted schema, `LLMProvider`, or
  `LearnedMemorySelector` contract changed.

### Verification

- The package-aware full local suite contains 1,611 passing automated tests.
- Twenty-one new tests cover disabled-path equivalence, semantic recovery of
  differently worded memories, exclusion of unrelated memories, the fused bound,
  keyword/semantic deduplication, rejection of superseded records, empty-result
  and provider-failure fallback, exactly one query per turn, absence of rebuilds
  from the conversation path, no memory write on retrieval, unchanged explicit
  semantic recall, and fusion against a reloaded persistent store.
- A local harness measured the fusion overhead at roughly 0.4 ms per turn over
  the lexical path with 200 learned memories and 16 semantic candidates,
  excluding the embedding call itself.
- Black, Ruff, and MyPy pass for all 352 Python source and test files.

## [0.3.120] - 2026-08-23

### Verification

- Added an end-to-end regression proving the primary natural-memory product
  behavior across a full runtime restart: a stated preference is extracted and
  persisted to the local memory file, a second Bootstrap reading the same file
  loads it, and the durable value reaches the provider prompt for a later
  question without any explicit recall command.
- The same suite asserts that an unrelated durable memory stays out of that
  prompt, that a corrected value supersedes the stale one across the restart,
  and that non-JSON extraction output leaves chat working while emitting exactly
  one bounded failure event with a `ValueError` cause.
- The tests assert the deterministic context and prompt boundary rather than any
  model-specific generated wording, so they do not depend on a particular local
  Ollama model.
- The package-aware full local suite contains 1,590 passing automated tests.
- Black, Ruff, and MyPy pass for all 349 Python source and test files.

## [0.3.119] - 2026-08-23

### Changed

- Ordinary chat now defaults to bounded, request-relevant learned memory. When
  `HYPATIA_LEARNED_MEMORY_SELECTOR` is absent, Bootstrap builds the existing
  deterministic `RankedKeywordLearnedMemorySelector` bounded to 8 memories
  instead of supplying every current learned memory unbounded.
- `HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT` now also overrides that bound in
  the default case.

### Added

- `HYPATIA_LEARNED_MEMORY_SELECTOR=none` explicitly restores the earlier
  unbounded no-selector behavior for callers that depended on it.
- `DEFAULT_LEARNED_MEMORY_SELECTOR_LIMIT` names the default bound in one place.

### Safety

- Only the Bootstrap composition default changed. `CognitiveEngine` keeps its
  explicit-injection contract, so a directly constructed engine behaves exactly
  as before.
- Learned-memory correction and supersession are unchanged; the latest value for
  a key still wins and stale values stay out of the prompt.
- Explicit recall and semantic recall commands are unchanged.
- No persisted schema, provider, network, or retrieval-mechanism change. No
  vector database was introduced.

### Verification

- The package-aware full local suite contains 1,587 passing automated tests.
- Seven new integration tests lock relevant inclusion, unrelated exclusion, the
  bound under overflow, correction supersession, plain conversation with no
  learned memory, unchanged explicit recall, and the `none` escape hatch.
- Three existing bootstrap tests now pin the legacy unbounded path behind the
  explicit `none` value rather than absent configuration.
- Black, Ruff, and MyPy pass for all 348 Python source and test files.

## [0.3.118] - 2026-08-23

### Added

- `LLMLearnedMemoryCandidateExtractor` now detects providers that expose the
  optional `generate_json(...)` capability through a local runtime-checkable
  Protocol, matching the pattern already used by
  `LLMResearchClaimContradictionProposalProvider`.
- When that capability is present, extraction requests a bounded structured
  response: a trusted system instruction, `max_tokens=512`, and an exact JSON
  response schema whose allowed `kind` values, required fields, and
  `additionalProperties: false` constraints mirror the existing parser.
- The learned-memory prompt boundary now also owns
  `LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION`, `EXTRACTION_MAX_TOKENS`, and
  `build_learned_memory_candidate_response_schema()`, which returns a fresh
  dictionary per call so no caller can mutate shared schema state.
- Ordinary chat now emits one bounded `brain.learned_memory.extraction_failed`
  event when learned-memory extraction fails, replacing a fully silent swallow.

### Safety

- The existing parser remains the final authority. A declared schema never
  bypasses validation, so reasoning preambles and Markdown-fenced payloads are
  still rejected.
- The failure event payload carries only `request_id` and the cause class name.
  It never carries the user message, source text, candidate values, or the raw
  model response.
- No event is emitted for successful or no-op extraction, so the established
  exact conversation event order is unchanged.
- Chat still succeeds when extraction fails, and the conversation record is
  still persisted.
- `TypeError` from an incompatible provider `generate_json` signature keeps
  propagating instead of being normalized into an extraction failure.
- Providers exposing only `generate` keep their exact previous call, with no
  system instruction and empty history.
- The persisted memory schema, the global `LLMProvider` Protocol, semantic chat
  retrieval, and the learned-memory retrieval defaults are all unchanged.

### Verification

- The package-aware full local suite contains 1,580 passing automated tests.
- Twelve new focused tests lock structured-capability routing and exact
  arguments, unchanged `generate`-only fallback, `LLMError` normalization with
  preserved cause, `TypeError` propagation, parser rejection of reasoning and
  fenced output, schema freshness and parser agreement, bounded failure-event
  payload, `unknown` cause categorization, and absence of the event on both
  successful and no-op extraction.
- Black, Ruff, and MyPy pass for all 347 Python source and test files.

## [0.3.117] - 2026-08-22

### Added

- The Research workspace now exposes a dedicated `Plan draft` authored-analysis
  tab without changing the established four-step workflow or its 1080p height.
- The editor shares the explicit authored question, collects one ordered
  instruction per line, and binds optional comma-separated exact source document
  IDs from the matching line.
- `DesktopController.preview_research_plan_draft` converts only those visible
  fields into the existing structured `research_plan_draft_preview` request. The
  editor shows the complete ready or rejected Brain message in its own read-only
  result area and in the ordinary transcript.

### Safety

- Empty, duplicate, excessive, or misaligned authored rows are not silently
  repaired into a different plan. They remain visible to the existing bounded
  domain validation and return a no-write rejection.
- The desktop adds no confirmation, persistence, `ResearchRun` mutation,
  provider, network, LLM, event-bus, tool, automatic source selection, or plan
  execution path. Changing tabs and editing fields remain presentation-only.
- The new instruction, source, and result text controls follow the selected Eye
  comfort, Light, or High contrast palette and the existing 10-to-20-point text
  setting.

### Verification

- The package-aware full local suite contains 1,568 passing automated tests.
- Four new focused tests lock exact structured metadata and order, preservation
  of invalid row alignment for runtime rejection, non-text rejection before
  Brain, and complete desktop rejection rendering without confirmation.
- Black, Ruff, and MyPy pass for all 346 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory. A direct 1920-by-1080 Tkinter
  smoke check maps both aligned editors and the complete preview area, exercises
  ready and rejected Brain responses, and observes no temporary-data change.

## [0.3.116] - 2026-08-22

### Added

- The explicit structured `research_plan_draft_preview` intent now reaches the
  pure draft service through `ResearchPlanPreviewApplicationService`.
- `BrainResponse` carries the complete `ResearchPlanDraftPreview`, while
  `ResponseComposer` renders either all authored ordered steps and exact selected
  source IDs or one bounded rejection reason.
- Ready output states that explicit confirmation is still required, persistent
  writes were not used, and execution was not started. Rejected output contains
  no partial plan and makes the same no-write/no-execution guarantees.

### Safety

- The route accepts only exact structured metadata and has no plain-message
  heuristic. It does not add persistence, `ResearchRun` mutation, provider,
  network, LLM, event-bus, tool, automatic source selection, or execution work.
- Direct cognition coverage proves that preview routing leaves memory, knowledge
  documents, and published events unchanged. No desktop binding is added.

### Verification

- The package-aware full local suite contains 1,564 passing automated tests.
- Focused ResponseComposer coverage contains 66 passing tests and focused
  cognition coverage contains 267 passing tests. Six new tests lock exact ready
  and rejected messages, structured-intent recognition, metadata delegation,
  bounded missing-metadata behavior, and side-effect-free engine routing.
- Black, Ruff, and MyPy pass for all 346 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.115] - 2026-08-22

### Added

- `ResearchPlanDraftService` converts only an explicit authored question and an
  immutable ordered tuple of `(instruction, selected source IDs)` drafts into
  the stable `ResearchPlan` domain contract.
- Valid drafts receive deterministic plan-local `step-1` through `step-20`
  identities plus an injected or local plan identity and creation time.
- `ResearchPlanDraftPreview` returns either one complete immutable plan ready
  for a future explicit confirmation or one bounded validation reason with no
  partial plan.

### Safety

- Invalid question, step shape, instruction, source selection, generated plan
  identity, or creation time is converted from `ResearchError` into a no-write
  rejected preview. Unexpected programming or factory errors are not hidden.
- The service has no Brain, response, manager, store, `ResearchRun`, desktop,
  provider, network, LLM, path, event-bus, or execution integration. It does not
  persist a draft or authorize automatic source selection.

### Verification

- The package-aware full local suite contains 1,558 passing automated tests.
- Eight direct tests cover exact ordered construction, normalized plan-local
  step identities, empty source selections, input immutability, structural and
  domain failures, invalid generated values, and exclusive ready/rejected
  preview invariants.
- Black, Ruff, and MyPy pass for all 343 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.114] - 2026-08-22

### Added

- `ResearchPlan` provides the first immutable user-authored Research planning
  contract: one bounded question, one to twenty explicitly ordered steps, and a
  timezone-aware creation time.
- Each immutable `ResearchPlanStep` keeps one bounded authored instruction and
  zero to twenty exact user-selected source document IDs. An empty tuple means
  no source was selected for that step; it grants no automatic source choice.
- Plans expose only the deduplicated first-selected source order derived from
  their steps. They contain no execution status, provider instruction, or run
  lifecycle state.

### Safety

- Plan, step, instruction, and source identifiers are normalized and bounded;
  duplicate step IDs and duplicate per-step source selections are rejected.
- The domain-only slice imports no Brain, manager, store, provider, network,
  LLM, desktop, path, event bus, or execution boundary. It does not alter the
  existing `ResearchRun` schema or persistence format.

### Verification

- The package-aware full local suite contains 1,550 passing automated tests.
- Nine direct domain tests cover normalization, immutable ordered steps, explicit
  empty source selection, first-selection order, strict character/count limits,
  duplicate refusal, typed tuples, and timezone-aware creation.
- Black, Ruff, and MyPy pass for all 340 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.113] - 2026-08-22

### Changed

- Existing claim-history, accepted-source comparison, and accepted-source
  assessment previews now live behind the dedicated read-only
  `ResearchAuthoredHistoryApplicationService` application boundary.
- `CognitiveEngine` delegates those three routes at their original precedence
  points. Its size falls from 3,157 to 3,054 lines without changing any Brain
  request, response, message, persistence, provider, or UI contract.

### Safety

- The extracted service reads only existing persisted Research snapshots through
  `ResearchRunManager`. It adds no mutation, schema, store, network, provider,
  LLM, UI, or automatic-analysis behavior.
- Missing or invalid identifiers, duplicate or out-of-bound comparison source
  selections, unavailable persistence, unknown runs, and unaccepted sources
  retain their exact bounded failure responses.

### Verification

- The package-aware full local suite contains 1,541 passing automated tests.
- Focused cognition coverage contains 263 passing tests, including eight direct
  service contract tests for exact recognition, validation, dependency absence,
  domain failures, raw identifier delegation, and successful composition.
- Black, Ruff, and MyPy pass for all 337 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.112] - 2026-08-22

### Changed

- Research-run listing, one-run evidence listing, accepted-content restoration
  status, and evidence-integrity status now live behind the dedicated read-only
  `ResearchOverviewApplicationService` application boundary.
- `CognitiveEngine` delegates those four existing routes at their original
  precedence points. Its size falls from 3,243 to 3,157 lines without changing
  any Brain request, response, message, persistence, provider, or UI contract.

### Safety

- The extracted service only composes already supported read results. It adds no
  mutation, schema, persistence, network, provider, LLM, UI, or automatic-
  analysis behavior.
- Missing persistence and audit dependencies, invalid or missing run IDs,
  unknown runs, and `ResearchError` audit failures retain their exact bounded
  failure or unavailable responses.

### Verification

- The package-aware full local suite contains 1,533 passing automated tests.
- Focused cognition coverage contains 255 passing tests, including 11 direct
  service contract tests for recognition, exact delegation, validation,
  dependency absence, successful snapshots, and safe audit degradation.
- Black, Ruff, and MyPy pass for all 335 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.111] - 2026-08-22

### Changed

- Research catalog filtering, status facets, deterministic ordering, run
  progress/coverage/metadata, and canonical selected-source presentation now
  live in one immutable `ResearchWorkspaceReadModel` outside Tkinter.
- `TkinterDesktopWindow` delegates those existing values through frozen run and
  source read views. Its size falls from 4,631 to 4,437 lines while adding the
  requested startup sizing, without changing
  any visible text, command, field, provider, persistence, or runtime contract.
- The desktop now requests a 1,920-by-1,080-pixel initial client area, centers
  that size on larger displays, and clamps both dimensions to smaller screens.
  The window remains resizable and retains a screen-safe bounded minimum.

### Safety

- The read model accepts only already loaded immutable snapshots and imports no
  Tkinter, Brain, controller, manager, provider, path, network, or store boundary.
- Exact canonical source membership, external-data taint, instruction authority
  `none`, current/superseded assessment handling, unique evidence membership,
  deterministic ties, and URL/content exclusion remain unchanged.
- Initial sizing is presentation-only and opens no runtime boundary. Invalid
  screen dimensions are rejected by the pure sizing helper.

### Verification

- The package-aware full local suite contains 1,522 passing automated tests.
- Focused desktop coverage contains 163 passing tests, including direct frozen
  read-model coverage for empty catalogs, exact filtering, deterministic ties,
  duplicate evidence, hidden source membership, superseded/foreign records,
  canonical-source refusal, safe URL-free details, exact 1,920-by-1,080 sizing,
  smaller-screen fitting, and invalid-dimension refusal.
- Black, Ruff, and MyPy pass for all 333 Python source and test files.
- A real Tk check reports `1920x1080+0+0` on the current 1,920-by-1,080
  display. The pinned Windows onedir package builds and initializes its local
  session snapshot in a fresh temporary data directory.

## [0.3.110] - 2026-08-22

### Added

- Sources & evidence now provides one explicit `Source details` action for the
  selected accepted source without adding another layout row.
- The read-only dialog shows normalized bounded title, exact source/run IDs,
  persisted content type, and timezone-aware fetched/accepted timestamps at
  seconds precision.

### Safety

- Details require complete canonical source-record membership in the selected
  immutable run. Changed, foreign, empty, or stale selection is refused.
- The dialog deliberately excludes source URL and content, changes no authored
  field, and opens no controller, provider, persistence, network, or mutation
  boundary.

### Verification

- The package-aware full local suite contains 1,510 passing automated tests.
- Focused desktop coverage contains 151 passing tests, including exact safe
  fields, timezone precision, URL exclusion, canonical-record refusal,
  no-selection refusal, field isolation, and zero controller calls.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one `Source details`
  button in the established 954-by-973-pixel requested window.

## [0.3.109] - 2026-08-22

### Added

- The selected-source summary now reports unique recorded evidence explicitly
  cited by current assessments beside the source's complete evidence count.
- The existing Records line keeps evidence, assessment history/current totals,
  and current cited-evidence coverage together without adding window height.

### Safety

- Citation membership uses only non-superseded assessments for the exact source
  and only evidence IDs present in that source's immutable evidence records.
  Repeated IDs count once; superseded, foreign, or unknown IDs cannot contribute.
- The count is an audit inventory, not a completeness or quality verdict. It
  opens no controller, provider, persistence, network, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,506 passing automated tests.
- Focused desktop coverage contains 147 passing tests, including repeated
  citations, corrections, foreign/unknown IDs, zero evidence, exact provenance,
  safety separation, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the four-line summary
  preserves the established desktop window boundary.

## [0.3.108] - 2026-08-22

### Added

- The selected-source summary now reports the complete distribution of current
  user-authored information-trust labels: Unassessed, Low, Medium, and High.
- Provenance, persisted safety boundary, record totals, and current trust
  distribution are separated into four explicit read-only lines for clarity.

### Safety

- Distribution membership includes only non-superseded assessments for the
  exact selected source. Superseded history remains in the history total but
  not the trust counts; foreign-source records cannot contribute.
- Counts describe authored labels only. They infer no verdict or quality and
  cannot change the source's independent instruction authority `none`; no
  controller, provider, persistence, network, or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,505 passing automated tests.
- Focused desktop coverage contains 146 passing tests, including all four trust
  labels, corrected/superseded history, foreign-record isolation, zero counts,
  safety-boundary separation, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the structured four-line
  summary preserves the established desktop window boundary.

## [0.3.107] - 2026-08-22

### Added

- The selected-source summary now exposes the canonical persisted safety
  boundary beside provenance: data taint `external_untrusted_data` and
  instruction authority `none`.

### Safety

- Safety text is derived only from the complete canonical source record already
  bound to the immutable run; it makes no new trust, quality, or authority
  decision and opens no controller, provider, persistence, network, or mutation
  boundary.
- A user-authored high information-trust assessment cannot alter or obscure the
  source's untrusted-data taint or grant instruction authority. Hidden/invalid
  state continues to clear the entire source summary.

### Verification

- The package-aware full local suite contains 1,504 passing automated tests.
- Focused desktop coverage contains 145 passing tests, including canonical
  safety-boundary presentation, high-information-trust isolation, exact
  provenance/counts, canonical-record refusal, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the wrapped safety line
  preserves the established desktop window boundary.

## [0.3.106] - 2026-08-22

### Added

- The selected-source record summary now keeps a normalized bounded source
  title, exact source document ID, and exact immutable research-run ID visible
  beside the evidence and assessment counts.

### Safety

- Summary binding requires the complete selected source record to match one
  canonical source in the selected immutable run. A changed or foreign record
  is refused rather than presenting counts under misleading provenance.
- Untrusted title whitespace is normalized and display length is bounded while
  both identity fields remain exact. Hidden/invalid state still clears the
  summary, no quality or trust is inferred, and no runtime or mutation boundary
  opens.

### Verification

- The package-aware full local suite contains 1,503 passing automated tests.
- Focused desktop coverage contains 144 passing tests, including exact source/
  run provenance, canonical-record refusal, whitespace normalization, title
  bounds, record counts, correction history, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one wrapped provenance/
  record-summary label in the existing desktop window.

## [0.3.105] - 2026-08-22

### Added

- Sources & evidence now shows one compact read-only record summary for the
  selected accepted source: exact evidence count, authored assessment-history
  count, and current authored-assessment count.

### Safety

- The summary derives only from the already loaded immutable run and selected
  exact source ID. Correction records remain visible in history while only
  non-superseded records count as current; foreign malformed records cannot
  inflate the selected source.
- Hidden, empty, or invalid source presentation clears the summary instead of
  retaining stale data. The summary infers no quality or trust and opens no
  controller, provider, persistence, network, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,501 passing automated tests.
- Focused desktop coverage contains 142 passing tests, including exact
  evidence/history/current counts, correction history, foreign-record
  isolation, zero records, and hidden-source clearing/restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound selected-source
  summary label in the existing desktop layout.

## [0.3.104] - 2026-08-22

### Added

- Sources & evidence now provides one explicit `Show active source` recovery
  action beside the accepted-source coverage catalog summary.
- The action restores All sources and reselects the exact active source when a
  local coverage view has hidden it.

### Safety

- Recovery requires the current run ID, loaded immutable run, source catalog,
  and active source ID to agree exactly. Empty, stale, or unknown identity state
  is refused without changing the prior view.
- Restoring the source rehydrates only its read-only evidence and assessment
  presentation. Catalog totals, authored fields, and persisted state remain
  unchanged, and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,499 passing automated tests.
- Focused desktop coverage contains 140 passing tests, including hidden-source
  restoration, exact identity and read-only record rehydration, empty/stale/
  unknown state refusal, catalog-summary invariance, and field isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one recovery button in
  the existing 954-by-973-pixel requested window.

## [0.3.103] - 2026-08-22

### Added

- Sources & evidence now shows one compact read-only accepted-source coverage
  catalog summary for the selected immutable run.
- The summary reports complete All, Without evidence, and Without current
  assessment counts independently of the active local source view.

### Safety

- Repeated evidence and current assessment records count one source once.
  Correction chains exclude superseded history, while malformed foreign records
  cannot inflate or hide accepted-source membership.
- Source-view changes cannot alter the catalog totals, exact active identity, or
  authored fields. Empty/invalid selection clears stale totals, no quality or
  readiness is inferred, and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,495 passing automated tests.
- Focused desktop coverage contains 136 passing tests, including repeated and
  foreign records, correction/superseded-only history, empty catalogs, selected
  run binding, facet invariance, identity preservation, and field isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound summary label
  in the existing 954-by-973-pixel requested window.

## [0.3.102] - 2026-08-22

### Added

- Sources & evidence now provides a third local accepted-source view: Without
  current assessment.
- The view derives stable source membership from the selected immutable run and
  shares the same current-assessment definition as the Overview coverage line.

### Safety

- Superseded-only assessment history remains uncovered, repeated current
  assessments count a source once, and malformed foreign assessment records
  cannot hide an accepted source.
- A visible or hidden active source keeps its exact identity and is restored by
  All sources. Authored fields remain unchanged; invalid or stale state leaves
  the prior view intact and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,492 passing automated tests.
- Focused desktop coverage contains 133 passing tests, including correction
  chains, repeated current records, foreign/superseded-only history, stable
  order, visible and hidden active identity, restoration, and no-match state.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one read-only three-choice
  selector in the existing 954-by-973-pixel requested window.

## [0.3.101] - 2026-08-22

### Added

- Research Overview now shows one read-only current-assessment coverage summary
  for the selected immutable run snapshot.
- The summary reports accepted sources, sources having a current authored
  assessment, and accepted sources without a current assessment.

### Safety

- Superseded assessment history does not count as current, and multiple current
  records for one accepted source count that source once. Malformed foreign
  assessment references cannot inflate coverage.
- Empty and invalid selections replace stale coverage with explicit guidance.
  The summary infers no quality, truth, completeness, or readiness and opens no
  Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary.

### Verification

- The package-aware full local suite contains 1,488 passing automated tests.
- Focused desktop coverage contains 129 passing tests, including correction
  chains, source deduplication, superseded-only history, malformed foreign
  references, empty runs, valid selection binding, and stale-state clearing.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the additional bound
  coverage label remains within the existing 954-by-973-pixel requested window.

## [0.3.100] - 2026-08-22

### Added

- Sources & evidence now provides an explicit local accepted-source view with
  All sources and Without evidence choices.
- The view derives stable membership from the selected immutable run, reports
  visible/total counts, and preserves a visible or hidden active source ID.

### Safety

- Repeated evidence for one source does not affect membership, and malformed
  foreign evidence cannot hide an accepted source. Hidden active sources are
  restored exactly when All sources is selected again.
- View changes preserve run/source identity and authored fields and open no
  Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary. Invalid or stale local state leaves the prior view intact.

### Verification

- The package-aware full local suite contains 1,485 passing automated tests.
- Focused desktop coverage contains 126 passing tests, including stable order,
  repeated/foreign evidence, visible and hidden active identity, restoration,
  no-match, empty catalog, invalid facet, and stale-snapshot isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one read-only two-choice
  selector in the existing 954-by-973-pixel requested window.

## [0.3.99] - 2026-08-22

### Added

- Research Overview now shows one read-only evidence-coverage summary for the
  selected immutable run snapshot.
- The summary reports complete accepted-source, represented-source, and
  accepted-source-without-evidence counts without a score or readiness claim.

### Safety

- Multiple evidence records for one source count that source once. A malformed
  foreign evidence reference cannot inflate represented membership.
- Empty and invalid selections replace stale coverage with explicit guidance.
  Selection opens no Brain, controller, storage, provider, network, LLM,
  index, event-bus, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,479 passing automated tests.
- Focused desktop coverage contains 120 passing tests, including repeated
  evidence for one source, empty coverage, malformed foreign references,
  selection binding, empty catalogs, and invalid-selection clearing.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound coverage label
  in the existing 954-by-973-pixel requested window.

## [0.3.98] - 2026-08-22

### Added

- Research Overview now provides one explicit `Reset view` action for the
  local run-catalog controls.
- Reset clears the bounded text and status filters, restores Updated-newest
  sorting, re-shows the complete catalog, and reselects a loaded active run.

### Safety

- Reset changes presentation state only. It preserves the immutable loaded
  catalog, exact active run identity, authored assessment/claim fields, and the
  complete catalog summary and opens no runtime or mutation boundary.
- Empty catalogs and stale active IDs are explicit. Neither case selects a
  different row, and invalid local filter/sort state can be safely recovered.

### Verification

- The package-aware full local suite contains 1,476 passing automated tests.
- Focused desktop coverage contains 117 passing tests, including hidden active
  restoration, default sort, authored-field preservation, empty catalogs,
  stale active identity, and controller isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the action in the
  existing 1080p-safe desktop layout.

## [0.3.97] - 2026-08-22

### Added

- Research Overview now shows one compact complete catalog summary with All,
  Collecting, Completed, Failed, and Cancelled counts.
- Counts are derived from the full already loaded run tuple and remain truthful
  while text filtering, status filtering, or local sorting changes the view.

### Safety

- The summary is presentation-only. It preserves the immutable catalog, active
  run, visible selection, and authored fields and opens no Brain, controller,
  storage, provider, network, LLM, index, event-bus, or mutation boundary.
- Empty catalogs show explicit zero counts for every lifecycle instead of stale
  values. Filtering changes neither the summary nor its source tuple.

### Verification

- The package-aware full local suite contains 1,473 passing automated tests.
- Focused desktop coverage contains 114 passing tests, including every
  lifecycle, repeated lifecycle membership, the empty catalog, and
  text/status-filter invariance.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the read-only catalog
  summary in the existing 1080p-safe desktop layout.

## [0.3.96] - 2026-08-22

### Added

- Research Overview now provides an explicit local status view with All,
  Collecting, Completed, Failed, and Cancelled choices.
- The status choice composes with the bounded text filter and current
  deterministic sort. Visible/total feedback includes the selected status.

### Safety

- Status filtering reads only the immutable loaded run catalog. It preserves
  the active run and authored fields and opens no Brain, controller, storage,
  provider, network, LLM, index, event-bus, or mutation boundary.
- Clearing the text filter preserves the status choice. `Show active run`
  clears both presentation filters while preserving sort; invalid status state
  leaves the prior visible tuple unchanged.

### Verification

- The package-aware full local suite contains 1,471 passing automated tests.
- Focused desktop coverage contains 112 passing tests, including every exact
  lifecycle, text/status/sort composition, status-preserving text clear,
  no-match active/authored-field preservation, and invalid-state isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the read-only five-choice
  status selector in a 954-by-973-pixel requested window.

## [0.3.95] - 2026-08-22

### Added

- Research Overview now provides an explicit `Show active run` action when the
  local filter hides the currently active research run.
- The action restores the complete loaded view in the already selected order,
  makes the active run visible in the selector, and reports the exact outcome.

### Safety

- Showing the active run clears only the presentation filter. It preserves the
  selected sort, immutable loaded catalog, active run, and authored fields and
  opens no Brain, controller, storage, provider, network, LLM, index, event-bus,
  or mutation boundary.
- Missing, stale, or invalid local selection/sort state leaves the prior filter
  and visible tuple unchanged and replaces ambiguous behavior with guidance.

### Verification

- The package-aware full local suite contains 1,467 passing automated tests.
- Focused desktop coverage contains 108 passing tests, including hidden active-
  run restoration, sort and authored-field preservation, no-selection and
  stale-catalog isolation, and invalid-sort refusal.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one working action and
  its empty state in a 954-by-973-pixel requested window.

## [0.3.94] - 2026-08-22

### Added

- Research Overview can sort the current loaded or filtered run view by newest
  update, oldest update, newest creation, or question text.
- One explicit current-sort line remains visible beside the read-only selector.
  Equal timestamps and equal case-folded questions use ascending exact run IDs
  as deterministic tie breaks.

### Safety

- Sorting reorders only the current presentation tuple. It does not change the
  immutable loaded catalog, filter membership, active run, or authored fields,
  and it opens no Brain, controller, storage, provider, network, LLM, index,
  event-bus, or mutation boundary.
- Refresh and filter application reuse the selected sort. Invalid local sort
  state leaves the visible view untouched, and hidden active runs remain active
  until the user explicitly chooses another visible run.

### Verification

- The package-aware full local suite contains 1,463 passing automated tests.
- Focused desktop coverage contains 104 passing tests, including all four sort
  modes, deterministic ties, filter-membership isolation, active-selection and
  authored-field preservation, and invalid-state isolation.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms the read-only sort
  selector in a 954-by-973-pixel requested window.

## [0.3.93] - 2026-08-22

### Added

- Research Overview now shows the selected run's immutable creation and update
  timestamps as seconds-level timezone-aware ISO-8601 text.
- The same metadata line reports the complete count of persisted safe failures.
  Empty and invalid selection states replace stale metadata with guidance.

### Safety

- Metadata is derived only from the already selected immutable `ResearchRun`
  snapshot. Failure stage/reason details are never presented, and no Brain,
  controller, storage, provider, network, LLM, index, event-bus, or mutation
  boundary is opened.
- Filtering and hidden/no-match active-run behavior remain presentation-only;
  all authored fields and existing run-bound views are preserved.

### Verification

- The package-aware full local suite contains 1,460 passing automated tests.
- Focused desktop coverage contains 101 passing tests, including timezone-aware
  bounded formatting, exact failure count, failure-detail hiding, and selected,
  empty, and invalid metadata states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one metadata label
  in a 954-by-973-pixel requested window.

## [0.3.92] - 2026-08-22

### Added

- Research Overview can filter the already loaded run catalog by case-
  insensitive bounded question text, exact status, or exact run ID.
- A persistent local result summary reports matching/total counts, an explicit
  no-match state, or an overlong-filter refusal; `Clear` restores the full
  loaded catalog.

### Safety

- Filtering is presentation-only and capped at 200 characters. It never opens
  a Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary and never modifies the immutable full catalog.
- A still-visible active run remains selected. A hidden or no-match active run
  remains active until the user explicitly chooses another visible run; all
  authored fields and run-bound presentations remain unchanged.

### Verification

- The package-aware full local suite contains 1,459 passing automated tests.
- Focused desktop coverage contains 100 passing tests for question/status/exact-
  ID matching, partial-ID refusal, visible selection preservation, no-match
  field preservation, clear restoration, and overlong input isolation.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one filter field
  and its Filter/Clear controls in a 954-by-973-pixel requested window.

## [0.3.91] - 2026-08-22

### Added

- Research Overview now includes one compact `Workflow snapshot` for the
  selected run: complete source/evidence counts, authored assessment/comparison-
  note/claim/contradiction counts, and the existing review status.
- Empty and invalid selections replace stale stage records with direct guidance.

### Safety

- The snapshot reads only the already selected immutable `ResearchRun` object.
  It does not infer readiness or truth, recommend a conclusion, change status,
  hide controls, or open a Brain, controller, manager, provider, persistence,
  network, LLM, index, event-bus, or mutation boundary.
- Existing fields, commands, confirmations, schemas, and provider paths remain
  unchanged.

### Verification

- The package-aware full local suite contains 1,455 passing automated tests.
- Focused desktop coverage contains 96 passing tests, including every displayed
  stage count/status plus selected, empty, and invalid snapshot states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one workflow-
  snapshot label in a 954-by-973-pixel requested window.

## [0.3.90] - 2026-08-22

### Added

- The shared current-run banner on Sources & evidence, Authored analysis, and
  Review & export now includes complete source, evidence, and claim counts.
- Empty or invalid run selections replace stale counts with explicit progress-
  unavailable guidance.

### Safety

- Progress is calculated only from the already selected immutable `ResearchRun`
  snapshot. It opens no Brain, controller, manager, storage, provider, network,
  LLM, knowledge-index, event-bus, or mutation boundary.
- The three tabs share one presentation value; all existing fields, commands,
  confirmations, schemas, provider paths, and mutation contracts remain intact.

### Verification

- The package-aware full local suite contains 1,454 passing automated tests.
- Focused desktop coverage contains 95 passing tests, including complete count
  formatting and selected, empty, and invalid presentation states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms three context and
  three progress labels in a 954-by-973-pixel requested window.

## [0.3.89] - 2026-08-22

### Added

- Sources & evidence, Authored analysis, and Review & export now show the same
  read-only `Current research run` banner with the selected question, status,
  and exact run ID.
- Empty and invalid selections replace stale context with direct guidance to
  return to Overview, refresh the catalog, or start a research run.

### Safety

- The banner is derived only from the already selected immutable `ResearchRun`
  snapshot. It opens no Brain, controller, storage, provider, network, LLM,
  knowledge-index, event-bus, or mutation boundary.
- Existing fields, commands, tab navigation, confirmation boundaries, provider
  paths, persistence schemas, and mutation contracts remain unchanged.

### Verification

- The package-aware full local suite contains 1,453 passing automated tests.
- Focused desktop coverage contains 94 passing tests for exact run identity,
  bounded long questions, selected/empty/invalid states, and existing workflow
  behavior.
- Black, Ruff, and MyPy pass, and a real Tk measurement confirms three bound
  context labels in a 954-by-973-pixel requested window.

## [0.3.88] - 2026-08-22

### Changed

- The dense desktop Research workspace is now presented as four ordered workflow
  tabs: Overview, Sources & evidence, Authored analysis, and Review & export.
- Authored analysis has four compact sub-tabs for saved records, comparison,
  assessment, and claims/contradictions so the complete workspace fits a 1080p
  desktop without hiding controls below the screen.
- Each section includes concise guidance while retaining every existing field,
  selector, button, confirmation boundary, and keyboard-reachable control.

### Safety

- Changing workflow or analysis tabs is presentation-only and starts no Brain,
  controller, storage, provider, network, LLM, knowledge-index, event-bus, or
  mutation work.
- The exact multisets of 59 existing command bindings and 41 field bindings are
  preserved from v0.3.87; no research contract or persisted schema changes.

### Verification

- The package-aware full local suite contains 1,452 passing automated tests.
- Focused desktop coverage contains 93 passing tests, including the exact ordered
  workflow and analysis section labels.
- A real Tk layout measurement confirms a 973-pixel requested window height on a
  1080-pixel desktop, down from the initial 1,110-pixel intermediate layout.

## [0.3.87] - 2026-08-22

### Added

- The selected desktop research run now exposes its persisted user-authored
  source-comparison notes from the already loaded immutable run snapshot.
- Each selector label retains bounded authored text, timezone-aware recorded
  time, and exact note ID; a separate read-only summary shows every exact source,
  evidence, and assessment reference.
- Three separate explicit actions can copy only the selected note's source,
  evidence, or assessment references into the matching manual field.

### Safety

- Selecting a comparison note never edits form fields or starts Brain, storage,
  provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Each handoff preserves the authored comparison text and all non-target fields;
  stale or invalid selections are cleared or refused locally.

### Verification

- The package-aware full local suite contains 1,451 passing automated tests.
- Focused desktop coverage contains 92 passing tests for immutable-snapshot
  rendering, bounded labels, complete exact-reference summaries, selection-only
  behavior, isolated handoffs, field preservation, and stale-run guards.

## [0.3.86] - 2026-08-21

### Added

- The selected desktop research run now exposes its persisted user-reviewed
  claim contradictions from the already loaded immutable run snapshot.
- Contradiction labels retain the exact claim pair, bounded authored note,
  timezone-aware recorded time, and exact contradiction ID.
- A separate explicit action can copy one recorded exact pair into the manual
  contradiction field while preserving the authored note field.

### Safety

- Selecting or handing off a persisted contradiction never starts Brain,
  storage, provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Stale and invalid selections are cleared or refused locally without changing
  either manual contradiction field.

### Verification

- The package-aware full local suite contains 1,447 passing automated tests.
- Focused desktop coverage contains 88 passing tests for immutable-snapshot
  rendering, exact pair/time/ID labels, bounded notes, field preservation,
  explicit pair handoff, invalid selection, and stale-run guards.

## [0.3.85] - 2026-08-21

### Added

- The selected desktop research run now exposes its user-authored claims from
  the already loaded immutable run snapshot.
- Claim labels distinguish `current` and `superseded` audit state while showing
  bounded authored text, epistemic state, categorical confidence, and exact ID.
- Separate explicit actions can copy one current claim ID into the manual
  predecessor field or append it to the two-ID contradiction field.

### Safety

- Selecting a claim never edits authored fields or starts Brain, storage,
  provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Superseded, stale, duplicate, and over-two contradiction selections are
  refused locally without changing form values.

### Verification

- The package-aware full local suite contains 1,443 passing automated tests.
- Focused desktop coverage contains 84 passing tests for audit-state rendering,
  uncertainty labels, current-record preference, exact-ID handoff, duplicate and
  two-ID limits, field preservation, and stale-selection guards.

## [0.3.84] - 2026-08-21

### Added

- The accepted source currently selected in the desktop now exposes its
  user-authored assessments from the already loaded immutable run snapshot.
- Assessment labels distinguish `current` and `superseded` audit state while
  retaining bounded authored text and the exact assessment ID.
- Explicit actions can copy one current assessment ID into the manual
  correction-target field or append it to comparison-assessment IDs.

### Safety

- Selecting a source or assessment never edits authored fields or starts Brain,
  storage, provider, network, LLM, knowledge-index, or mutation work.
- Superseded, stale, cross-source, duplicate, non-comparison-source, and over-50
  comparison selections are refused locally without changing form values.

### Verification

- The package-aware full local suite contains 1,439 passing automated tests.
- Focused desktop coverage contains 80 passing tests for audit-state rendering,
  current-record preference, exact-ID handoff, ownership, duplicate/limit, and
  stale-selection guards.

## [0.3.83] - 2026-08-21

### Added

- The accepted source currently selected in the desktop now exposes only its
  persisted evidence from the already loaded research-run snapshot.
- Evidence labels show a bounded single-line excerpt and the exact evidence ID.
- Separate explicit handoffs append the exact ID to the manual assessment,
  claim, or comparison evidence field.

### Safety

- Selecting a source or evidence record edits no manual field and starts no
  Brain, store, provider, network, LLM, knowledge-index, or mutation operation.
- Assessment handoff requires the same accepted-source ID. Comparison handoff
  requires that source in the manual comparison, while claim and comparison
  limits remain 20 and 100 evidence IDs. Duplicate and stale cross-run/source
  selections cannot overwrite authored fields.

### Verification

- The package-aware full local suite contains 1,435 passing automated tests.
- Focused desktop coverage contains 76 passing tests for source filtering,
  exact-ID handoff, ownership guards, duplicate prevention, limits, and stale
  selection rejection.

## [0.3.82] - 2026-08-21

### Added

- The selected research run now exposes its accepted sources in a read-only
  desktop selector labelled with bounded title text and the exact document ID.
- Separate `Use for assessment` and `Add to comparison` actions copy only the
  selected exact ID into the corresponding existing manual field.

### Safety

- Merely selecting or refreshing a run never overwrites either manual source
  field and starts no Brain, store, provider, network, or mutation operation.
- Accepted-source choices are tied to one exact loaded run snapshot. Stale
  cross-run choices are cleared and refused, duplicate comparison IDs are not
  added, and the existing five-source comparison limit is preserved.

### Verification

- The package-aware full local suite contains 1,430 passing automated tests.
- Focused desktop coverage verifies snapshot-only rendering, exact-ID handoff,
  manual-field isolation, duplicate prevention, and stale-run rejection.

## [0.3.81] - 2026-08-21

### Added

- The selected research run now has a compact read-only summary directly below
  the desktop selector: status plus complete source, evidence, and claim counts.
- Empty and invalid selection states provide explicit guidance instead of
  retaining a stale summary.

### Safety

- The summary is computed only from the already loaded immutable catalog
  snapshot. It opens no Brain, storage, provider, network, or mutation path.
- Counts are complete collection sizes, not model estimates or silently
  truncated detail counts.

### Verification

- The package-aware full local suite contains 1,425 passing automated tests.
- Focused coverage verifies collecting/completed summaries, selection changes,
  empty catalogs, invalid selection, and zero side-effect catalog behavior.

## [0.3.80] - 2026-08-21

### Added

- `Research runs` now populates a read-only desktop selector whose labels show
  each persisted question, run status, and exact run ID.
- Creating a run immediately places the new record in the same selector, so
  ordinary research actions no longer require manual run-ID copy and paste.

### Changed

- Refresh preserves the current run when it still exists; otherwise it selects
  the first persisted result. An empty catalog clears the selected run.
- Changing runs clears only stale presentation state tied to the prior run:
  source candidates, contradiction suggestions, and export preview.

### Safety

- Catalog refresh and selection are local, read-only presentation actions. They
  start no discovery, source load, provider, network, or research mutation.
- User-authored research fields remain untouched, and the status line explicitly
  reports that selection started no action.

### Verification

- The package-aware full local suite contains 1,424 passing automated tests.
- Focused coverage verifies catalog rendering, created-run selection,
  empty-catalog clearing, run switching, and absence of runtime side effects.

## [0.3.79] - 2026-08-21

### Added

- Successful contradiction suggestions now populate a read-only desktop pair
  selector for the exact research run that produced them.
- `Use selected pair` copies only the chosen two persisted claim IDs into the
  existing manual contradiction form.

### Changed

- Starting a new suggestion or creating a different research run clears the
  ephemeral candidate selector. A run mismatch also discards stale candidates
  before refusing the handoff.

### Safety

- Selecting a pair never copies model rationale into the user's note, invokes a
  provider, records a relationship, or bypasses preview, confirmation, and final
  runtime revalidation.
- The user's existing note remains untouched and the interface states that
  nothing was recorded.

### Verification

- The package-aware full local suite contains 1,422 passing automated tests.
- Focused coverage verifies successful handoff, unchanged authored notes,
  cancellable generation, stale-run rejection, and selector clearing.

## [0.3.78] - 2026-08-21

### Added

- An explicit desktop action can ask the configured LLM for up to ten possible
  contradiction pairs among at most fifty current, non-superseded claims.
- Every read-only candidate cites exactly two persisted claim IDs and the exact
  ordered evidence union derived by Hypatia from those claims; model-authored
  rationale remains visibly labelled as an untrusted review suggestion.

### Changed

- The OpenAI-compatible provider supports bounded JSON-schema completions with
  reasoning disabled and deterministic sampling for this structured review
  task. Providers without that extension retain the existing strict JSON
  fallback contract.
- Already recorded unordered claim pairs are omitted, and a changed research
  run invalidates the provider result before it can be displayed.

### Safety

- Candidate generation runs only after the user selects `Suggest
  contradictions`. It receives no conversation history, tools, or instruction
  authority from research data and performs no persistence.
- Hypatia still does not decide truth, rewrite claims, select evidence from
  model output, create a relationship automatically, or bypass the existing
  user-authored note, preview, confirmation, and final revalidation boundary.

### Verification

- The package-aware full local suite contains 1,420 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 331 source files.
- The focused suite was also exercised against local Ollama `qwen3:4b`; one
  ephemeral contradictory pair returned in about four seconds without changing
  project data.

## [0.3.77] - 2026-08-21

### Added

- A collecting research run can preview and append one explicit user-reviewed
  contradiction relationship between exactly two persisted claims.
- Each append-only relationship stores the selected claim order, the exact
  de-duplicated evidence union derived from both claims, a required
  user-authored note, its own ID, and a timezone-aware audit timestamp.
- Brain, the desktop Research tab, read-only history, committed responses, and
  deterministic Markdown exports expose the persisted relationship.

### Changed

- Research-run schema v9 persists claim contradictions while loading v1-v8
  snapshots with an empty contradiction collection and rewriting them only
  during a later successful atomic save.
- A reversed claim pair is treated as the same relationship, so the same two
  claims cannot receive duplicate contradiction records.

### Safety

- Preview is read-only. Recording requires a separate desktop confirmation and
  final runtime revalidation of the open run, both claims, their evidence, the
  duplicate-pair guard, and atomic persistence.
- Hypatia does not detect contradictions automatically, choose claims or
  evidence, decide truth, rewrite either claim, or grant external source text
  instruction authority.

### Verification

- The package-aware full local suite contains 1,403 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 326 source files.

## [0.3.76] - 2026-08-21

### Added

- The desktop now separates Chat, Knowledge, Research, and Appearance into
  dedicated tabs so ordinary conversation is not crowded by specialist tools.
- A soft eye-comfort theme is the default, with separate light and high-contrast
  choices plus the existing 10-to-20-point text-size controls.
- Empty session lists, unavailable session data, the conversation transcript,
  and the message composer now provide concise guidance instead of blank space.

### Changed

- Session, recall, knowledge, and research controls use clearer labels and more
  compact grouped layouts. Session actions share consistent widths, and the
  message composer advertises its `Ctrl+Enter` shortcut.
- Tkinter uses a style backend and explicit active, focused, disabled,
  read-only, selection, border, and scrollbar colors so native Windows widgets
  remain readable in every supported theme.

### Accessibility

- The default palette avoids pure black and pure white while retaining visible
  focus and selection states. High contrast remains an explicit opt-in mode.
- Theme and text-size changes remain presentation-only: they do not invoke a
  provider or change conversation, session, memory, knowledge, or research
  state.

### Verification

- The package-aware full local suite contains 1,388 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 322 source files.

## [0.3.75] - 2026-08-21

### Added

- Research runs can store explicit user-authored claims with one epistemic
  state: `fact`, `strong_evidence`, `likely`, `hypothesis`, `speculation`,
  `unknown`, or `contradicted`.
- Every claim cites persisted evidence IDs and the exact ordered accepted
  source IDs derived from that evidence. It also carries one categorical
  authored confidence label: `unassessed`, `low`, `medium`, or `high`.
- The Brain, desktop, and deterministic Markdown export expose claim history
  through read-only previews and a separate preview-confirm-record boundary.

### Changed

- Research-run schema v8 persists evidence-linked claims while loading v1-v7
  snapshots with an empty claim collection and rewriting them only during a
  later successful atomic save.
- Claim corrections append a backward supersession link. The predecessor
  remains immutable and can have at most one successor.

### Safety

- Hypatia does not extract claims automatically, select their evidence,
  calculate truth, or turn authored confidence into a numeric score.
- Final recording revalidates the collecting run, every evidence/source
  relationship, categorical values, and any supersession target. External
  source text retains instruction authority `none` regardless of claim state.

### Verification

- The package-aware full local suite contains 1,384 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 322 source files.

## [0.3.74] - 2026-08-21

### Added

- User-authored source assessments can carry one explicit information-trust
  label: `unassessed`, `low`, `medium`, or `high`.
- Accepted external sources persist the fixed taint label
  `external_untrusted_data` and fixed instruction authority `none`.
- The desktop assessment preview-confirm flow, source comparison, committed
  response, and deterministic Markdown export display the new trust metadata.

### Changed

- Research-run schema v7 stores source taint, instruction authority, and
  assessment information trust while loading v1-v6 snapshots with safe
  defaults and rewriting them only during a later successful atomic save.
- Assessment corrections may replace an earlier authored information-trust
  label through the existing append-only supersession link; the original audit
  record remains immutable.

### Safety

- Information trust describes the user's assessment of source content only.
  It never grants an external source instruction authority, tool access, or
  permission to override trusted code-owned instructions.
- Hypatia does not calculate the label, choose evidence, or convert it into an
  automatic truth, credibility, or execution score. Invalid labels and any
  attempt to elevate source authority fail closed before persistence.

### Verification

- The package-aware full local suite contains 1,366 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 316 source files.

## [0.3.73] - 2026-08-21

### Added

- A thread-safe, one-way cancellation signal can travel with an in-process
  `BrainRequest` without appearing in its representation or equality contract.
- Desktop Crossref discovery, explicit HTTPS source loading, and confirmed
  candidate loading now attach that signal to their existing Brain request.

### Changed

- Research discovery checks cancellation before provider access, after the
  bounded network call returns, after provider-contract validation, and before
  discovery persistence.
- Research source loading checks cancellation before acquisition, after the
  bounded fetch returns, and immediately before knowledge indexing begins.

### Safety

- A cancelled network result creates no discovery, failure audit, knowledge
  document, accepted-source record, or content-store write. A provider call
  already in progress is still bounded by its timeout and is never forcefully
  terminated.
- Desktop result suppression remains valid even if an optional cooperative
  callback fails. Closing the window signals cooperative cancellation and
  continues to discard late presentation results.
- Other LLM and desktop actions retain presentation-only cancellation; this
  release does not claim that every provider path can stop between stages.

### Verification

- The package-aware full local suite contains 1,362 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 315 source files.

## [0.3.72] - 2026-08-21

### Added

- The desktop status line reports elapsed whole seconds for the one active
  request without inventing a completion percentage or provider stage.
- A dedicated `Cancel request` control lets the user discard the active
  request's eventual value or error presentation.

### Safety

- Cancellation never claims to terminate an in-flight Ollama or HTTPS call.
  Normal command controls remain disabled until that bounded operation returns,
  and the late result is then replaced with one generic cancelled completion.
- A completed-but-undrained result retains the single-flight reservation, so a
  keyboard submission cannot replace its presentation handler before the
  Tkinter event thread consumes it.
- Closing the window still rejects new work and discards every late completion;
  provider and transport timeouts remain the hard bound on active I/O.

### Verification

- The package-aware full local suite contains 1,357 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.71] - 2026-08-21

### Added

- LLM providers accept one optional, trusted per-request system instruction
  without changing ordinary conversation calls or persisted configuration.
- Explicit `ask knowledge` requests use a code-owned system instruction that
  treats every retrieved source excerpt as untrusted evidence rather than an
  instruction.

### Changed

- The explicit user question is separated from bounded source excerpts, and
  every supplied excerpt is visibly labelled `UNTRUSTED SOURCE` before it is
  sent to the configured model.

### Safety

- Retrieved text is told that it has no authority to change roles or rules,
  reveal secrets, request tools or files, or override other instructions. The
  local-RAG path still receives no tool capability and uses no conversation
  history.
- This is a prompt-level instruction-authority boundary, not a claim that a
  language model can never be influenced by adversarial text. Existing source,
  response-size, transport, and user-initiation limits remain in force.

### Verification

- The package-aware full local suite contains 1,353 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.70] - 2026-08-21

### Changed

- Explicit desktop chat, semantic recall, cited knowledge questions, research
  discovery, and approved HTTPS source loading now run through one daemon
  request worker instead of holding the Tkinter event thread.
- Tkinter polls completed responses and performs every widget update on its own
  event thread. All command buttons are disabled while the single request is
  active, and a second keyboard submission is rejected instead of queued.
- Text entered in the composer while a response is pending is preserved; only
  the exact submitted text is cleared after its response is presented.

### Safety

- Window close stops accepting work, discards late results, and destroys the UI
  without forcefully terminating the provider call. Existing provider and
  transport timeouts remain the hard bound on that daemon operation.
- Expected input-validation errors remain visible. Unexpected worker,
  provider, and presentation exceptions produce one generic desktop failure
  without exposing internal transport or credential details.

### Verification

- The package-aware full local suite contains 1,350 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.69] - 2026-08-21

### Changed

- Semantic add, update, delete, and expiry maintenance now uses the same daemon
  single-worker boundary as full rebuilds. A successful primary-memory write
  returns without waiting for the local embedding provider.
- Pending incremental work is bounded to 20,000 memory IDs and deterministically
  coalesces repeated events so the last operation for one record wins.
- `semantic recall status` reports `updating` while incremental work is active;
  semantic queries use lexical fallback until the worker is idle.

### Safety

- Per-record generations reject an embedding result superseded by a later
  update or delete. A queued full rebuild runs after any in-flight incremental
  provider call and replaces queued updates from one fresh memory snapshot.
- Failed or rejected record IDs retain the generic incremental diagnostic until
  that record is successfully reconciled or a complete rebuild succeeds.
  Shutdown clears queued work and suppresses in-flight publication.

### Verification

- The package-aware full local suite contains 1,341 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.68] - 2026-08-21

### Changed

- Opt-in semantic-index initialization now starts as one daemon background job
  after Bootstrap publishes the primary dependency container. A cold or
  unavailable Ollama service no longer holds the primary startup path.
- `semantic recall status` now reports `initializing`, `refreshing`, `ready`,
  `unavailable`, `disabled`, or `stopped` without generating an embedding.
- The exact `semantic recall retry` command schedules the same bounded
  background rebuild and reports an already-running job without starting a
  duplicate. Semantic queries use deterministic lexical fallback while a
  rebuild is active.

### Safety

- Full rebuilds are single-flight. Memory events during a build mark its
  snapshot dirty and permit at most one coalesced retry; a second changing
  snapshot is rejected without publishing a partial or stale index.
- Shutdown rejects new semantic work, signals the builder to cancel, and
  suppresses index publication from in-flight work. Cancellation is checked
  after provider calls and before derived-cache replacement; the provider call
  itself remains bounded by the existing request and shared rebuild deadlines.

### Verification

- The package-aware full local suite contains 1,334 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.
- A temporary-data live smoke check against local Ollama
  `embeddinggemma:latest` built one 768-dimensional record through the
  background worker and returned it through explicit semantic recall.

## [0.3.67] - 2026-08-21

### Changed

- Full semantic-index rebuilds now share one monotonic 120-second deadline by
  default. `HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS` accepts a positive
  finite override through 3,600 seconds.
- Each missing embedding receives only the time remaining in the shared rebuild
  budget. The Ollama transport uses the shorter of that remainder and its
  configured per-request timeout, so a rebuild cannot renew the full request
  timeout for every sequential cache miss.

### Safety

- The shared deadline begins before memory, source, and cache preflight work.
  Expiry before or after a provider call rejects the incomplete build before
  cache replacement or runtime publication.
- A cache-preflight overrun skips all provider work. A failed startup remains
  semantically unavailable, while a failed later rebuild or explicit retry
  preserves the last complete index and exposes only the existing safe rebuild
  diagnostic.

### Verification

- The package-aware full local suite contains 1,324 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.66] - 2026-08-21

### Changed

- An initial optional semantic-index failure no longer stops primary Bootstrap.
  Hypatia publishes its normal dependency container, attaches the semantic
  lifecycle listener, and keeps conversation, sessions, lexical recall, and
  primary memory available while semantic retrieval is unavailable.
- `semantic recall status` now distinguishes `unavailable` from `disabled` and
  reports separate safe full-rebuild and incremental-update diagnostics.
- An exact `semantic recall retry` request explicitly retries one complete
  rebuild through the existing source, cache, index, and provider-call bounds.

### Safety

- Rebuild failures retain the last complete index, record only the generic
  `Semantic index rebuild failed.` diagnostic, and never expose provider,
  cache, transport, or budget details through status or retry responses.
- Retry is never automatic and does not run for ordinary chat, recall, status,
  or memory events. A failed retry leaves either the previous complete index
  available or the runtime safely unavailable without changing primary memory.

### Verification

- The package-aware full local suite contains 1,317 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.65] - 2026-08-21

### Changed

- Cold semantic-index rebuilds now allow at most 256 embedding-provider calls
  by default. `HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS` can set an
  explicit whole-number budget from 0 through the 20,000-entry index limit;
  zero permits only empty or fully cached rebuilds.
- Rebuilds resolve the complete provider-scoped cache view before any network
  work. Exact-budget misses are embedded in deterministic memory-record order,
  the cache is replaced only after the full build succeeds, and the live index
  is published only after the builder returns a complete replacement.

### Safety

- A rebuild whose cache misses exceed its budget fails before the first
  provider call, cache replacement, or runtime publication. Cache-read failure
  is attempted once and conservatively treats the whole rebuild as uncached.
- A valid foreign-provider cache snapshot is retained as an in-memory empty
  provider view, preserving isolation without repeatedly reading or decoding
  the same file for every active memory record.

### Verification

- The package-aware full local suite contains 1,312 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.64] - 2026-08-21

### Changed

- Embedding source text is capped at 1,000,000 characters across full rebuilds,
  incremental updates, direct semantic queries, and the Ollama provider.
- Outbound Ollama embedding JSON is capped at 8 MiB of exact compact UTF-8.
  A bounded writer streams serialization into the request body without first
  constructing a complete JSON string.

### Safety

- Full rebuilds validate every active source before cache lookup or provider
  work. Oversized semantic queries skip the provider and retain deterministic
  lexical fallback behavior.
- Oversized, recursive, or non-serializable request payloads fail before the
  network opener is called. Turkish and other Unicode input remains exact and
  is sent without ASCII escape expansion.

### Verification

- The package-aware full local suite contains 1,306 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.63] - 2026-08-21

### Changed

- Every `Embedding` is capped at 16,384 finite values. The derived live semantic
  index accepts at most 20,000 entries, 1,024 characters per memory ID, and
  4,000,000 aggregate vector values.
- Full index rebuilds reject excessive record populations before provider work
  and reject an excessive aggregate after the first dimension is established.
  Ollama responses reject oversized raw vectors before constructing a second
  normalized representation.
- Cosine ranking now uses overflow-safe norms and normalized summation, keeping
  scores finite and within `[-1.0, 1.0]` even for very large finite values.

### Safety

- Rejected incremental updates preserve the last complete live index and do not
  add the rejected entry to the optional cache. Primary memory writes remain
  successful and the existing safe semantic-update diagnostic is retained.
- Exact-limit inserts and replacements remain deterministic; failed new-entry
  attempts do not establish a dimension or partially change the live index.

### Verification

- The package-aware full local suite contains 1,302 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.62] - 2026-08-21

### Changed

- The optional schema-v1 semantic embedding cache now accepts at most 20,000
  ordered entries, 1,024 characters per provider key and memory ID, 1,000,000
  characters per source value, 16,384 values per embedding, 4,000,000 values
  across the snapshot, and 64 MiB of complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes before
  publishing the deterministic provider-scoped snapshot.

### Safety

- Oversized collections, fields, and vectors are rejected before entry parsing,
  hashing, or serialization. Embedding dimensions must remain consistent within
  one provider cache, while a valid foreign-provider snapshot remains isolated
  without parsing its entries.
- Invalid candidates, oversized output, and failed replacements preserve the
  previous on-disk snapshot and in-memory entries and clean partial temporary
  files.

### Verification

- The package-aware full local suite contains 1,296 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.61] - 2026-08-21

### Changed

- The schema-v1 general memory snapshot now accepts at most 20,000 ordered
  records, 1,024 characters per memory ID, 1,000,000 characters per content
  value, and 64 MiB of complete UTF-8 JSON.
- Snapshot-wide metadata is capped at 100,000 top-level entries and 8 MiB of
  compact UTF-8 JSON. Tags are capped at 100,000 total values and 256
  characters per value.
- Reads consume at most one byte beyond the physical limit before decoding;
  atomic writes count exact UTF-8 bytes before publication.

### Safety

- Oversized collections and fields are rejected before record parsing or
  serialization, boolean schema values are not coerced to schema v1, and
  recursive or non-serializable metadata fails before a temporary write.
- Invalid save candidates, duplicate IDs, timezone-naive timestamps, failed
  replacements, and oversized output preserve the previous memory snapshot and
  clean partial temporary files.

### Verification

- The package-aware full local suite contains 1,287 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.60] - 2026-08-21

### Changed

- The schema-v1 session registry now accepts at most 20,000 ordered sessions,
  1,024 characters per session ID, and 64 MiB of complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes in the
  temporary file before publication.

### Safety

- Oversized files are not decoded, excessive session collections and IDs are
  rejected before record parsing or serialization, and boolean schema values
  are not coerced to schema v1.
- Failed or oversized writes preserve the previous registry and clean partial
  temporary files. Session order and the default/active-session invariants
  remain unchanged.

### Verification

- The package-aware full local suite contains 1,277 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.59] - 2026-08-21

### Changed

- The explicit knowledge-relation schema-v1 snapshot now accepts at most 20,000
  ordered relations, 1,024 characters per endpoint document ID, and 64 MiB of
  complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes in the
  temporary file before publication.

### Safety

- Oversized files are not decoded, excessive collections and endpoint IDs are
  rejected before record parsing or serialization, and boolean schema values
  are not coerced to schema v1.
- Failed or oversized writes preserve the previous relation snapshot and clean
  partial temporary files. Relation order, duplicate rejection, graph rollback,
  and schema v1 remain unchanged.

### Verification

- The package-aware full local suite contains 1,272 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.58] - 2026-08-21

### Changed

- The accepted-source content store now reads at most its 40,000,000-byte
  physical limit plus one detection byte directly from the opened descriptor
  before JSON decoding.
- Atomic writes stream JSON through an exact UTF-8 byte counter instead of
  constructing a second complete serialized snapshot in memory.

### Safety

- The existing schema-v1, 64-record, 32,000,000-content-byte, SHA-256, rollback,
  and atomic replacement contracts are unchanged.
- Oversized input is never decoded. Oversized or incomplete temporary output is
  not published, the previous snapshot is preserved, and partial files are
  removed.

### Verification

- The package-aware full local suite contains 1,267 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.57] - 2026-08-21

### Changed

- Research-run schema v6 now limits the complete UTF-8 JSON snapshot to 64 MiB
  and all nested collection entries to an aggregate 20,000 items.
- Reads consume at most one byte beyond the physical limit before JSON decoding.
  Writes count exact UTF-8 bytes while producing the temporary snapshot and
  stop before atomically replacing the current file.

### Safety

- Oversized input is rejected before decoding, and oversized in-memory
  collections are rejected before record parsing or serialization.
- Failed bounded writes preserve the previous snapshot and remove partial
  temporary files. Schema v1-v6 compatibility and successful atomic replacement
  remain unchanged.

### Verification

- The package-aware full local suite contains 1,265 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.56] - 2026-08-21

### Added

- A bounded read-only evidence integrity auditor compares persisted research
  evidence with the current accepted-content paragraphs by document, paragraph
  position, opaque identity, and exact-content SHA-256.
- Brain and the desktop expose an explicit `Evidence integrity` action that
  reports only recorded, matched, missing, and changed aggregate counts.

### Safety

- The audit is limited to 20,000 runs, evidence records, and indexed chunks.
  Ambiguous or oversized state returns a safe unavailable result.
- Audit requests use only already validated in-memory runs and chunks. They do
  not read or write persistence, access the network, invoke an LLM, mutate
  memory or knowledge, reveal content, paths, IDs, hashes, or repair records.

### Verification

- The package-aware full local suite contains 1,258 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.55] - 2026-08-21

### Changed

- Paragraphs indexed for an explicitly selected persistent research run now
  receive an opaque versioned identity derived from document ID, paragraph
  position, and exact-content SHA-256.
- Startup restoration opts into the same identity contract, so evidence
  recorded after this release can resolve the same accepted paragraph after a
  restart.

### Safety

- Temporary or run-free knowledge parsing retains its existing ephemeral
  identity behavior. Research-run and content-store schemas are unchanged.
- Existing evidence records are not rewritten, remapped, deleted, or migrated.
  A changed paragraph receives a different identity rather than silently
  inheriting an old evidence locator.

### Verification

- The package-aware full local suite contains 1,246 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 306 source files.

## [0.3.54] - 2026-08-21

### Added

- Bootstrap now captures an immutable accepted-content restoration status after
  startup validation, including only availability plus restored document and
  paragraph counts.
- Brain and the desktop expose that captured snapshot through an explicit
  read-only `Research content` action.

### Safety

- Status requests never read or write the content store, refetch a source,
  invoke an LLM, mutate memory, or change the knowledge index. An engine without
  a captured startup status reports a bounded unavailable state.
- The response excludes content, source metadata, paths, hashes, record IDs,
  and internal error details. Existing fail-closed startup validation remains
  unchanged.

### Verification

- The package-aware full local suite contains 1,243 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 306 source files.

## [0.3.53] - 2026-08-21

### Added

- Bootstrap now restores accepted research source content into the existing
  in-memory knowledge index after both the research-run and content snapshots
  have been fully validated.
- A dedicated `ResearchSourceContentRestorer` reconciles stable document ID,
  final URL, title, content type, and fetch time against accepted run
  provenance before constructing any knowledge document.

### Safety

- Orphaned content, conflicting run provenance, mismatched metadata,
  noncanonical text, or a document ID that does not match the stable URL-derived
  identity fails closed before indexing. Historical run provenance without a
  content record remains valid but cannot be restored.
- Restoration requires an empty startup index, performs no persistent writes or
  network requests, and is bounded to 20,000 paragraphs across the validated
  snapshot. An unexpected indexing failure clears every document added during
  that attempt before startup reports a controlled research error.
- Startup does not refetch, repair, delete, migrate, or quarantine either
  snapshot and does not invoke an LLM or change the research-run schema.

### Verification

- The package-aware full local suite contains 1,236 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 303 source files.

## [0.3.52] - 2026-08-21

### Changed

- A research source accepted into a selected collecting run now saves its exact
  extracted text to the separate schema-v1 content store after knowledge
  indexing and before research provenance is published.
- Bootstrap owns and registers the content store. Installed Windows and Linux
  desktop runtimes place it at `research/content.json` beneath the existing
  user-writable data root.

### Safety

- Content loading, validation, record construction, and atomic snapshot writing
  are part of the source-acceptance transaction. Failure removes the new
  unlinked knowledge document and publishes no accepted-source provenance.
- If provenance persistence fails after content is saved, Hypatia first
  restores the exact prior content collection and independently attempts to
  remove the new knowledge document. Controlled responses distinguish partial
  rollback failures without exposing source content or storage details.
- Direct source loads without a research run retain their existing in-memory
  behavior. Startup content restoration, refetch, crawling, LLM calls, and
  research-run schema changes remain outside this increment.

### Verification

- The package-aware full local suite contains 1,227 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 301 source files.

## [0.3.51] - 2026-08-21

### Added

- A separate `ResearchSourceContentRecord` contract binds one explicitly
  accepted source's exact extracted text to document ID, URL, title, content
  type, fetch/storage times, complete UTF-8 byte count, and SHA-256.
- A replaceable `ResearchSourceContentStore` boundary and strict schema-v1 JSON
  implementation can load or atomically replace the complete ordered content
  snapshot. Missing storage reads as an empty collection.

### Safety

- One record is limited to 4 MB of UTF-8 content. A snapshot is limited to 64
  unique document IDs/URLs, 32 MB of total content, and a 40 MB serialized file.
  Oversized files are rejected before JSON parsing.
- Loading revalidates exact fields, schema type/version, timezone-aware and
  ordered timestamps, byte count, and content fingerprint. Unknown fields,
  duplicate IDs/URLs, tampering, malformed Unicode, and stale fingerprints fail
  before a record is returned.
- Writes serialize and validate the complete snapshot before creating a
  same-directory temporary file, flush and fsync it, then atomically replace the
  destination. A failed replace preserves the prior snapshot and removes the
  temporary file.
- This release does not wire the store into Bootstrap, source acceptance, Brain,
  or desktop startup. It performs no automatic restore, refetch, indexing, or
  migration and does not change the research-run schema.

### Verification

- The package-aware full local suite contains 1,221 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 301 source files.

## [0.3.50] - 2026-08-21

### Changed

- The shared pinned HTTPS transport now carries the complete ordered set of
  public addresses from one DNS validation into the connection boundary.
- If an address fails during TCP or TLS setup, the transport closes that socket
  and tries the next already validated address exactly once. It never performs
  a new resolution while selecting a connection target.
- All address attempts and TLS handshakes share one decreasing connection-time
  budget. Exhausting that budget stops further attempts, and a successful TLS
  socket receives only the remaining timeout.

### Safety

- Every attempt retains hostname-based TLS SNI and certificate verification.
  Proxy tunnels remain rejected, address order remains deterministic, and
  complete failure returns one controlled message without address-specific
  transport details.
- The fallback applies to the existing explicit page loader and fixed Crossref
  metadata provider only; it adds no crawling, automatic acceptance, provider
  expansion, LLM call, or persistence.

### Verification

- Tests cover first-address TLS failure with second-address success, failed
  socket cleanup, ordered attempts, a decreasing shared deadline, deadline
  exhaustion before an untried address, and safe all-address failure.
- The package-aware full local suite contains 1,212 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 296 source files.
- Live bounded page acquisition and one-result Crossref metadata discovery both
  completed through the multi-address transport.

## [0.3.49] - 2026-08-21

### Security

- Address-pinned HTTPS connection and TLS handling now live in one shared
  research transport boundary instead of inside the explicit page fetcher.
- The fixed Crossref REST v1 discovery provider uses that boundary for its
  initial request and every same-origin redirect. It validates that the exact
  HTTPS origin and `/v1/works` path are retained, requires public-only DNS
  answers, and connects to an address from the same validation.
- Hostname-based TLS SNI, certificate verification, disabled system proxies,
  ten-second timeout, 500 KB JSON limit, and explicit-only discovery remain
  unchanged. No general search, crawling, or automatic acceptance is added.

### Verification

- Offline tests cover exact Crossref destination resolution, public-address
  propagation, private-address rejection, and wrong-origin rejection.
- The package-aware full local suite contains 1,209 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 296 source files.
- A live one-result Crossref metadata query completed through the shared pinned
  transport without fetching or accepting the returned paper.

## [0.3.48] - 2026-08-21

### Security

- The standard public-HTTPS research source fetcher now carries the exact
  validated public DNS address into its TCP connection instead of resolving
  the hostname again inside the transport. This closes the previously
  documented DNS-rebinding gap for explicit source acquisition.
- TLS still authenticates the normalized URL hostname with certificate and
  hostname verification enabled; the pinned IP address never replaces the
  HTTP host or TLS server name.
- Every redirect destination is normalized, resolved, and checked for public
  addresses again before its separate connection is pinned. Proxy tunnels
  remain rejected and the default source-fetch path still ignores system
  proxy configuration.

### Verification

- Tests prove exact address-to-socket propagation, hostname-based TLS,
  certificate-verification settings, proxy-tunnel rejection, and independent
  redirect resolution.
- The package-aware full local suite contains 1,206 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 295 source files.
- A live bounded acquisition of `https://example.com/` completed through the
  pinned default transport without changing the explicit-only research scope.

## [0.3.47] - 2026-08-21

### Added

- The desktop adds a separate `Verify export` action for one explicitly
  selected terminal research run and existing local `.md` file.
- Brain asks the research manager to re-render the current immutable run and
  compare its complete UTF-8 byte count and SHA-256 with the selected file.
  Both exact values and an honest `MATCH` or `DOES NOT MATCH` result are returned
  in a structured verification response.
- Verification hashes the selected file as a stream from one open descriptor
  and confirms that its identity, size, modification time, and change time stay
  stable through the read.

### Safety

- Verification accepts only an absolute `.md` path resolving to a regular file.
  Relative paths, wrong extensions, directories, missing files, collecting
  runs, mid-read changes, and unexpectedly large inputs are rejected.
- Unexpected local input is bounded to 64 MiB; a legitimate deterministic
  export larger than that remains verifiable up to its exact expected byte
  length. The complete accepted file is hashed rather than decoded or parsed.
- A mismatch is a successful read-only result, not an import or repair action.
  No file, research record, memory, graph, live index, or event is changed, and
  no provider, network, or LLM call occurs.

### Verification

- The package-aware full local suite contains 1,201 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 295 source files.

## [0.3.46] - 2026-08-21

### Added

- The desktop now offers a separate `Save export` action after a successful
  terminal-run Markdown preview. The user chooses the destination and confirms
  the exact path and full-content SHA-256 before the final request.
- The final Brain request carries the preview's run ID, timezone-aware snapshot
  update time, full-content fingerprint, and explicit destination path. The
  research manager re-renders persisted state under its lock and revalidates
  both snapshot identity values before any filesystem operation.
- Successful saves return a structured result containing the run ID, immutable
  snapshot time, absolute destination, byte count, and verified SHA-256.

### Safety

- Exports require an absolute `.md` destination inside an existing directory.
  Relative paths, other extensions, missing directories, collecting runs,
  malformed metadata, and stale preview identities are rejected before a
  destination is published.
- Complete UTF-8 bytes are written to a temporary file in the selected
  directory, flushed, and atomically linked to the final name. An existing
  destination is never replaced, including when it appears between selection
  and publication; temporary-file cleanup is attempted after success or
  failure.
- Saving performs no provider, network, LLM, memory, graph, live-index, event,
  or research-audit mutation. Controlled failures do not expose internal
  filesystem errors.

### Verification

- The package-aware full local suite contains 1,187 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 293 source files.

## [0.3.45] - 2026-08-21

### Added

- One explicitly selected terminal research run can be rendered as a
  deterministic, read-only Markdown export preview from its immutable persisted
  snapshot.
- The export includes run identity and lifecycle, accepted-source provenance,
  bounded evidence excerpts and user notes, complete assessment history with
  current/superseded labels, comparison notes, and safe failure records in
  persisted order.
- The desktop adds `Export preview` beside the existing terminal-status action.
  It requires only the selected run ID and passes no destination path.
- The Linux verification workflow now derives its archive name from package
  metadata so each release receives a correctly versioned build artifact.
- The preview carries the exact snapshot update time, a sanitized suggested
  filename, complete character count, omitted character count, and SHA-256 of
  the full deterministic Markdown content for a later revalidating save flow.

### Safety

- Collecting runs cannot be exported. The preview performs no file write,
  provider or network request, LLM call, live knowledge lookup, event
  publication, graph change, or conversation-memory mutation.
- Display is bounded to 24,000 source characters with an explicit omitted
  count. The SHA-256 still describes the complete content rather than the
  bounded display.
- Persisted remote excerpts and user-authored text are rendered as escaped
  block quotes so headings, raw HTML, image references, and Markdown control
  characters remain literal report data instead of active document structure.
  ASCII controls and directional-override characters are made visible rather
  than retained as hidden display instructions.
- Suggested filenames are reduced to a bounded basename and cannot carry a
  directory separator. No document is saved in this release.

### Verification

- The package-aware full local suite contains 1,174 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 291 source files.

## [0.3.44] - 2026-08-21

### Added

- The installed Linux desktop now has direct tests for its XDG data-directory
  contract: an absolute `XDG_DATA_HOME` resolves beneath `hypatia`, while an
  absent or invalid relative value falls back to `~/.local/share/hypatia`.
- `tools/build_desktop.sh --clean` creates a pinned PyInstaller onedir package
  at `dist/Hypatia/Hypatia` from the same desktop entry point used on Windows.
- `tools/smoke_desktop_linux.sh` starts the packaged Tkinter application under
  Xvfb with a temporary explicit data root and verifies local session-state
  initialization without leaving user data behind.
- A least-privilege GitHub Actions workflow runs the full suite, builds and
  smoke-tests the desktop on Ubuntu 24.04 x64, then publishes a bounded-retention
  Linux archive artifact. Third-party actions are pinned to exact commits.
- ADR 0003 records the Ubuntu 24.04 x64 package, XDG storage, manual-update,
  no-telemetry, no-bundled-credential, and supported-platform boundaries.

### Changed

- POSIX absolute-path validation now uses POSIX path semantics even when the
  platform behavior is exercised from a Windows test host. Windows data paths
  and the absolute `HYPATIA_DESKTOP_DATA_DIR` override remain unchanged.

### Verification

- The package-aware full local suite contains 1,162 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 287 source files.
- The Linux package build and packaged startup smoke check are verified by the
  Ubuntu workflow before release rather than inferred from Windows behavior.

## [0.3.43] - 2026-08-21

### Added

- A collecting research run can preview and separately append one
  user-authored comparison note for two to five explicitly ordered accepted
  sources.
- Each note cites exact persisted evidence IDs and exact current assessment
  IDs. Every selected source must be covered by both reference types, and every
  cited assessment's evidence must also be cited explicitly.
- The existing comparison preview is the read boundary after restart: it shows
  matching notes for the exact selected source order, bounded to 20 notes while
  reporting the complete count.
- Research-run schema v6 stores comparison notes append-only and loads v1-v5
  snapshots with an empty comparison-note collection until a later successful
  mutation rewrites the snapshot.

### Safety

- Preview performs no write. Confirmed recording revalidates the open run,
  accepted sources, evidence ownership, current assessments, assessment
  evidence, and complete per-source coverage before atomically replacing the
  research snapshot.
- Hypatia does not generate the note, choose references, score sources, produce
  a verdict, call an LLM or provider, fetch content, write conversation memory,
  or change knowledge and graph state through this flow.
- Existing notes remain immutable when a cited assessment is corrected later;
  the correction is appended separately and historical note references remain
  intact.

### Verification

- The package-aware full local suite contains 1,158 passing automated tests.

## [0.3.42] - 2026-08-20

### Added

- A read-only manual comparison preview now accepts an ordered selection of two
  to five unique sources already accepted into the same research run.
- Each comparison column shows persisted source provenance, only evidence the
  user explicitly selected for that source, and only current user-authored
  assessments. Superseded assessment text remains in the audit history but is
  not presented as current comparison material.
- The desktop adds a comma-separated `Comparison source IDs` field and an
  explicit `Compare sources` action. The preview remains available after a run
  reaches a terminal status.

### Security

- Comparison validates the exact run and every source ID before rendering. It
  rejects missing, duplicate, unaccepted, cross-run, or out-of-bounds source
  selections and preserves the caller's explicit order.
- The preview performs no network, discovery, fetch, LLM, memory, graph,
  knowledge-index, event-bus, or persistence operation. It assigns no verdict,
  trust score, or automatic evidence selection.
- Comparison rendering is bounded to the first 20 persisted evidence records
  and first 10 current assessments per selected source. It reports complete and
  displayed counts so large valid histories remain honest without generating
  an unbounded desktop response.

### Verification

- The package-aware full local suite contains 1,142 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 284 source files.

## [0.3.41] - 2026-08-20

### Added

- A new user-authored source assessment may explicitly supersede one earlier
  assessment from the same research run and accepted source. The earlier record
  remains intact and the new immutable record stores its exact predecessor ID.
- Assessment preview, confirmation, committed response, and read-only history
  now show the optional supersession link. History marks records as `current`
  or `superseded` without deleting or rewriting either record.
- The desktop adds an optional `Supersedes assessment ID` field to the existing
  preview-confirm-save flow.

### Security

- Preview and final recording independently reject missing, cross-source, or
  already superseded targets. A target must appear earlier in the same run and
  may have only one direct successor, preventing forks and cycles.
- Corrections remain user-authored, collecting-run-only, evidence-explicit,
  append-only, and atomically persisted. They invoke no network, provider, LLM,
  memory, graph, or event-bus side effect.
- Research-run schema v5 reads v1-v4 snapshots; v4 assessments receive a null
  supersession link and are rewritten only on a later successful atomic save.

### Verification

- The package-aware full local suite contains 1,129 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 281 source files.

## [0.3.40] - 2026-08-20

### Added

- A collecting research run can now persist an append-only, user-authored
  assessment for one accepted source. The record stores the source document
  ID, the exact evidence IDs explicitly entered by the user, bounded assessment
  text, a unique assessment ID, and its timezone-aware recording time.
- The desktop adds separate assessment-evidence and assessment-text fields plus
  `Preview & save assessment`. It displays the runtime preview and requests
  confirmation before sending a distinct record request.
- The accepted-source assessment view now includes the source's persisted
  authored-assessment history after restart.

### Security

- Preview performs no write. Final recording revalidates the exact run, accepted
  source, and every evidence ID; missing, cross-source, duplicate, or closed-run
  selections are rejected before persistence.
- The assessment is user-authored and evidence selection is explicit. Hypatia
  assigns no automatic trust, credibility, relevance, support, or quality score
  and invokes no source fetcher, discovery provider, LLM, memory, graph, or
  event-bus side effect.
- Research-run schema v4 reads v1-v3 snapshots with missing collections treated
  as empty and upgrades only on a later successful atomic save.

### Verification

- The package-aware full local suite contains 1,121 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 281 source files.

## [0.3.39] - 2026-08-20

### Added

- One accepted source can now be selected by exact run and document ID for a
  read-only manual-assessment preview. The preview displays persisted
  provenance and only evidence records explicitly selected by the user for
  that source.
- The desktop includes a separate source-document field and `Preview
  assessment` action. A successful attached-source load selects its returned
  document ID for this view without invoking the preview automatically.

### Security

- Assessment rejects unknown, unaccepted, or cross-run document IDs and never
  consults the live knowledge index, source fetcher, LLM, conversation memory,
  event bus, or graph.
- Missing evidence is reported honestly: no trust, credibility, relevance, or
  quality score is inferred. The read-only view remains available for terminal
  research runs and performs no persistence write.

### Verification

- The package-aware full local suite contains 1,103 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 278 source files.

## [0.3.38] - 2026-08-20

### Added

- A discovered source candidate now has a read-only acceptance preview that
  proves the exact run, discovery record, and persisted candidate URL before
  any source content is fetched.
- The desktop adds `Preview & load`: it displays the runtime decision, asks for
  explicit confirmation only when allowed, and then sends a separate acceptance
  request through the existing guarded public-HTTPS source loader.

### Security

- Final acceptance revalidates the candidate against current persisted run
  state. Unknown discoveries, unlisted or stale URLs, and closed runs are
  rejected before network access.
- Preview performs no network, indexing, LLM, graph, or conversation-memory
  operation. Existing source-audit failure rollback remains authoritative.

### Verification

- The package-aware full local suite contains 1,091 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in an isolated local tool
  environment.

## [0.3.37] - 2026-08-20

### Added

- The packaged process-environment runtime now enables an explicit Crossref
  REST v1 scholarly-metadata discovery provider by default. It can be disabled
  with `HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER=disabled`.
- The desktop can discover up to five candidates for the selected collecting
  run, display their title and DOI URL, and copy one explicitly selected URL
  into the separate source-load field.

### Security

- Crossref discovery is restricted to the fixed `api.crossref.org` HTTPS
  endpoint and same-origin redirects, does not inherit proxy settings, accepts
  only JSON, reads at most 500 KB, and uses a ten-second timeout.
- Discovery retrieves bibliographic metadata only. Selecting a candidate does
  not fetch, trust, accept, index, cite, or write it to conversation memory.
  A candidate from a different run cannot be copied through the desktop view.

### Verification

- The package-aware full local suite contains 1,079 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.36] - 2026-08-20

### Added

- A replaceable source-discovery provider boundary can return at most five
  ordered HTTPS metadata candidates for an explicit collecting research run.
- Every successful discovery is atomically stored with its query, provider
  identity, timestamp, ordered title/URL/snippet metadata, and a unique audit
  ID. Empty result sets remain auditable.
- Brain and the desktop controller expose a structured discovery request
  without accepting, fetching, indexing, or trusting candidate content.

### Changed

- Research-run JSON schema v3 persists discovery records while continuing to
  load v1 and v2 snapshots without eager migration.
- Closed or unknown research runs are rejected before the discovery provider
  is called. Controlled provider failures retain only a bounded safe failure
  reason, and failed snapshot writes do not publish candidate state.

### Verification

- The package-aware full local suite contains 1,064 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.35] - 2026-08-20

### Added

- Research runs now have explicit `collecting`, `completed`, `failed`, and
  `cancelled` lifecycle states. A completed run requires at least one accepted
  source and one evidence record; a failed run requires a failure record;
  cancellation may close an otherwise empty run honestly.
- The desktop uses a read-only preview followed by a separate confirmation for
  every terminal transition. The update revalidates current state before its
  atomic snapshot write.

### Changed

- Terminal research runs are immutable: they cannot accept further sources,
  evidence, or failure records, and they cannot transition to a different
  status. A source request for a closed run is rejected before network access.

### Verification

- The package-aware full local suite contains 1,047 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.34] - 2026-08-20

### Added

- A user can explicitly select an indexed paragraph from a source already
  attached to a research run and persist it as evidence with a bounded note,
  source/chunk locator, paragraph index, up-to-1,000-character excerpt,
  truncation marker, and SHA-256 fingerprint of the complete paragraph.
- The desktop exposes separate `Save evidence` and read-only `View evidence`
  actions. Evidence recording/listing remains inside the Brain boundary and
  does not call an LLM, write conversation memory, or infer a claim.
- Research-run JSON schema v2 persists evidence and loads v1 snapshots with an
  empty evidence collection, rewriting them as v2 only on the next successful
  save.

### Verification

- The package-aware full local suite contains 1,034 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.33] - 2026-08-20

### Added

- Persistent, versioned research runs now retain the user's original question,
  collecting status, accepted source provenance, safe failure records, and
  timezone-aware creation/update times without duplicating downloaded page
  content.
- The desktop can start a research run, list stored runs, and attach an
  explicitly entered HTTPS source to the selected run. These structured Brain
  actions remain user initiated and do not call an LLM or write conversation
  memory.
- Research-run snapshots use validated atomic JSON replacement under the
  desktop's user-owned local data directory. A failed audit write rolls back a
  newly indexed knowledge document so the two runtime views cannot silently
  diverge.

### Verification

- The package-aware full local suite contains 1,017 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.32] - 2026-08-20

### Added

- The first real internet-research acquisition slice: the desktop can load one
  explicitly entered public HTTPS page into the existing in-memory knowledge
  pipeline with its final URL, title, content type, fetch time, and stable
  source identity preserved.
- External source acquisition is provider-independent and bounded: credentials,
  non-HTTPS URLs, nonstandard ports, private/loopback/link-local DNS answers,
  unsafe redirects, unsupported content types, responses over 1 MiB, and
  unreadable encodings fail before indexing.
- Standard-library HTML extraction removes active and non-readable content and
  keeps readable block text. Plain-text and Markdown HTTPS sources are also
  accepted.

### Verification

- A live bounded fetch of `https://example.com/` returned its final source URL,
  page title, and readable text.
- The package-aware full local suite contains 990 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.31] - 2026-08-20

### Added

- The local desktop shell now offers user-controlled text size from 10 through
  20 points and a high-contrast toggle. These are presentation-only settings:
  they do not persist data, call an LLM, or alter session, memory, or knowledge
  state.

### Changed

- The default LLM system prompt now asks Hypatia for calm, warm, natural
  English responses, including when a user writes in Turkish.

### Verification

- The package-aware full local suite contains 966 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.30] - 2026-08-15

### Added

- The desktop entry point now uses user-writable persistence paths instead of
  an installed application directory: `%LOCALAPPDATA%\Hypatia` on Windows by
  default, with an absolute-only `HYPATIA_DESKTOP_DATA_DIR` override. The
  terminal developer entry point keeps its repository data-path behavior.
- The first Windows desktop packaging path is defined by ADR 0002: a pinned
  PyInstaller `6.21.0` dependency and `tools/build_desktop.ps1` produce an
  inspectable onedir package at `dist/Hypatia/Hypatia.exe`. Updates remain
  manual; the package does not self-update, migrate data, or bundle secrets.

### Verification

- The package-aware full local suite contains 963 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.
- The Windows build script produced `dist/Hypatia/Hypatia.exe` and its bundled
  Tcl/Tk runtime assets. A sandbox policy prevented an automated background GUI
  launch, so this release does not claim an executable-startup smoke test.

## [0.3.29] - 2026-08-15

### Added

- The desktop shell now provides `Load file` for one explicitly selected local
  Markdown (`.md`) or plain-text (`.txt`) source. The selected path reaches
  `KnowledgeEngine` only through a structured Brain request, avoiding command
  parsing of Windows paths. The runtime validates the source before indexing it
  and returns its title, source path, type, chunk count, and stable ID.
- Cancelling selection, an empty path, unsupported/missing/empty files, and an
  already loaded source return controlled outcomes. The load path does not call
  an LLM, write conversation memory, emit a conversation event, or maintain a
  desktop-side source store.

### Verification

- The package-aware full local suite contains 957 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.28] - 2026-08-15

### Added

- The desktop shell now provides `Search this session`, delegating only to the
  existing explicit selected-session conversation search. Empty session IDs and
  queries are rejected locally; successful or empty search responses remain
  read-only and do not change sessions, memory, or provider state.

### Verification

- The package-aware full local suite contains 949 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter session-search
  smoke test pass with the documented project virtual environment.

## [0.3.27] - 2026-08-15

### Added

- The desktop shell now exposes `Preview delete` for a selected session. It
  opens confirmation only when the existing structured runtime preview marks
  deletion allowed; blocked or failed previews cannot show confirmation or
  issue a delete request. A successful delete clears the selection and refreshes
  the session list from Brain.

### Verification

- The package-aware full local suite contains 947 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and real Tkinter allowed/blocked
  session-delete smoke tests pass with the documented project virtual environment.

## [0.3.26] - 2026-08-15

### Added

- The desktop shell now exposes `Preview rename` for the selected session and a
  user-entered replacement ID. It shows the existing transactional runtime
  preview, calls the revalidating rename command only after confirmation, then
  refreshes the session list from Brain after a successful rename. A declined
  or failed preview makes no session or memory change.

### Verification

- The package-aware full local suite contains 946 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm session-rename smoke test pass with the documented project virtual
  environment.

## [0.3.25] - 2026-08-15

### Added

- The desktop shell now exposes `Active links`, delegating only to the existing
  deterministic read-only local source-relation catalog. It reports active
  links and their persistence state without calling an LLM or changing source,
  graph, or conversation-memory state.

### Verification

- The package-aware full local suite contains 941 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter active-links
  smoke test pass with the documented project virtual environment.

## [0.3.24] - 2026-08-15

### Added

- The desktop shell now exposes a `Preview and remove` source-relation flow.
  It delegates first to the existing read-only removal preview, shows that
  exact preview for confirmation, and calls the existing revalidating removal
  command only after approval. Cancellation and a failed preview make no
  relation change.

### Verification

- The package-aware full local suite contains 940 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm relation-removal smoke test pass with the documented project virtual
  environment.

## [0.3.23] - 2026-08-15

### Added

- The desktop shell now exposes a `Preview and link` source-relation flow. It
  first delegates both entered source IDs to the existing read-only runtime
  preview, displays that exact preview for confirmation, and calls the existing
  revalidating apply command only after the user confirms. Cancellation and a
  failed preview make no relation change.

### Verification

- The package-aware full local suite contains 934 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm relation smoke test pass with the documented project virtual
  environment.

## [0.3.22] - 2026-08-15

### Added

- The desktop transcript now renders source records already returned on a
  knowledge response, in their existing order. Each visible citation keeps its
  title, local path, one-based paragraph, and chunk ID; the UI performs no
  additional lookup or citation construction.

### Verification

- The package-aware full local suite contains 928 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter citation-
  rendering smoke test pass with the documented project virtual environment.

## [0.3.21] - 2026-08-15

### Added

- The desktop shell now exposes `Ask sources`, an explicit user-initiated local
  RAG question action. It delegates to the established `ask knowledge` command,
  passes only the entered question, and preserves the runtime's controlled
  unavailable/failure result. It never augments ordinary chat or changes
  conversation memory.

### Verification

- The package-aware full local suite contains 926 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter unavailable-
  runtime `Ask sources` smoke test pass with the documented project virtual
  environment.

## [0.3.20] - 2026-08-15

### Added

- The desktop shell now provides explicit `Knowledge graph` and `Loaded
  sources` actions. They delegate to the existing bounded, cited graph and
  read-only local source-catalog commands; neither action calls an LLM nor
  changes conversation memory or local knowledge state.

### Verification

- The package-aware full local suite contains 924 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter knowledge-view
  smoke test pass with the documented project virtual environment.

## [0.3.19] - 2026-08-15

### Added

- The desktop shell now provides an explicit `Knowledge context` action for a
  user-entered query. It delegates to the existing bounded, cited local context
  command, rejects an empty query locally, and does not call an LLM or change
  conversation memory.

### Verification

- The package-aware full local suite contains 921 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter knowledge-
  context smoke test pass with the documented project virtual environment.

## [0.3.18] - 2026-08-15

### Added

- The desktop shell now has separate user-initiated lexical `Recall` and
  opt-in `Semantic recall` actions. They reject an empty query locally and
  delegate only the explicit existing Brain command; ordinary chat remains
  free of automatic retrieval or prompt augmentation.

### Verification

- The package-aware full local suite contains 919 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter recall-window
  smoke test pass with the documented project virtual environment.

## [0.3.17] - 2026-08-15

### Added

- The desktop shell now provides explicit, read-only actions for the selected
  session's details, five most recent conversations, and first/last activity.
  Each action delegates to the existing Brain command and rejects an empty
  session selection before any runtime call.

### Fixed

- The project virtual environment now uses the complete local Python 3.14
  installation, allowing the documented Tkinter desktop command to create a
  real window instead of failing to locate Tcl/Tk runtime files.

### Verification

- The package-aware full local suite contains 916 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter session-views
  smoke test pass with the documented project virtual environment.

## [0.3.16] - 2026-08-15

### Added

- The desktop shell now refreshes a read-only session overview, displaying the
  ordered session IDs, active-session marker, and conversation counts returned
  through the existing Brain boundary. Selecting a listed ID only fills the
  input; the existing explicit activation action still performs the change.
- `BrainResponse` now carries ordered `SessionSummary` values for existing
  session-list and session-overview responses, so presentation adapters do not
  need to parse formatted text or read session persistence directly.

### Verification

- The package-aware full local suite contains 912 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a Windows Tkinter session-list
  smoke test pass locally.

## [0.3.15] - 2026-08-15

### Added

- The first local Tkinter desktop shell. It starts the existing Hypatia
  application lifecycle and delegates text chat, explicit session selection,
  and read-only semantic-runtime status to the already constructed `Brain`.
- A headless-tested desktop controller prevents empty input locally while
  preserving non-empty conversation text and without creating a second store,
  provider, or network client.

### Verification

- The package-aware full local suite contains 911 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass for the full repository.

## [0.3.14] - 2026-08-15

### Security

- The local Ollama embedding transport now reads at most 1 MiB before JSON
  parsing, rejecting oversized responses before they can consume unbounded
  process memory.

### Verification

- The package-aware full local suite contains 906 passing automated tests.

## [0.3.13] - 2026-08-15

### Security

- The local Ollama embedding transport now rejects HTTP redirects, keeping an
  opted-in semantic request at its validated local endpoint.

### Verification

- The package-aware full local suite contains 905 passing automated tests.

## [0.3.12] - 2026-08-15

### Fixed

- Knowledge loading now rejects a source that is already loaded before parsing
  or indexing it, so a failed duplicate load cannot leave orphaned chunks in
  the search index.

### Verification

- A versioned v2 hybrid semantic-ranking corpus adds Turkish and English query
  cases with explicit expected ordering and relevance rationales. The runtime
  ranking algorithm remains unchanged.
- The package-aware full local suite contains 904 passing automated tests.

## [0.3.11] - 2026-08-15

### Added

- A read-only `semantic recall status` command that makes the opt-in local
  semantic-memory runtime observable without embedding a query or changing
  conversation memory. It reports disabled, initializing, or ready state; a
  ready runtime also reports its index size, embedding dimension, and safe
  latest incremental-update diagnostic.

### Verification

- The package-aware full local suite contains 902 passing automated tests.

## [0.3.10] - 2026-08-15

### Fixed

- Requests that begin with an English or Turkish greeting but contain a
  substantive question now use the normal conversation path instead of being
  reduced to a standalone greeting response.
- Standalone `merhaba` and `selam` greetings now receive a deterministic
  Turkish response.

### Verification

- The package-aware full local suite contains 897 passing automated tests.
- The local Ollama runtime was exercised with a Turkish substantive greeting;
  it reached the LLM conversation path and returned a successful response.

## [0.3.9] - 2026-08-15

### Added

- A validated `HYPATIA_LLM_TIMEOUT_SECONDS` setting for the optional
  OpenAI-compatible chat runtime. It accepts only positive finite seconds.
- A 120-second default for explicitly loopback chat endpoints such as local
  Ollama, while non-local endpoints retain their established 30-second default.

### Safety

- Invalid timeout settings fail during configuration rather than silently
  altering network behavior. The configured value is non-secret and never
  changes the keyless-loopback or remote HTTPS/API-key policy.

### Verification

- The package-aware full local suite contains 893 passing automated tests.

## [0.3.8] - 2026-08-15

### Added

- Keyless chat-runtime activation for explicitly loopback OpenAI-compatible
  endpoints such as local Ollama. In this mode Hypatia deliberately omits the
  `Authorization` header instead of sending an empty bearer token.

### Safety

- Non-local endpoints continue to require an API key and HTTPS. Plain HTTP is
  still restricted to `localhost`, `127.0.0.1`, and `::1`; redirects remain
  rejected for chat-completion requests.

### Verification

- The package-aware full local suite contains 885 passing automated tests.

## [0.3.7] - 2026-08-15

### Added

- A read-only `list knowledge relations` catalog for active explicit local
  document links. Each entry exposes loaded source and target document IDs,
  the `related_to` type, and whether the link is persisted or in-memory only.

### Safety

- The catalog reports only relations active in the current graph. It does not
  infer endpoints, materialize an unloaded persisted relation, change graph or
  relation-store state, write conversation memory, or call an LLM.

### Verification

- The package-aware full local suite contains 880 passing automated tests.

## [0.3.6] - 2026-08-15

### Added

- A read-only `preview remove knowledge relation <source_document_id> --
  <target_document_id>` command for an existing explicit local relation.
- An explicit `remove knowledge relation <source_document_id> --
  <target_document_id>` command. It removes the derived graph edge and, when
  present, its separate persisted relation record.

### Safety

- Removal requires an existing relation, rejects a repeated request, and makes
  no conversation-memory or LLM call. If the relation snapshot cannot be
  written, the removed graph edge is restored before the failure is returned.

### Verification

- The package-aware full local suite contains 875 passing automated tests.

## [0.3.5] - 2026-08-15

### Added

- A separate, versioned, atomically replaced local JSON store for explicitly
  applied `related_to` document relations. The Bootstrap runtime wires the
  store beside its other local data.
- Restart-safe relation restoration: a persisted link is restored to the
  derived graph only after both of its stable local source identities have been
  loaded again.
- Transactional relation application: if the local relation file cannot be
  written, the just-added in-memory graph edge is removed again.

### Safety

- The store accepts only distinct `related_to` document IDs, rejects duplicate
  records and unsupported schemas, and never writes conversation memory or
  sends a request to an LLM.

### Verification

- The package-aware full local suite contains 869 passing automated tests.

## [0.3.4] - 2026-08-15

### Added

- Stable document IDs for files loaded through the local Knowledge Foundation.
  The ID is deterministically derived from the resolved local source path, so
  reopening the same source retains its identity even when its content changes.
  Distinct local source paths retain distinct identities.

### Verification

- The package-aware full local suite contains 861 passing automated tests.

## [0.3.3] - 2026-08-15

### Added

- An explicit `apply knowledge relation <source_document_id> --
  <target_document_id>` command. It freshly validates the two documents, then
  adds one `related_to` edge to the derived, in-memory local graph. Duplicate,
  self, unknown, and non-user-selectable relations are rejected without a
  partial change.
- `knowledge graph <query>` now shows an explicitly applied `related_to` edge
  when either selected document endpoint is relevant to the query.

### Safety

- Applying a relation changes only the current in-memory graph. It does not
  write JSON memory, create a conversation-memory record, call an LLM, or
  persist across restart.

### Verification

- The package-aware full local suite contains 858 passing automated tests.

## [0.3.2] - 2026-08-15

### Added

- An explicit, read-only `preview knowledge relation <source_document_id> --
  <target_document_id>` command. It validates two distinct catalogued local
  documents for the first user-selectable `related_to` relationship, but does
  not alter graph state, JSON memory, or conversation memory.

### Verification

- The package-aware full local suite contains 853 passing automated tests.

## [0.3.1] - 2026-08-15

### Added

- An explicit `list knowledge` catalog for loaded local sources. It returns
  stable document IDs, titles, source paths, document types, and chunk counts
  in load order, without LLM use or conversation-memory mutation.

### Verification

- The package-aware full local suite contains 846 passing automated tests.

## [0.3.0] - 2026-08-15

### Added

- An explicit `knowledge graph <query>` view for locally loaded sources. It
  exposes deterministic document-to-paragraph `contains` relationships with
  visible source citations, without LLM use or conversation-memory mutation.
- A derived, in-memory local knowledge-graph foundation. It keeps document and
  paragraph nodes plus `contains` and `precedes` edges separate from the JSON
  memory schema, and indexes each source atomically.

### Verification

- The package-aware full local suite contains 840 passing automated tests.

## [0.2.10] - 2026-08-15

### Fixed

- Reconciled the runtime version, current verification baseline, and explicit
  local-RAG boundary across the project status and architecture-audit documents.

### Verification

- The package-aware full local suite contains 830 passing automated tests.

## [0.2.9] - 2026-08-15

### Fixed

- Bound each source chunk in an `ask knowledge` LLM prompt to 600 characters,
  matching the visible context limit and preventing an oversized local prompt.

### Verification

- The package-aware full local suite contains 830 passing automated tests.

## [0.2.8] - 2026-08-15

### Added

- Explicit `ask knowledge <query>` local RAG answers. The LLM receives only up
  to three cited local chunks and the answer retains those citations in its
  response model; normal conversation is never automatically augmented.

### Verification

- The package-aware full local suite contains 828 passing automated tests.

## [0.2.7] - 2026-08-15

### Added

- An explicit `knowledge context <query>` command that composes up to three
  local knowledge chunks with visible ordered source citations. It does not
  alter normal search or conversation behavior and does not create a memory
  record.
- Bounded context display: each rendered chunk is limited to 600 characters,
  while the complete selected result remains available in the response model.

### Verification

- The package-aware full local suite contains 825 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.6] - 2026-08-15

### Added

- Stable local source citations for knowledge-search results. Every response
  now carries a matching ordered citation with document ID, title, local source,
  paragraph index, and chunk ID, without changing the existing search text or
  raw result list.
- Parser propagation of source-document identity into indexed chunks, forming
  the explainability boundary required by later local RAG work.

### Verification

- The package-aware full local suite contains 822 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.5] - 2026-08-15

### Added

- An optional, model-scoped local embedding cache for semantic memory. When
  `HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS=true`, unchanged local memory can
  be indexed after restart without calling Ollama again.
- Atomic cache replacement, source-content SHA-256 invalidation, strict cache
  validation, and lifecycle updates for added, changed, expired, and deleted
  memory records. The cache is separate from the primary memory schema and is
  never required for a successful primary-memory operation.

### Verification

- The package-aware full local suite contains 819 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.4] - 2026-08-15

### Added

- Connected reciprocal-rank fusion to the explicit `semantic recall <query>`
  path when both current-session semantic and lexical candidates are present.
  The response labels this mode `hybrid` and clearly identifies its displayed
  values as rank scores rather than cosine-similarity scores.
- Preserved semantic-only results, deterministic lexical fallback, and
  current-session isolation when hybrid evidence is unavailable.

### Verification

- The package-aware full local suite contains 812 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.3] - 2026-08-15

### Security

- Disabled automatic HTTP redirect following for authenticated LLM completion
  requests, so an `Authorization` bearer token cannot be forwarded to a
  redirect target.

### Verification

- The package-aware full local suite contains 811 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.2] - 2026-08-15

### Security

- Added a validated endpoint policy for optional authenticated LLM runtimes:
  remote providers must use HTTPS, while plain HTTP is limited to explicit
  loopback endpoints (`localhost`, `127.0.0.1`, and `::1`).
- Rejected malformed endpoint URLs and URLs containing embedded credentials
  before the provider factory can receive an API key.
- Added an initial responsible-disclosure and runtime-security baseline in the
  repository security documentation.

### Verification

- The package-aware full local suite contains 810 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.1] - 2026-08-15

### Added

- Local JSON persistence for structured memory and session registry snapshots,
  including atomic writes and explicit failure handling.
- Session creation, activation, overview, details, activity, recent-history,
  conversation search, rename preview/commit, delete preview/commit, and
  guarded transactional deletion.
- Deterministic cognitive orchestration for knowledge search, planning,
  explicit recall, session commands, and optional LLM conversations.
- Learned-memory candidate extraction, append-only correction history,
  bounded context composition, keyword selection, deterministic ranking, and
  configurable ranked top-k selection.
- OpenAI-compatible chat-completions transport with an optional system prompt
  and bounded same-session conversation history.
- A dependency-free semantic retrieval core: validated immutable embeddings,
  an embedding-provider boundary, and a derived in-memory cosine-similarity
  index with deterministic ordering and a fresh-index builder for active
  memory records.
- An explicit stdlib-based Ollama `/api/embed` adapter with strict single-vector
  response validation, opt-in Bootstrap activation, and atomic replacement of
  the last successful derived index. After startup, lifecycle events keep the
  derived index current without allowing embedding failures to disrupt primary
  memory writes.
- A validated configurable local embedding-transport timeout with a 120-second
  default for cold local-model startup.
- A bounded `semantic recall <query>` path that exposes similarity scores only
  for current-session conversation records and falls back to deterministic
  lexical recall when semantic retrieval is unavailable or empty.
- A pure reciprocal-rank fusion evaluator with a versioned hybrid-ranking
  fixture corpus; it is evaluation-only and does not alter runtime ordering.

### Changed

- Restored a complete MyPy quality gate for both `src` and `tests` by making
  package-base discovery explicit and aligning test doubles with their runtime
  contracts.
- Made the full unittest command package-aware so nested test directories are
  included without shadowing source packages.

### Verification

- The package-aware full local suite contains 806 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.0] - 2026-08-03

### Added

- Knowledge Foundation pipeline from document loading to search.
- `.txt` and `.md` document loading.
- Paragraph parsing into ordered chunks.
- In-memory chunk indexing and case-insensitive text search.
- KnowledgeEngine orchestration for loading, indexing, searching, and clearing.

### Tests

- Added 37 Knowledge Foundation tests.
- Expanded the full suite to 68 passing unit tests.
- Verified Black, Ruff, MyPy, unittest, and whitespace checks.

## [0.1.7] - 2026-08-03

### Changed

- Standardized project formatting and static analysis configuration.
- Improved logger output format.
- Standardized core exception types.
- Updated README and project status documentation.

### Tests

- Expanded the core test suite to 31 passing unit tests.
- Verified Black, Ruff, MyPy, unittest, and whitespace checks.
