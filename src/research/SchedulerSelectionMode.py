"""Separate explicit human cycles from future unattended selection."""

from enum import StrEnum


class SchedulerSelectionMode(StrEnum):
    MANUAL = "manual"
    DEFERRED = "deferred"
