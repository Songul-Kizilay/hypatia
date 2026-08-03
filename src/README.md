# Source Layout

This directory is intentionally code-free during the documentation phase. The folders below reserve stable homes for future modules; they do not imply an implementation commitment.

| Directory | Intended scope |
| --- | --- |
| `core` | Shared orchestration and domain primitives. |
| `agents` | Deliberately scoped agent workflows. |
| `memory` | User-controlled memory capabilities. |
| `research` | Research collection and synthesis workflows. |
| `sentinel` | Security-awareness capabilities. |
| `voice` | Speech input and output. |
| `vision` | Opt-in visual understanding. |
| `robotics` | Robot and hardware integrations. |
| `home` | Smart-home integrations. |
| `career` | Career intelligence features. |
| `entertainment` | Recommendations and media experiences. |
| `desktop`, `mobile`, `watch`, `xr` | User-facing application surfaces. |
| `api` | External and internal service interfaces. |

## Planned agents

`brain`, `research`, `security`, `career`, `planner`, `memory`, `home`, `vision`, `voice`, `gaming`, `cinema`, `companion`, and `teacher` are reserved as separate future agent workspaces. Their specifications belong in `docs/Modules` before code is introduced.

## Layer boundaries

- `agents/` decide, coordinate, and request approved work.
- `modules/` implement domain capabilities such as research, memory, or voice.
- `services/` provide shared technical capabilities such as model access, storage, speech, and notifications.

Agents must depend on public module and service contracts rather than each other's internal implementation.
