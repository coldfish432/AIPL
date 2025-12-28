from pathlib import Path

from services import profile_service


# test计算fingerprintchanges，写入文件内容
def test_compute_fingerprint_changes(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("pytest==1.0\n", encoding="utf-8")
    first = profile_service.compute_fingerprint(tmp_path)
    req.write_text("pytest==2.0\n", encoding="utf-8")
    second = profile_service.compute_fingerprint(tmp_path)
    assert first != second


# test档案lifecyclewithdb，写入文件内容，创建目录
def test_profile_lifecycle_with_db(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setenv("AIPL_DB_PATH", str(db_path))
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (workspace / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    profile = profile_service.ensure_profile(tmp_path, workspace)
    assert profile["created"] is True

    profile = profile_service.propose_soft(tmp_path, workspace, reason="test")
    assert profile.get("soft_draft") is not None

    profile = profile_service.approve_soft(tmp_path, workspace)
    assert profile.get("soft_approved") is not None
    assert int(profile.get("soft_version") or 0) >= 1

    profile = profile_service.reject_soft(tmp_path, workspace)
    assert profile.get("soft_draft") is None
