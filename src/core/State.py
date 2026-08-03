"""
System runtime states.
"""

from enum import Enum


class SystemState(str, Enum):

    STARTING = "STARTING"

    INITIALIZING = "INITIALIZING"

    READY = "READY"

    RUNNING = "RUNNING"

    PAUSED = "PAUSED"

    STOPPING = "STOPPING"

    STOPPED = "STOPPED"

    ERROR = "ERROR"