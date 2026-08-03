from enum import StrEnum


class AppState(StrEnum):
    STARTING = "Starting"
    READY = "Ready"
    DEGRADED = "Degraded"
    STOPPING = "Stopping"
    STOPPED = "Stopped"