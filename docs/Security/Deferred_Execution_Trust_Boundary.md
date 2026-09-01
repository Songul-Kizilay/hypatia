# Deferred Execution Trust Boundary

Runtime at decision: `v0.3.281 (Genesis)`.

## Policy

For Hypatia's current local-first threat model, explicit human approval for
deferred execution is a confirmation made through the trusted local desktop
control plane. That desktop surface is part of the local trusted computing
base.

This is not cryptographic identity, password authentication, remote-user
authentication, or protection from arbitrary malicious Python code already
executing inside Hypatia. It distinguishes the desktop confirmation route from
Brain/model requests, ordinary CognitiveEngine intents, scheduler self-actions,
Curiosity output, and callers that can construct a `BrainRequest`.

## Authority

A deferred grant is a durable permission for one exact queued task to be
considered by a future automatic trigger without another confirmation at fire
time. It binds the task ID, execution ID, current plan digest, plan-derived
capabilities and the scheduler task's outer bound.

It creates no `ResearchPlanAuthorization`, allowance, capability, budget,
retry, provider call, model call, network request, execution step, or worker
cycle. Existing execution state, remaining allowance, plan capabilities,
`progress_block`, and task state remain authoritative.

Tasks without a separate active grant are manual-only, including task records
created by older releases. Revocation removes only future deferred eligibility;
it does not cancel or modify the task or execution and refunds nothing.

## Current Limit

There is deliberately no timer, polling loop, recurrence, `run_at`, startup
worker, or automatic scheduler cycle in this release. The grant and the pure
eligibility decision establish the authority boundary needed before such a
trigger can be designed safely.
