"""Interpret one proven, bounded file range as local-only UTF-8 text.

This tool is registered only when desktop composition explicitly supplies the
same bounded scope and supported platform reader to ``ToolRuntime``. A reader
is injected; this module never opens a path, owns a native handle, retries a
read, or continues into another range.

Only bytes retained by the reader enter the text policy.  NUL means binary and
is declined.  A UTF-8 BOM is stripped only at offset zero.  Everything else is
decoded strictly as UTF-8, so split multi-byte ranges are declined rather than
silently repaired.  Successful text remains local-only, untrusted data in the
typed ``FilesystemContentPayload`` channel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from tools.FilesystemContentPayload import (
    MAX_CONTENT_BYTES,
    MAX_CONTENT_OFFSET,
    FilesystemContentPayload,
)
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult
from tools.WindowsRootedOpen import (
    WindowsRootedOpenError,
    WindowsRootedOpenFailure,
)

FILESYSTEM_READ_SUMMARY = (
    "Read one explicitly authorized, bounded local-file range as strict UTF-8 "
    "text. Returns local-only untrusted data."
)

PATH_ARGUMENT = "path"
OFFSET_ARGUMENT = "offset"
MAX_BYTES_ARGUMENT = "max_bytes"
ACCEPTED_ARGUMENTS: frozenset[str] = frozenset(
    {PATH_ARGUMENT, OFFSET_ARGUMENT, MAX_BYTES_ARGUMENT}
)

MISSING_PATH_DETAIL = "This tool requires a 'path' argument."
MISSING_OFFSET_DETAIL = "This tool requires an 'offset' argument."
MISSING_MAX_BYTES_DETAIL = "This tool requires a 'max_bytes' argument."
BAD_PATH_DETAIL = "The 'path' argument must be text."
UNKNOWN_ARGUMENT_DETAIL = (
    "This tool accepts only 'path', 'offset', and 'max_bytes' arguments."
)
BAD_OFFSET_DETAIL = (
    "The 'offset' argument must be a whole byte number within the supported range."
)
BAD_MAX_BYTES_DETAIL = (
    "The 'max_bytes' argument must be a whole byte count within the supported range."
)
BINARY_DETAIL = "The requested range contains binary data and was not returned."
INVALID_UTF8_DETAIL = "The requested range is not valid UTF-8 text."
READ_FAILED_DETAIL = "The bounded file-content request could not be completed safely."
READ_SUCCEEDED_DETAIL = "Read one bounded UTF-8 text range."

_UTF8_BOM = b"\xef\xbb\xbf"


class _ContentRangeObservation(Protocol):
    root_id: str
    resource: str
    offset: int
    bytes_requested: int
    bytes_returned: int
    truncated: bool
    file_size_bytes: int
    modified_utc: datetime
    read_at_utc: datetime
    content: bytes


@runtime_checkable
class _ContentRangeReader(Protocol):
    @property
    def root_id(self) -> str: ...

    def read_range(
        self,
        relative: str,
        *,
        offset: int,
        max_bytes: int,
    ) -> _ContentRangeObservation: ...


class FilesystemReadTool:
    """Return one authorized text range without registering it globally."""

    def __init__(self, reader: object) -> None:
        if not isinstance(reader, _ContentRangeReader):
            raise TypeError("A filesystem read tool requires a bounded range reader.")
        self._reader = reader
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.FILESYSTEM_READ,
            effects=frozenset({ToolEffect.READS_FILESYSTEM_CONTENT}),
            summary=FILESYSTEM_READ_SUMMARY,
        )

    @property
    def root_id(self) -> str:
        """Return the opaque reader scope used to bind runtime composition."""
        return self._reader.root_id

    @property
    def descriptor(self) -> ToolDescriptor:
        """Declare the effect checked before this implementation is reached."""
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Read exactly one range and apply the fixed Phase-A text policy."""
        if self._unsupported(invocation):
            return self._declined(UNKNOWN_ARGUMENT_DETAIL)
        for name, detail in (
            (PATH_ARGUMENT, MISSING_PATH_DETAIL),
            (OFFSET_ARGUMENT, MISSING_OFFSET_DETAIL),
            (MAX_BYTES_ARGUMENT, MISSING_MAX_BYTES_DETAIL),
        ):
            if not self._supplied(invocation, name):
                return self._declined(detail)

        requested = invocation.argument(PATH_ARGUMENT)
        if not isinstance(requested, str):
            # Defence in depth: ToolInvocation validates this at construction,
            # but a content carrier must still fail boundedly if a caller
            # bypasses or corrupts that contract.
            return self._declined(BAD_PATH_DETAIL)
        if not requested.strip():
            return self._declined(MISSING_PATH_DETAIL)
        offset = self._whole_number(
            invocation.argument(OFFSET_ARGUMENT),
            maximum=MAX_CONTENT_OFFSET,
        )
        if offset is None:
            return self._declined(BAD_OFFSET_DETAIL)
        max_bytes = self._whole_number(
            invocation.argument(MAX_BYTES_ARGUMENT),
            maximum=MAX_CONTENT_BYTES,
        )
        if max_bytes is None:
            return self._declined(BAD_MAX_BYTES_DETAIL)

        try:
            observation = self._reader.read_range(
                requested,
                offset=offset,
                max_bytes=max_bytes,
            )
        except WindowsRootedOpenError as error:
            return self._rooted_failure(error)
        except Exception:
            # Reader exceptions can contain paths, native codes, or file data.
            return self._failed(READ_FAILED_DETAIL)

        return self._interpret(
            observation,
            requested_offset=offset,
            requested_max_bytes=max_bytes,
        )

    def _interpret(
        self,
        observation: _ContentRangeObservation,
        *,
        requested_offset: int,
        requested_max_bytes: int,
    ) -> ToolResult:
        try:
            raw = observation.content
            if not isinstance(raw, bytes):
                return self._failed(READ_FAILED_DETAIL)
            if (
                observation.offset != requested_offset
                or observation.bytes_requested != requested_max_bytes
            ):
                return self._failed(READ_FAILED_DETAIL)
            if b"\x00" in raw:
                return self._declined(BINARY_DETAIL)

            bom_stripped = observation.offset == 0 and raw.startswith(_UTF8_BOM)
            encoded_text = raw[len(_UTF8_BOM) :] if bom_stripped else raw
            try:
                text = encoded_text.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                return self._declined(INVALID_UTF8_DETAIL)

            payload = FilesystemContentPayload(
                root_id=observation.root_id,
                resource=observation.resource,
                offset=observation.offset,
                bytes_requested=observation.bytes_requested,
                bytes_returned=observation.bytes_returned,
                truncated=observation.truncated,
                file_size_bytes=observation.file_size_bytes,
                modified_utc=observation.modified_utc,
                bom_stripped=bom_stripped,
                read_at_utc=observation.read_at_utc,
                text=text,
            )
        except Exception:
            # Observation access and validation can surface adapter-owned
            # details. Nothing from that boundary may escape in an exception.
            return self._failed(READ_FAILED_DETAIL)

        return ToolResult(
            capability=ToolCapability.FILESYSTEM_READ,
            performed=True,
            detail=READ_SUCCEEDED_DETAIL,
            succeeded=True,
            content=payload,
        )

    @staticmethod
    def _rooted_failure(error: WindowsRootedOpenError) -> ToolResult:
        # WindowsRootedOpenError owns fixed, path-free wording. Forward only
        # these exact bounded decline branches; every machine failure is
        # collapsed to READ_FAILED_DETAIL instead of forwarding native detail.
        if error.failure is WindowsRootedOpenFailure.PATH_REFUSED:
            if error.path_refusal is FilesystemPathRefusal.UNREADABLE:
                return FilesystemReadTool._failed(READ_FAILED_DETAIL)
            return FilesystemReadTool._declined(str(error))
        if error.failure in (
            WindowsRootedOpenFailure.NOT_FILE,
            WindowsRootedOpenFailure.SENSITIVE_FILE,
        ):
            return FilesystemReadTool._declined(str(error))
        return FilesystemReadTool._failed(READ_FAILED_DETAIL)

    @staticmethod
    def _whole_number(raw: object, *, maximum: int) -> int | None:
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        if not text or not text.isascii() or not text.isdigit():
            return None
        value = int(text)
        return value if value <= maximum else None

    @staticmethod
    def _declined(detail: str) -> ToolResult:
        return ToolResult.declined(ToolCapability.FILESYSTEM_READ, detail)

    @staticmethod
    def _failed(detail: str) -> ToolResult:
        return ToolResult.failed(ToolCapability.FILESYSTEM_READ, detail)

    @staticmethod
    def _unsupported(invocation: ToolInvocation) -> tuple[str, ...]:
        return tuple(
            name for name, _ in invocation.arguments if name not in ACCEPTED_ARGUMENTS
        )

    @staticmethod
    def _supplied(invocation: ToolInvocation, name: str) -> bool:
        return any(candidate == name for candidate, _ in invocation.arguments)
