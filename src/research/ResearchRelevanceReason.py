"""Why a candidate scored what it scored, in codes rather than prose.

A ranking a person cannot interrogate is a ranking they have to trust, and the
whole point of ranking sources for a researcher is that they should not have to.
So every score carries the reasons that produced it.

Codes, not sentences. Prose would be generated text about a deterministic
calculation, which is the shape of an explanation that can drift away from what
the code actually did. A closed vocabulary cannot drift: each member is emitted
by exactly one condition, and a test can assert that the condition and the code
agree. Display text for a person is looked up from the code, never composed.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchRelevanceReason(StrEnum):
    """Name one deterministic contribution to a relevance score."""

    ALL_QUERY_TERMS_IN_TITLE = "all_query_terms_in_title"
    SOME_QUERY_TERMS_IN_TITLE = "some_query_terms_in_title"
    NO_QUERY_TERM_IN_TITLE = "no_query_term_in_title"
    TECHNICAL_IDENTIFIER_MATCHED = "technical_identifier_matched"
    TECHNICAL_IDENTIFIER_MISSING = "technical_identifier_missing"
    QUERY_PHRASE_IN_TITLE = "query_phrase_in_title"
    QUERY_TERM_IN_VENUE = "query_term_in_venue"
    NEWER_THAN_OTHER_RESULTS = "newer_than_other_results"
    OLDER_THAN_OTHER_RESULTS = "older_than_other_results"
    RECENCY_NOT_REQUESTED = "recency_not_requested"
    PUBLICATION_YEAR_UNKNOWN = "publication_year_unknown"
    SAME_RESOURCE_AS_EARLIER_RESULT = "same_resource_as_earlier_result"
