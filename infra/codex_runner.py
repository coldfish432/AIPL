import os
import selectors
import socket
import subprocess
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from shutil import which
from typing import Callable, Sequence


if os.name == "nt":
    try:
        # Trigger WSAStartup so selectors.select can run safely on Windows.
        init_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        init_sock.close()
    except Exception:
        pass


def normalize_cmd_path(cmd: str) -> str:
    raw = str(cmd)
    if os.name == "nt" and raw.startswith("\\\\?\\"):
        return raw[4:]
    return raw


def find_codex_bin() -> Path | None:
    explicit = os.environ.get("CODEX_BIN")
    if explicit:
        return Path(normalize_cmd_path(explicit))

    candidate = which("codex")
    if candidate:
        return Path(normalize_cmd_path(candidate))

    if os.name == "nt":
        for cand in ("codex.cmd", "codex.exe", "codex.bat"):
            path = which(cand)
            if path:
                return Path(normalize_cmd_path(path))
    return None


def decode_output(data: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class CodexIdleTimeout(Exception):
    """Codex idle timeout."""


class CodexHardTimeout(Exception):
    """Codex hard timeout."""


def run_codex_with_files(
    prompt: str,
    root_dir: Path,
    schema_path: Path,
    *,
    io_dir: Path | None = None,
    extra_args: Sequence[str] | None = None,
    sandbox: str = "workspace-write",
    work_dir: Path | None = None,
    startup_timeout: int = 300,  # 启动后5分钟内必须有输出
    idle_timeout: int = 600,     # 有输出后，10分钟无新输出则 timeout
    hard_timeout: int = 3600,    # 总超时1小时
    on_stderr: Callable[[str], None] | None = None,
    on_activity: Callable[[float], None] | None = None,
) -> str:
    """
    Execute Codex CLI with optional stderr/activity callbacks and timeout detection.
    """
    io_root = io_dir or (root_dir / ".tmp_custom" / "codex_io")
    io_root.mkdir(parents=True, exist_ok=True)
    prompt_path = io_root / "prompt.txt"
    output_path = io_root / "output.json"
    error_path = io_root / "error.log"
    prompt_path.write_text(prompt, encoding="utf-8")

    bin_path = find_codex_bin()
    cmd = [
        str(bin_path or "codex"),
        "exec",
        "--full-auto",
        "--sandbox",
        sandbox,
        "-C",
        str(work_dir or root_dir),
        "--skip-git-repo-check",
        "--output-schema",
        str(schema_path),
        "--color",
        "never",
    ]
    if extra_args:
        cmd.extend(extra_args)

    clean_env = os.environ.copy()
    clean_env["PYTHONUTF8"] = "1"
    clean_env["PYTHONIOENCODING"] = "utf-8"
    clean_env["CONDA_AUTO_ACTIVATE_BASE"] = "false"
    for key in ("CONDA_SHLVL", "CONDA_PROMPT_MODIFIER"):
        clean_env.pop(key, None)

    stderr_lines: list[str] = []
    stdout_content: list[str] = []
    last_activity: float | None = None  # 初始为 None，表示还没有任何输出
    activity_lock = threading.Lock()

    def update_activity(ts: float) -> None:
        nonlocal last_activity
        with activity_lock:
            last_activity = ts
        if on_activity:
            try:
                on_activity(ts)
            except Exception:
                pass

    def get_idle_seconds() -> float:
        with activity_lock:
            if last_activity is None:
                return 0.0  # 还没有任何输出，不算 idle
            return time.time() - last_activity

    use_selector = os.name != "nt"
    is_windows = not use_selector
    sel = None
    stderr_thread = None
    stdout_path = io_root / "codex_stdout.txt"
    stderr_path = io_root / "codex_stderr.txt"

    with prompt_path.open("r", encoding="utf-8") as stdin_file, ExitStack() as stack:
        stdout_target = subprocess.PIPE
        stderr_target = subprocess.PIPE
        if is_windows:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            stdout_handle = stack.enter_context(
                stdout_path.open("w", encoding="utf-8", errors="replace", buffering=1)
            )
            stderr_handle = stack.enter_context(
                stderr_path.open("w", encoding="utf-8", errors="replace", buffering=1)
            )
            stdout_target = stdout_handle
            stderr_target = stderr_handle

        proc = subprocess.Popen(
            cmd,
            stdin=stdin_file,
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=clean_env,
        )

        if use_selector:
            sel = selectors.DefaultSelector()
            sel.register(proc.stdout, selectors.EVENT_READ)
            sel.register(proc.stderr, selectors.EVENT_READ)
        else:
            last_stdout_size = 0

            def _handle_stderr_line(line: str) -> None:
                stripped = line.rstrip()
                stderr_lines.append(stripped)
                update_activity(time.time())
                if on_stderr:
                    try:
                        on_stderr(stripped)
                    except Exception:
                        pass

            def _tail_stderr_file() -> None:
                buffer = ""
                with stderr_path.open("r", encoding="utf-8", errors="replace") as fh:
                    while True:
                        chunk = fh.read()
                        if chunk:
                            buffer += chunk
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                _handle_stderr_line(line)
                        else:
                            if proc.poll() is not None:
                                if buffer:
                                    _handle_stderr_line(buffer)
                                    buffer = ""
                                break
                            time.sleep(0.1)
                    if buffer:
                        _handle_stderr_line(buffer)

            stderr_thread = threading.Thread(target=_tail_stderr_file, daemon=True)
            stderr_thread.start()

        try:
            start_time = time.time()

            while True:
                if proc.poll() is not None:
                    if use_selector and sel:
                        for key, _ in sel.select(timeout=0.1):
                            try:
                                remaining = key.fileobj.read()
                                if remaining:
                                    if key.fileobj is proc.stderr:
                                        for line in remaining.splitlines():
                                            stderr_lines.append(line)
                                            if on_stderr:
                                                try:
                                                    on_stderr(line)
                                                except Exception:
                                                    pass
                                    else:
                                        stdout_content.append(remaining)
                                        update_activity(time.time())
                            except Exception:
                                pass
                    break

                if not use_selector:
                    try:
                        current_size = stdout_path.stat().st_size
                    except OSError:
                        current_size = 0
                    if current_size != last_stdout_size:
                        last_stdout_size = current_size
                        update_activity(time.time())

                elapsed = time.time() - start_time
                if elapsed > hard_timeout:
                    proc.kill()
                    proc.wait()
                    raise CodexHardTimeout(f"Codex total timeout ({hard_timeout}s)")

                idle = get_idle_seconds()
                # 区分两种情况：
                # 1. 还没有任何输出（启动阶段）→ 检查 startup_timeout
                # 2. 已有输出后停止输出 → 检查 idle_timeout
                with activity_lock:
                    has_output = last_activity is not None
                
                if not has_output:
                    # 启动阶段：检查是否超过 startup_timeout
                    if elapsed > startup_timeout:
                        proc.kill()
                        proc.wait()
                        raise CodexIdleTimeout(
                            f"Codex startup timeout ({startup_timeout}s) - no output received"
                        )
                else:
                    # 已有输出：检查是否超过 idle_timeout
                    if idle > idle_timeout:
                        proc.kill()
                        proc.wait()
                        raise CodexIdleTimeout(
                            f"Codex idle timeout ({idle_timeout}s) - no output for {int(idle)}s"
                        )

                if use_selector and sel:
                    events = sel.select(timeout=1)
                    for key, _ in events:
                        line = key.fileobj.readline()
                        if not line:
                            continue

                        update_activity(time.time())

                        if key.fileobj is proc.stderr:
                            line = line.rstrip()
                            stderr_lines.append(line)
                            if on_stderr:
                                try:
                                    on_stderr(line)
                                except Exception:
                                    pass
                        else:
                            stdout_content.append(line)
        except (CodexIdleTimeout, CodexHardTimeout):
            raise
        except Exception as exc:
            proc.kill()
            proc.wait()
            raise RuntimeError(f"Codex execution failed: {exc}") from exc
        finally:
            if sel:
                sel.close()

    if stderr_lines:
        error_path.write_text("\n".join(stderr_lines), encoding="utf-8")

    if use_selector:
        stdout_text = "".join(stdout_content)
    else:
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    output_path.write_text(stdout_text, encoding="utf-8")

    if stderr_thread:
        stderr_thread.join(timeout=1)

    if proc.returncode != 0:
        err_text = "\n".join(stderr_lines) if stderr_lines else ""
        raise RuntimeError((err_text or stdout_text or f"codex exit code {proc.returncode}").strip())

    return stdout_text.strip()
