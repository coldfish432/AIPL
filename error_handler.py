from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

from exceptions import AIPLError, StorageError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def handle_errors(default_return: Any = None, reraise: bool = False, log_level: int = logging.ERROR) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except AIPLError as exc:
                logger.log(log_level, f"{func.__name__} failed: [{exc.code}] {exc.message}", extra=exc.details)
                if reraise:
                    raise
                return default_return
            except Exception as exc:
                logger.log(log_level, f"{func.__name__} unexpected error: {type(exc).__name__}: {exc}")
                if reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def safe_json_load(path, default: Any = None, error_class: type = StorageError):
    import json
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid JSON in {path}: {exc}")
        return default
    except IOError as exc:
        raise error_class(f"Cannot read {path}: {exc}", {"path": str(path)})


class CondaEnvironmentError(Exception):
    """Conda environment related error."""
    pass


def handle_conda_error(error_code: int, detail: str = "") -> str:
    """Return user-friendly message for Conda errors."""
    error_messages = {
        0xC0000142: (
            "应用程序无法正常启动 (0xc0000142)\n\n"
            "可能的解决方案：\n"
            "1. 重新安装 Anaconda 或 Miniconda\n"
            "2. 以管理员身份运行\n"
            "3. 检查是否有多个 Python 安装冲突\n"
            "4. 将 Conda 路径添加到系统 PATH 环境变量\n"
        ),
    }
    return error_messages.get(error_code, f"未知错误: {hex(error_code)}\n{detail}")
