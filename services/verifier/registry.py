from __future__ import annotations

from typing import Callable


CHECK_REGISTRY: dict[str, Callable] = {}


def register_check(name: str):
    def decorator(fn: Callable):
        CHECK_REGISTRY[name] = fn
        return fn

    return decorator
