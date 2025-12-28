from soft_proposer import propose_soft_profile


# testsoftproposerpythonproject，写入文件内容
def test_soft_proposer_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\nLine2\n", encoding="utf-8")

    draft = propose_soft_profile(tmp_path, fingerprint="abc")

    assert draft["project_type"] == "python"
    assert "python -m pytest -q" in draft["build_and_test"]
    assert "pytest.ini" in draft["test_entry_files"]
    assert draft["readme_summary"]
