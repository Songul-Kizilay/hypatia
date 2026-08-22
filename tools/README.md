# Tools

Reusable maintenance, backup, migration, benchmark, and diagnostic utilities will live here. Each tool requires documented purpose, permissions, and safe-use instructions.

## diagnostics/durable_memory_check.py

Developer-only check that the durable-memory chain works against a real local
model: write, persist across a fresh runtime, retrieve, answer. It runs the same
runtime path as the desktop without a Tkinter window and prints PASS/FAIL per
stage, including the exact learned-memory context that would be injected.

```
python tools/diagnostics/durable_memory_check.py           # temporary data
python tools/diagnostics/durable_memory_check.py --real    # real desktop memory
```

Defaults to an isolated temporary data directory; the real desktop memory file
requires the explicit `--real` flag. It changes no production behavior, adds no
dependency, and prints no secret. Without a running local model every stage
reports FAIL rather than pretending success.
