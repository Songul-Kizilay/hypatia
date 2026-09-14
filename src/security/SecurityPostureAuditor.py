"""Check that the boundaries the rest of Hypatia relies on still hold.

Tests prove the boundaries held when the code was written. This proves they hold
in the data now — that no source in the store arrived over plain HTTP, that
nothing points at a loopback address, that no embedded credential was persisted,
that two accepted sources are not quietly the same page. Those are different
claims, and only the second one survives a bad migration, a hand-edited file, or
a bug nobody has found yet.

The checks are chosen for what the domain types do not already guarantee.
`ResearchRun` refuses evidence citing a missing source and claims citing missing
evidence at construction, so re-checking those here would be theatre that
inflates the count of things audited. What no type checks is the shape of a
persisted source URL, its content type, whether its timestamps are ordered, or
whether the same page was accepted twice — and that last one matters more than
it looks, because a duplicated source makes a single-source claim read as
corroborated to calibration and to the hypothesis appraiser.

The audit performs no network operation, and the address check is deliberately
literal rather than resolved. Re-resolving a hostname at audit time would be a
network call the audit has no authorisation to make, and a DNS answer today says
nothing about the answer when the source was fetched — the resolution that
mattered already happened at the fetch boundary, where it was pinned.

Nothing here is repaired automatically. A finding says what is wrong; deciding
what to do about a source already accepted, cited, and reasoned from is a
judgement with consequences the auditor cannot see.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from ipaddress import ip_address
from urllib.parse import urlsplit

from research.ResearchRun import ResearchRun
from research.ResearchSourceRecord import (
    EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY,
    EXTERNAL_SOURCE_TAINT_LABEL,
    ResearchSourceRecord,
)
from research.SourceIdentity import identity_of
from security.SecurityFinding import MAX_FINDING_DETAIL_LENGTH, SecurityFinding
from security.SecurityFindingKind import SecurityFindingKind
from security.SecurityPostureReport import SecurityPostureReport

CHECK_COUNT = len(SecurityFindingKind)

ACCEPTABLE_CONTENT_TYPES = frozenset(
    {
        "application/xhtml+xml",
        "text/html",
        "text/markdown",
        "text/plain",
    }
)

_NON_PUBLIC_HOSTS = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})


class SecurityPostureAuditor:
    """Audit Hypatia's own persisted research state, touching no network."""

    def audit(self, runs: Iterable[ResearchRun]) -> SecurityPostureReport:
        """Return every finding, together with the scope that produced it."""
        findings: list[SecurityFinding] = []
        run_count = source_count = evidence_count = claim_count = 0
        for run in runs:
            run_count += 1
            source_count += len(run.sources)
            evidence_count += len(run.evidence)
            claim_count += len(run.claims)
            for source in run.sources:
                findings.extend(self._url_findings(run, source))
                findings.extend(self._record_findings(run, source))
            findings.extend(self._duplicate_findings(run))
        findings.sort(
            key=lambda finding: (
                -finding.severity.rank,
                finding.kind.value,
                finding.subject_id,
            )
        )
        return SecurityPostureReport(
            findings=tuple(findings),
            checks_run=CHECK_COUNT,
            runs_examined=run_count,
            sources_examined=source_count,
            evidence_examined=evidence_count,
            claims_examined=claim_count,
        )

    def _url_findings(
        self,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> list[SecurityFinding]:
        """Check the shape of a persisted URL, which no type validates."""
        parts = urlsplit(source.url)
        findings: list[SecurityFinding] = []
        if parts.scheme.casefold() != "https":
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.NON_HTTPS_SOURCE,
                    source.document_id,
                    "This accepted source was not obtained over HTTPS, so its "
                    "content was never protected in transit.",
                )
            )
        if parts.username or parts.password:
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.CREDENTIALS_IN_SOURCE_URL,
                    source.document_id,
                    "This source URL carries embedded credentials, which should "
                    "never have been persisted.",
                )
            )
        if self._non_public(parts.hostname):
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.NON_PUBLIC_SOURCE,
                    source.document_id,
                    "This source names a loopback or private address, which the "
                    "fetch boundary refuses.",
                )
            )
        return findings

    def _record_findings(
        self,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> list[SecurityFinding]:
        """Check labelling, content type, and the order of the timestamps."""
        findings: list[SecurityFinding] = []
        if source.taint_label != EXTERNAL_SOURCE_TAINT_LABEL:
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.UNLABELLED_SOURCE,
                    source.document_id,
                    "This source has lost its untrusted-data label, so its text "
                    "could be read as though Hypatia wrote it.",
                )
            )
        if source.instruction_authority != EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY:
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.SOURCE_CLAIMS_INSTRUCTION_AUTHORITY,
                    source.document_id,
                    "This source claims instruction authority. Fetched text is "
                    "data and must never be able to direct behaviour.",
                )
            )
        if source.content_type not in ACCEPTABLE_CONTENT_TYPES:
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.UNSUPPORTED_CONTENT_TYPE,
                    source.document_id,
                    f"This source is stored as {source.content_type}, which the "
                    "fetch boundary does not accept.",
                )
            )
        if source.fetched_at > source.added_at:
            findings.append(
                self._finding(
                    run,
                    SecurityFindingKind.IMPLAUSIBLE_PROVENANCE,
                    source.document_id,
                    "This source was recorded as fetched after it was added, so "
                    "its provenance timestamps cannot both be right.",
                )
            )
        return findings

    def _duplicate_findings(self, run: ResearchRun) -> list[SecurityFinding]:
        """Find one page accepted twice, which would fake corroboration.

        Two accepted sources naming the same resource used to read as two
        independent sources to anything counting them. Support counting now
        works over resource identities, so the inflation is fixed; this check
        stays because the duplicate records are still worth knowing about, and
        because a check that is currently redundant is the one that notices when
        the protection regresses.
        """
        counts = Counter(identity_of(source.url) for source in run.sources)
        return [
            self._finding(
                run,
                SecurityFindingKind.DUPLICATE_SOURCE_URL,
                source.document_id,
                "This resource was accepted more than once. Support counting "
                "already treats it as one source; the duplicate records remain.",
            )
            for source in run.sources
            if counts[identity_of(source.url)] > 1
        ]

    @staticmethod
    def _non_public(hostname: str | None) -> bool:
        """Return whether a hostname is literally a non-public address.

        No name is resolved. A hostname that resolves privately today is not
        detectable here by design, and pretending otherwise would turn an audit
        into a network client.
        """
        if not hostname:
            return False
        normalised = hostname.casefold().strip("[]")
        if normalised in _NON_PUBLIC_HOSTS:
            return True
        try:
            address = ip_address(normalised)
        except ValueError:
            return False
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        )

    @staticmethod
    def _finding(
        run: ResearchRun,
        kind: SecurityFindingKind,
        subject_id: str,
        detail: str,
    ) -> SecurityFinding:
        return SecurityFinding(
            kind=kind,
            run_id=run.run_id,
            subject_id=subject_id,
            detail=detail[:MAX_FINDING_DETAIL_LENGTH],
        )
