"""Discovery from a small, hand-reviewed catalog of fixed authoritative URLs.

Crossref and NVD each speak to a live API and can be asked almost anything.
This provider speaks to nothing. It holds a short, literal, code-reviewed list
of specific URLs at a small number of recognized security-teaching and
official tool-documentation sources (PortSwigger Web Security Academy, the
OWASP Cheat Sheet Series, and each covered tool's own project documentation --
nmap.org, curl.se, wireshark.org, tcpdump.org, sqlmap's and ffuf's and
gobuster's and Nuclei's own project pages, and openssl.org) and returns
entries from that list only when the question names a topic the catalog
actually covers. There is no search, no network call, no model call, and no
way for the question text to produce a URL that is not already written here:
a provider whose candidate list could be influenced by its input is exactly
the SSRF-shaped mistake `PublicHttpsUrlValidator` and `PinnedHttpsTransport`
exist to prevent downstream, and the cheapest way to keep this provider out
of that category is to let it return literal constants and nothing else.

The Kali Linux tool entries (Nmap, Burp Suite, curl, ffuf, Gobuster,
Wireshark, tcpdump, sqlmap, Nuclei, Netcat/Ncat, OpenSSL) exist to teach
*what a tool is and how it is documented to be used* -- purpose, inputs and
outputs, and official usage guidance -- not to grant any execution authority.
Nothing in this file runs a tool, and an example command inside a fetched
page is educational content, not permission to execute it; that remains a
separate, unstarted, explicitly authorized milestone.

Matching is deliberately shallow, reusing the same `ResearchQueryTerms`
normalization NVD uses for its keyword route, so punctuation and case never
change the result. A topic matches when its required terms are all present, or
one short alias term-set is fully present (a topic may list more than one
alias shape -- "XSS" and the unhyphenated "cross site scripting" both name the
same topic that "cross-site scripting" names as a single hyphenated token). A
question matching no topic returns an empty list rather than a guessed
nearest topic, because an empty result is an honest "this catalog has nothing
for that" and a guessed one is not. A question naming more than one covered
topic (for example, asking to compare SQL injection and XSS) returns every
matching topic's candidates, catalog order, still bounded by ``limit`` -- this
is what lets a single discovery step gather sources for distinguishing two
topics rather than only ever answering about one.

Every candidate URL still passes through the same `ResearchSourceCandidate`
validation (credential-free HTTPS, bounded lengths) as every other provider's
candidates, and still has to be explicitly accepted and fetched afterwards
through the ordinary, unmodified `HttpResearchSourceFetcher` — pinned address,
redirect revalidation, content-type and size bounds included. This provider
only ever shortens "which URL", never "is the URL safe to fetch".

Adding a topic later means adding a catalog entry by hand and reviewing it
like any other code change — not teaching this provider to search, infer, or
accept a URL from a caller. `GENERAL_DISCOVERY_PROVIDERS` in
`ResearchDiscoveryProviderName` deliberately excludes this provider: curiosity
and knowledge-gap "ask the provider(s) this run has not asked" logic must
never auto-propose asking a catalog that was never meant to answer every
question.

A handful of tool names are also ordinary English words -- "burp", "curl",
"nuclei" -- so a sentence that happens to contain one of them ("I felt a burp
after lunch") can trigger a match that has nothing to do with the tool. This
is an accepted, deliberate tradeoff rather than an oversight: unlike "SQL
injection" or "cross-site scripting", the catalog has no natural second word
to pair a single-word tool name with that every real question about the tool
would still contain, and narrowing match to only two-word phrasings would
silently break the much more common case of a short, direct question ("what
is curl?"). The worst outcome of a false match is an extra, still-pinned,
still-official, still-harmless documentation citation in a LEARN-only
pipeline -- never a wrong URL, an executed command, or an expanded authority
-- so the asymmetry favors recall here, unlike the vulnerability-class
entries above where a wrong match would misname a security concept.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchQueryTerms import ResearchQueryTerms
from research.ResearchSourceCandidate import ResearchSourceCandidate

CURATED_PROVIDER_NAME = ResearchDiscoveryProviderName.CURATED.value

_MAXIMUM_LIMIT = 10


@dataclass(frozen=True, slots=True)
class _CuratedTopic:
    """One catalog entry: how a question is recognized, and what it returns."""

    #: Every one of these terms must appear for a match (order-independent).
    required_terms: frozenset[str]
    #: Each inner set is itself a complete alternative match (all of its terms
    #: present); any one of these alternative shapes is also a match. Lets a
    #: topic be named by a short acronym ("xss") or by a phrasing that tokenizes
    #: differently than `required_terms` ("cross site scripting" as three
    #: separate words, where `required_terms` is the hyphenated single token).
    alias_term_sets: tuple[frozenset[str], ...] = ()
    candidates: tuple[ResearchSourceCandidate, ...] = ()


#: The fixed, hand-reviewed catalog. Each URL was checked by hand to resolve
#: directly (no redirect) to a live, official page at the time it was added;
#: the fetcher still revalidates everything itself at fetch time regardless.
_CATALOG: tuple[_CuratedTopic, ...] = (
    _CuratedTopic(
        required_terms=frozenset({"sql", "injection"}),
        alias_term_sets=(frozenset({"sqli"}),),
        candidates=(
            ResearchSourceCandidate(
                url="https://portswigger.net/web-security/sql-injection",
                title="SQL injection | Web Security Academy",
                snippet=(
                    "PortSwigger Web Security Academy's topic page on SQL "
                    "injection: what it is, how it arises, and how to find "
                    "and exploit it in a lab."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url="https://portswigger.net/web-security/sql-injection/cheat-sheet",
                title="SQL injection cheat sheet | Web Security Academy",
                snippet=(
                    "PortSwigger's reference tables of SQL injection syntax "
                    "and techniques across common database engines."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url=(
                    "https://cheatsheetseries.owasp.org/cheatsheets/"
                    "SQL_Injection_Prevention_Cheat_Sheet.html"
                ),
                title="SQL Injection Prevention Cheat Sheet",
                snippet=(
                    "OWASP's official guidance on preventing SQL injection, "
                    "centered on parameterized queries and safe query "
                    "construction."
                ),
                container="OWASP Cheat Sheet Series",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"cross-site", "scripting"}),
        alias_term_sets=(
            frozenset({"xss"}),
            frozenset({"cross", "site", "scripting"}),
        ),
        candidates=(
            ResearchSourceCandidate(
                url="https://portswigger.net/web-security/cross-site-scripting",
                title="Cross-site scripting | Web Security Academy",
                snippet=(
                    "PortSwigger Web Security Academy's topic page on XSS: "
                    "what it is, the reflected/stored/DOM-based types, and "
                    "how to find and exploit it in a lab."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url=(
                    "https://portswigger.net/web-security/"
                    "cross-site-scripting/cheat-sheet"
                ),
                title="Cross-site scripting cheat sheet | Web Security Academy",
                snippet=(
                    "PortSwigger's reference vectors for XSS across browsers "
                    "and contexts."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url=(
                    "https://cheatsheetseries.owasp.org/cheatsheets/"
                    "Cross_Site_Scripting_Prevention_Cheat_Sheet.html"
                ),
                title="Cross Site Scripting Prevention Cheat Sheet",
                snippet=(
                    "OWASP's official guidance on preventing XSS, centered on "
                    "contextual output encoding and safe DOM APIs."
                ),
                container="OWASP Cheat Sheet Series",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"nmap"}),
        alias_term_sets=(frozenset({"network", "mapper"}),),
        candidates=(
            ResearchSourceCandidate(
                url="https://nmap.org/book/man.html",
                title="Nmap Reference Guide",
                snippet=(
                    "The official Nmap man page: scan techniques, host "
                    "discovery, port specification, service/version "
                    "detection, and output formats."
                ),
                container="Nmap.org",
            ),
            ResearchSourceCandidate(
                url="https://nmap.org/book/toc.html",
                title="Nmap Network Scanning (book table of contents)",
                snippet=(
                    "The official Nmap project's own book-length "
                    "documentation, covering the tool end to end."
                ),
                container="Nmap.org",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"burp"}),
        alias_term_sets=(frozenset({"burpsuite"}),),
        candidates=(
            ResearchSourceCandidate(
                url="https://portswigger.net/burp/documentation",
                title="Burp Suite documentation",
                snippet=(
                    "PortSwigger's official documentation hub for Burp "
                    "Suite: Proxy, Repeater, Intruder, Scanner and the rest "
                    "of the toolset."
                ),
                container="PortSwigger",
            ),
            ResearchSourceCandidate(
                url="https://portswigger.net/burp/documentation/desktop/getting-started",
                title="Getting started with Burp Suite",
                snippet=(
                    "PortSwigger's official getting-started guide: "
                    "configuring the browser, intercepting traffic, and the "
                    "basic workflow."
                ),
                container="PortSwigger",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"curl"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://curl.se/docs/manpage.html",
                title="curl man page",
                snippet=(
                    "The official curl manual: every option, protocol "
                    "support, and usage examples, maintained by the curl "
                    "project itself."
                ),
                container="curl.se",
            ),
            ResearchSourceCandidate(
                url="https://curl.se/docs/",
                title="curl documentation index",
                snippet=(
                    "The curl project's own index of its manuals, "
                    "tutorials, and protocol-specific guides."
                ),
                container="curl.se",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"ffuf"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://github.com/ffuf/ffuf",
                title="ffuf -- Fuzz Faster U Fool",
                snippet=(
                    "ffuf's own official repository README: installation, "
                    "command-line usage, and fuzzing examples."
                ),
                container="ffuf (official GitHub repository)",
            ),
            ResearchSourceCandidate(
                url="https://github.com/ffuf/ffuf/wiki",
                title="ffuf wiki",
                snippet=(
                    "ffuf's own project wiki with extended usage examples "
                    "and advanced filtering/matching options."
                ),
                container="ffuf (official GitHub repository)",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"gobuster"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://github.com/OJ/gobuster",
                title="Gobuster",
                snippet=(
                    "Gobuster's own official repository README: the dir, "
                    "dns, vhost and other scan modes, and their options."
                ),
                container="Gobuster (official GitHub repository)",
            ),
            ResearchSourceCandidate(
                url="https://github.com/OJ/gobuster/wiki",
                title="Gobuster wiki",
                snippet=(
                    "Gobuster's own project wiki with mode-by-mode usage " "notes."
                ),
                container="Gobuster (official GitHub repository)",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"wireshark"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://www.wireshark.org/docs/wsug_html_chunked/",
                title="Wireshark User's Guide",
                snippet=(
                    "The official Wireshark User's Guide: capturing, "
                    "filtering, and analyzing network traffic."
                ),
                container="Wireshark.org",
            ),
            ResearchSourceCandidate(
                url="https://www.wireshark.org/docs/man-pages/wireshark.html",
                title="wireshark(1) man page",
                snippet=(
                    "The official Wireshark man page: command-line "
                    "invocation, capture options, and display filters."
                ),
                container="Wireshark.org",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"tcpdump"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://www.tcpdump.org/manpages/tcpdump.1.html",
                title="tcpdump(1) man page",
                snippet=(
                    "The official tcpdump man page: capture filters, "
                    "interface selection, and output options."
                ),
                container="tcpdump.org",
            ),
            ResearchSourceCandidate(
                url="https://www.tcpdump.org/",
                title="TCPDUMP/LIBPCAP public repository",
                snippet="The tcpdump project's own official home page.",
                container="tcpdump.org",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"sqlmap"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://github.com/sqlmapproject/sqlmap/wiki/Usage",
                title="sqlmap usage",
                snippet=(
                    "sqlmap's own official usage wiki: detection, "
                    "enumeration, and database-takeover options."
                ),
                container="sqlmap (official GitHub repository)",
            ),
            ResearchSourceCandidate(
                url="https://github.com/sqlmapproject/sqlmap",
                title="sqlmap",
                snippet=(
                    "sqlmap's own official repository README: what the "
                    "tool automates and how it is invoked."
                ),
                container="sqlmap (official GitHub repository)",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"nuclei"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://docs.projectdiscovery.io/tools/nuclei/overview",
                title="Nuclei overview",
                snippet=(
                    "ProjectDiscovery's official documentation for Nuclei: "
                    "template-based vulnerability scanning, how it works, "
                    "and how templates are selected and run."
                ),
                container="ProjectDiscovery (official documentation)",
            ),
            ResearchSourceCandidate(
                url="https://github.com/projectdiscovery/nuclei",
                title="Nuclei",
                snippet=(
                    "Nuclei's own official repository README: installation "
                    "and command-line usage."
                ),
                container="ProjectDiscovery (official GitHub repository)",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"netcat"}),
        alias_term_sets=(frozenset({"ncat"}),),
        candidates=(
            ResearchSourceCandidate(
                url="https://nmap.org/ncat/guide/index.html",
                title="Ncat Reference Guide",
                snippet=(
                    "The Nmap Project's official guide to Ncat, its modern, "
                    "actively maintained replacement for the classic "
                    "Netcat utility."
                ),
                container="Nmap.org",
            ),
            ResearchSourceCandidate(
                url="https://nmap.org/ncat/",
                title="Ncat home page",
                snippet=("The Nmap Project's own official Ncat project page."),
                container="Nmap.org",
            ),
        ),
    ),
    _CuratedTopic(
        required_terms=frozenset({"openssl"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://docs.openssl.org/master/man1/openssl/",
                title="openssl(1) -- OpenSSL command line tool",
                snippet=(
                    "The official OpenSSL project's current documentation "
                    "for the openssl command itself: its subcommands and "
                    "how they are organized."
                ),
                container="OpenSSL.org",
            ),
            ResearchSourceCandidate(
                url="https://www.openssl.org/docs/manmaster/man1/openssl.html",
                title="openssl(1) man page",
                snippet=(
                    "The official OpenSSL command-line tool man page: its "
                    "subcommands for keys, certificates, and TLS testing."
                ),
                container="OpenSSL.org",
            ),
        ),
    ),
)


class CuratedResearchSourceDiscoveryProvider:
    """Return catalog entries for a recognized topic; nothing for anything else."""

    provider_name = CURATED_PROVIDER_NAME

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        """Return at most ``limit`` fixed candidates for a catalog topic.

        No network call is made and none could be: every candidate already
        exists as a literal constant above, built before this method is ever
        called. The query only ever selects among constants; it never shapes
        one.
        """
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise ResearchError("Curated discovery query cannot be empty.")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > _MAXIMUM_LIMIT
        ):
            raise ResearchError(
                f"Curated discovery limit must be between 1 and {_MAXIMUM_LIMIT}."
            )
        topics = _matching_topics(normalized_query)
        candidates = [candidate for topic in topics for candidate in topic.candidates]
        return candidates[:limit]


def _matching_topics(query: str) -> tuple[_CuratedTopic, ...]:
    """Return every catalog topic this query names, in catalog order.

    Plural on purpose: a question naming two covered topics (comparing SQL
    injection and XSS, say) gets candidates for both, not only whichever is
    listed first in `_CATALOG`.
    """
    try:
        terms = frozenset(ResearchQueryTerms.of(query).terms)
    except ResearchError:
        return ()
    return tuple(
        topic
        for topic in _CATALOG
        if topic.required_terms <= terms
        or any(alias_terms <= terms for alias_terms in topic.alias_term_sets)
    )
