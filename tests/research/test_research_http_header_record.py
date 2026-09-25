"""`ResearchHttpHeaderRecord` preserves one observed header exactly as received."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from core.Exceptions import ResearchError
from research.ResearchHttpHeaderRecord import (
    MAX_HTTP_HEADER_NAME_CHARACTERS,
    MAX_HTTP_HEADER_VALUE_CHARACTERS,
    ResearchHttpHeaderRecord,
)


class ValidConstructionTests(unittest.TestCase):
    def test_a_normal_header_round_trips_exactly(self) -> None:
        header = ResearchHttpHeaderRecord(name="Content-Type", value="text/html")

        self.assertEqual(header.name, "Content-Type")
        self.assertEqual(header.value, "text/html")

    def test_casing_is_never_folded(self) -> None:
        header = ResearchHttpHeaderRecord(name="content-type", value="text/html")

        self.assertEqual(header.name, "content-type")

    def test_a_value_containing_a_colon_is_preserved_verbatim(self) -> None:
        header = ResearchHttpHeaderRecord(
            name="Date", value="Thu, 24 Sep 2026 22:57:48 GMT"
        )

        self.assertEqual(header.value, "Thu, 24 Sep 2026 22:57:48 GMT")

    def test_an_empty_value_is_allowed(self) -> None:
        header = ResearchHttpHeaderRecord(name="X-Empty", value="")

        self.assertEqual(header.value, "")


class MalformedFieldRejectionTests(unittest.TestCase):
    def test_an_empty_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name="", value="value")

    def test_a_non_string_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name=1, value="value")  # type: ignore[arg-type]

    def test_a_non_string_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name="X-Foo", value=1)  # type: ignore[arg-type]

    def test_control_data_in_the_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name="X-Foo\r\nX-Bar: 1", value="value")

    def test_control_data_in_the_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name="X-Foo", value="value\r\nX-Bar: 1")

    def test_a_null_byte_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(name="X-Foo", value="va\x00lue")

    def test_an_oversized_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(
                name="a" * (MAX_HTTP_HEADER_NAME_CHARACTERS + 1), value="value"
            )

    def test_an_oversized_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpHeaderRecord(
                name="X-Foo", value="a" * (MAX_HTTP_HEADER_VALUE_CHARACTERS + 1)
            )


class ImmutabilityTests(unittest.TestCase):
    def test_the_record_is_frozen(self) -> None:
        header = ResearchHttpHeaderRecord(name="X-Foo", value="1")

        with self.assertRaises(FrozenInstanceError):
            header.value = "2"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
