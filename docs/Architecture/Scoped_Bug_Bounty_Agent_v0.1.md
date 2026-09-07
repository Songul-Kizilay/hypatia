# Scope-bound bug bounty companion: implementation direction

## User outcome

The user wants a cybersecurity companion that independently progresses research
and permitted bug bounty checks inside an explicitly authorized program scope.
They should not have to approve every routine step of an already approved job.
The system must explain observations, distinguish hypotheses from verified
findings, preserve evidence, and stop rather than expand its own authority.

## Current checkpoint: v0.3.308

This increment supplies a tested request-target gate, not a finished bounty
agent. `ResearchTargetScope` is immutable, bounded to 100 combined rules, and
contains exact DNS names, descendant-only DNS rules, and IPv4/IPv6 CIDR rules.
Exclusions win. Descendant rules do not include the apex. A name cannot be
authorized by a substring match or merely by resolving inside an allowed CIDR.
A permitted domain resolving to an IP does not authorize direct requests to
that IP. CIDRs with host bits are refused rather than silently widened.

`ScopedPublicHttpsUrlValidator` composes these rules with the existing public
HTTPS policy and can be injected through the existing constructor:

```python
scope = ResearchTargetScope(
    allowed_hosts=(TargetHostRule("example.test"),),
    excluded_hosts=(TargetHostRule("payments.example.test"),),
)
validator = ScopedPublicHttpsUrlValidator(scope)
fetcher = HttpResearchSourceFetcher(validator=validator)
```

This is an example of dependency composition, not a live target or permission
to make a request. No live target traffic is used in this milestone's tests.

The existing production opener reuses the validator before opening, before each
redirect, at HTTPS connection address pinning, and before reading the final
body. Unlisted or excluded request authorities are rejected before DNS. Any
excluded resolved address rejects the complete address set, including an
IPv4-mapped representation of an excluded IPv4 address. Private/loopback DNS
answers remain prohibited by the existing public policy. Literal-IP resolution
must not substitute another address. Unicode authorities must be entered as
explicit ASCII A-labels; whitespace, controls and ambiguous authority syntax
are rejected before parsing can erase them.

## v0.3.298: scope snapshot persistence and content identity

`ResearchTargetScopeCodec` serializes every host/subdomain and CIDR rule under
a strict versioned schema. `target_scope_digest()` identifies that exact
validated content, including exclusions and authored rule order. Domain case
and a single trailing root dot normalize through `TargetHostRule`; formatting
the JSON differently does not alter content identity. Future model fields
require an explicit schema update rather than silently escaping the digest.

`JsonFileResearchTargetScopeStore` stores one snapshot in a caller-selected
local path, with a 64 KiB bounded read and validated bounded serialization.
Writes use a same-directory temporary file, flush/fsync, and atomic replacement
following existing research stores. Failed writes preserve the previous file.
Reads neither write nor start research. Missing means `None`, not unrestricted
scope. Corruption, duplicate/unknown/missing fields, unsupported schemas and
digest mismatches fail closed. The restored scope can be passed directly to
the existing scoped HTTPS validator and retains all exclusions.

This is trusted single-writer snapshot storage, not append-only revision
history, a program registry, a user-confirmation UI or execution authorization.
The digest is not a signature: a local writer can edit and rehash a snapshot.
A future grant must bind a separately confirmed scope digest AND program/job
identity. Replacing the file must never silently reauthorize an existing job.
No program prose or path restriction is converted into a host-wide permission.

## v0.3.299: exact-plan approval and scoped acquisition

`ResearchPlanTargetBinding(program_id, scope)` began as an optional field on the
canonical `ResearchPlan`. In v0.3.305 the binding also carries
`scope_revision_id` and `scope_revision_digest`, and the entire binding
participates in the existing recursive plan digest under scoped schema v6.
Unscoped reference plans skip the absent field and retain their original v2/v4
identities. No duplicate scope authority is added to authorizations or deferred
grants: their existing exact-plan digest checks reject any changed program,
rule, exclusion, revision identity or step.

The structured authored-plan metadata key `research_plan_target_binding`
accepts this typed value, never prose or a partially parsed dictionary. Draft,
approval and Start rebuilds all preserve it. The draft and approval preview
display the program, all target rules and exclusions, scope content identity
and the supported transport limits before confirmation. This is a core service
path, not yet a desktop program-enrollment workflow. Trusted composition still
owns the distinction between reference research and authorized target work.

For now a target-bound plan may contain only the existing `SOURCE_FETCH` and
`SOURCE_ACCEPT` capabilities. Discovery APIs and all other capabilities are
refused in target plans, not silently routed out of scope. `PlanSourceFetcher`
uses `HttpResearchSourceFetcher` with `ScopedPublicHttpsUrlValidator` for the
bound immutable scope. It never uses the injected general/reference fetcher
for target work, including on failure. Canonical acceptance is unchanged.

Start requires a recorded human authorization even in a composition where
legacy reference plans can start without one. Start remains zero-step. Each
Advance takes its binding from the canonical live plan, not caller metadata;
the existing allowance charges an attempted operation as before. This is an
operation/attempt budget, not a per-HTTP-request or redirect rate limiter.

Target execution snapshots record the full `target_plan_digest`. Rebind checks
that digest and the recorded research run before making an execution live.
Changed or removed bindings are refused, and a target plan cannot resume from
a legacy snapshot that lacks this proof. The exact plan must still be supplied
by the trusted caller; neither scope nor complete plan is reconstructed from
the narrow execution bookkeeping snapshot. Editing or revoking a saved scope
does not rewrite an already approved plan, but v0.3.305 requires the exact
active revision to remain valid at Start, restore and every Advance before side
effects.

## Boundaries that are NOT implemented yet

- Target plans now bind one exact active revision identity and re-check it at
  plan approval, Start, restore and every Advance.
- The default generic reference-source fetcher is unchanged. Constructing an
  unscoped fetcher does not acquire a bug bounty permission. The future target
  enrollment/runner must require a scope. Bound source operations already
  refuse fallback to that reference path.
- The adapter supports the existing public HTTPS port-443 bounded text GET
  path only. It does not add HTTP, alternate ports, probes, scanning, shell
  tools, request bodies, session credentials or vulnerability exploitation.
- Host/CIDR rules cannot represent path-specific program exclusions, allowed
  test categories, time windows, per-program rate limits or request budgets.
  Do not translate a path-limited program into an unrestricted host rule.
- There is no public-suffix/ownership verification. Explicitly authored broad
  rules are not proof of domain ownership or a program's consent.
- The gate is target identity policy, not a grant of execution authority.
  A trusted caller still controls construction; adversarial Python code or a
  replacement opener is not confined by an injected validator.

## Required next integration milestones

1. Program scope enrollment: exact assets, exclusions, permitted check classes,
   transport/port/path constraints, request/rate/time budgets, expiry and an
   operator-confirmed immutable revision. Unsupported rules must be visibly
   rejected, never ignored or converted into broader host access.
2. Mandatory target-request boundary bound to that revision and the existing
   execution authority. Verify redirects and pinned addresses on every request;
   enforce revocation and budget at dispatch. Keep external reference research
   (e.g. vulnerability documentation) separate from authorized test targets.
3. Bounded autonomous loop: plan -> permitted action -> observed result -> next
   action, within one approved job; cancellation, reproducible event history,
   bounded retries and no scope expansion. Test first against local/fake
   fixtures with no third-party target traffic.
4. Explicitly permitted checks, evidence validation and report production.
   Weak signals remain hypotheses, duplicate evidence is not independent
   confirmation, and failed checks become useful lessons rather than automatic
   prohibitions. Program-forbidden operations are refused.

Completion is the end-to-end user workflow above, not merely a passing URL
matcher. Existing research, hypothesis, memory and reporting components should
be reused where their actual contracts fit that workflow.

## Verification evidence

`tests/research/test_research_target_scope.py` exercises rule precedence,
label boundaries, malformed input, CIDRs, independent IP authorization,
Unicode case-folding hazards, address substitutions, exclusion after DNS
changes, actual installed redirect/pinning handlers, pre-open rejection and
pre-body-read rejection. DNS and HTTP are replaced with deterministic test
doubles. Existing public-HTTPS/transport tests remain unchanged.

`tests/research/test_plan_target_binding.py` locks legacy digests, target
identity changes, snapshot compatibility and deferred-grant mismatch/revocation.
`tests/integration/test_target_bound_research_plan.py` covers real authored
preview/confirmation/Start/Advance, both acquisition operations, explicit
disclosure, missing authorization, changed scope, restart, and actual installed
redirect/pinning handlers. Only DNS and the network opener are replaced; no
third-party traffic occurs. A fetched page remains untrusted source material,
not a vulnerability finding.
## v0.3.300: desktop target-plan authoring

The desktop Plan draft panel can now create an inert typed target draft from
an explicit program ID, allow/exclusion host and CIDR rules, exact public HTTPS
URLs, and a fetch-or-accept action. Applying the editor performs no I/O and
reuses the canonical preview, approval, confirmation, Start and Advance
boundaries. Changing the target clears cached approval preview state.

The form deliberately cannot express crawling, active scanning, credentials,
exploitation or path-specific program policy. It is session-only and does not
prove permission; durable program enrollment, policy expiry/revocation and an
operator-approved autonomous job remain future milestones.

## v0.3.301: immutable program-scope revision history

Hypatia can now represent and atomically persist one human-confirmed immutable
program-scope revision. The record binds the program identity, exact existing
scope and digest, fixed currently supported acquisition capabilities,
HTTPS:443 transport, confirmation/expiry times, and one-way human revocation.
History cannot be shortened or rewritten, and a successor requires explicit
revocation of the previous revision.

This is the enrollment record foundation, not permission to execute. Plan
binding and dispatch-time enforcement were added in v0.3.305: approval, Start,
restore and every Advance resolve the exact active revision before any budget,
DNS, checkpoint or network side effect.

## Future Kali security-tool boundary

The requested security-tool capability is accepted only as a scope-bound,
tool-specific execution layer. Hypatia will not expose a general terminal or
accept raw command strings. Every executable, option, target, port, check class,
rate, duration and output limit must come from reviewed code and exact active
program authority. See
[`Kali_Tool_Execution_Design.md`](../Security/Kali_Tool_Execution_Design.md).

Kali execution remains blocked until enrollment can represent the program's
permitted check classes, ports and budgets without broadening them, and until a
reviewed operation preview/authorization/fake-runner path exists.

## v0.3.303: explicit scope enrollment service

The core application layer now supports separate create/revoke preview and
exact-confirm operations for immutable program-scope revisions. The complete
revision is held in a bounded process-local preview, and confirmation names its
exact revision ID and digest rather than resubmitting editable scope fields.
Persistence succeeds before the service publishes the new history in memory.
An active program revision must be explicitly revoked before a successor can
be previewed.

## v0.3.304: desktop scope enrollment controls

The desktop target-program editor now reaches the enrollment service. From the
same validated program ID and target rules, the operator can preview and
confirm a saved active scope revision, refresh active revisions, and separately
preview and confirm human revocation. Confirmation refuses a stale preview if
the form's program ID or target rules changed after preview.

This still does not approve or run a plan. It performs no DNS lookup, network
request, model call, Kali operation, terminal launch or tool registration.

## v0.3.305: exact active scope revision dispatch gate

Target drafts now select an active saved scope revision and carry its revision
ID and digest into the target binding. Approval preview, confirmation,
Curiosity proposal approval, Start, restore and every Advance independently
reload the saved program-scope revision history and require the exact revision
to remain active and to match the target program and scope.

Refusals happen before approval consumption, durable execution checkpoints,
budget spend, DNS lookup, provider calls or network traffic. This is still not
Kali execution; it is the required authority gate that future structured Kali
operations must reuse.

## v0.3.306: explicit program execution policy snapshot

Program-scope revisions now record an explicit bounded execution policy:
permitted check classes, permitted ports, maximum request count, maximum
request rate and maximum time. The initial default policy truthfully represents
the existing HTTPS-only acquisition surface: public HTTPS content on port 443,
with bounded request/rate/time limits. A separate policy digest protects those
facts without changing existing scope revision identity.

This still does not run Kali or add a process capability. It is the policy
record a future inert Kali-operation preview and authorization path must bind
before any child process can be considered.

## v0.3.307: inert Kali operation preview

Hypatia can now build the first structured Kali-operation preview for a
DNS-record lookup profile. The preview is bound to:

- exact active program-scope revision identity and digest;
- execution-policy digest;
- reviewed operation kind and check class;
- admitted hostname;
- DNS record type;
- permitted ports and operation budget.

The preview does not construct a raw command string, start Kali, launch a
terminal, create a process, perform DNS, use the network or write durable state.
It is the visible proposal a future exact operation authorization must approve.

## v0.3.308: exact Kali operation authorization

Hypatia can now authorize the first structured Kali-operation preview by exact
operation digest. The authorization service rebuilds the preview from the
current active program-scope revision before approval, then refuses if the
supplied digest no longer matches the operation facts.

The authorization names the human decision, operation digest, program, scope
revision digest, execution-policy digest and short expiry window. It still does
not build a command line, launch a terminal, start Kali, create a child process,
perform DNS, use the network or persist runner state. The next safe milestone
is a fake runner that consumes this boundary without creating a real process.
