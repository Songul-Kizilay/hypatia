"""
Shared exceptions.
"""


class HypatiaError(Exception):
    """Base exception."""


class ConfigurationError(HypatiaError):
    """Configuration error."""


class BootstrapError(HypatiaError):
    """Bootstrap error."""


class ContainerError(HypatiaError):
    """Dependency container error."""


class EventBusError(HypatiaError):
    """Event bus error."""


class BrainError(HypatiaError):
    """Brain request-processing error."""


class MemoryError(HypatiaError):
    """Memory error."""


class SessionError(HypatiaError):
    """Raised when session registry operations cannot be completed."""


class SessionRenameRollbackError(SessionError):
    """Raised when session rename failure cannot restore memory persistence."""

    def __init__(
        self,
        original_error: Exception,
        rollback_error: Exception,
    ) -> None:
        super().__init__(
            "Session rename failed and memory rollback could not be completed."
        )
        self.original_error = original_error
        self.rollback_error = rollback_error


class PlannerError(HypatiaError):
    """Planner error."""


class KnowledgeError(HypatiaError):
    """Knowledge engine error."""


class AgentError(HypatiaError):
    """Agent error."""


class ServiceError(HypatiaError):
    """Service error."""
