from pathlib import Path

from services.code_graph_service import CodeGraphService


# test代码图buildsedges，写入文件内容，创建目录
def test_code_graph_builds_edges(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPL_CODE_GRAPH_CACHE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIPL_CODE_GRAPH_CACHE", "0")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.py").write_text("import b\n", encoding="utf-8")
    (workspace / "b.py").write_text("x = 1\n", encoding="utf-8")
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_a.py").write_text("import a\n", encoding="utf-8")

    service = CodeGraphService()
    graph = service.build(workspace)

    assert "a.py" in graph.nodes
    assert "b.py" in graph.nodes
    assert "tests/test_a.py" in graph.nodes
    assert "b.py" in graph.deps.get("a.py", set())
    assert "tests/test_a.py" in graph.tests_for_files(["a.py"])


# test代码图规范化路径，写入文件内容，创建目录
def test_code_graph_normalize_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPL_CODE_GRAPH_CACHE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIPL_CODE_GRAPH_CACHE", "0")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    file_path = workspace / "src" / "main.py"
    file_path.parent.mkdir()
    file_path.write_text("print('ok')\n", encoding="utf-8")

    service = CodeGraphService()
    graph = service.build(workspace)
    assert graph.normalize_path(file_path) == "src/main.py"
