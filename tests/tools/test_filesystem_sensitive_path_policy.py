"""The sensitive-name floor declines explicit classes without reading files."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from tools.FilesystemSensitivePathPolicy import (
    FilesystemSensitiveClass,
    FilesystemSensitivePathPolicy,
)


class SensitivePathPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = FilesystemSensitivePathPolicy()

    def assert_class(
        self,
        expected: FilesystemSensitiveClass,
        *components: str,
        windows_names: bool = False,
    ) -> None:
        self.assertIs(
            self.policy.classify(tuple(components), windows_names=windows_names),
            expected,
        )

    def test_environment_file_patterns_are_case_insensitive(self) -> None:
        for components in (
            (".env",),
            ("config", ".ENV.local"),
            ("deploy", "production.EnV"),
        ):
            with self.subTest(components=components):
                self.assert_class(
                    FilesystemSensitiveClass.ENVIRONMENT_FILE,
                    *components,
                )

    def test_environment_near_misses_are_not_presented_as_complete_detection(
        self,
    ) -> None:
        for name in ("env.txt", ".envrc", "environment.json", "safe.txt"):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.NONE, name)

    def test_windows_trailing_dots_and_spaces_cannot_disguise_environment_files(
        self,
    ) -> None:
        for name in (".env.", ".env   ", "production.env. "):
            with self.subTest(name=name):
                self.assert_class(
                    FilesystemSensitiveClass.ENVIRONMENT_FILE,
                    name,
                    windows_names=True,
                )

    def test_private_key_extensions_and_names_are_refused(self) -> None:
        for name in (
            "server.pem",
            "SIGNING.KEY",
            "identity.p12",
            "certificate.pfx",
            "id_rsa",
            "ID_ED25519",
            "id_ecdsa",
        ):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.PRIVATE_KEY, name)

    def test_public_key_and_unlisted_key_names_are_not_private_key_matches(
        self,
    ) -> None:
        for name in ("id_rsa.pub", "key.txt", "certificate.crt"):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.NONE, name)

    def test_any_file_directly_inside_dot_ssh_is_ssh_material(self) -> None:
        for name in ("config", "known_hosts", "id_rsa", "notes.txt"):
            with self.subTest(name=name):
                self.assert_class(
                    FilesystemSensitiveClass.SSH_MATERIAL,
                    "home",
                    ".SSH",
                    name,
                )

    def test_dot_ssh_rule_is_direct_parent_only(self) -> None:
        self.assert_class(
            FilesystemSensitiveClass.NONE,
            ".ssh",
            "archive",
            "notes.txt",
        )

    def test_aws_config_and_credentials_are_cloud_material(self) -> None:
        for name in ("config", "credentials"):
            with self.subTest(name=name):
                self.assert_class(
                    FilesystemSensitiveClass.CLOUD_CREDENTIAL,
                    "home",
                    ".aws",
                    name,
                )

    def test_aws_rule_does_not_match_same_names_elsewhere(self) -> None:
        for name in ("config", "credentials"):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.NONE, "project", name)

    def test_kubeconfig_suffix_is_cloud_material(self) -> None:
        for name in ("cluster.kubeconfig", ".kubeconfig", "PROD.KUBECONFIG"):
            with self.subTest(name=name):
                self.assert_class(
                    FilesystemSensitiveClass.CLOUD_CREDENTIAL,
                    name,
                )

    def test_known_gcloud_credential_files_are_refused_under_gcloud(self) -> None:
        for name in (
            "credentials.db",
            "access_tokens.db",
            "application_default_credentials.json",
            "adc.json",
        ):
            with self.subTest(name=name):
                self.assert_class(
                    FilesystemSensitiveClass.CLOUD_CREDENTIAL,
                    ".config",
                    "gcloud",
                    "legacy_credentials",
                    name,
                )

    def test_gcloud_name_outside_gcloud_is_not_a_cloud_match(self) -> None:
        self.assert_class(
            FilesystemSensitiveClass.NONE,
            "project",
            "credentials.db",
        )

    def test_vcs_credential_names_and_git_config_are_refused(self) -> None:
        for components in (
            (".git-credentials",),
            ("home", ".netrc"),
            ("home", "_NETRC"),
            ("project", ".git", "config"),
        ):
            with self.subTest(components=components):
                self.assert_class(
                    FilesystemSensitiveClass.VCS_CREDENTIAL,
                    *components,
                )

    def test_unrelated_git_file_is_not_a_vcs_credential_match(self) -> None:
        self.assert_class(
            FilesystemSensitiveClass.NONE,
            ".git",
            "description",
        )

    def test_package_manager_auth_files_are_refused(self) -> None:
        for components in (
            (".npmrc",),
            ("home", ".PYPIRC"),
            ("home", ".docker", "config.json"),
        ):
            with self.subTest(components=components):
                self.assert_class(
                    FilesystemSensitiveClass.PACKAGE_MANAGER_AUTH,
                    *components,
                )

    def test_config_json_outside_dot_docker_is_not_package_auth(self) -> None:
        self.assert_class(FilesystemSensitiveClass.NONE, "project", "config.json")

    def test_browser_profile_sqlite_files_are_refused(self) -> None:
        for components in (
            ("Chrome", "Default", "Cookies.sqlite"),
            ("Firefox", "abcd.default-release", "places.sqlite"),
            ("Edge", "Profile 3", "History.sqlite"),
        ):
            with self.subTest(components=components):
                self.assert_class(
                    FilesystemSensitiveClass.BROWSER_OS_STORE,
                    *components,
                )

    def test_sqlite_outside_a_profile_component_is_not_a_browser_match(self) -> None:
        self.assert_class(FilesystemSensitiveClass.NONE, "project", "state.sqlite")

    def test_login_data_and_vault_extensions_are_refused(self) -> None:
        for name in (
            "Login Data",
            "login.keychain-db",
            "secrets.keyring",
            "vault.vcrd",
            "policy.vpol",
        ):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.BROWSER_OS_STORE, name)

    def test_ci_secret_patterns_are_refused(self) -> None:
        for name in (
            "secrets.yaml",
            "SECRETS.json",
            "build.secrets.toml",
            "production.secrets.env",
        ):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.CI_SECRET, name)

    def test_ci_near_misses_are_not_refused(self) -> None:
        for name in ("secrets", "mysecrets.yaml", "secret.yaml"):
            with self.subTest(name=name):
                self.assert_class(FilesystemSensitiveClass.NONE, name)

    def test_contextual_classes_have_deterministic_precedence(self) -> None:
        cases = {
            (".ssh", "id_rsa"): FilesystemSensitiveClass.SSH_MATERIAL,
            (".env.key",): FilesystemSensitiveClass.ENVIRONMENT_FILE,
            ("build.secrets.pem",): FilesystemSensitiveClass.CI_SECRET,
        }
        for components, expected in cases.items():
            with self.subTest(components=components):
                self.assert_class(expected, *components)

    def test_invalid_component_shapes_fail_with_fixed_non_disclosing_text(self) -> None:
        invalid: tuple[object, ...] = (
            (),
            [],
            ("",),
            (".",),
            ("..",),
            ("private/sentinel",),
            ("private\x00sentinel",),
            (7,),
        )
        for components in invalid:
            with self.subTest(components=components):
                with self.assertRaises(ValueError) as raised:
                    self.policy.classify(components)  # type: ignore[arg-type]
                self.assertNotIn("private", str(raised.exception))
                self.assertNotIn("sentinel", str(raised.exception))

    def test_windows_only_forbids_backslash_and_colon_components(self) -> None:
        self.assert_class(FilesystemSensitiveClass.NONE, "name:part")
        self.assert_class(FilesystemSensitiveClass.NONE, r"name\part")

        for component in ("name:part", r"name\part"):
            with self.subTest(component=component):
                with self.assertRaises(ValueError):
                    self.policy.classify((component,), windows_names=True)

    def test_non_boolean_windows_mode_is_refused(self) -> None:
        with self.assertRaisesRegex(TypeError, "boolean"):
            self.policy.classify(("safe.txt",), windows_names=1)  # type: ignore[arg-type]

    def test_every_class_has_fixed_non_path_operator_wording(self) -> None:
        labels = {
            sensitive_class.operator_label
            for sensitive_class in FilesystemSensitiveClass
        }

        self.assertEqual(len(labels), len(FilesystemSensitiveClass))
        for label in labels:
            self.assertNotIn("/", label)
            self.assertNotIn("\\", label)
            self.assertNotIn(":", label)


class SensitivePathPolicySourceGuards(unittest.TestCase):
    @classmethod
    def source(cls) -> str:
        return (SRC_DIR / "tools" / "FilesystemSensitivePathPolicy.py").read_text(
            encoding="utf-8"
        )

    def test_policy_has_no_filesystem_content_or_process_authority(self) -> None:
        for forbidden in (
            "import os",
            "from pathlib",
            "open(",
            "read_text(",
            "read_bytes(",
            "os.read(",
            "ReadFile",
            "NtReadFile",
            "subprocess",
            "ToolRuntime",
            "ToolInvocation",
            "FilesystemContentPayload",
            "LLMProvider",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_source_calls_the_policy_a_floor_not_a_complete_boundary(self) -> None:
        source = self.source().casefold()

        self.assertIn("floor, not a fence", source)
        self.assertNotIn("all sensitive", source)
        self.assertNotIn("guarantees safety", source)


if __name__ == "__main__":
    unittest.main()
