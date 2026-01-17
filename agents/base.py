"""
Sub Agent 基础模块
提供所有 Sub Agent 共用的基础功能
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


def extract_root_arg(argv: list[str]) -> Path | None:
    """从命令行参数中提取 --root 参数"""
    for idx, arg in enumerate(argv):
        if arg == "--root" and idx + 1 < len(argv):
            return Path(argv[idx + 1])
    return None


def init_root() -> Path:
    """初始化 ROOT_DIR 并添加到 sys.path"""
    root = extract_root_arg(sys.argv)
    if not root:
        raise RuntimeError("--root is required (pass --root <repo_root>)")
    root = root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def load_json_file(path: Path, default: Any = None) -> Any:
    """安全加载 JSON 文件"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path: Path, data: Any) -> None:
    """写入 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_event(run_dir: Path, event: dict) -> None:
    """追加事件到 events.jsonl"""
    events_path = run_dir / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def resolve_path_under(base: Path, rel_path: str) -> Path | None:
    """
    解析相对路径，确保在 base 目录下
    返回 None 表示路径不合法
    """
    rel_path = rel_path.replace("\\", "/")
    if rel_path.startswith("/") or rel_path.startswith("\\"):
        return None
    parts = Path(rel_path).parts
    if any(p == ".." for p in parts):
        return None
    dest = (base / rel_path).resolve()
    try:
        dest.relative_to(base.resolve())
    except Exception:
        return None
    return dest


def is_path_allowed(path: Path, allowlist: list[str], denylist: list[str]) -> bool:
    """检查路径是否在允许列表中"""
    posix = path.as_posix()
    for d in denylist:
        if d and (posix == d or posix.startswith(d.rstrip("/") + "/")):
            return False
    if not allowlist:
        return True
    for a in allowlist:
        if a == "" or posix == a or posix.startswith(a.rstrip("/") + "/"):
            return True
    return False


class AgentResult:
    """Sub Agent 执行结果"""
    
    def __init__(self, ok: bool = True, data: dict = None, error: str = None):
        self.ok = ok
        self.data = data or {}
        self.error = error
    
    def to_dict(self) -> dict:
        result = {"ok": self.ok}
        if self.data:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        return result
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class BaseAgent:
    """Sub Agent 基类"""
    
    def __init__(self, root: Path, run_dir: Path):
        self.root = root
        self.run_dir = run_dir
        self.start_time = time.time()
    
    def log_event(self, event_type: str, **kwargs):
        """记录事件"""
        event = {
            "type": event_type,
            "ts": time.time(),
            "agent": self.__class__.__name__,
            **kwargs,
        }
        append_event(self.run_dir, event)
    
    def run(self, **kwargs) -> AgentResult:
        """执行 agent，子类需要实现此方法"""
        raise NotImplementedError("Subclasses must implement run()")
    
    def execute(self, **kwargs) -> AgentResult:
        """执行并记录开始/结束事件"""
        self.log_event(f"{self.__class__.__name__}_start")
        try:
            result = self.run(**kwargs)
            self.log_event(f"{self.__class__.__name__}_done", ok=result.ok)
            return result
        except Exception as exc:
            self.log_event(f"{self.__class__.__name__}_error", error=str(exc))
            return AgentResult(ok=False, error=str(exc))
