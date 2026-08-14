from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMEndpointPolicy import validate_llm_endpoint


class LLMEndpointPolicyTests(unittest.TestCase):
    def test_accepts_https_and_explicit_loopback_http_endpoints(self) -> None:
        for endpoint in (
            "https://api.example.test/v1/chat/completions",
            "http://localhost:11434/v1/chat/completions",
            "http://127.0.0.1:11434/v1/chat/completions",
            "http://[::1]:11434/v1/chat/completions",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(validate_llm_endpoint(endpoint), endpoint)

    def test_rejects_plain_http_for_non_loopback_endpoints(self) -> None:
        expected_message = (
            "LLM base URL must use HTTPS unless it targets localhost, "
            "127.0.0.1, or ::1."
        )

        with self.assertRaises(ValueError) as raised:
            validate_llm_endpoint("http://api.example.test/v1/chat/completions")

        self.assertEqual(str(raised.exception), expected_message)

    def test_rejects_malformed_or_credential_bearing_endpoints(self) -> None:
        non_empty_url_message = "LLM base URL must be a non-empty HTTP(S) URL."
        invalid_url_message = "LLM base URL must be a valid HTTP(S) URL."
        invalid_endpoints = {
            "": non_empty_url_message,
            " https://api.example.test/v1": non_empty_url_message,
            "ftp://api.example.test/v1": invalid_url_message,
            "https://": invalid_url_message,
            "https://user:password@api.example.test/v1": (
                "LLM base URL must not include credentials."
            ),
            "https://api.example.test:99999/v1": invalid_url_message,
        }

        for endpoint, expected_message in invalid_endpoints.items():
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError) as raised:
                    validate_llm_endpoint(endpoint)
                self.assertEqual(str(raised.exception), expected_message)
