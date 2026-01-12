import os
import subprocess
from pathlib import Path
from shutil import which
from typing import Sequence


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


def run_codex_with_files(
    prompt: str,
    root_dir: Path,
    schema_path: Path,
    *,
    io_dir: Path | None = None,
    extra_args: Sequence[str] | None = None,
    sandbox: str = "workspace-write",
    work_dir: Path | None = None,
) -> str:
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

    with prompt_path.open("r", encoding="utf-8") as stdin, output_path.open("w", encoding="utf-8") as stdout, error_path.open("w", encoding="utf-8") as stderr:
        result = subprocess.run(
            cmd,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            shell=False,
        )

    if result.returncode != 0:
        err_text = decode_output(error_path.read_bytes()) if error_path.exists() else ""
        out_text = decode_output(output_path.read_bytes()) if output_path.exists() else ""
        raise RuntimeError((err_text or out_text or "codex failed").strip())

    return decode_output(output_path.read_bytes()).strip()
