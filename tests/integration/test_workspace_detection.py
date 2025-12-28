import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


# test工作区detectionviasubprocess，写入文件内容，执行外部命令
def test_workspace_detection_via_subprocess(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "package.json").write_text('{"scripts": {"test": "pytest -q", "build": "vite build"}}', encoding="utf-8")
    (workspace / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    result = subprocess.run(
        ["python", "detect_workspace.py", str(workspace)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    data = json.loads(result.stdout)
    commands = [c["cmd"] for c in data["capabilities"]["commands"]]
    assert "npm run test" in commands
    assert "npm run build" in commands
