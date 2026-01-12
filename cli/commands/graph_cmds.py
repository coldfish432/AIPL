from __future__ import annotations

import json
from pathlib import Path

from cli.utils import envelope
from services.code_graph_service import CodeGraphService
from services.profile_service import compute_fingerprint


def cmd_code_graph_build(args, root: Path):
    code_graph_service = CodeGraphService(cache_root=root)
    workspace = Path(args.workspace)
    fingerprint = compute_fingerprint(workspace)
    graph = code_graph_service.build(workspace, fingerprint=fingerprint, watch=args.watch)
    graph_path = None
    if args.output:
        graph_path = Path(args.output)
        code_graph_service.save(graph, graph_path)
    data = {
        "workspace": str(workspace.resolve()),
        "fingerprint": fingerprint,
        "graph_path": str(graph_path) if graph_path else None,
        "graph": graph.to_dict(),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_code_graph_related(args, root: Path):
    code_graph_service = CodeGraphService(cache_root=root)
    workspace = Path(args.workspace)
    graph = None
    if args.graph:
        graph_path = Path(args.graph)
        if graph_path.exists():
            try:
                graph = code_graph_service.load(graph_path)
            except Exception:
                graph = None
    if not graph:
        fingerprint = compute_fingerprint(workspace)
        graph = code_graph_service.build(workspace, fingerprint=fingerprint)
    related = graph.related_files([args.file], max_hops=args.max_hops)
    data = {
        "file": args.file,
        "related_files": related,
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))
