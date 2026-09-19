# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.

## Current

| Field | Value |
| --- | --- |
| Milestone | none defined |
| Base SHA | - |
| Status | - |
| Specialists | - |
| Blockers | - |

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.394: add runtime capability self-awareness |
| SHA | c321b7b27285899d53f06380cd8883e0151c55b6 |
| Linux desktop CI | success (run 35457649057) |
| Windows desktop CI | success (run 35457650977) |

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
