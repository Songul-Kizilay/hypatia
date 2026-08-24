"""Decline a small explicit floor of sensitive local-file name classes.

This policy is deliberately a floor, not a fence.  It catches common credential
locations before a future content capability can read a byte, but it cannot
prove that every other filename is safe.  It performs no filesystem access,
content inspection, secret guessing, operator override, or telemetry.

Callers pass canonical path components obtained from an admitted path or from a
final safely-opened resource.  Windows callers request trailing-dot/space
normalization because those suffixes do not distinguish an NTFS filename.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FilesystemSensitiveClass", "FilesystemSensitivePathPolicy"]


class FilesystemSensitiveClass(StrEnum):
    """Name one bounded sensitive class without carrying a path."""

    NONE = "none"
    ENVIRONMENT_FILE = "environment_file"
    PRIVATE_KEY = "private_key"
    SSH_MATERIAL = "ssh_material"
    CLOUD_CREDENTIAL = "cloud_credential"
    VCS_CREDENTIAL = "vcs_credential"
    PACKAGE_MANAGER_AUTH = "package_manager_auth"
    BROWSER_OS_STORE = "browser_os_store"
    CI_SECRET = "ci_secret"

    @property
    def operator_label(self) -> str:
        """Return fixed wording suitable for a future decline sentence."""
        return _OPERATOR_LABELS[self]

    @property
    def refused(self) -> bool:
        """Return whether this class must stop a future content read."""
        return self is not FilesystemSensitiveClass.NONE


_OPERATOR_LABELS: dict[FilesystemSensitiveClass, str] = {
    FilesystemSensitiveClass.NONE: "no sensitive class",
    FilesystemSensitiveClass.ENVIRONMENT_FILE: "an environment file",
    FilesystemSensitiveClass.PRIVATE_KEY: "private-key material",
    FilesystemSensitiveClass.SSH_MATERIAL: "SSH material",
    FilesystemSensitiveClass.CLOUD_CREDENTIAL: "cloud credential material",
    FilesystemSensitiveClass.VCS_CREDENTIAL: "version-control credentials",
    FilesystemSensitiveClass.PACKAGE_MANAGER_AUTH: (
        "package-manager authentication material"
    ),
    FilesystemSensitiveClass.BROWSER_OS_STORE: (
        "a browser or operating-system credential store"
    ),
    FilesystemSensitiveClass.CI_SECRET: "CI secret material",
}

_PRIVATE_KEY_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
_PRIVATE_KEY_NAMES = frozenset({"id_rsa", "id_ed25519", "id_ecdsa"})
_GCLOUD_CREDENTIAL_NAMES = frozenset(
    {
        "access_tokens.db",
        "adc.json",
        "application_default_credentials.json",
        "credentials.db",
    }
)
_VCS_CREDENTIAL_NAMES = frozenset({".git-credentials", ".netrc", "_netrc"})
_PACKAGE_AUTH_NAMES = frozenset({".npmrc", ".pypirc"})
_VAULT_SUFFIXES = (".keychain", ".keychain-db", ".keyring", ".vcrd", ".vpol")


class FilesystemSensitivePathPolicy:
    """Classify canonical components using explicit, non-content rules."""

    def classify(
        self,
        components: tuple[str, ...],
        *,
        windows_names: bool = False,
    ) -> FilesystemSensitiveClass:
        """Return a bounded class, with contextual classes taking precedence."""
        normalized = self._normalize(components, windows_names=windows_names)
        name = normalized[-1]
        parents = normalized[:-1]
        direct_parent = parents[-1] if parents else ""

        # Contextual locations are more useful to the operator than a generic
        # extension when more than one rule matches the same resource.
        if direct_parent == ".ssh":
            return FilesystemSensitiveClass.SSH_MATERIAL
        if direct_parent == ".aws" and name in {"config", "credentials"}:
            return FilesystemSensitiveClass.CLOUD_CREDENTIAL
        if name.endswith(".kubeconfig"):
            return FilesystemSensitiveClass.CLOUD_CREDENTIAL
        if "gcloud" in parents and name in _GCLOUD_CREDENTIAL_NAMES:
            return FilesystemSensitiveClass.CLOUD_CREDENTIAL
        if name in _VCS_CREDENTIAL_NAMES or (
            direct_parent == ".git" and name == "config"
        ):
            return FilesystemSensitiveClass.VCS_CREDENTIAL
        if name in _PACKAGE_AUTH_NAMES or (
            direct_parent == ".docker" and name == "config.json"
        ):
            return FilesystemSensitiveClass.PACKAGE_MANAGER_AUTH
        if self._is_browser_or_os_store(name, parents):
            return FilesystemSensitiveClass.BROWSER_OS_STORE
        if name.startswith("secrets.") or ".secrets." in name:
            return FilesystemSensitiveClass.CI_SECRET
        if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
            return FilesystemSensitiveClass.ENVIRONMENT_FILE
        if name in _PRIVATE_KEY_NAMES or name.endswith(_PRIVATE_KEY_SUFFIXES):
            return FilesystemSensitiveClass.PRIVATE_KEY
        return FilesystemSensitiveClass.NONE

    @classmethod
    def _normalize(
        cls,
        components: tuple[str, ...],
        *,
        windows_names: bool,
    ) -> tuple[str, ...]:
        if not isinstance(windows_names, bool):
            raise TypeError("Windows-name normalization must be a boolean.")
        if not isinstance(components, tuple) or not components:
            raise ValueError("Sensitive-path classification needs path components.")
        normalized: list[str] = []
        for component in components:
            if (
                not isinstance(component, str)
                or not component
                or component in {".", ".."}
                or "/" in component
                or "\x00" in component
                or (
                    windows_names
                    and any(separator in component for separator in ("\\", ":"))
                )
            ):
                raise ValueError(
                    "Sensitive-path classification received an invalid component."
                )
            canonical = (
                cls._windows_component(component) if windows_names else component
            )
            if not canonical:
                raise ValueError(
                    "Sensitive-path classification received an invalid component."
                )
            normalized.append(canonical.casefold())
        return tuple(normalized)

    @staticmethod
    def _windows_component(component: str) -> str:
        return component.rstrip(" .")

    @classmethod
    def _is_browser_or_os_store(
        cls,
        name: str,
        parents: tuple[str, ...],
    ) -> bool:
        if name == "login data" or name.endswith(_VAULT_SUFFIXES):
            return True
        return name.endswith(".sqlite") and any(
            cls._is_browser_profile(component) for component in parents
        )

    @staticmethod
    def _is_browser_profile(component: str) -> bool:
        return (
            component in {"default", "profile", "profiles"}
            or component.startswith("profile ")
            or component.endswith(".default")
            or component.endswith(".default-release")
        )
