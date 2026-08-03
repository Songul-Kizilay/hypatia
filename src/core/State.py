"""
System runtime states.
"""

from enum import StrEnum


class SystemState(StrEnum):

    STARTING = "STARTING"

    INITIALIZING = "INITIALIZING"

    READY = "READY"

    RUNNING = "RUNNING"

    PAUSED = "PAUSED"

    STOPPING = "STOPPING"

    STOPPED = "STOPPED"

    ERROR = "ERROR"
