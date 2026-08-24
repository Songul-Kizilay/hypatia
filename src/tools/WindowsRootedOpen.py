"""Acquire one Windows file by held handles without reading its contents.

This module is the production-owned but deliberately inert foundation for a
future local-file content capability.  It performs lexical admission through
``FilesystemRoot`` and then repeats the decisive proof with Windows handles:
the configured root is opened without following its final reparse point, each
relative component is opened against its held parent, every reparse point is
refused, and the final handle is checked for containment and identity.

No capability imports this module.  It has no read method, returns no path or
native handle, and loads Windows system APIs only when constructed on Windows.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot

__all__ = [
    "WindowsOpenedFile",
    "WindowsRootedOpen",
    "WindowsRootedOpenError",
    "WindowsRootedOpenFailure",
]

FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400

FILE_READ_ATTRIBUTES = 0x00000080
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
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_FILESYSTEM_NAME_CAPACITY = 64


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
    ) -> None:
        self.failure = failure
        self.path_refusal = path_refusal
        super().__init__(_FAILURE_DETAILS[failure])


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


class _FileIdentity(tuple[int, int]):
    """A hashable NTFS volume-serial and 64-bit file-index pair."""

    __slots__ = ()

    def __new__(cls, volume_serial: int, file_index: int) -> _FileIdentity:
        return super().__new__(cls, (volume_serial, file_index))


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


class _WindowsApi(Protocol):
    def open_root(self, absolute_root: str) -> int: ...

    def open_relative(self, parent: int, component: str, *, final: bool) -> int: ...

    def close(self, handle: int) -> bool: ...

    def attributes(self, handle: int) -> int: ...

    def filesystem_name(self, handle: int) -> str: ...

    def identity(self, handle: int) -> _FileIdentity: ...

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
        access = FILE_READ_ATTRIBUTES | SYNCHRONIZE
        del final  # Kind is proven after the attribute-only acquisition.
        status = int(
            self._nt_create_file(
                ctypes.byref(output),
                access,
                ctypes.byref(attributes),
                ctypes.byref(status_block),
                None,
                FILE_ATTRIBUTE_NORMAL,
                _SHARE_ALL,
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
        info = _ByHandleFileInformation()
        succeeded = self._file_information(wintypes.HANDLE(handle), ctypes.byref(info))
        if not succeeded:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        file_index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
        return _FileIdentity(int(info.dwVolumeSerialNumber), file_index)

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
    ) -> None:
        if not isinstance(root, FilesystemRoot):
            raise TypeError("WindowsRootedOpen requires a FilesystemRoot.")
        if _api is None:
            if os.name != "nt":
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_WINDOWS)
            _api = _SystemWindowsApi()
        self._root = root
        self._api = _api
        with self._open_root() as root_handle:
            self._require_directory_without_reparse(root_handle)
            self._require_supported_filesystem(root_handle)
            self._api.final_path(root_handle._native_value)
            self._configured_root_identity = self._identity(root_handle)

    @contextmanager
    def acquire(
        self,
        relative: str,
        *,
        _seam: _Seam | None = None,
    ) -> Iterator[WindowsOpenedFile]:
        """Yield one opaque proven file and close all handles before success."""
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
                    self._open_relative(parent, component, final=final)
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
            if not self._is_strict_descendant(final_path, root_path):
                raise WindowsRootedOpenError(
                    WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN
                )
            if self._identity(final_handle) != admitted_identity:
                raise WindowsRootedOpenError(WindowsRootedOpenFailure.IDENTITY_MISMATCH)

            opened = WindowsOpenedFile(
                root_id=self._root.root_id,
                component_count=len(parts),
            )
            try:
                yield opened
            finally:
                opened._deactivate()

    def _open_root(self) -> _OwnedHandle:
        return _OwnedHandle(self._api, self._api.open_root(str(self._root.path)))

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
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.PATH_REFUSED)
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

    @staticmethod
    def _is_strict_descendant(
        final_path: PureWindowsPath,
        root_path: PureWindowsPath,
    ) -> bool:
        return final_path != root_path and final_path.is_relative_to(root_path)

    @staticmethod
    def _notify(
        seam: _Seam | None,
        stage: _WindowsRootedOpenStage,
        component_index: int = -1,
    ) -> None:
        if seam is not None:
            seam(stage, component_index)
