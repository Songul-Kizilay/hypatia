"""Developer-only durable-memory check against a real local model.

Exercises the same runtime path as the desktop (Bootstrap -> CognitiveEngine ->
configured LLM provider) without needing a Tkinter window, and reports whether
each link of the durable-memory chain works: write, persist, retrieve, answer.

This is a diagnostic, not part of the runtime. It changes no production
behavior and adds no dependency.

    python tools/diagnostics/durable_memory_check.py           # temporary data
    python tools/diagnostics/durable_memory_check.py --real    # real desktop memory

Defaults to an isolated temporary data directory. Using the real desktop memory
file requires the explicit --real flag. Requires a running local model at the
configured endpoint; without one every stage reports FAIL rather than
pretending success.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from brain.BrainRequest import BrainRequest  # noqa: E402
from cognition.CognitiveEngine import CognitiveEngine  # noqa: E402
from cognition.LearnedMemoryContextService import (  # noqa: E402
    LearnedMemoryContextService,
)
from core.Bootstrap import Bootstrap  # noqa: E402
from desktop.DesktopDataPaths import DesktopDataPaths  # noqa: E402
from memory.LearnedMemoryStore import load_learned_memories  # noqa: E402

STATEMENT = "My favorite test animal is raven."
QUESTION = "What is my favorite test animal?"

ENVIRONMENT = {
    "HYPATIA_LLM_ENABLED": "true",
    "HYPATIA_LLM_BASE_URL": "http://127.0.0.1:11434/v1/chat/completions",
    "HYPATIA_LLM_MODEL": os.environ.get("HYPATIA_LLM_MODEL", "llama3.2:latest"),
    "HYPATIA_LEARNING_ENABLED": "true",
}


def build_engine(memory_path: Path, session_path: Path) -> CognitiveEngine:
    for key, value in ENVIRONMENT.items():
        os.environ[key] = value
    bootstrap = Bootstrap.from_process_environment(memory_path, session_path)
    bootstrap.initialize()
    return bootstrap.container.resolve(CognitiveEngine)


def show_learned(engine: CognitiveEngine, label: str) -> tuple:
    memories = load_learned_memories(engine._memory_manager)
    noun = "memory" if len(memories) == 1 else "memories"
    print(f"\n  {label}: {len(memories)} learned {noun}")
    for memory in memories:
        print(f"     - {memory.kind} | {memory.key} = {memory.value}")
    return memories


def main() -> int:
    use_real = "--real" in sys.argv

    if use_real:
        paths = DesktopDataPaths.from_process_environment()
        memory_path, session_path = paths.memory_path, paths.session_path
        temporary_directory = None
        print(f"Using REAL desktop data: {memory_path}")
    else:
        temporary_directory = tempfile.TemporaryDirectory()
        root = Path(temporary_directory.name)
        memory_path, session_path = root / "memory.json", root / "sessions.json"
        print(f"Using temporary data: {memory_path}")
        print("(pass --real to use your actual desktop memory file)")

    print(f"Model: {ENVIRONMENT['HYPATIA_LLM_MODEL']}")

    failures: list[dict] = []

    print("\n=== RUN 1: state the preference ===")
    engine = build_engine(memory_path, session_path)
    engine._event_bus.subscribe(
        "brain.learned_memory.extraction_failed",
        lambda event: failures.append(dict(event.payload)),
    )
    before = show_learned(engine, "before")

    started = time.perf_counter()
    try:
        response = engine.process(BrainRequest(message=STATEMENT))
    except Exception as error:  # noqa: BLE001
        print(f"\n  CHAT FAILED: {type(error).__name__}: {error}")
        print("  Is Ollama running on 127.0.0.1:11434?")
        return 2
    elapsed = time.perf_counter() - started

    print(f"\n  user      : {STATEMENT}")
    print(f"  Hypatia   : {response.message.strip()[:300]}")
    print(
        f"  success   : {response.success}" f"  ({elapsed:.1f}s incl. extraction call)"
    )
    after = show_learned(engine, "after")

    if failures:
        print(f"\n  EXTRACTION FAILURE EVENTS: {failures}")

    wrote = len(after) > len(before)
    print(f"\n  WRITE  -> {'PASS' if wrote else 'FAIL'}")
    if not wrote:
        print(
            "     No learned record was created. Extraction did not produce candidates."
        )

    print("\n=== RUN 2: fresh runtime from the same file (restart) ===")
    engine2 = build_engine(memory_path, session_path)
    reloaded = show_learned(engine2, "reloaded from disk")

    context = LearnedMemoryContextService(
        selector=engine2._learned_memory_selector,
        context_limit=engine2._learned_memory_context_limit,
    ).build(engine2._memory_manager, QUESTION)
    print("\n  learned-memory context that will be injected:")
    print("     " + (context.replace("\n", "\n     ") if context else "(empty)"))

    retrieved = "raven" in context.lower()
    print(f"\n  RETRIEVE -> {'PASS' if retrieved else 'FAIL'}")

    try:
        answer = engine2.process(BrainRequest(message=QUESTION))
    except Exception as error:  # noqa: BLE001
        print(f"  CHAT FAILED: {type(error).__name__}: {error}")
        return 2

    print(f"\n  user     : {QUESTION}")
    print(f"  Hypatia  : {answer.message.strip()[:300]}")

    answered = "raven" in answer.message.lower()
    print(f"\n  ANSWER   -> {'PASS' if answered else 'FAIL'}")

    print("\n" + "=" * 60)
    print(f"  write     : {'PASS' if wrote else 'FAIL'}")
    print(f"  persist   : {'PASS' if reloaded else 'FAIL'}")
    print(f"  retrieve  : {'PASS' if retrieved else 'FAIL'}")
    print(f"  answer    : {'PASS' if answered else 'FAIL'}")
    print("=" * 60)

    if temporary_directory is not None:
        temporary_directory.cleanup()

    return 0 if (wrote and reloaded and retrieved and answered) else 1


if __name__ == "__main__":
    raise SystemExit(main())
