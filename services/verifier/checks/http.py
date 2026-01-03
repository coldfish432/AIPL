from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..config import HTTP_RETRIES, HTTP_SOFT_FAIL, HTTP_TIMEOUT
from ..registry import register_check
from ..utils import reason


def _json_contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if k not in actual or not _json_contains(actual[k], v):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            return False
        for idx, v in enumerate(expected):
            if not _json_contains(actual[idx], v):
                return False
        return True
    return actual == expected


def _http_request_with_retry(req: Request, data: bytes | None, timeout: int, retries: int):
    last_error = None
    for _ in range(max(retries, 1)):
        try:
            if data is None:
                with urlopen(req, timeout=timeout) as resp:
                    return resp.getcode(), resp.read().decode("utf-8", errors="replace"), None
            with urlopen(req, data=data, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8", errors="replace"), None
        except Exception as exc:
            last_error = exc
    return None, "", last_error


@register_check("http_check")
def handle_http_check(check: dict, run_dir, workspace, log_dir, idx):
    url = check.get("url", "")
    parsed = urlparse(url)
    allow_hosts = set(check.get("allow_hosts", []) or [])
    allow_hosts.update({"127.0.0.1", "localhost"})
    if parsed.scheme not in ("http", "https") or parsed.hostname not in allow_hosts:
        return False, reason("http_not_allowed", url=url, expected=f"host in {sorted(allow_hosts)}"), {"url": url, "executed": False}

    method = check.get("method", "GET")
    headers = check.get("headers", {}) or {}
    body = check.get("body")
    retry = int(check.get("retry", HTTP_RETRIES))
    timeout = int(check.get("timeout", HTTP_TIMEOUT))
    expected_status = int(check.get("expected_status", 200))

    req = Request(url, method=method)
    for key, value in headers.items():
        req.add_header(key, value)

    data = None
    if body is not None:
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        else:
            data = str(body).encode("utf-8")

    status, resp_body, error = _http_request_with_retry(req, data, timeout, retry)
    if error:
        if HTTP_SOFT_FAIL and parsed.hostname in allow_hosts:
            return True, None, {"url": url, "status": "skipped", "executed": False, "reason": str(error)}
        return False, reason("http_error", url=url, actual=str(error)), {"url": url, "status": "error", "executed": True}

    if status != expected_status:
        return False, reason("http_status_mismatch", url=url, expected=expected_status, actual=status), {"url": url, "status": status, "executed": True}

    contains = check.get("contains")
    if contains and contains not in resp_body:
        return False, reason("http_body_missing", url=url, expected=f"contains {contains!r}", actual=resp_body[:200]), {"url": url, "status": status, "executed": True}

    json_contains = check.get("json_contains")
    if json_contains is None:
        return True, None, {"url": url, "status": status, "executed": True}

    try:
        data_obj = json.loads(resp_body)
    except Exception as exc:
        return False, reason("http_json_invalid", url=url, actual=str(exc)), {"url": url, "status": status, "executed": True}

    ok = _json_contains(data_obj, json_contains)
    err = None if ok else reason("http_json_mismatch", url=url, expected=json_contains, actual=data_obj)
    return ok, err, {"url": url, "status": status, "executed": True}
