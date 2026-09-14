"""Acquire or read one bounded Windows file range through held handles.

This module is the production-owned Windows foundation for the explicitly
composed local-file content capability. It performs lexical admission through
``FilesystemRoot`` and then repeats the decisive proof with Windows handles:
the configured root is opened without following its final reparse point, each
relative component is opened against its held parent, every reparse point is
refused, and the final handle is checked for containment and identity.

Only the desktop composition root and isolated text-policy Tool import this
module's bounded failure and observation contract. Its content-range method
returns one bounded raw observation, never a native handle, decoded text, or
``ToolResult``. It loads Windows system APIs only when constructed on Windows.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import (
    MAX_PATH_DEPTH,
    MAX_RELATIVE_PATH_LENGTH,
    MAX_ROOT_ID_LENGTH,
    FilesystemRoot,
)
from tools.FilesystemSensitivePathPolicy import (
    FilesystemSensitiveClass,
    FilesystemSensitivePathPolicy,
)

__all__ = [
    "WindowsContentRangeObservation",
    "WindowsOpenedFile",
    "WindowsRootedOpen",
    "WindowsRootedOpenError",
    "WindowsRootedOpenFailure",
]

FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400

FILE_READ_ATTRIBUTES = 0x00000080
FILE_READ_DATA = 0x00000001
SYNCHRONIZE = 0x00100000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
_SHARE_ALL = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE

OPEN_EXISTING = 3
FILE_OPEN = 1

FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_OPEN_REPARSE_POINT = 0x00200000

OBJ_CASE_INSENSITIVE = 0x00000040
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
VOLUME_NAME_NT = 0x00000002
LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x00000800
ERROR_HANDLE_EOF = 38
ERROR_IO_PENDING = 997
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_FILESYSTEM_NAME_CAPACITY = 64
_MAX_CONTENT_BYTES = 64 * 1024
_MAX_CONTENT_OFFSET = (1 << 63) - 1
_MAX_FILETIME = (1 << 64) - 1
_WINDOWS_EPOCH_UTC = datetime(1601, 1, 1, tzinfo=UTC)


class WindowsRootedOpenFailure(StrEnum):
    """Name one bounded reason the rooted-open proof did not complete."""

    NOT_WINDOWS = "not_windows"
    API_UNAVAILABLE = "api_unavailable"
    UNSUPPORTED_FILESYSTEM = "unsupported_filesystem"
    PATH_REFUSED = "path_refused"
    ENTRY_CHANGED = "entry_changed"
    NOT_FILE = "not_file"
    ROOT_CHANGED = "root_changed"
    OPEN_FAILED = "open_failed"
    REPARSE_POINT = "reparse_point"
    NOT_DIRECTORY = "not_directory"
    CONTAINMENT_UNPROVEN = "containment_unproven"
    IDENTITY_MISMATCH = "identity_mismatch"
    SENSITIVE_FILE = "sensitive_file"
    READ_FAILED = "read_failed"
    READ_INCOMPLETE = "read_incomplete"
    CONTENT_CHANGED = "content_changed"
    CLOSE_FAILED = "close_failed"


_FAILURE_DETAILS: dict[WindowsRootedOpenFailure, str] = {
    WindowsRootedOpenFailure.NOT_WINDOWS: (
        "The Windows rooted-open boundary is unavailable on this platform."
    ),
    WindowsRootedOpenFailure.API_UNAVAILABLE: (
        "A required Windows rooted-open API is unavailable."
    ),
    WindowsRootedOpenFailure.UNSUPPORTED_FILESYSTEM: (
        "The acquired root is not on the supported filesystem boundary."
    ),
    WindowsRootedOpenFailure.PATH_REFUSED: (
        "The configured filesystem policy refused the relative path."
    ),
    WindowsRootedOpenFailure.ENTRY_CHANGED: (
        "The admitted entry changed before handle acquisition."
    ),
    WindowsRootedOpenFailure.NOT_FILE: ("The admitted target is not a regular file."),
    WindowsRootedOpenFailure.ROOT_CHANGED: (
        "The configured filesystem root changed after construction."
    ),
    WindowsRootedOpenFailure.OPEN_FAILED: (
        "A required rooted handle could not be acquired or queried."
    ),
    WindowsRootedOpenFailure.REPARSE_POINT: (
        "An acquired component is a refused reparse point."
    ),
    WindowsRootedOpenFailure.NOT_DIRECTORY: (
        "An intermediate component is not a directory."
    ),
    WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN: (
        "Final-handle containment could not be proven."
    ),
    WindowsRootedOpenFailure.IDENTITY_MISMATCH: (
        "The admitted and acquired file identities differ."
    ),
    WindowsRootedOpenFailure.SENSITIVE_FILE: (
        "The requested file belongs to a refused sensitive class."
    ),
    WindowsRootedOpenFailure.READ_FAILED: (
        "The bounded file-content read did not complete safely."
    ),
    WindowsRootedOpenFailure.READ_INCOMPLETE: (
        "The bounded file-content read ended before a stable boundary."
    ),
    WindowsRootedOpenFailure.CONTENT_CHANGED: (
        "The file changed during the bounded content read."
    ),
    WindowsRootedOpenFailure.CLOSE_FAILED: (
        "A native rooted-open handle could not be closed."
    ),
}


class WindowsRootedOpenError(RuntimeError):
    """Stop with a bounded category and no native or path-shaped detail."""

    def __init__(
        self,
        failure: WindowsRootedOpenFailure,
        *,
        path_refusal: FilesystemPathRefusal = FilesystemPathRefusal.NONE,
        sensitive_class: FilesystemSensitiveClass = FilesystemSensitiveClass.NONE,
    ) -> None:
        if failure is WindowsRootedOpenFailure.SENSITIVE_FILE:
            if not sensitive_class.refused:
                raise ValueError("A sensitive-file refusal needs a bounded class.")
            detail = (
                f"The requested file is refused as {sensitive_class.operator_label}."
            )
        else:
            if sensitive_class.refused:
                raise ValueError("Only a sensitive-file refusal may carry a class.")
            detail = _FAILURE_DETAILS[failure]
        self.failure = failure
        self.path_refusal = path_refusal
        self.sensitive_class = sensitive_class
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class WindowsContentRangeObservation:
    """Return one closed-handle, bounded raw content observation."""

    root_id: str
    resource: str
    offset: int
    bytes_requested: int
    bytes_returned: int
    truncated: bool
    file_size_bytes: int
    modified_utc: datetime
    read_at_utc: datetime
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.root_id, str)
            or not self.root_id.strip()
            or len(self.root_id) > MAX_ROOT_ID_LENGTH
        ):
            raise ValueError("A content observation needs a root identifier.")
        if (
            not isinstance(self.resource, str)
            or not self.resource.strip()
            or len(self.resource) > MAX_RELATIVE_PATH_LENGTH
        ):
            raise ValueError("A content observation needs a relative resource.")
        try:
            self.root_id.encode("utf-8", errors="strict")
            self.resource.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise ValueError(
                "Content observation references must be valid Unicode."
            ) from None
        parts = self.resource.split("/")
        if (
            self.resource.startswith("/")
            or "\\" in self.resource
            or ":" in self.resource
            or any(part in {"", ".", ".."} for part in parts)
            or len(parts) > MAX_PATH_DEPTH
        ):
            raise ValueError("The content observation resource is not canonical.")
        self._require_bounded_integer(
            self.offset,
            maximum=_MAX_CONTENT_OFFSET,
            label="offset",
        )
        self._require_bounded_integer(
            self.bytes_requested,
            maximum=_MAX_CONTENT_BYTES,
            label="requested byte count",
        )
        self._require_bounded_integer(
            self.bytes_returned,
            maximum=self.bytes_requested,
            label="returned byte count",
        )
        self._require_bounded_integer(
            self.file_size_bytes,
            maximum=_MAX_CONTENT_OFFSET,
            label="file size",
        )
        if not isinstance(self.content, bytes):
            raise TypeError("Content observation bytes must be immutable bytes.")
        if len(self.content) != self.bytes_returned:
            raise ValueError("Content observation byte count is inconsistent.")
        if not isinstance(self.truncated, bool):
            raise TypeError("Content observation truncation must be boolean.")
        expected_truncation = self.offset + self.bytes_returned < self.file_size_bytes
        if self.truncated is not expected_truncation:
            raise ValueError("Content observation truncation is inconsistent.")
        for value in (self.modified_utc, self.read_at_utc):
            if (
                not isinstance(value, datetime)
                or value.utcoffset() is None
                or value.utcoffset() != timedelta(0)
            ):
                raise ValueError("Content observation times must be UTC-aware.")

    @staticmethod
    def _require_bounded_integer(value: int, *, maximum: int, label: str) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > maximum
        ):
            raise ValueError(f"Content observation {label} is invalid.")


class WindowsOpenedFile:
    """Expose bounded proof state while keeping the native handle private."""

    __slots__ = (
        "__active",
        "__component_count",
        "__root_id",
    )

    def __init__(
        self,
        *,
        root_id: str,
        component_count: int,
    ) -> None:
        self.__root_id = root_id
        self.__component_count = component_count
        self.__active = True

    @property
    def root_id(self) -> str:
        """Return the configured root identifier, never its path."""
        return self.__root_id

    @property
    def component_count(self) -> int:
        """Return path shape without disclosing a component name."""
        return self.__component_count

    @property
    def content_bytes_read(self) -> int:
        """Prove that this inert foundation read no file bytes."""
        return 0

    @property
    def is_open(self) -> bool:
        """Return whether the owning acquire context is still active."""
        return self.__active

    def _deactivate(self) -> None:
        self.__active = False


class _WindowsRootedOpenStage(StrEnum):
    """Deterministic private seams for adversarial replacement tests."""

    AFTER_ADMISSION = "after_admission"
    AFTER_ROOT_OPEN = "after_root_open"
    BEFORE_COMPONENT_OPEN = "before_component_open"
    AFTER_COMPONENT_OPEN = "after_component_open"
    BEFORE_FINAL_PROOF = "before_final_proof"
    BEFORE_CONTENT_READ = "before_content_read"
    AFTER_CONTENT_READ = "after_content_read"


class _FileIdentity(tuple[int, int]):
    """A hashable NTFS volume-serial and 64-bit file-index pair."""

    __slots__ = ()

    def __new__(cls, volume_serial: int, file_index: int) -> _FileIdentity:
        return super().__new__(cls, (volume_serial, file_index))


@dataclass(frozen=True, slots=True)
class _FileObservation:
    identity: _FileIdentity
    size: int
    last_write_filetime: int


@dataclass(frozen=True, slots=True)
class _NativeReadResult:
    content: bytes
    count: int
    eof_signal: bool = False


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", wintypes.LPVOID),
        ("SecurityQualityOfService", wintypes.LPVOID),
    ]


class _IoStatusValue(ctypes.Union):
    _fields_ = [("Status", wintypes.LONG), ("Pointer", wintypes.LPVOID)]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [("Value", _IoStatusValue), ("Information", ctypes.c_size_t)]


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


class _WindowsApi(Protocol):
    def open_root(self, absolute_root: str) -> int: ...

    def open_relative(self, parent: int, component: str, *, final: bool) -> int: ...

    def open_relative_content(self, parent: int, component: str) -> int: ...

    def close(self, handle: int) -> bool: ...

    def attributes(self, handle: int) -> int: ...

    def filesystem_name(self, handle: int) -> str: ...

    def identity(self, handle: int) -> _FileIdentity: ...

    def observation(self, handle: int) -> _FileObservation: ...

    def read(self, handle: int, *, offset: int, capacity: int) -> _NativeReadResult: ...

    def final_path(self, handle: int) -> PureWindowsPath: ...


class _SystemWindowsApi:
    """Lazily bind only the approved Windows system-DLL entry points."""

    def __init__(self) -> None:
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.API_UNAVAILABLE)
        try:
            self._kernel32 = loader(
                "kernel32.dll",
                use_last_error=True,
                winmode=LOAD_LIBRARY_SEARCH_SYSTEM32,
            )
            self._ntdll = loader(
                "ntdll.dll",
                use_last_error=True,
                winmode=LOAD_LIBRARY_SEARCH_SYSTEM32,
            )
            self._bind()
        except AttributeError, OSError, TypeError:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.API_UNAVAILABLE
            ) from None

    def _bind(self) -> None:
        self._create_file = self._kernel32.CreateFileW
        self._create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self._create_file.restype = wintypes.HANDLE

        self._close_handle = self._kernel32.CloseHandle
        self._close_handle.argtypes = [wintypes.HANDLE]
        self._close_handle.restype = wintypes.BOOL

        self._file_information = self._kernel32.GetFileInformationByHandle
        self._file_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        self._file_information.restype = wintypes.BOOL

        self._read_file = self._kernel32.ReadFile
        self._read_file.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(_Overlapped),
        ]
        self._read_file.restype = wintypes.BOOL

        self._file_information_ex = self._kernel32.GetFileInformationByHandleEx
        self._file_information_ex.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self._file_information_ex.restype = wintypes.BOOL

        self._final_path = self._kernel32.GetFinalPathNameByHandleW
        self._final_path.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self._final_path.restype = wintypes.DWORD

        self._volume_information = self._kernel32.GetVolumeInformationByHandleW
        self._volume_information.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self._volume_information.restype = wintypes.BOOL

        self._nt_create_file = self._ntdll.NtCreateFile
        self._nt_create_file.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            ctypes.POINTER(_ObjectAttributes),
            ctypes.POINTER(_IoStatusBlock),
            wintypes.LPVOID,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.LPVOID,
            wintypes.ULONG,
        ]
        self._nt_create_file.restype = wintypes.LONG

    def open_root(self, absolute_root: str) -> int:
        value = self._create_file(
            absolute_root,
            FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            _SHARE_ALL,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        numeric = int(value or 0)
        if not numeric or numeric == _INVALID_HANDLE_VALUE:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        return numeric

    def open_relative(self, parent: int, component: str, *, final: bool) -> int:
        del final  # Kind is proven after the attribute-only acquisition.
        return self._open_relative(
            parent,
            component,
            access=FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            share_access=_SHARE_ALL,
        )

    def open_relative_content(self, parent: int, component: str) -> int:
        return self._open_relative(
            parent,
            component,
            access=FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            share_access=FILE_SHARE_READ,
        )

    def _open_relative(
        self,
        parent: int,
        component: str,
        *,
        access: int,
        share_access: int,
    ) -> int:
        buffer = ctypes.create_unicode_buffer(component)
        encoded_length = len(component.encode("utf-16-le"))
        name = _UnicodeString(
            Length=encoded_length,
            MaximumLength=encoded_length + 2,
            Buffer=ctypes.cast(buffer, wintypes.LPWSTR),
        )
        attributes = _ObjectAttributes(
            Length=ctypes.sizeof(_ObjectAttributes),
            RootDirectory=wintypes.HANDLE(parent),
            ObjectName=ctypes.pointer(name),
            Attributes=OBJ_CASE_INSENSITIVE,
            SecurityDescriptor=None,
            SecurityQualityOfService=None,
        )
        status_block = _IoStatusBlock()
        output = wintypes.HANDLE()
        status = int(
            self._nt_create_file(
                ctypes.byref(output),
                access,
                ctypes.byref(attributes),
                ctypes.byref(status_block),
                None,
                FILE_ATTRIBUTE_NORMAL,
                share_access,
                FILE_OPEN,
                FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                None,
                0,
            )
        )
        numeric = int(output.value or 0)
        if status != 0 or not numeric:
            if numeric:
                try:
                    closed = self.close(numeric)
                except Exception:
                    raise WindowsRootedOpenError(
                        WindowsRootedOpenFailure.CLOSE_FAILED
                    ) from None
                if not closed:
                    raise WindowsRootedOpenError(WindowsRootedOpenFailure.CLOSE_FAILED)
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        return numeric

    def close(self, handle: int) -> bool:
        return bool(self._close_handle(wintypes.HANDLE(handle)))

    def attributes(self, handle: int) -> int:
        info = _FileAttributeTagInfo()
        succeeded = self._file_information_ex(
            wintypes.HANDLE(handle),
            FILE_ATTRIBUTE_TAG_INFO_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not succeeded:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        return int(info.FileAttributes)

    def filesystem_name(self, handle: int) -> str:
        serial = wintypes.DWORD()
        maximum_component = wintypes.DWORD()
        flags = wintypes.DWORD()
        name = ctypes.create_unicode_buffer(_FILESYSTEM_NAME_CAPACITY)
        succeeded = self._volume_information(
            wintypes.HANDLE(handle),
            None,
            0,
            ctypes.byref(serial),
            ctypes.byref(maximum_component),
            ctypes.byref(flags),
            name,
            len(name),
        )
        if not succeeded:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.UNSUPPORTED_FILESYSTEM
            )
        return name.value

    def identity(self, handle: int) -> _FileIdentity:
        return self._observation(
            handle,
            failure=WindowsRootedOpenFailure.OPEN_FAILED,
        ).identity

    def observation(self, handle: int) -> _FileObservation:
        return self._observation(
            handle,
            failure=WindowsRootedOpenFailure.READ_FAILED,
        )

    def _observation(
        self,
        handle: int,
        *,
        failure: WindowsRootedOpenFailure,
    ) -> _FileObservation:
        info = _ByHandleFileInformation()
        succeeded = self._file_information(wintypes.HANDLE(handle), ctypes.byref(info))
        if not succeeded:
            raise WindowsRootedOpenError(failure)
        file_index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
        file_size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        last_write = (int(info.ftLastWriteTime.dwHighDateTime) << 32) | int(
            info.ftLastWriteTime.dwLowDateTime
        )
        return _FileObservation(
            identity=_FileIdentity(int(info.dwVolumeSerialNumber), file_index),
            size=file_size,
            last_write_filetime=last_write,
        )

    def read(self, handle: int, *, offset: int, capacity: int) -> _NativeReadResult:
        buffer = ctypes.create_string_buffer(capacity)
        count = wintypes.DWORD()
        overlapped = _Overlapped()
        overlapped.Offset = offset & 0xFFFFFFFF
        overlapped.OffsetHigh = (offset >> 32) & 0xFFFFFFFF
        ctypes.set_last_error(0)
        succeeded = self._read_file(
            wintypes.HANDLE(handle),
            ctypes.byref(buffer),
            capacity,
            ctypes.byref(count),
            ctypes.byref(overlapped),
        )
        numeric_count = int(count.value)
        if not succeeded:
            error = ctypes.get_last_error()
            if error == ERROR_HANDLE_EOF:
                return _NativeReadResult(b"", numeric_count, eof_signal=True)
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        if numeric_count > capacity:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        return _NativeReadResult(bytes(buffer.raw[:numeric_count]), numeric_count)

    def final_path(self, handle: int) -> PureWindowsPath:
        required = int(
            self._final_path(wintypes.HANDLE(handle), None, 0, VOLUME_NAME_NT)
        )
        if not required:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN)
        buffer = ctypes.create_unicode_buffer(required + 1)
        written = int(
            self._final_path(
                wintypes.HANDLE(handle), buffer, len(buffer), VOLUME_NAME_NT
            )
        )
        if not written or written >= len(buffer):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN)
        return PureWindowsPath(buffer.value)


class _OwnedHandle:
    """Own exactly one native handle and report any close failure."""

    __slots__ = ("_api", "_value")

    def __init__(self, api: _WindowsApi, value: int) -> None:
        self._api = api
        self._value = value

    @property
    def is_open(self) -> bool:
        return bool(self._value)

    @property
    def _native_value(self) -> int:
        if not self._value:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        return self._value

    def __enter__(self) -> _OwnedHandle:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._value:
            return
        value = self._value
        self._value = 0
        try:
            succeeded = self._api.close(value)
        except Exception:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.CLOSE_FAILED
            ) from None
        if not succeeded:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.CLOSE_FAILED)


_Seam = Callable[[_WindowsRootedOpenStage, int], None]


class WindowsRootedOpen:
    """Prove and temporarily own one contained NTFS file handle."""

    def __init__(
        self,
        root: FilesystemRoot,
        *,
        _api: _WindowsApi | None = None,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(root, FilesystemRoot):
            raise TypeError("WindowsRootedOpen requires a FilesystemRoot.")
        if _api is None:
            if os.name != "nt":
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_WINDOWS)
            _api = _SystemWindowsApi()
        self._root = root
        self._api = _api
        if _clock is not None and not callable(_clock):
            raise TypeError("WindowsRootedOpen clock must be callable.")
        self._clock = _clock or (lambda: datetime.now(UTC))
        self._sensitive_policy = FilesystemSensitivePathPolicy()
        with self._open_root() as root_handle:
            self._require_directory_without_reparse(root_handle)
            self._require_supported_filesystem(root_handle)
            self._api.final_path(root_handle._native_value)
            self._configured_root_identity = self._identity(root_handle)

    @property
    def root_id(self) -> str:
        """Return the opaque scope identity without exposing its path."""
        return self._root.root_id

    @contextmanager
    def acquire(
        self,
        relative: str,
        *,
        _seam: _Seam | None = None,
    ) -> Iterator[WindowsOpenedFile]:
        """Yield one opaque proven file and close all handles before success."""
        with self._acquire_proven(
            relative,
            content=False,
            _seam=_seam,
        ) as (_, components):
            opened = WindowsOpenedFile(
                root_id=self._root.root_id,
                component_count=len(components),
            )
            try:
                yield opened
            finally:
                opened._deactivate()

    def read_range(
        self,
        relative: str,
        *,
        offset: int,
        max_bytes: int,
        _seam: _Seam | None = None,
    ) -> WindowsContentRangeObservation:
        """Read one bounded raw range and return only after every handle closes."""
        self._validate_range(offset=offset, max_bytes=max_bytes)
        capacity = max_bytes + 1
        pending: WindowsContentRangeObservation | None = None
        with self._acquire_proven(
            relative,
            content=True,
            _seam=_seam,
        ) as (final_handle, components):
            self._notify(_seam, _WindowsRootedOpenStage.BEFORE_CONTENT_READ)
            pre_read = self._observation(final_handle)
            native = self._read(
                final_handle,
                offset=offset,
                capacity=capacity,
            )
            self._notify(_seam, _WindowsRootedOpenStage.AFTER_CONTENT_READ)
            post_read = self._observation(final_handle)
            pending = self._content_observation(
                components=components,
                offset=offset,
                max_bytes=max_bytes,
                capacity=capacity,
                native=native,
                pre_read=pre_read,
                post_read=post_read,
            )

        if pending is None:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        return pending

    @contextmanager
    def _acquire_proven(
        self,
        relative: str,
        *,
        content: bool,
        _seam: _Seam | None,
    ) -> Iterator[tuple[_OwnedHandle, tuple[str, ...]]]:
        refusal, admitted = self._root.locate(relative)
        if not refusal.admitted or admitted is None:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.PATH_REFUSED,
                path_refusal=refusal,
            )
        try:
            admitted_status = admitted.lstat()
            admitted_kind = FilesystemEntryKind.from_status(
                admitted_status,
                admitted.is_symlink(),
            )
            parts = admitted.relative_to(self._root.path).parts
        except OSError, ValueError:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.ENTRY_CHANGED
            ) from None
        if admitted_kind is not FilesystemEntryKind.FILE or not parts:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_FILE)
        self._require_not_sensitive(
            parts,
            invalid_failure=WindowsRootedOpenFailure.ENTRY_CHANGED,
        )
        admitted_identity = _FileIdentity(
            int(admitted_status.st_dev) & 0xFFFFFFFF,
            int(admitted_status.st_ino),
        )
        self._notify(_seam, _WindowsRootedOpenStage.AFTER_ADMISSION)

        with ExitStack() as stack:
            root_handle = stack.enter_context(self._open_root())
            self._require_directory_without_reparse(root_handle)
            self._require_supported_filesystem(root_handle)
            root_path = self._api.final_path(root_handle._native_value)
            root_identity = self._identity(root_handle)
            if root_identity != self._configured_root_identity:
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.ROOT_CHANGED)
            self._notify(_seam, _WindowsRootedOpenStage.AFTER_ROOT_OPEN)

            parent = root_handle
            final_handle: _OwnedHandle | None = None
            for index, component in enumerate(parts):
                final = index == len(parts) - 1
                self._notify(
                    _seam,
                    _WindowsRootedOpenStage.BEFORE_COMPONENT_OPEN,
                    index,
                )
                child = stack.enter_context(
                    self._open_relative(
                        parent,
                        component,
                        final=final,
                        content=content and final,
                    )
                )
                self._notify(
                    _seam,
                    _WindowsRootedOpenStage.AFTER_COMPONENT_OPEN,
                    index,
                )
                attributes = self._api.attributes(child._native_value)
                if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    raise WindowsRootedOpenError(WindowsRootedOpenFailure.REPARSE_POINT)
                directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY)
                if final:
                    if directory:
                        raise WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_FILE)
                    final_handle = child
                else:
                    if not directory:
                        raise WindowsRootedOpenError(
                            WindowsRootedOpenFailure.NOT_DIRECTORY
                        )
                    parent = child

            if final_handle is None:
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
            self._notify(_seam, _WindowsRootedOpenStage.BEFORE_FINAL_PROOF)
            final_path = self._api.final_path(final_handle._native_value)
            final_components = self._strict_relative_components(final_path, root_path)
            if final_components is None:
                raise WindowsRootedOpenError(
                    WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN
                )
            self._require_not_sensitive(
                final_components,
                invalid_failure=WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN,
            )
            if self._identity(final_handle) != admitted_identity:
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.IDENTITY_MISMATCH)

            yield final_handle, final_components

    def _open_root(self) -> _OwnedHandle:
        return _OwnedHandle(self._api, self._api.open_root(str(self._root.path)))

    def _open_relative(
        self,
        parent: _OwnedHandle,
        component: str,
        *,
        final: bool,
        content: bool,
    ) -> _OwnedHandle:
        if (
            not component
            or component in {".", ".."}
            or any(separator in component for separator in ("/", "\\", ":"))
        ):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.PATH_REFUSED)
        if content:
            if not final:
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
            value = self._api.open_relative_content(
                parent._native_value,
                component,
            )
        else:
            value = self._api.open_relative(
                parent._native_value,
                component,
                final=final,
            )
        return _OwnedHandle(self._api, value)

    def _require_directory_without_reparse(self, handle: _OwnedHandle) -> None:
        attributes = self._api.attributes(handle._native_value)
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.REPARSE_POINT)
        if not attributes & FILE_ATTRIBUTE_DIRECTORY:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_DIRECTORY)

    def _require_supported_filesystem(self, handle: _OwnedHandle) -> None:
        if self._api.filesystem_name(handle._native_value).casefold() != "ntfs":
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.UNSUPPORTED_FILESYSTEM
            )

    def _identity(self, handle: _OwnedHandle) -> _FileIdentity:
        return self._api.identity(handle._native_value)

    def _observation(self, handle: _OwnedHandle) -> _FileObservation:
        try:
            observation = self._api.observation(handle._native_value)
        except Exception:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED) from None
        if (
            not isinstance(observation, _FileObservation)
            or not isinstance(observation.identity, _FileIdentity)
            or isinstance(observation.size, bool)
            or not isinstance(observation.size, int)
            or observation.size < 0
            or observation.size > _MAX_CONTENT_OFFSET
            or isinstance(observation.last_write_filetime, bool)
            or not isinstance(observation.last_write_filetime, int)
            or observation.last_write_filetime < 0
            or observation.last_write_filetime > _MAX_FILETIME
        ):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        return observation

    def _read(
        self,
        handle: _OwnedHandle,
        *,
        offset: int,
        capacity: int,
    ) -> _NativeReadResult:
        try:
            return self._api.read(
                handle._native_value,
                offset=offset,
                capacity=capacity,
            )
        except Exception:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED) from None

    def _content_observation(
        self,
        *,
        components: tuple[str, ...],
        offset: int,
        max_bytes: int,
        capacity: int,
        native: _NativeReadResult,
        pre_read: _FileObservation,
        post_read: _FileObservation,
    ) -> WindowsContentRangeObservation:
        if pre_read != post_read:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.CONTENT_CHANGED)
        if (
            not isinstance(native, _NativeReadResult)
            or not isinstance(native.content, bytes)
            or isinstance(native.count, bool)
            or not isinstance(native.count, int)
            or native.count < 0
            or native.count > capacity
            or len(native.content) != native.count
            or not isinstance(native.eof_signal, bool)
        ):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        if native.eof_signal and (
            native.count != 0 or native.content or offset < pre_read.size
        ):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        if native.count and offset + native.count > pre_read.size:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        if native.count < capacity and offset + native.count < pre_read.size:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_INCOMPLETE)

        retained = native.content[:max_bytes]
        bytes_returned = len(retained)
        truncated = offset + bytes_returned < pre_read.size
        try:
            modified_utc = self._filetime_to_utc(pre_read.last_write_filetime)
            read_at_utc = self._read_time_utc()
            return WindowsContentRangeObservation(
                root_id=self._root.root_id,
                resource="/".join(components),
                offset=offset,
                bytes_requested=max_bytes,
                bytes_returned=bytes_returned,
                truncated=truncated,
                file_size_bytes=pre_read.size,
                modified_utc=modified_utc,
                read_at_utc=read_at_utc,
                content=retained,
            )
        except WindowsRootedOpenError:
            raise
        except Exception:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED) from None

    def _read_time_utc(self) -> datetime:
        value = self._clock()
        if (
            not isinstance(value, datetime)
            or value.utcoffset() is None
            or value.utcoffset() != timedelta(0)
        ):
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED)
        return value.astimezone(UTC)

    @staticmethod
    def _filetime_to_utc(value: int) -> datetime:
        try:
            return _WINDOWS_EPOCH_UTC + timedelta(microseconds=value // 10)
        except OverflowError:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.READ_FAILED) from None

    @staticmethod
    def _validate_range(*, offset: int, max_bytes: int) -> None:
        for value, maximum, label in (
            (offset, _MAX_CONTENT_OFFSET, "offset"),
            (max_bytes, _MAX_CONTENT_BYTES, "maximum byte count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Content-range {label} must be an integer.")
            if value < 0 or value > maximum:
                raise ValueError(f"Content-range {label} is outside its bound.")

    @staticmethod
    def _strict_relative_components(
        final_path: PureWindowsPath,
        root_path: PureWindowsPath,
    ) -> tuple[str, ...] | None:
        try:
            components = final_path.relative_to(root_path).parts
        except ValueError:
            return None
        return components or None

    def _require_not_sensitive(
        self,
        components: tuple[str, ...],
        *,
        invalid_failure: WindowsRootedOpenFailure,
    ) -> None:
        try:
            sensitive_class = self._sensitive_policy.classify(
                components,
                windows_names=True,
            )
        except TypeError, ValueError:
            raise WindowsRootedOpenError(invalid_failure) from None
        if sensitive_class.refused:
            raise WindowsRootedOpenError(
                WindowsRootedOpenFailure.SENSITIVE_FILE,
                sensitive_class=sensitive_class,
            )

    @staticmethod
    def _notify(
        seam: _Seam | None,
        stage: _WindowsRootedOpenStage,
        component_index: int = -1,
    ) -> None:
        if seam is not None:
            seam(stage, component_index)
