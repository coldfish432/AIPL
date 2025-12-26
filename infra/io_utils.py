import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")
