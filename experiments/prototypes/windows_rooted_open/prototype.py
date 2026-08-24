"""Prove a Windows root-handle open without reading file contents.

This is deliberately outside ``src``. It is an experiment that answers one
question for the filesystem-content security design: can every component be
opened relative to a held directory handle while reparse processing is disabled,
and can the final handle then prove containment? It registers no capability,
declares no effect, returns no handle, and reads no file bytes.

The native call is narrow on purpose. ``NtCreateFile`` accepts an object name
relative to ``OBJECT_ATTRIBUTES.RootDirectory`` and ``FILE_OPEN_REPARSE_POINT``
prevents normal reparse processing for that one component. Supplying exactly one
component per call is what keeps an unexamined parent out of the native open.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from contextlib import ExitStack
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath

from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot

FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400

FILE_LIST_DIRECTORY = 0x00000001
FILE_READ_DATA = 0x00000001
FILE_TRAVERSE = 0x00000020
FILE_READ_ATTRIBUTES = 0x00000080
SYNCHRONIZE = 0x00100000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
SHARE_ALL = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE

OPEN_EXISTING = 3
FILE_OPEN = 1

FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_OPEN_REPARSE_POINT = 0x00200000

OBJ_CASE_INSENSITIVE = 0x00000040
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PrototypeFailure(StrEnum):
    """Name one bounded reason the experiment could not prove the boundary."""

    NOT_WINDOWS = "not_windows"
    API_UNAVAILABLE = "api_unavailable"
    PATH_REFUSED = "path_refused"
    ENTRY_CHANGED = "entry_changed"
    NOT_FILE = "not_file"
    ROOT_CHANGED = "root_changed"
    OPEN_FAILED = "open_failed"
    REPARSE_POINT = "reparse_point"
    NOT_DIRECTORY = "not_directory"
    CONTAINMENT_UNPROVEN = "containment_unproven"
    IDENTITY_MISMATCH = "identity_mismatch"


class PrototypeStage(StrEnum):
    """Deterministic seams used to replace entries without timing a race."""

    AFTER_ADMISSION = "after_admission"
    AFTER_ROOT_OPEN = "after_root_open"
    BEFORE_COMPONENT_OPEN = "before_component_open"
    AFTER_COMPONENT_OPEN = "after_component_open"
    BEFORE_FINAL_PROOF = "before_final_proof"


_FAILURE_DETAILS: dict[PrototypeFailure, str] = {
    PrototypeFailure.NOT_WINDOWS: "This experiment runs only on Windows.",
    PrototypeFailure.API_UNAVAILABLE: "The required Windows API is unavailable.",
    PrototypeFailure.PATH_REFUSED: "The existing filesystem policy refused the path.",
    PrototypeFailure.ENTRY_CHANGED: "The entry changed during admission.",
    PrototypeFailure.NOT_FILE: "The admitted entry is not a regular file.",
    PrototypeFailure.ROOT_CHANGED: "The configured root identity changed.",
    PrototypeFailure.OPEN_FAILED: "A rooted handle could not be acquired.",
    PrototypeFailure.REPARSE_POINT: "A rooted handle names a reparse point.",
    PrototypeFailure.NOT_DIRECTORY: "An intermediate component is not a directory.",
    PrototypeFailure.CONTAINMENT_UNPROVEN: "Final-handle containment was not proven.",
    PrototypeFailure.IDENTITY_MISMATCH: "The admitted and opened identities differ.",
}


class WindowsRootedOpenPrototypeError(RuntimeError):
    """Stop the experiment with a bounded category and no path disclosure."""

    def __init__(
        self,
        failure: PrototypeFailure,
        *,
        path_refusal: FilesystemPathRefusal = FilesystemPathRefusal.NONE,
    ) -> None:
        self.failure = failure
        self.path_refusal = path_refusal
        super().__init__(_FAILURE_DETAILS[failure])


@dataclass(frozen=True, slots=True)
class FileIdentity:
    """Windows volume and file IDs obtained from an acquired handle."""

    volume_serial: int
    file_index: int


@dataclass(frozen=True, slots=True)
class RootedOpenProof:
    """Bounded evidence from one handle-only proof; contains no path or content."""

    root_id: str
    component_count: int
    root_identity: FileIdentity
    file_identity: FileIdentity
    reparse_free: bool = True
    final_contained: bool = True
    content_bytes_read: int = 0


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


class _WindowsApi:
    """Bind only the native calls this experiment measures."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.NOT_WINDOWS)
        try:
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        except (AttributeError, OSError) as error:
            raise WindowsRootedOpenPrototypeError(
                PrototypeFailure.API_UNAVAILABLE
            ) from error

        self.create_file = self.kernel32.CreateFileW
        self.create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.create_file.restype = wintypes.HANDLE

        self.close_handle = self.kernel32.CloseHandle
        self.close_handle.argtypes = [wintypes.HANDLE]
        self.close_handle.restype = wintypes.BOOL

        self.file_information = self.kernel32.GetFileInformationByHandle
        self.file_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        self.file_information.restype = wintypes.BOOL

        self.file_information_ex = self.kernel32.GetFileInformationByHandleEx
        self.file_information_ex.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.file_information_ex.restype = wintypes.BOOL

        self.final_path = self.kernel32.GetFinalPathNameByHandleW
        self.final_path.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self.final_path.restype = wintypes.DWORD

        self.nt_create_file = self.ntdll.NtCreateFile
        self.nt_create_file.argtypes = [
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
        self.nt_create_file.restype = wintypes.LONG


class _OwnedHandle:
    """Close one native handle on every return and exception branch."""

    def __init__(self, api: _WindowsApi, value: int) -> None:
        self._api = api
        self.value = value

    def __enter__(self) -> _OwnedHandle:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self.value:
            self._api.close_handle(wintypes.HANDLE(self.value))
            self.value = 0


PrototypeSeam = Callable[[PrototypeStage, str], None]


class WindowsRootedOpenPrototype:
    """Acquire and close one proven-contained file handle without reading it."""

    def __init__(self, root: FilesystemRoot) -> None:
        if not isinstance(root, FilesystemRoot):
            raise TypeError("The rooted-open prototype requires a FilesystemRoot.")
        self._root = root
        self._api = _WindowsApi()
        with self._open_root() as handle:
            self._require_directory_without_reparse(handle)
            self._configured_root_identity = self._identity(handle)

    def prove(
        self,
        relative: str,
        *,
        seam: PrototypeSeam | None = None,
    ) -> RootedOpenProof:
        """Prove a no-follow rooted open and return no content or live handle."""
        refusal, admitted = self._root.locate(relative)
        if not refusal.admitted or admitted is None:
            raise WindowsRootedOpenPrototypeError(
                PrototypeFailure.PATH_REFUSED,
                path_refusal=refusal,
            )
        try:
            admitted_status = admitted.lstat()
            admitted_kind = FilesystemEntryKind.from_status(
                admitted_status,
                admitted.is_symlink(),
            )
            parts = admitted.relative_to(self._root.path).parts
        except (OSError, ValueError) as error:
            raise WindowsRootedOpenPrototypeError(
                PrototypeFailure.ENTRY_CHANGED
            ) from error
        if admitted_kind is not FilesystemEntryKind.FILE or not parts:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.NOT_FILE)
        admitted_identity = FileIdentity(
            # CPython's Windows st_dev carries more than the DWORD volume
            # serial returned by BY_HANDLE_FILE_INFORMATION. The measured low
            # DWORD is the same serial; st_ino maps to the 64-bit file index.
            volume_serial=int(admitted_status.st_dev) & 0xFFFFFFFF,
            file_index=int(admitted_status.st_ino),
        )
        self._seam(seam, PrototypeStage.AFTER_ADMISSION)

        with ExitStack() as stack:
            root_handle = stack.enter_context(self._open_root())
            self._require_directory_without_reparse(root_handle)
            root_identity = self._identity(root_handle)
            if root_identity != self._configured_root_identity:
                raise WindowsRootedOpenPrototypeError(PrototypeFailure.ROOT_CHANGED)
            self._seam(seam, PrototypeStage.AFTER_ROOT_OPEN)

            parent = root_handle
            final_handle: _OwnedHandle | None = None
            for index, component in enumerate(parts):
                final = index == len(parts) - 1
                self._seam(seam, PrototypeStage.BEFORE_COMPONENT_OPEN, component)
                child = stack.enter_context(
                    self._open_relative(parent, component, final=final)
                )
                self._seam(seam, PrototypeStage.AFTER_COMPONENT_OPEN, component)
                if self._is_reparse(child):
                    raise WindowsRootedOpenPrototypeError(
                        PrototypeFailure.REPARSE_POINT
                    )
                if final:
                    if self._is_directory(child):
                        raise WindowsRootedOpenPrototypeError(PrototypeFailure.NOT_FILE)
                    final_handle = child
                else:
                    if not self._is_directory(child):
                        raise WindowsRootedOpenPrototypeError(
                            PrototypeFailure.NOT_DIRECTORY
                        )
                    parent = child

            if final_handle is None:
                raise WindowsRootedOpenPrototypeError(PrototypeFailure.OPEN_FAILED)
            self._seam(seam, PrototypeStage.BEFORE_FINAL_PROOF)
            if not self._handle_is_under(final_handle, root_handle):
                raise WindowsRootedOpenPrototypeError(
                    PrototypeFailure.CONTAINMENT_UNPROVEN
                )
            file_identity = self._identity(final_handle)
            if file_identity != admitted_identity:
                raise WindowsRootedOpenPrototypeError(
                    PrototypeFailure.IDENTITY_MISMATCH
                )
            return RootedOpenProof(
                root_id=self._root.root_id,
                component_count=len(parts),
                root_identity=root_identity,
                file_identity=file_identity,
            )

    def _open_root(self) -> _OwnedHandle:
        access = (
            FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE
        )
        value = self._api.create_file(
            str(self._root.path),
            access,
            SHARE_ALL,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        numeric = int(value or 0)
        if not numeric or numeric == INVALID_HANDLE_VALUE:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.OPEN_FAILED)
        return _OwnedHandle(self._api, numeric)

    def _open_relative(
        self,
        parent: _OwnedHandle,
        component: str,
        *,
        final: bool,
    ) -> _OwnedHandle:
        if (
            not component
            or component in {".", ".."}
            or any(separator in component for separator in ("/", "\\", ":"))
        ):
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.PATH_REFUSED)
        buffer = ctypes.create_unicode_buffer(component)
        encoded_length = len(component.encode("utf-16-le"))
        name = _UnicodeString(
            Length=encoded_length,
            MaximumLength=encoded_length + 2,
            Buffer=ctypes.cast(buffer, wintypes.LPWSTR),
        )
        attributes = _ObjectAttributes(
            Length=ctypes.sizeof(_ObjectAttributes),
            RootDirectory=wintypes.HANDLE(parent.value),
            ObjectName=ctypes.pointer(name),
            Attributes=OBJ_CASE_INSENSITIVE,
            SecurityDescriptor=None,
            SecurityQualityOfService=None,
        )
        status_block = _IoStatusBlock()
        output = wintypes.HANDLE()
        access = FILE_READ_ATTRIBUTES | SYNCHRONIZE
        if final:
            access |= FILE_READ_DATA
        else:
            access |= FILE_LIST_DIRECTORY | FILE_TRAVERSE
        options = FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
        if final:
            options |= FILE_NON_DIRECTORY_FILE
        status = self._api.nt_create_file(
            ctypes.byref(output),
            access,
            ctypes.byref(attributes),
            ctypes.byref(status_block),
            None,
            FILE_ATTRIBUTE_NORMAL,
            SHARE_ALL,
            FILE_OPEN,
            options,
            None,
            0,
        )
        if status < 0 or not output.value:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.OPEN_FAILED)
        return _OwnedHandle(self._api, int(output.value))

    def _require_directory_without_reparse(self, handle: _OwnedHandle) -> None:
        if self._is_reparse(handle):
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.REPARSE_POINT)
        if not self._is_directory(handle):
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.NOT_DIRECTORY)

    def _attributes(self, handle: _OwnedHandle) -> int:
        info = _FileAttributeTagInfo()
        succeeded = self._api.file_information_ex(
            wintypes.HANDLE(handle.value),
            FILE_ATTRIBUTE_TAG_INFO_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not succeeded:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.OPEN_FAILED)
        return int(info.FileAttributes)

    def _is_reparse(self, handle: _OwnedHandle) -> bool:
        return bool(self._attributes(handle) & FILE_ATTRIBUTE_REPARSE_POINT)

    def _is_directory(self, handle: _OwnedHandle) -> bool:
        return bool(self._attributes(handle) & FILE_ATTRIBUTE_DIRECTORY)

    def _identity(self, handle: _OwnedHandle) -> FileIdentity:
        info = _ByHandleFileInformation()
        succeeded = self._api.file_information(
            wintypes.HANDLE(handle.value), ctypes.byref(info)
        )
        if not succeeded:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.OPEN_FAILED)
        file_index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
        return FileIdentity(int(info.dwVolumeSerialNumber), file_index)

    def _handle_path(self, handle: _OwnedHandle) -> PureWindowsPath:
        required = self._api.final_path(wintypes.HANDLE(handle.value), None, 0, 0)
        if not required:
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.CONTAINMENT_UNPROVEN)
        buffer = ctypes.create_unicode_buffer(required + 1)
        written = self._api.final_path(
            wintypes.HANDLE(handle.value), buffer, len(buffer), 0
        )
        if not written or written >= len(buffer):
            raise WindowsRootedOpenPrototypeError(PrototypeFailure.CONTAINMENT_UNPROVEN)
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return PureWindowsPath(value)

    def _handle_is_under(
        self,
        final_handle: _OwnedHandle,
        root_handle: _OwnedHandle,
    ) -> bool:
        final_path = self._handle_path(final_handle)
        root_path = self._handle_path(root_handle)
        return final_path != root_path and final_path.is_relative_to(root_path)

    @staticmethod
    def _seam(
        seam: PrototypeSeam | None,
        stage: PrototypeStage,
        component: str = "",
    ) -> None:
        if seam is not None:
            seam(stage, component)
