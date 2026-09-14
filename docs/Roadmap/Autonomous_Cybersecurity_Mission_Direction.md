# Autonomous cybersecurity mission direction

## Purpose

Hypatia is being built as an autonomous, local-first research system. Its
cybersecurity direction builds on that mission runtime; it does not replace it
with a chat interface, a collection of tool buttons, or an unconstrained
pentesting loop.

The eventual user contract is:

```text
goal + authorized scope + constraints + cumulative budget
    -> understand -> plan -> inspect -> form hypotheses
    -> use allowed tools -> observe -> verify -> adapt
    -> gather provenance-backed evidence -> correlate -> explain -> learn
```

Ordinary safe work within that exact contract should not require a person to
press Continue for every internal step. Neither autonomy nor a model can create
target authority, broaden a scope, select an unapproved destination, reset a
budget, or convert a tentative observation into a verified security finding.

## Non-negotiable evidence rules

- Model confidence is not security evidence.
- Tool output is not a verified finding.
- A fetched source is not trusted simply because it was fetched.
- A CVE description is not confirmation that a particular target is exploitable.
- A possible vulnerability is not a confirmed vulnerability.
- A failed payload does not prove absence of a vulnerability.
- A completed plan is not proof that a security goal was achieved.

Every material output must retain its scope, source or tool provenance, time,
identity, bounded uncertainty, and the observation or test that supports it.
Verification must remain distinct from execution and from explanation.

## Long-term capability layers

### 1. Public vulnerability intelligence

Within explicitly approved source families, Hypatia should normalize and
correlate CVE intelligence across sources such as NVD, CISA KEV, GitHub Security
Advisories, vendor advisories, and CERT publications. It should preserve source
differences, affected products and versions, remediation, known-exploitation
status, and uncertainty rather than treating one record as complete truth.

### 2. Sentinel-style stateful monitoring

Monitoring must compare newly observed intelligence with prior canonical state,
deduplicate it, identify meaningful changes, and notify only when useful. A
meaningful change can include KEV status, exploitation evidence, affected-version
or severity changes, a material advisory revision, a remediation change, or a
relevant dependency impact. Polling and dumping every feed item is not Sentinel.

### 3. Security reasoning and code review

The system should reason about vulnerability mechanisms: root cause,
prerequisites, observable behavior, discriminating tests, false-positive
conditions, mitigation, and detection. Authorized code review should follow
evidence-backed source -> transformation -> sink -> missing control paths,
including authentication, authorization, injection, deserialization,
filesystem/process use, secret handling, crypto, unsafe defaults, outbound
access, and business-logic assumptions. A dangerous function name alone is not
a finding.

### 4. Scope-bound security operations

Only in an owned, lab, CTF, or other explicitly authorized target scope should
Hypatia autonomously perform a bounded cycle of reconnaissance, observation,
hypothesis formation, allowed test selection, tool execution, response
inspection, verification, adaptation, and evidence-backed reporting. A generic
planner must never infer that a host, domain, account, or network is authorized.

Tools such as HTTP clients, scanners, static analysis, dependency analysis, or
Kali-hosted utilities must expose typed capabilities, permission requirements,
scope bindings, budgets, result contracts, and verification boundaries. Tool
success never creates a finding automatically.

### 5. Security knowledge, attack surface, and hypotheses

Mission-scoped evidence should support structured relationships between CVEs,
CWEs, CAPEC entries, products, advisories, patches, weaknesses, mitigations,
and detections. An attack-surface model may represent only mission-owned
evidence such as hosts, services, endpoints, parameters, roles, trust
boundaries, technologies, and integrations; it must not become uncontrolled
target inventory collection.

Security hypotheses must record plausibility, supporting and opposing
observations, a discriminating test, whether that test is authorized, its
outcome, and current status. A hypothesis is not a finding. Failed tests may
change a hypothesis but do not manufacture certainty.

## Delivery order

The Autonomous Mission Runtime remains the Phase 2 architectural priority:

1. durable, idempotent, recoverable mission execution;
2. evidence, result-verification, failure, and mission-outcome honesty;
3. bounded adaptation and completion evaluation;
4. only then domain-specific intelligence, monitoring, code-review, and
   scope-bound security-operation capabilities.

No cybersecurity capability may bypass canonical authorization, cumulative
accounting, evidence provenance, durable recovery, or explanatory reporting.
Current text-research milestones are a foundation for this direction, not a
claim that autonomous security testing or security findings are implemented.
