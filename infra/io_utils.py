import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")


def append_jsonl(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def load_json(path: str | Path) -> Any:
    return read_json(path)


def save_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    write_json(path, data, indent=indent)