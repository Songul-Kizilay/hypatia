"""Read-only preview and confirmed file export of one mission audit bundle.

Preview renders both files from canonical state and writes nothing.  Saving
re-renders, refuses if either fingerprint changed since the preview, and only
then publishes two new files that must not already exist.  Neither step
executes, resumes, fetches, calls a model or provider, spends, reviews,
approves, closes or otherwise changes any mission, run or approval record.
"""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchExportPublisher import publish_new_export_file
from research.ResearchMissionAudit import (
    build_mission_audit,
    mission_audit_json,
    render_mission_audit_markdown,
)
from research.ResearchMissionAuditExport import (
    MAX_MISSION_AUDIT_PREVIEW_CHARACTERS,
    ResearchMissionAuditExportPreview,
    ResearchMissionAuditExportResult,
    mission_audit_filenames,
)
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.SourceIdentity import identity_of

MISSION_AUDIT_PREVIEW_INTENT = "research_mission_audit_export_preview"
MISSION_AUDIT_SAVE_INTENT = "research_mission_audit_export_save"


class ResearchMissionAuditApplicationService:
    """Assemble canonical mission audit files; never an execution path."""

    def __init__(
        self,
        execution: ResearchPlanExecutionApplicationService,
        runs: ResearchRunManager | None,
        authorizations: ResearchPlanAuthorizationApplicationService | None,
        hypatia_version: Callable[[], str],
    ) -> None:
        self._execution = execution
        self._runs = runs
        self._authorizations = authorizations
        self._hypatia_version = hypatia_version

    @staticmethod
    def is_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") in {
            MISSION_AUDIT_PREVIEW_INTENT,
            MISSION_AUDIT_SAVE_INTENT,
        }

    def process(self, request: BrainRequest) -> BrainResponse:
        intent = str(request.metadata.get("intent"))
        try:
            if intent == MISSION_AUDIT_PREVIEW_INTENT:
                return self._preview(request)
            return self._save(request)
        except ResearchError as error:
            return BrainResponse(
                message=f"Mission audit export was not completed: {error}",
                request_id=request.request_id,
                intent=intent,
                memory_count=0,
                success=False,
            )

    def render(self, plan_id: str) -> tuple[str, str, str, bytes, bytes]:
        """Return run ID, summary and both encoded files for one mission."""
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ResearchError("A mission plan ID is required.")
        snapshot = self._execution.mission_snapshot(plan_id.strip())
        if snapshot is None:
            raise ResearchError("No mission execution with that plan ID is known.")
        run: ResearchRun | None = None
        if self._runs is not None and snapshot.research_run_id:
            try:
                run = self._runs.get(snapshot.research_run_id)
            except ResearchError:
                run = None
        authorization = (
            self._authorizations.authorization_for_execution(snapshot.plan_id)
            if self._authorizations is not None
            else None
        )
        audit = build_mission_audit(
            snapshot,
            run,
            authorization,
            hypatia_version=self._hypatia_version(),
            source_revalidations=(
                tuple(self._runs.source_revalidations())
                if self._runs is not None
                else ()
            ),
            temporal_histories=(
                tuple(
                    self._runs.temporal_history(requested_url, run_id=run.run_id)
                    for requested_url in sorted(
                        {
                            identity: source.requested_url
                            for source in run.sources
                            if source.requested_url is not None
                            for identity in (identity_of(source.requested_url),)
                            if identity
                        }.values()
                    )
                )
                if self._runs is not None and run is not None
                else ()
            ),
        )
        markdown = render_mission_audit_markdown(audit, run)
        evaluation = audit["evaluation"]
        summary = "\n".join(
            (
                f"Mission audit for plan {snapshot.plan_id} "
                f"(run {snapshot.research_run_id or 'unavailable'}).",
                f"Execution status: {snapshot.status.value}; recorded stop reason: "
                + (audit["execution"]["stop_reason"] or "unavailable")
                + ".",
                "Goal satisfaction: "
                + (
                    evaluation["goal_satisfaction"]["status"]
                    if evaluation
                    else "unavailable"
                )
                + "; readiness: "
                + (
                    evaluation["completion_readiness"]["status"]
                    if evaluation
                    else "unavailable"
                )
                + ".",
                "Limitations: " + ", ".join(audit["limitations"]) + ".",
                "Preview only: no file is written until you confirm. Exporting "
                "executes, fetches, calls, spends and changes nothing.",
            )
        )
        return (
            snapshot.research_run_id or "",
            summary,
            snapshot.plan_id,
            markdown.encode("utf-8"),
            mission_audit_json(audit).encode("utf-8"),
        )

    def _preview(self, request: BrainRequest) -> BrainResponse:
        run_id, summary, plan_id, markdown, document = self.render(
            str(request.metadata.get("research_plan_id", ""))
        )
        text = markdown.decode("utf-8")
        markdown_name, json_name = mission_audit_filenames(plan_id)
        preview = ResearchMissionAuditExportPreview(
            plan_id=plan_id,
            research_run_id=run_id,
            markdown_filename=markdown_name,
            json_filename=json_name,
            markdown_sha256=sha256(markdown).hexdigest(),
            json_sha256=sha256(document).hexdigest(),
            summary=summary,
            markdown_preview=text[:MAX_MISSION_AUDIT_PREVIEW_CHARACTERS],
            total_markdown_characters=len(text),
        )
        return BrainResponse(
            message=f"{summary}\nFiles: {markdown_name}, {json_name}.",
            request_id=request.request_id,
            intent=MISSION_AUDIT_PREVIEW_INTENT,
            memory_count=0,
            research_mission_audit_export_preview=preview,
        )

    def _save(self, request: BrainRequest) -> BrainResponse:
        directory = self._directory(request.metadata.get("destination_directory"))
        _, _, plan_id, markdown, document = self.render(
            str(request.metadata.get("research_plan_id", ""))
        )
        markdown_sha = sha256(markdown).hexdigest()
        json_sha = sha256(document).hexdigest()
        if (
            request.metadata.get("expected_markdown_sha256") != markdown_sha
            or request.metadata.get("expected_json_sha256") != json_sha
        ):
            raise ResearchError(
                "the mission audit changed since its preview; preview it again."
            )
        markdown_name, json_name = mission_audit_filenames(plan_id)
        markdown_path = directory / markdown_name
        json_path = directory / json_name
        if markdown_path.exists() or json_path.exists():
            raise ResearchError("an audit file already exists; no file was replaced.")
        publish_new_export_file(markdown_path, markdown)
        try:
            publish_new_export_file(json_path, document)
        except ResearchError:
            # Only the file this call just created is removed, so a partial
            # bundle is never left behind.
            markdown_path.unlink(missing_ok=True)
            raise
        result = ResearchMissionAuditExportResult(
            plan_id=plan_id,
            markdown_path=str(markdown_path),
            json_path=str(json_path),
            markdown_sha256=markdown_sha,
            json_sha256=json_sha,
            markdown_bytes=len(markdown),
            json_bytes=len(document),
        )
        return BrainResponse(
            message=(
                f"Mission audit exported: {markdown_path} and {json_path}. "
                "Nothing else was changed."
            ),
            request_id=request.request_id,
            intent=MISSION_AUDIT_SAVE_INTENT,
            memory_count=0,
            research_mission_audit_export_result=result,
        )

    @staticmethod
    def _directory(value: object) -> Path:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ResearchError("an export directory is required.")
        directory = Path(value.strip())
        if not directory.is_absolute() or not directory.is_dir():
            raise ResearchError(
                "the export directory must be an existing absolute path."
            )
        return directory
