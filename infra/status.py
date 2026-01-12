from __future__ import annotations

class StatusSet:
    RUNNING = frozenset({"running", "doing"})
    COMPLETED = frozenset({"done", "completed", "success"})
    TERMINAL = frozenset({"done", "failed", "canceled", "discarded"})


def is_running(status: str) -> bool:
    return (status or "").lower() in StatusSet.RUNNING


def is_terminal(status: str) -> bool:
    return (status or "").lower() in StatusSet.TERMINAL
