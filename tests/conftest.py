import json
import os
import queue
import socket
import threading
import time
import uuid
from pathlib import Path

import pytest

from services.verifier import CommandRunner, set_command_runner

REPO_ROOT = Path(__file__).resolve().parent.parent


# 自定义临时目录工厂，避免 pytest 内置 tmp_path 清理目录时触发权限错误
class SimpleTmpPathFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        base = basename.replace(os.sep, "_")
        name = f"{base}-{uuid.uuid4().hex}" if numbered else base
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def getbasetemp(self) -> Path:
        return self.root


@pytest.fixture()
def tmp_path():
    factory = SimpleTmpPathFactory(REPO_ROOT / ".tmp_custom")
    return factory.mktemp("tmp")


class FakeRunner(CommandRunner):
    # 初始化
    def __init__(self) -> None:
        self.results: list[dict] = []
        self.calls: list[dict] = []

    # queue结果
    def queue_result(self, result: dict) -> None:
        self.results.append(result)

    # 运行
    def run(self, cmd: str, cwd: Path, timeout: int) -> dict:
        self.calls.append({"cmd": cmd, "cwd": cwd, "timeout": timeout})
        if self.results:
            return self.results.pop(0)
        return {"executed": True, "timed_out": False, "returncode": 0, "stdout": "", "stderr": ""}


# fakerunner
@pytest.fixture()
def fake_runner():
    runner = FakeRunner()
    set_command_runner(runner)
    try:
        yield runner
    finally:
        set_command_runner(None)


# 待办任务，写入文件内容，创建目录
@pytest.fixture()
def backlog_task():
    created: list[Path] = []

    # 创建，写入文件内容，创建目录
    def _make(checks: list[dict], task_id: str | None = None, workspace: Path | None = None, status: str = "todo"):
        tid = task_id or f"test-{uuid.uuid4().hex}"
        data = {"tasks": [{"id": tid, "status": status, "checks": checks}]}
        if workspace:
            data["tasks"][0]["workspace"] = {"path": str(workspace)}
        path = REPO_ROOT / "backlog" / f"{tid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        created.append(path)
        return tid, path

    try:
        yield _make
    finally:
        for path in created:
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass


# temp工作区，写入文件内容，创建目录
@pytest.fixture()
def temp_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return workspace


class MockHttpServer:
    # 初始化
    def __init__(self) -> None:
        self._responses: "queue.Queue[tuple[int, str]]" = queue.Queue()
        self._server = None
        self._thread = None
        self.port = None

    # 启动
    def start(self) -> None:
        # serve
        def _serve(server):
            server.serve_forever(poll_interval=0.1)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        import socketserver

        responses = self._responses

        class _Handler(socketserver.BaseRequestHandler):
            # handle
            def handle(self) -> None:
                try:
                    status, body = responses.get_nowait()
                except queue.Empty:
                    status, body = 200, "ok"
                data = body.encode("utf-8")
                self.request.sendall(
                    b"HTTP/1.1 " + str(status).encode("ascii") + b" OK\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: " + str(len(data)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + data
                )
                self.request.close()

        self._server = socketserver.TCPServer(("127.0.0.1", self.port), _Handler)
        self._server.allow_reuse_address = True
        self._thread = threading.Thread(target=_serve, args=(self._server,), daemon=True)
        self._thread.start()

    # 停止
    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=1.0)

    # enqueue
    def enqueue(self, status: int, body: str) -> None:
        self._responses.put((status, body))

    # URL
    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


# mockHTTPserver
@pytest.fixture()
def mock_http_server():
    server = MockHttpServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


# 档案db
@pytest.fixture()
def profile_db(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setenv("AIPL_DB_PATH", str(db_path))
    return db_path


# 记录 pytest 输出，确保安静模式也包含 collected 行，并写入文件
_pytest_terminal_reporter = None
_pytest_collected_count = 0
_pytest_start_time = None


def pytest_configure(config):
    global _pytest_terminal_reporter, _pytest_start_time
    _pytest_terminal_reporter = config.pluginmanager.get_plugin("terminalreporter")
    _pytest_start_time = time.time()


def pytest_collection_finish(session):
    global _pytest_collected_count
    _pytest_collected_count = len(session.items)
    message = f"collected {_pytest_collected_count} items"
    if _pytest_terminal_reporter is not None:
        _pytest_terminal_reporter.write_line(message)
    else:
        print(message)


def pytest_sessionfinish(session, exitstatus):
    duration = time.time() - _pytest_start_time if _pytest_start_time is not None else None
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = reporter.stats if reporter else {}

    def _count(key: str) -> int:
        return len(stats.get(key, []))

    passed = _count("passed")
    failed = _count("failed") + _count("error")
    skipped = _count("skipped")
    xfailed = _count("xfailed")
    xpassed = _count("xpassed")
    deselected = _count("deselected")

    summary_parts = []
    if passed:
        summary_parts.append(f"{passed} passed")
    if failed:
        summary_parts.append(f"{failed} failed")
    if skipped:
        summary_parts.append(f"{skipped} skipped")
    if xfailed:
        summary_parts.append(f"{xfailed} xfailed")
    if xpassed:
        summary_parts.append(f"{xpassed} xpassed")
    if deselected:
        summary_parts.append(f"{deselected} deselected")
    if duration is not None:
        summary_parts.append(f"in {duration:.2f}s")

    lines = [f"collected {_pytest_collected_count} items"]
    if summary_parts:
        lines.append(", ".join(summary_parts))
    else:
        lines.append("no tests were run")

    output_path = REPO_ROOT / "src" / "pytest-output.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
