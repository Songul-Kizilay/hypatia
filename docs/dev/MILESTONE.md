# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.

## Current

| Field | Value |
| --- | --- |
| Milestone | Close Kali HTTPS_HEADER_LOOKUP SSRF / address-pinning gap |
| Base SHA | 4b1c5666c936f00e1d113d561d7ef40aff1abc58 |
| Status | release |
| Specialists | hypatia-runtime (implementation), hypatia-security (review: APPROVED WITH NOTES), hypatia-qa (independent verification: APPROVED WITH NOTES) |
| Blockers | none |

Scope: before building/authorizing/running the `HTTPS_HEADER_LOOKUP` Kali
operation, resolve the authorized hostname once, reject any non-global
resolved address (reusing `PublicHttpsUrlValidator`/
`ScopedPublicHttpsUrlValidator.require_addresses`), pin the actual `curl`
connection to the validated address, bind the operation's
authorization/digest to that validated address so DNS drift between preview
and run fails closed, and record validated/contacted address provenance.
Non-goals: `DNS_RECORD_LOOKUP` is unchanged; no new Kali operation kinds; no
change to existing Kali authorization single-use/5-minute-window/opt-in
rules; no change to the fetch-path validators beyond reuse. Full rationale in
the architectural review preceding this ledger entry (see chat/PR history for
this milestone).

Known residual (recorded per QA's approval condition, not blocking this
milestone): `kali_operation_preview_failure()` in
`src/response/ResponseComposer.py` unconditionally renders
`"Network/DNS: not used"` on every refusal path, but a refusal from
`validate_and_resolve`'s address-validation or from
`ResearchTargetScope.require_addresses` occurs *after* a real DNS resolution
already happened, making that line inaccurate for those two refusal
reasons specifically. The refusal itself is still correctly fail-closed (no
address bypass, no authority/budget granted, no process started); this is a
wording-accuracy gap on the refusal path only, mirroring the accepted-preview
message fixed in this milestone. Left open for a future small follow-up.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.394: add runtime capability self-awareness |
| SHA | c321b7b27285899d53f06380cd8883e0151c55b6 |
| Linux desktop CI | success (run 35457649057) |
| Windows desktop CI | success (run 35457650977) |

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
