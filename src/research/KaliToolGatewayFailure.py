"""Inert failure facts from the existing reviewed Kali execution boundary.

These facts describe a single call, confer no authority, and are not durable
execution receipts. An adapter exception cannot establish whether a process ran.
"""

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError


class KaliToolGatewayStage(StrEnum):
    REQUEST = "request"
    SCOPE_POLICY = "scope_policy"
    AUTHORIZATION = "authorization"
    RUNTIME_READINESS = "runtime_readiness"
    AUTHORIZATION_CONSUMPTION = "authorization_consumption"
    DISPATCH = "dispatch"


@dataclass(frozen=True, slots=True)
class KaliToolGatewayFailure:
    """Stage-owned facts; never accept status claims from request metadata."""

    stage: KaliToolGatewayStage
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, KaliToolGatewayStage):
            raise ResearchError("Kali gateway failure stage is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Kali gateway failure reason is invalid.")

    @property
    def authorization_consumption(self) -> str:
        if self.stage is KaliToolGatewayStage.DISPATCH:
            return "consumed"
        if self.stage is KaliToolGatewayStage.AUTHORIZATION_CONSUMPTION:
            return "unknown; persistence did not confirm completion"
        return "not attempted by this call"

    @property
    def adapter_invoked(self) -> bool:
        return self.stage is KaliToolGatewayStage.DISPATCH


class KaliToolGatewayError(ResearchError):
    """Carry descriptive failure facts back to the presentation boundary."""

    def __init__(self, failure: KaliToolGatewayFailure) -> None:
        super().__init__(failure.reason)
        self.failure = failure
