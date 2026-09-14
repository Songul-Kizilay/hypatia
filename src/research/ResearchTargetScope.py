"""Explicit target boundaries, not proof of authorization or a scanning grant.

DNS names are authorized by name, never by where another name resolves. Literal
IPs require their own network rule. Exclusions always win. Rules contain no URL
paths, prose, ownership guesses, or model decisions.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_SCOPE_RULES = 100
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def _dns_name(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or len(value) > 253:
        raise ResearchError("Target scope requires an ASCII DNS name.")
    name = value.lower().removesuffix(".")
    labels = name.split(".")
    if (
        len(labels) < 2
        or any(_LABEL.fullmatch(label) is None for label in labels)
        or labels[-1].isdigit()
    ):
        raise ResearchError("Target scope DNS name is invalid.")
    return name


@dataclass(frozen=True, slots=True)
class TargetHostRule:
    """Match one host, or descendants only (the equivalent of *.host).

    Descendants include multiple label levels, but not the apex. To allow both,
    author two explicit rules. Unicode names must be supplied as ASCII A-labels.
    """

    host: str
    subdomains_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.subdomains_only, bool):
            raise ResearchError("Target scope subdomain selection must be boolean.")
        object.__setattr__(self, "host", _dns_name(self.host))

    def matches(self, hostname: str) -> bool:
        if self.subdomains_only:
            return hostname.endswith("." + self.host)
        return hostname == self.host


@dataclass(frozen=True, slots=True)
class ResearchTargetScope:
    """Immutable allow/exclude rules for HTTPS target acquisition.

    Network rules use strict CIDR notation, including /32 or /128 for single IPs.
    An allowed DNS host may use public CDN addresses; allowed CIDRs do not grant
    access to otherwise unlisted hostnames. Excluded CIDRs also veto DNS answers.
    """

    allowed_hosts: tuple[TargetHostRule, ...] = ()
    excluded_hosts: tuple[TargetHostRule, ...] = ()
    allowed_networks: tuple[str, ...] = ()
    excluded_networks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        groups = (
            self.allowed_hosts,
            self.excluded_hosts,
            self.allowed_networks,
            self.excluded_networks,
        )
        if any(not isinstance(group, tuple) for group in groups):
            raise ResearchError("Target scope rules must be immutable tuples.")
        if sum(len(group) for group in groups) > MAX_SCOPE_RULES:
            raise ResearchError("Target scope has too many rules.")
        if not self.allowed_hosts and not self.allowed_networks:
            raise ResearchError("Target scope needs an explicit allowed target.")
        if any(
            not isinstance(rule, TargetHostRule)
            for rule in (*self.allowed_hosts, *self.excluded_hosts)
        ):
            raise ResearchError("Target scope host rules are invalid.")
        for network in (*self.allowed_networks, *self.excluded_networks):
            if not isinstance(network, str) or len(network) > 49 or "/" not in network:
                raise ResearchError("Target scope networks require explicit CIDR.")
            try:
                ipaddress.ip_network(network, strict=True)
            except ValueError as error:
                raise ResearchError("Target scope network is invalid.") from error

    @staticmethod
    def _in_networks(address: str, networks: tuple[str, ...]) -> bool:
        parsed = ipaddress.ip_address(address)
        # An IPv4 exclusion must not be bypassed with an IPv4-mapped IPv6 form.
        mapped = (
            parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) else None
        )
        return any(
            parsed in ipaddress.ip_network(network)
            or (mapped is not None and mapped in ipaddress.ip_network(network))
            for network in networks
        )

    def require_hostname(self, hostname: str) -> None:
        """Refuse out-of-scope request authorities before any DNS lookup."""
        if not isinstance(hostname, str) or "%" in hostname:
            raise ResearchError("Target scope host is invalid.")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            name = _dns_name(hostname)
            if any(rule.matches(name) for rule in self.excluded_hosts):
                raise ResearchError(
                    "Target host is explicitly excluded from scope."
                ) from None
            if not any(rule.matches(name) for rule in self.allowed_hosts):
                raise ResearchError("Target host is outside scope.") from None
        else:
            if self._in_networks(hostname, self.excluded_networks):
                raise ResearchError("Target address is explicitly excluded from scope.")
            if not self._in_networks(hostname, self.allowed_networks):
                raise ResearchError("Target address is outside scope.")

    def require_addresses(self, addresses: tuple[str, ...]) -> None:
        """Reject the whole resolution if any address is explicitly excluded."""
        if not isinstance(addresses, tuple) or not 1 <= len(addresses) <= 64:
            raise ResearchError("Target scope address set is invalid.")
        for address in addresses:
            if not isinstance(address, str) or "%" in address:
                raise ResearchError("Target scope address is invalid.")
            try:
                excluded = self._in_networks(address, self.excluded_networks)
            except (ValueError, TypeError) as error:
                raise ResearchError("Target scope address is invalid.") from error
            if excluded:
                raise ResearchError("Target address is explicitly excluded from scope.")
