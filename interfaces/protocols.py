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
    # 验证任务
    def verify_task(self, run_dir: Path, task_id: str, workspace_path: Path | None = None) -> tuple[bool, list[JsonDict]]:
        ...

    # 收集错误用于返工
    def collect_errors_for_retry(self, **kwargs) -> Any:
        ...


@runtime_checkable
class IProfileService(Protocol):
    # 确保档案
    def ensure_profile(self, root: Path, workspace: Path) -> JsonDict:
        ...

    # 加载档案
    def load_profile(self, root: Path, workspace: Path) -> JsonDict | None:
        ...


@runtime_checkable
class ICodeGraphService(Protocol):
    # 构建
    def build(self, workspace_root: Path, fingerprint: str | None = None) -> Any:
        ...

    # 加载
    def load(self, path: Path) -> Any:
        ...

    # 保存
    def save(self, graph: Any, path: Path) -> None:
        ...
