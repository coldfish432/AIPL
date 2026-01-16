from __future__ import annotations

import json
import os
import re
import time
import hashlib
import threading
from collections import deque
from pathlib import Path
from typing import Any

from .co_change import CoChangeCollector, CoChangeLearner


MAX_FILE_BYTES = 512 * 1024
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "outputs",
    "target",
}

LANG_BY_EXT = {
    ".py": "python",
    ".java": "java",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "js",
    ".jsx": "js",
}

JS_TS_EXTS = [".ts", ".tsx", ".js", ".jsx"]


# envbool
def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# 规范化rel路径
def _normalize_rel_path(workspace_root: Path, path: str | Path) -> str | None:
    if isinstance(path, Path):
        candidate = path
    else:
        candidate = Path(path)
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(workspace_root.resolve())
        except Exception:
            return None
        return rel.as_posix().lstrip("./")
    rel = Path(str(candidate).replace("\\", "/"))
    if rel.is_absolute():
        return None
    if any(part == ".." for part in rel.parts):
        return None
    return rel.as_posix().lstrip("./")


class CodeGraph:
    # 初始化
    def __init__(self, workspace_root: Path, fingerprint: str | None = None):
        self.workspace_root = workspace_root.resolve()
        self.fingerprint = fingerprint
        self.nodes: dict[str, dict] = {}
        self.deps: dict[str, set[str]] = {}
        self.rdeps: dict[str, set[str]] = {}
        self._edges: set[tuple[str, str, str]] = set()

    # 构建
    @classmethod
    def build(cls, workspace_root: Path, fingerprint: str | None = None) -> "CodeGraph":
        graph = cls(workspace_root, fingerprint=fingerprint)
        graph._build()
        return graph

    # 加载，解析JSON，读取文件内容
    @classmethod
    def load(cls, path: Path) -> "CodeGraph":
        data = json.loads(path.read_text(encoding="utf-8"))
        workspace_root = Path(data.get("workspace_root") or ".")
        graph = cls(workspace_root, fingerprint=data.get("fingerprint"))
        nodes = data.get("nodes", [])
        for node in nodes:
            node_path = node.get("path")
            if not node_path:
                continue
            graph.nodes[node_path] = node
        deps = data.get("deps", {}) or {}
        for src, items in deps.items():
            graph.deps[src] = set(items or [])
        rdeps = data.get("rdeps", {}) or {}
        for dst, items in rdeps.items():
            graph.rdeps[dst] = set(items or [])
        edges = data.get("edges", []) or []
        if graph.nodes and edges:
            id_to_path = {node.get("id"): node.get("path") for node in nodes if node.get("id") is not None}
            for edge in edges:
                src = id_to_path.get(edge.get("from"))
                dst = id_to_path.get(edge.get("to"))
                etype = edge.get("edge_type") or "imports"
                if src and dst:
                    graph._edges.add((src, dst, etype))
        return graph

    # 保存，写入文件内容，创建目录
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # todict
    def to_dict(self) -> dict:
        node_paths = sorted(self.nodes.keys())
        nodes = []
        path_to_id: dict[str, int] = {}
        for idx, path in enumerate(node_paths, start=1):
            meta = dict(self.nodes[path])
            meta["id"] = idx
            meta["path"] = path
            nodes.append(meta)
            path_to_id[path] = idx
        edges = []
        for src, dst, etype in sorted(self._edges):
            src_id = path_to_id.get(src)
            dst_id = path_to_id.get(dst)
            if not src_id or not dst_id:
                continue
            edges.append({"from": src_id, "to": dst_id, "edge_type": etype})
        deps = {k: sorted(v) for k, v in sorted(self.deps.items())}
        rdeps = {k: sorted(v) for k, v in sorted(self.rdeps.items())}
        return {
            "workspace_root": str(self.workspace_root),
            "generated_at": int(time.time()),
            "fingerprint": self.fingerprint,
            "nodes": nodes,
            "edges": edges,
            "deps": deps,
            "rdeps": rdeps,
        }

    # 规范化路径
    def normalize_path(self, path: str | Path) -> str | None:
        return _normalize_rel_path(self.workspace_root, path)

    # relatedfiles
    def related_files(self, paths: list[str], max_hops: int = 2) -> list[str]:
        if max_hops < 0:
            return []
        seeds = []
        for p in paths or []:
            norm = self.normalize_path(p)
            if norm and norm in self.nodes:
                seeds.append(norm)
        if not seeds:
            return []
        visited = set(seeds)
        queue = deque((p, 0) for p in seeds)
        while queue:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue
            neighbors = set()
            neighbors.update(self.deps.get(current, set()))
            neighbors.update(self.rdeps.get(current, set()))
            for nxt in neighbors:
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append((nxt, depth + 1))
        return sorted(visited)

    # testsforfiles
    def tests_for_files(self, paths: list[str]) -> list[str]:
        test_files = [p for p in self.nodes if _is_test_file(p)]
        if not test_files:
            return []
        test_names = {Path(p).name: p for p in test_files}
        matches: set[str] = set()
        for raw in paths or []:
            norm = self.normalize_path(raw)
            if not norm:
                continue
            if _is_test_file(norm):
                matches.add(norm)
                continue
            base = Path(norm).stem
            ext = Path(norm).suffix
            if ext == ".py":
                candidates = [f"test_{base}.py", f"{base}_test.py"]
            elif ext == ".java":
                candidates = [f"{base}Test.java", f"Test{base}.java"]
            elif ext in JS_TS_EXTS:
                candidates = [
                    f"{base}.test{ext}",
                    f"{base}.spec{ext}",
                ]
            else:
                candidates = []
            for name in candidates:
                hit = test_names.get(name)
                if hit:
                    matches.add(hit)
        return sorted(matches)

    # 构建
    def _build(self) -> None:
        files = self._scan_files()
        java_class_map: dict[str, str] = {}
        for rel_path, lang, text in files:
            self._ensure_node(rel_path, lang)
            if lang == "java":
                pkg = _parse_java_package(text)
                class_name = Path(rel_path).stem
                full = f"{pkg}.{class_name}" if pkg else class_name
                java_class_map[full] = rel_path
        for rel_path, lang, text in files:
            if lang == "python":
                imports = _parse_python_imports(text)
                for entry in imports:
                    for target in _resolve_python_import(self.workspace_root, rel_path, entry):
                        self._add_edge(rel_path, target, "imports")
            elif lang == "java":
                for imp in _parse_java_imports(text):
                    if imp.endswith(".*"):
                        continue
                    target = java_class_map.get(imp)
                    if target:
                        self._add_edge(rel_path, target, "imports")
            elif lang in ("ts", "js"):
                for spec in _parse_js_imports(text):
                    for target in _resolve_js_import(self.workspace_root, rel_path, spec):
                        self._add_edge(rel_path, target, "imports")
        self._finalize_deps()

    # scanfiles，读取文件内容
    def _scan_files(self) -> list[tuple[str, str, str]]:
        results: list[tuple[str, str, str]] = []
        for root, dirs, files in os.walk(self.workspace_root):
            rel_dir = _normalize_rel_path(self.workspace_root, root)
            if rel_dir:
                parts = set(rel_dir.split("/"))
                if parts & DEFAULT_EXCLUDE_DIRS:
                    dirs[:] = []
                    continue
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]
            for name in files:
                ext = Path(name).suffix.lower()
                lang = LANG_BY_EXT.get(ext)
                if not lang:
                    continue
                file_path = Path(root) / name
                try:
                    if file_path.stat().st_size > MAX_FILE_BYTES:
                        continue
                except Exception:
                    continue
                rel_path = _normalize_rel_path(self.workspace_root, file_path)
                if not rel_path:
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                results.append((rel_path, lang, text))
        return results

    # 确保node
    def _ensure_node(self, rel_path: str, lang: str) -> None:
        if rel_path in self.nodes:
            return
        self.nodes[rel_path] = {"type": "file", "lang": lang}

    # 添加edge
    def _add_edge(self, src: str, dst: str, edge_type: str) -> None:
        if src == dst:
            return
        if src not in self.nodes or dst not in self.nodes:
            return
        self.deps.setdefault(src, set()).add(dst)
        self._edges.add((src, dst, edge_type))

    # finalizedeps
    def _finalize_deps(self) -> None:
        for src, targets in self.deps.items():
            for dst in targets:
                self.rdeps.setdefault(dst, set()).add(src)


# 解析pythonimports
def _parse_python_imports(text: str) -> list[dict]:
    imports = []
    try:
        import ast

        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "level": 0, "names": []})
            elif isinstance(node, ast.ImportFrom):
                names = [alias.name for alias in node.names]
                imports.append({"module": node.module, "level": node.level, "names": names})
        return imports
    except Exception:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("import "):
            mod = line.replace("import", "", 1).strip().split(" as ")[0]
            imports.append({"module": mod.strip(), "level": 0, "names": []})
        elif line.startswith("from "):
            m = re.match(r"from\s+([A-Za-z0-9_\.]+)\s+import\s+(.+)", line)
            if m:
                module = m.group(1)
                names = [n.strip().split(" as ")[0] for n in m.group(2).split(",")]
                imports.append({"module": module, "level": 0, "names": names})
    return imports


# pythonsearchroots，检查路径是否存在
def _python_search_roots(workspace_root: Path) -> list[Path]:
    roots = [workspace_root]
    src = workspace_root / "src"
    if src.exists():
        roots.append(src)
    return roots


# 解析pythonimport，检查路径是否存在
def _resolve_python_import(workspace_root: Path, rel_path: str, entry: dict) -> list[str]:
    module = entry.get("module")
    level = int(entry.get("level") or 0)
    names = entry.get("names") or []
    rel_dir = Path(rel_path).parent
    roots = _python_search_roots(workspace_root)
    candidates: list[Path] = []
    if level > 0:
        base = rel_dir
        for _ in range(level):
            base = base.parent
        if module:
            base = base / module.replace(".", "/")
        candidates.extend(_expand_python_candidates(base))
        if not module:
            for name in names:
                candidates.extend(_expand_python_candidates(base / name))
    else:
        if module:
            mod_path = Path(module.replace(".", "/"))
            for root in roots:
                candidates.extend(_expand_python_candidates(root / mod_path))
        if module and names:
            mod_path = Path(module.replace(".", "/"))
            for root in roots:
                for name in names:
                    candidates.extend(_expand_python_candidates(root / mod_path / name))
    resolved = []
    for cand in candidates:
        abs_path = cand if cand.is_absolute() else (workspace_root / cand)
        try:
            abs_path = abs_path.resolve()
        except Exception:
            continue
        if not abs_path.exists() or not abs_path.is_file():
            continue
        rel = _normalize_rel_path(workspace_root, abs_path)
        if rel:
            resolved.append(rel)
    return list(dict.fromkeys(resolved))


# expandpythoncandidates
def _expand_python_candidates(base: Path) -> list[Path]:
    candidates = []
    if base.suffix == ".py":
        candidates.append(base)
    else:
        candidates.append(base.with_suffix(".py"))
        candidates.append(base / "__init__.py")
    return candidates


# 解析javapackage
def _parse_java_package(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("package "):
            m = re.match(r"package\s+([A-Za-z0-9_.]+)\s*;", line)
            if m:
                return m.group(1)
    return ""


# 解析javaimports
def _parse_java_imports(text: str) -> list[str]:
    imports = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("import "):
            continue
        m = re.match(r"import\s+(?:static\s+)?([A-Za-z0-9_.\*]+)\s*;", line)
        if m:
            imports.append(m.group(1))
    return imports


# 解析jsimports
def _parse_js_imports(text: str) -> list[str]:
    imports = []
    for m in re.finditer(r"from\s+['\"]([^'\"]+)['\"]", text):
        imports.append(m.group(1))
    for m in re.finditer(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
        imports.append(m.group(1))
    return list(dict.fromkeys(imports))


# 解析jsimport，检查路径是否存在
def _resolve_js_import(workspace_root: Path, rel_path: str, spec: str) -> list[str]:
    spec = spec.strip()
    if not spec:
        return []
    if not (spec.startswith(".") or spec.startswith("/")):
        return []
    base_dir = Path(rel_path).parent
    if spec.startswith("/"):
        base = workspace_root / spec.lstrip("/")
    else:
        base = (workspace_root / base_dir / spec).resolve()
    candidates = []
    if base.suffix:
        candidates.append(base)
    else:
        for ext in JS_TS_EXTS + [".d.ts"]:
            candidates.append(base.with_suffix(ext))
            candidates.append(base / f"index{ext}")
    resolved = []
    for cand in candidates:
        abs_path = cand if cand.is_absolute() else (workspace_root / cand)
        try:
            abs_path = abs_path.resolve()
        except Exception:
            continue
        if not abs_path.exists() or not abs_path.is_file():
            continue
        rel = _normalize_rel_path(workspace_root, abs_path)
        if rel:
            resolved.append(rel)
    return list(dict.fromkeys(resolved))


# 判断是否test文件
def _is_test_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    if "/tests/" in f"/{rel_path}/" or "/test/" in f"/{rel_path}/" or "/__tests__/" in f"/{rel_path}/":
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    if name.endswith("Test.java") or (name.startswith("Test") and name.endswith(".java")):
        return True
    if re.search(r"\.(test|spec)\.(ts|tsx|js|jsx)$", name):
        return True
    return False


# 加载缓存，解析JSON，检查路径是否存在
def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"files": {}}
    if not isinstance(data, dict):
        return {"files": {}}
    data.setdefault("files", {})
    return data


# 保存缓存，写入文件内容，创建目录
def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# 解析文件元数据
def _parse_file_meta(workspace_root: Path, rel_path: str, lang: str, text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"lang": lang}
    if lang == "python":
        meta["imports"] = _parse_python_imports(text)
    elif lang == "java":
        meta["java_package"] = _parse_java_package(text)
        meta["class_name"] = Path(rel_path).stem
        meta["imports"] = _parse_java_imports(text)
    elif lang in ("ts", "js"):
        meta["imports"] = _parse_js_imports(text)
    else:
        meta["imports"] = []
    return meta


# scanfilesincremental，读取文件内容
def _scan_files_incremental(workspace_root: Path, cache: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    files_cache: dict[str, Any] = cache.get("files", {}) or {}
    seen: set[str] = set()
    for root, dirs, files in os.walk(workspace_root):
        rel_dir = _normalize_rel_path(workspace_root, root)
        if rel_dir:
            parts = set(rel_dir.split("/"))
            if parts & DEFAULT_EXCLUDE_DIRS:
                dirs[:] = []
                continue
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]
        for name in files:
            ext = Path(name).suffix.lower()
            lang = LANG_BY_EXT.get(ext)
            if not lang:
                continue
            file_path = Path(root) / name
            try:
                stat = file_path.stat()
            except Exception:
                continue
            if stat.st_size > MAX_FILE_BYTES:
                continue
            rel_path = _normalize_rel_path(workspace_root, file_path)
            if not rel_path:
                continue
            seen.add(rel_path)
            cached = files_cache.get(rel_path)
            if cached and cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size and cached.get("lang") == lang:
                meta = dict(cached)
            else:
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                meta = _parse_file_meta(workspace_root, rel_path, lang, text)
                meta["mtime"] = stat.st_mtime
                meta["size"] = stat.st_size
            meta["path"] = rel_path
            files_cache[rel_path] = {k: v for k, v in meta.items() if k != "path"}
            results.append(meta)
    for rel_path in list(files_cache.keys()):
        if rel_path not in seen:
            files_cache.pop(rel_path, None)
    cache["files"] = files_cache
    return results, cache


# 构建from元数据
def _build_from_meta(workspace_root: Path, fingerprint: str | None, files_meta: list[dict[str, Any]]) -> CodeGraph:
    graph = CodeGraph(workspace_root, fingerprint=fingerprint)
    java_class_map: dict[str, str] = {}
    for entry in files_meta:
        rel_path = entry["path"]
        lang = entry["lang"]
        graph._ensure_node(rel_path, lang)
        if lang == "java":
            pkg = entry.get("java_package") or ""
            class_name = entry.get("class_name") or Path(rel_path).stem
            full = f"{pkg}.{class_name}" if pkg else class_name
            java_class_map[full] = rel_path
    for entry in files_meta:
        rel_path = entry["path"]
        lang = entry["lang"]
        imports = entry.get("imports") or []
        if lang == "python":
            for imp in imports:
                for target in _resolve_python_import(workspace_root, rel_path, imp):
                    graph._add_edge(rel_path, target, "imports")
        elif lang == "java":
            for imp in imports:
                if imp.endswith(".*"):
                    continue
                target = java_class_map.get(imp)
                if target:
                    graph._add_edge(rel_path, target, "imports")
        elif lang in ("ts", "js"):
            for spec in imports:
                for target in _resolve_js_import(workspace_root, rel_path, spec):
                    graph._add_edge(rel_path, target, "imports")
    graph._finalize_deps()
    return graph


# refresh缓存
def _refresh_cache(workspace_root: Path, fingerprint: str | None, cache_path: Path) -> None:
    cache = _load_cache(cache_path)
    _, cache = _scan_files_incremental(workspace_root, cache)
    cache["workspace_root"] = str(workspace_root)
    cache["fingerprint"] = fingerprint
    cache["generated_at"] = int(time.time())
    _save_cache(cache_path, cache)


_WATCHERS: dict[str, Any] = {}


# 启动watch
def _start_watch(workspace_root: Path, fingerprint: str | None, cache_path: Path) -> None:
    key = str(cache_path)
    if key in _WATCHERS:
        return
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        print("[GRAPH] watchdog not available; skip watch")
        return

    class _Handler(FileSystemEventHandler):
        # 初始化
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._last = 0.0

        # onany事件
        def on_any_event(self, event) -> None:
            now = time.time()
            with self._lock:
                if now - self._last < 0.5:
                    return
                self._last = now
            try:
                _refresh_cache(workspace_root, fingerprint, cache_path)
            except Exception:
                return

    observer = Observer()
    handler = _Handler()
    observer.schedule(handler, str(workspace_root), recursive=True)
    observer.daemon = True
    observer.start()
    _WATCHERS[key] = observer


class CodeGraphService:
    def __init__(self, cache_root: Path | None = None) -> None:
        self._cache_root = cache_root
        self._workspace_components: dict[str, tuple[CoChangeCollector, CoChangeLearner]] = {}

    def _resolve_cache_root(self) -> Path:
        if self._cache_root is not None:
            return self._cache_root
        root = os.getenv("AIPL_CODE_GRAPH_CACHE_ROOT")
        if root:
            return Path(root)
        return Path.cwd()

    def _get_cache_path(self, workspace_root: Path, fingerprint: str | None) -> Path:
        cache_root = self._resolve_cache_root() / "artifacts"
        cache_root.mkdir(parents=True, exist_ok=True)
        key = fingerprint or hashlib.sha256(str(workspace_root).encode("utf-8")).hexdigest()
        return cache_root / f"code-graph-cache-{key}.json"

    def build(self, workspace_root: Path, fingerprint: str | None = None, *, watch: bool = False) -> CodeGraph:
        use_cache = os.getenv("AIPL_CODE_GRAPH_CACHE", "1") != "0"
        watch = watch or _env_bool("AIPL_CODE_GRAPH_WATCH", False)
        if not use_cache:
            return CodeGraph.build(workspace_root, fingerprint=fingerprint)
        cache_path = self._get_cache_path(workspace_root, fingerprint)
        cache = _load_cache(cache_path)
        files_meta, cache = _scan_files_incremental(workspace_root, cache)
        cache["workspace_root"] = str(workspace_root)
        cache["fingerprint"] = fingerprint
        cache["generated_at"] = int(time.time())
        _save_cache(cache_path, cache)
        if watch:
            _start_watch(workspace_root, fingerprint, cache_path)
        return _build_from_meta(workspace_root, fingerprint, files_meta)

    def load(self, path: Path) -> CodeGraph:
        return CodeGraph.load(path)

    def save(self, graph: CodeGraph, path: Path) -> None:
        graph.save(path)

    def _workspace_key(self, workspace_path: Path) -> str:
        return str(workspace_path.resolve())

    def _get_workspace_components(self, workspace_path: Path) -> tuple[CoChangeCollector, CoChangeLearner]:
        key = self._workspace_key(workspace_path)
        components = self._workspace_components.get(key)
        if components:
            return components
        collector = CoChangeCollector(key)
        learner = CoChangeLearner(workspace_path / "learned" / "co_changes.json")
        self._workspace_components[key] = (collector, learner)
        return collector, learner

    def get_enhanced_graph(self, workspace_path: Path, fingerprint: str | None = None) -> CodeGraph:
        graph = self.build(workspace_path, fingerprint=fingerprint)
        _, learner = self._get_workspace_components(workspace_path)
        learner.load()
        graph.co_change_edges = learner.get_co_change_edges(min_confidence=0.3)
        return graph

    def get_related_files(
        self,
        workspace_path: Path,
        seed_paths: list[str],
        include_co_changes: bool = True,
        min_confidence: float = 0.5,
        max_results: int = 20,
    ) -> list[dict]:
        results: list[dict] = []
        graph = self.build(workspace_path)
        seen: set[str] = set()
        static_seeds: list[str] = []
        for seed in seed_paths or []:
            norm = graph.normalize_path(seed)
            if norm:
                static_seeds.append(norm)
        for seed in static_seeds:
            for dep in self._get_static_deps(graph, seed):
                if dep in seen:
                    continue
                seen.add(dep)
                results.append({"file": dep, "relation": "imports", "confidence": 1.0})
        if include_co_changes:
            _, learner = self._get_workspace_components(workspace_path)
            learner.load()
            for seed in static_seeds:
                for file_path, confidence in learner.query_co_changes(seed, min_confidence=min_confidence):
                    if file_path in seen:
                        continue
                    seen.add(file_path)
                    results.append({"file": file_path, "relation": "co_change", "confidence": confidence})
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:max_results]

    def suggest_missing_files(
        self,
        workspace_path: Path,
        modified_files: list[str],
        min_confidence: float = 0.7,
    ) -> list[dict]:
        suggestions: list[dict] = []
        _, learner = self._get_workspace_components(workspace_path)
        learner.load()
        modified_set = set(modified_files or [])
        for file_path in modified_files or []:
            for related_file, confidence in learner.query_co_changes(file_path, min_confidence=min_confidence):
                if related_file in modified_set:
                    continue
                suggestions.append({
                    "file": related_file,
                    "confidence": confidence,
                    "reason": f"Often modified together with {Path(file_path).name}",
                    "source": "co_change",
                    "triggered_by": file_path,
                })
        seen: dict[str, dict] = {}
        for suggestion in suggestions:
            key = suggestion["file"]
            if key not in seen or seen[key]["confidence"] < suggestion["confidence"]:
                seen[key] = suggestion
        return sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)

    def record_change_set(
        self,
        workspace_path: Path,
        run_id: str,
        task_id: str,
        modified_files: list[str],
        success: bool,
        task_type: str = "",
    ) -> None:
        collector, _ = self._get_workspace_components(workspace_path)
        collector.collect_from_run(run_id, task_id, modified_files, success, task_type=task_type)

    def learn_from_execution(self, workspace_path: Path) -> list[CoChangePattern]:
        collector, learner = self._get_workspace_components(workspace_path)
        change_sets = collector.get_change_sets()
        if not change_sets:
            return []
        learner.load()
        new_patterns = learner.learn_from_change_sets(change_sets)
        learner.save()
        collector.clear()
        return new_patterns

    def _build_static_graph(self, workspace_path: Path) -> CodeGraph:
        return self.build(workspace_path)

    def _get_static_deps(self, graph: CodeGraph, normalized_seed: str) -> list[str]:
        return sorted(graph.deps.get(normalized_seed, []))


__all__ = ["CodeGraph", "CodeGraphService"]
