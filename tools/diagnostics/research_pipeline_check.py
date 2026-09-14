"""Developer-only live check of the real research pipeline, stage by stage.

Every stage here is a different claim, and the report keeps them apart on
purpose:

    network request happened   != candidate discovered
    candidate discovered       != source accepted
    source accepted            != evidence recorded
    evidence recorded          != claim created

Nothing is promoted automatically. Discovery does not select, selection does not
fetch, a fetch does not accept, acceptance does not record evidence, and evidence
does not become a claim. Each stage runs only when you ask for it by flag, which
is the same rule the runtime itself enforces — the diagnostic is not allowed a
shortcut the architecture forbids.

    python tools/diagnostics/research_pipeline_check.py "your question"
    python tools/diagnostics/research_pipeline_check.py "your question" --discover
    python tools/diagnostics/research_pipeline_check.py "your question" \\
        --discover --accept 0
    python tools/diagnostics/research_pipeline_check.py "your question" \\
        --discover --accept 0 --evidence

With no flags nothing touches the network: the run is created and the plan is
printed. `--discover` performs one real discovery request. `--accept N` fetches
and accepts exactly the candidate you name. `--evidence` records one evidence
record from the first chunk of that accepted source.

Data goes to a temporary directory unless `--real` is passed. This is a
diagnostic, not part of the runtime; it adds no dependency and changes no
production behaviour.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cognition.ResearchSourceAcceptanceService import (  # noqa: E402
    ResearchSourceAcceptanceService,
)
from core.Exceptions import ResearchError  # noqa: E402
from desktop.DesktopDataPaths import DesktopDataPaths  # noqa: E402
from knowledge.KnowledgeEngine import KnowledgeEngine  # noqa: E402
from research.CanonicalResearchSummary import CanonicalResearchSummary  # noqa: E402
from research.CrossrefResearchSourceDiscoveryProvider import (  # noqa: E402
    CrossrefResearchSourceDiscoveryProvider,
)
from research.HttpResearchSourceFetcher import HttpResearchSourceFetcher  # noqa: E402
from research.JsonFileResearchRunStore import JsonFileResearchRunStore  # noqa: E402
from research.JsonFileResearchSourceContentStore import (  # noqa: E402
    JsonFileResearchSourceContentStore,
)
from research.ResearchRunManager import ResearchRunManager  # noqa: E402

DISCOVERY_LIMIT = 5


class Report:
    """Record each stage separately so no result implies the next one."""

    def __init__(self) -> None:
        self.stages: list[tuple[str, bool, str]] = []

    def add(self, name: str, done: bool, detail: str = "") -> None:
        self.stages.append((name, done, detail))
        mark = "DONE" if done else "not performed"
        print(f"  {name:<26}: {mark}{'  -- ' + detail if detail else ''}")

    def render(self) -> None:
        print("\n" + "=" * 68)
        print("  What actually happened")
        print("=" * 68)
        for name, done, detail in self.stages:
            mark = "yes" if done else "no"
            print(f"  {name:<26}: {mark}{'  -- ' + detail if detail else ''}")
        print("=" * 68)
        print("  A network request is not a discovery. A discovery is not an")
        print("  acceptance. An acceptance is not evidence. Evidence is not a")
        print("  verified claim, and a claim is not an established truth.")
        print("=" * 68)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="The research question for this run.")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Perform one real discovery request over the network.",
    )
    parser.add_argument(
        "--accept",
        type=int,
        default=None,
        metavar="N",
        help="Fetch and accept exactly candidate N from the discovery result.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Select this exact URL instead of a discovered candidate.",
    )
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="Record one evidence record from the accepted source.",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use the real desktop research data instead of a temporary copy.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    report = Report()

    if arguments.real:
        paths = DesktopDataPaths.from_process_environment()
        root = paths.memory_path.parent
        temporary_directory = None
        print(f"Using REAL research data under: {root}")
    else:
        temporary_directory = tempfile.TemporaryDirectory()
        root = Path(temporary_directory.name)
        print(f"Using temporary data: {root}")
        print("(pass --real to use your actual desktop research store)")

    manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
    manager.load()
    knowledge_engine = KnowledgeEngine()
    acceptance = ResearchSourceAcceptanceService(
        knowledge_engine,
        manager,
        JsonFileResearchSourceContentStore(root / "research_source_content.json"),
    )

    print(f"\nQuestion: {arguments.question}\n")
    run = manager.create(arguments.question)
    report.add("run created", True, run.run_id)

    candidates: list[object] = []
    if arguments.discover:
        provider = CrossrefResearchSourceDiscoveryProvider()
        print(f"\n  discovery provider: {provider.provider_name}")
        try:
            candidates = list(
                provider.discover(arguments.question, limit=DISCOVERY_LIMIT)
            )
        except ResearchError as error:
            report.add("network request", True, "attempted")
            report.add("candidates discovered", False, f"refused: {error}")
            report.render()
            return 1
        report.add("network request", True, "one discovery request")
        report.add(
            "candidates discovered", bool(candidates), f"{len(candidates)} found"
        )
        manager.add_discovery(
            run.run_id,
            arguments.question,
            provider.provider_name,
            candidates,
        )
        report.add(
            "discovery recorded",
            True,
            "audit record only, nothing accepted",
        )
        for index, candidate in enumerate(candidates):
            print(f"\n    [{index}] {candidate.title}")
            print(f"        {candidate.url}")
            if candidate.snippet:
                print(f"        {candidate.snippet[:160]}")
        print(
            "\n  A candidate is metadata someone else published. Nothing above "
            "has been read, fetched, or accepted."
        )
    else:
        report.add("network request", False, "no --discover")
        report.add("candidates discovered", False)
        report.add("discovery recorded", False)

    document_id: str | None = None
    selected_url: str | None = arguments.url
    selection_detail = "given explicitly by you"
    if selected_url is None and arguments.accept is not None:
        if not 0 <= arguments.accept < len(candidates):
            report.add("source selected", False, "index out of range")
            report.render()
            return 1
        selected_url = candidates[arguments.accept].url
        selection_detail = f"index {arguments.accept}, chosen by you"

    if selected_url is not None:
        report.add("source selected", True, selection_detail)
        try:
            source = HttpResearchSourceFetcher().fetch(selected_url)
        except ResearchError as error:
            report.add("source fetched", False, f"refused: {error}")
            report.render()
            return 1
        report.add("source fetched", True, f"{len(source.content)} characters")
        result = acceptance.accept(source, run.run_id)
        document_id = result.document_id
        report.add(
            "source accepted",
            result.accepted,
            document_id or result.failure_reason,
        )
    else:
        report.add("source selected", False, "no --accept or --url")
        report.add("source fetched", False)
        report.add("source accepted", False)

    if arguments.evidence and document_id is not None:
        chunk = next(
            (
                candidate
                for candidate in knowledge_engine.chunks()
                if candidate.document_id == document_id and candidate.index == 0
            ),
            None,
        )
        if chunk is None:
            report.add("evidence recorded", False, "no chunk to cite")
        else:
            updated = manager.add_evidence(
                run.run_id,
                chunk,
                "Recorded by the pipeline diagnostic.",
            )
            report.add(
                "evidence recorded",
                True,
                updated.evidence[-1].evidence_id,
            )
    else:
        report.add(
            "evidence recorded",
            False,
            "no --evidence" if not arguments.evidence else "nothing accepted",
        )

    report.add("assessment recorded", False, "requires an authored assessment step")
    report.add("claim created", False, "requires an authored claim step")

    report.render()

    summary = CanonicalResearchSummary.from_runs(manager.list())
    print("\n  Canonical research state now:")
    for line in summary.lines():
        print(f"    {line}")

    if temporary_directory is not None:
        temporary_directory.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
