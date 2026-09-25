"""The research secret-ingress floor returns categories, never values."""

from __future__ import annotations

import unittest

from research.ResearchSensitiveInputPolicy import (
    MAX_RESEARCH_SENSITIVE_INPUT_CHARACTERS,
    ResearchSensitiveInputClass,
    ResearchSensitiveInputPolicy,
)


class ResearchSensitiveInputPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ResearchSensitiveInputPolicy()

    def assert_class(self, expected: ResearchSensitiveInputClass, *values: str) -> None:
        for value in values:
            with self.subTest(value=value):
                self.assertIs(self.policy.classify(value), expected)

    def test_credential_bearing_urls_are_refused(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.CREDENTIAL_BEARING_URL,
            "https://operator:distinct-password@example.test/private",
            "https://distinct-token@example.test/private",
            "Observed ftp://name:pass@host.test/path during setup.",
        )

    def test_authentication_and_cookie_headers_are_refused(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.AUTHENTICATION_HEADER,
            "Authorization: Bearer distinct-token-value",
            "Observed Authorization: Bearer distinct-token-value",
            "note\n  COOKIE : session=distinct-value",
            "Proxy-Authorization:\tBasic distinct-value",
            "Set-Cookie: session=distinct-value; Secure",
        )

    def test_private_key_markers_are_refused(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.PRIVATE_KEY_MATERIAL,
            "-----BEGIN PRIVATE KEY-----",
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
        )

    def test_secret_assignments_are_refused(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.SECRET_ASSIGNMENT,
            "password=distinct-value",
            "note; API_KEY : distinct-value",
            "access-token='distinct-value'",
            "https://example.test/?refresh_token=distinct-value",
            "session_id=distinct-value",
        )

    def test_high_confidence_token_formats_are_refused(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.TOKEN_FORMAT,
            "sk-abcdefghijklmnopqrstuvwxyz123456",
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "AKIAABCDEFGHIJKLMNOP",
            "eyJabcdefghijk.abcdefghijklmnop.abcdefghijklmnop",
        )

    def test_benign_discussion_and_near_misses_remain_allowed(self) -> None:
        self.assert_class(
            ResearchSensitiveInputClass.NONE,
            "no password was used",
            "authorization was not available",
            "cookie behavior was observed without recording values",
            "https://example.test/path",
            "public-key discussion",
            "token handling remains out of scope",
            "test-user-1",
            "",
        )

    def test_input_shape_errors_use_fixed_non_reflective_text(self) -> None:
        sentinel = "distinct-secret-sentinel"
        with self.assertRaises(TypeError) as wrong_type:
            self.policy.classify(7)  # type: ignore[arg-type]
        with self.assertRaises(ValueError) as too_long:
            self.policy.classify(
                sentinel + "x" * MAX_RESEARCH_SENSITIVE_INPUT_CHARACTERS
            )
        for error in (wrong_type.exception, too_long.exception):
            self.assertNotIn(sentinel, str(error))

    def test_every_category_has_unique_fixed_operator_wording(self) -> None:
        labels = {
            sensitive_class.operator_label
            for sensitive_class in ResearchSensitiveInputClass
        }
        self.assertEqual(len(labels), len(ResearchSensitiveInputClass))
        for label in labels:
            self.assertNotIn("distinct", label)
            self.assertNotIn("=", label)
            self.assertNotIn(":", label)


if __name__ == "__main__":
    unittest.main()
