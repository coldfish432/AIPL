from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


JsonDict = dict[str, Any]


@dataclass
class VerifyResult:
    passed: bool
    reasons: list[JsonDict]


@runtime_checkable
class IVerifier(Protocol):
    def verify_task(self, run_dir: Path, task_id: str, workspace_path: Path | None = None) -> tuple[bool, list[JsonDict]]:
        ...


@runtime_checkable
class IProfileService(Protocol):
    def ensure_profile(self, root: Path, workspace: Path) -> JsonDict:
        ...

    def propose_soft(self, root: Path, workspace: Path, reason: str) -> JsonDict:
        ...

    def approve_soft(self, root: Path, workspace: Path) -> JsonDict:
        ...

    def reject_soft(self, root: Path, workspace: Path) -> JsonDict:
        ...

    def load_profile(self, root: Path, workspace: Path) -> JsonDict | None:
        ...

    def should_propose_on_failure(self, root: Path, workspace: Path, threshold: int = 2, limit: int = 20) -> bool:
        ...


@runtime_checkable
class ICodeGraphService(Protocol):
    def build(self, workspace_root: Path, fingerprint: str | None = None) -> Any:
        ...

    def load(self, path: Path) -> Any:
        ...

    def save(self, graph: Any, path: Path) -> None:
        ...
