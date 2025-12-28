import json
from pathlib import Path
from typing import Any


# 读取JSON，解析JSON，读取文件内容
def read_json(path: str | Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


# 写入JSON，序列化JSON，写入文件内容
def write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")


# 追加JSONL，创建目录，读取文件
def append_jsonl(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


# 加载JSON，读取文件内容
def load_json(path: str | Path) -> Any:
    return read_json(path)


# 保存JSON，写入文件内容
def save_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    write_json(path, data, indent=indent)
