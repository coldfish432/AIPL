import json
from pathlib import Path

from detect_workspace import detect_workspace


# test工作区detectionviasubprocess，写入文件内容，执行外部命令
def test_workspace_detection_via_subprocess(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "package.json").write_text('{"scripts": {"test": "pytest -q", "build": "vite build"}}', encoding="utf-8")
    (workspace / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    data = detect_workspace(workspace)
    commands = [c["cmd"] for c in data["capabilities"]["commands"]]
    assert "npm run test" in commands
    assert "npm run build" in commands
