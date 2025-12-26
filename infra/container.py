from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import inspect
from typing import Any, Callable


class Lifetime(str, Enum):
    SINGLETON = "singleton"


@dataclass
class _Registration:
    factory: Callable[[], Any]
    lifetime: Lifetime


class Container:
    def __init__(self) -> None:
        self._registrations: dict[type, _Registration] = {}
        self._singletons: dict[type, Any] = {}

    def register(self, interface: type, implementation: Any, lifetime: Lifetime = Lifetime.SINGLETON) -> None:
        if callable(implementation) and not inspect.isclass(implementation):
            factory = implementation
        elif inspect.isclass(implementation):
            factory = lambda: self._build(implementation)
        else:
            self._singletons[interface] = implementation
            return
        self._registrations[interface] = _Registration(factory=factory, lifetime=lifetime)

    def resolve(self, interface: type) -> Any:
        if interface in self._singletons:
            return self._singletons[interface]
        registration = self._registrations.get(interface)
        if not registration:
            raise KeyError(f"No registration for {interface}")
        instance = registration.factory()
        if registration.lifetime == Lifetime.SINGLETON:
            self._singletons[interface] = instance
        return instance

    def _build(self, cls: type) -> Any:
        signature = inspect.signature(cls.__init__)
        kwargs = {}
        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if param.annotation is inspect.Signature.empty:
                if param.default is not inspect.Signature.empty:
                    continue
                raise ValueError(f"Missing annotation for {cls.__name__}.{name}")
            dep_type = param.annotation
            kwargs[name] = self.resolve(dep_type)
        return cls(**kwargs)
