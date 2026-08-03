"""
Shared exceptions.
"""


class HypatiaError(Exception):
    """Base exception."""


class ConfigurationError(HypatiaError):
    """Configuration error."""


class BootstrapError(HypatiaError):
    """Bootstrap error."""


class MemoryError(HypatiaError):
    """Memory error."""


class PlannerError(HypatiaError):
    """Planner error."""


class KnowledgeError(HypatiaError):
    """Knowledge engine error."""


class AgentError(HypatiaError):
    """Agent error."""


class ServiceError(HypatiaError):
    """Service error."""