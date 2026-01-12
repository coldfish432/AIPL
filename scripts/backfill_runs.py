#!/usr/bin/env python
"""
Backfill run metadata into the SQLite database.

Usage:
    python scripts/backfill_runs.py --root D:\\AIPL
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from config import resolve_db_path
from infra.io_utils import read_json
from services.controller.sqlite_mirror import ensure_sqlite_schema


def _resolve_plan_workspace(plan_dir: Path) -> str | None:
    cap_path = plan_dir / "capabilities.json"
    if cap_path.exists():
        cap = read_json(cap_path, default={})
        if isinstance(cap, dict):
            workspace = cap.get("workspace")
            if isinstance(workspace, str) and workspace.strip():
                return workspace

    plan_path = plan_dir / "plan.json"
    if plan_path.exists():
        plan_data = read_json(plan_path, default={})
        if isinstance(plan_data, dict):
            for key in ("workspace", "workspace_path", "workspace_main_root"):
                workspace = plan_data.get(key)
                if isinstance(workspace, str) and workspace.strip():
                    return workspace

    return None


def backfill_runs(root: Path, dry_run: bool = False) -> None:
    db_path = resolve_db_path(root)
    print(f"Database path: {db_path}")

    ws_root = root / "artifacts" / "workspaces"
    if not ws_root.exists():
        print("No workspaces directory found under artifacts/workspaces")
        return

    if dry_run:
        print("DRY RUN - no changes will be made")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        ensure_sqlite_schema(conn)

        count = 0
        errors = 0

        for ws_dir in sorted(ws_root.iterdir()):
            if not ws_dir.is_dir():
                continue

            plan_root = ws_dir / "executions"
            if not plan_root.exists():
                continue

            for plan_dir in sorted(plan_root.iterdir()):
                if not plan_dir.is_dir():
                    continue

                plan_id = plan_dir.name
                runs_dir = plan_dir / "runs"
                if not runs_dir.exists():
                    continue

                plan_workspace = _resolve_plan_workspace(plan_dir)

                for run_dir in sorted(runs_dir.iterdir()):
                    if not run_dir.is_dir():
                        continue

                    run_id = run_dir.name
                    meta_path = run_dir / "meta.json"
                    if not meta_path.exists():
                        print(f"  SKIP {plan_id}/{run_id}: missing meta.json")
                        continue

                    try:
                        meta = read_json(meta_path, default={})
                        status = meta.get("status", "unknown")
                        workspace = (
                            meta.get("workspace_main_root")
                            or meta.get("workspace")
                            or plan_workspace
                            or ""
                        )
                        now_ms = int(time.time() * 1000)

                        raw_json = json.dumps(
                            {
                                "ok": True,
                                "ts": int(time.time()),
                                "data": {
                                    "run_id": run_id,
                                    "plan_id": plan_id,
                                    "status": status,
                                    "workspace_main_root": workspace,
                                    "mode": meta.get("mode"),
                                },
                            },
                            ensure_ascii=False,
                        )

                        if not dry_run:
                            conn.execute(
                                """INSERT INTO runs(run_id, plan_id, status, workspace, updated_at, raw_json) 
                                   VALUES(?,?,?,?,?,?) 
                                   ON CONFLICT(run_id) DO UPDATE SET 
                                   plan_id=excluded.plan_id, 
                                   status=excluded.status, 
                                   workspace=excluded.workspace,
                                   updated_at=excluded.updated_at, 
                                   raw_json=excluded.raw_json""",
                                (run_id, plan_id, status, workspace, now_ms, raw_json),
                            )

                        count += 1
                        display_workspace = workspace if workspace else "N/A"
                        print(
                            f"  OK {plan_id}/{run_id} -> status={status}, workspace={display_workspace}"
                        )

                    except Exception as exc:
                        errors += 1
                        print(f"  ERROR {plan_id}/{run_id}: {exc}")

        if not dry_run:
            conn.commit()

        prefix = "DRY RUN - " if dry_run else ""
        print(f"\n{prefix}Total: {count} runs processed, {errors} errors")


def show_current_data(root: Path) -> None:
    db_path = resolve_db_path(root)
    if not db_path or not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    print(f"Database: {db_path}")
    print("-" * 80)
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            "SELECT run_id, plan_id, status, workspace FROM runs ORDER BY run_id DESC LIMIT 20"
        )
        rows = cursor.fetchall()
        if not rows:
            print("No runs in database")
            return

        print(f"{'run_id':<25} {'plan_id':<25} {'status':<15} {'workspace'}")
        print("-" * 80)
        for run_id, plan_id, status, workspace in rows:
            ws_display = (
                (workspace[:40] + "...") if workspace and len(workspace) > 40 else (workspace or "N/A")
            )
            print(
                f"{run_id:<25} {plan_id:<25} {status or 'N/A':<15} {ws_display}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill runs data to SQLite database")
    parser.add_argument("--root", required=True, help="AIPL root directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--show", action="store_true", help="Show current data in database")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root directory not found: {root}")
        sys.exit(1)

    print(f"Root: {root}\n")

    if args.show:
        show_current_data(root)
    else:
        backfill_runs(root, dry_run=args.dry_run)
