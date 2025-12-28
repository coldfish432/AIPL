import json
from pathlib import Path

from detect_workspace import detect_workspace


# 写入JSON，写入文件内容，序列化JSON
def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# testdiscoverypackageJSON
def test_discovery_package_json(tmp_path):
    pkg = {
        "scripts": {
            "test": "pytest -q",
            "build": "vite build",
            "lint": "eslint .",
            "test:unit": "pytest -q",
        }
    }
    _write_json(tmp_path / "package.json", pkg)

    info = detect_workspace(tmp_path)
    commands = [c["cmd"] for c in info["capabilities"]["commands"]]
    assert "npm run test" in commands
    assert "npm run test:unit" in commands
    assert "npm run build" in commands
    assert "npm run lint" in commands


# testdiscoverymaven，写入文件内容
def test_discovery_maven(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")

    info = detect_workspace(tmp_path)
    commands = [c["cmd"] for c in info["capabilities"]["commands"]]
    assert "mvn -q test" in commands
    assert "mvn -q -DskipTests package" in commands


# testdiscoverypytest，写入文件内容
def test_discovery_pytest(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    info = detect_workspace(tmp_path)
    commands = [c["cmd"] for c in info["capabilities"]["commands"]]
    assert "python -m pytest -q" in commands
