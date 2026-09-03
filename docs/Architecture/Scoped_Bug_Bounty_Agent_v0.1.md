# Scope-bound bug bounty companion: implementation direction

## User outcome

The user wants a cybersecurity companion that independently progresses research
and permitted bug bounty checks inside an explicitly authorized program scope.
They should not have to approve every routine step of an already approved job.
The system must explain observations, distinguish hypotheses from verified
findings, preserve evidence, and stop rather than expand its own authority.

## Current checkpoint: v0.3.297

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

## Boundaries that are NOT implemented by this increment

- There is no UI/persisted program-scope enrollment or proof of authorization.
- There is no scope revision/digest binding to an execution grant yet.
- The default generic reference-source fetcher is unchanged. Constructing an
  unscoped fetcher does not acquire a bug bounty permission. The future target
  runner must require a scope and must never fall back to this unscoped path.
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
