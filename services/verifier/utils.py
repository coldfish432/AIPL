from __future__ import annotations

from typing import Any


def reason(mtype: str, **kwargs: Any) -> dict:
    payload = {"type": mtype}
    for k, v in kwargs.items():
        if v is not None:
            payload[k] = v
    return payload


def tail(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    return text[-max_len:]


def extract_key_error_lines(output: str, max_lines: int = 30) -> str:
    keywords = [
        "error:",
        "Error:",
        "ERROR:",
        "failed",
        "Failed",
        "FAILED",
        "Traceback",
        "SyntaxError",
        "TypeError",
        "ValueError",
        "AssertionError",
        "ImportError",
        "ModuleNotFoundError",
        "cannot find",
        "not found",
        "undefined",
    ]
    lines = output.split("\n")
    key_lines = []
    for line in lines:
        if any(kw in line for kw in keywords):
            key_lines.append(line)
    return "\n".join(key_lines[:max_lines])


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
