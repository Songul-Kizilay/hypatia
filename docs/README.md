# Hypatia Documentation

This directory is the source of truth for Hypatia's product intent and
technical design. Documents are written before implementation so that choices
remain reviewable and the system can grow without losing its purpose. For the
executable current-state boundary, use the repository-level
[`PROJECT_STATUS.md`](../PROJECT_STATUS.md) and the
[Architecture Audit v0.2](Architecture/Architecture_Audit_v0.2.md); vision and
roadmap documents do not by themselves prove implementation.

## Structure

| Directory | Contents |
| --- | --- |
| [Bible](Bible/README.md) | Vision, mission, principles, constitution, ethics, and shared vocabulary. |
| [Architecture](Architecture/README.md) | System boundaries, interfaces, data, security, and deployment design. |
| [Modules](Modules/README.md) | Responsibilities and specifications for individual capabilities. |
| [Roadmap](Roadmap/README.md) | Version goals, scope boundaries, and release criteria. |
| [Research](Research/README.md) | Research questions, source notes, and experiments. |
| [Journal](Journal/README.md) | Architecture decision records and project history. |
| [Decisions](Decisions/README.md) | Architecture Decision Records (ADRs). |
| [Design](Design/README.md) | User flows, interface concepts, and accessibility. |
| [Security](Security/README.md) | Threat models, privacy, permissions, and incident response. |
| [Testing](Testing/README.md) | Evaluation strategy and acceptance criteria. |
| [API](API/README.md) | Future API contracts and versioning. |
| [Diagrams](Diagrams/README.md) | Mermaid, Draw.io, UML, and other visual artifacts. |
| [Meeting Notes](MeetingNotes/README.md) | Dated planning and review notes. |

## Documentation rules

- State what is decided, proposed, or unknown.
- Keep product intent separate from implementation detail.
- Link supporting research for consequential claims.
- Record significant decisions in the journal.
- Update the roadmap when a scope decision changes.
