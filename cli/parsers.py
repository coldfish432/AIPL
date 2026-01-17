from __future__ import annotations

import argparse

from cli.commands import (
    assistant_cmds,
    graph_cmds,
    pack_cmds,
    profile_cmds,
    query_cmds,
    review_cmds,
    run_cmds,
    workspace_cmds,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIPL Engine CLI")
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("--db-path", help="SQLite database path (passed from Java)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--task", required=True)
    p_plan.add_argument("--plan-id")
    p_plan.add_argument("--workspace")
    p_plan.set_defaults(func=run_cmds.cmd_plan)

    p_run = sub.add_parser("run")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--plan-id")
    p_run.add_argument("--workspace")
    p_run.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"])
    p_run.set_defaults(func=run_cmds.cmd_run)

    p_run_plan = sub.add_parser("run-plan")
    p_run_plan.add_argument("--plan-id", required=True)
    p_run_plan.add_argument("--workspace")
    p_run_plan.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"])
    p_run_plan.set_defaults(func=run_cmds.cmd_run_plan)

    p_retry = sub.add_parser("retry")
    p_retry.add_argument("--plan-id")
    p_retry.add_argument("--run-id", required=True)
    p_retry.add_argument("--force", action="store_true")
    p_retry.add_argument("--retry-deps", action="store_true")
    p_retry.add_argument("--retry-id-suffix")
    p_retry.add_argument("--reuse-task-id", action="store_true")
    p_retry.set_defaults(func=run_cmds.cmd_retry)

    p_chat = sub.add_parser("assistant-chat")
    p_chat.add_argument("--messages-file", required=True)
    p_chat.add_argument("--workspace", help="workspace path (Codex will run here)")
    p_chat.set_defaults(func=assistant_cmds.cmd_assistant_chat)

    p_chat_stream = sub.add_parser("assistant-chat-stream")
    p_chat_stream.add_argument("--messages-file", required=True)
    p_chat_stream.add_argument("--workspace", help="workspace path (Codex will run here)")
    p_chat_stream.set_defaults(func=assistant_cmds.cmd_assistant_chat_stream)

    p_tree = sub.add_parser("workspace-tree")
    p_tree.add_argument("--workspace", required=True)
    p_tree.add_argument("--depth", type=int, default=3)
    p_tree.set_defaults(func=workspace_cmds.cmd_workspace_tree)

    p_read = sub.add_parser("workspace-read")
    p_read.add_argument("--workspace", required=True)
    p_read.add_argument("--path", required=True)
    p_read.set_defaults(func=workspace_cmds.cmd_workspace_read)

    p_status = sub.add_parser("status")
    p_status.add_argument("--plan-id")
    p_status.add_argument("--run-id")
    p_status.set_defaults(func=run_cmds.cmd_status)

    p_events = sub.add_parser("events")
    p_events.add_argument("--plan-id")
    p_events.add_argument("--run-id")
    p_events.add_argument("--cursor", type=int, default=0)
    p_events.add_argument("--limit", type=int, default=200)
    p_events.set_defaults(func=run_cmds.cmd_events)

    p_art = sub.add_parser("artifacts")
    p_art.add_argument("--plan-id")
    p_art.add_argument("--run-id")
    p_art.set_defaults(func=query_cmds.cmd_artifacts)

    p_dashboard = sub.add_parser("dashboard-stats")
    p_dashboard.add_argument("--workspace")
    p_dashboard.set_defaults(func=query_cmds.cmd_dashboard_stats)

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("--plan-id")
    p_cancel.add_argument("--run-id")
    p_cancel.set_defaults(func=review_cmds.cmd_cancel)

    p_pause = sub.add_parser("pause")
    p_pause.add_argument("--plan-id")
    p_pause.add_argument("--run-id")
    p_pause.set_defaults(func=review_cmds.cmd_pause)

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--plan-id")
    p_resume.add_argument("--run-id")
    p_resume.set_defaults(func=review_cmds.cmd_resume)

    p_cancel_plan = sub.add_parser("cancel-plan-runs")
    p_cancel_plan.add_argument("--plan-id", required=True)
    p_cancel_plan.set_defaults(func=review_cmds.cmd_cancel_plan_runs)

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--plan-id")
    p_apply.add_argument("--run-id")
    p_apply.set_defaults(func=review_cmds.cmd_apply)

    p_discard = sub.add_parser("discard")
    p_discard.add_argument("--plan-id")
    p_discard.add_argument("--run-id")
    p_discard.set_defaults(func=review_cmds.cmd_discard)

    p_rework = sub.add_parser("rework")
    p_rework.add_argument("--plan-id")
    p_rework.add_argument("--run-id")
    p_rework.add_argument("--step-id")
    p_rework.add_argument("--feedback")
    p_rework.add_argument("--scope")
    p_rework.set_defaults(func=review_cmds.cmd_rework)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--action", required=True, choices=["get", "update"])
    p_profile.add_argument("--workspace", required=True)
    p_profile.add_argument("--payload")
    p_profile.set_defaults(func=profile_cmds.cmd_profile)

    p_lang = sub.add_parser("language-packs")
    p_lang.add_argument("--action", required=True, choices=["list", "get", "import", "export", "export-merged", "learned-export", "delete", "update", "learned-clear"])
    p_lang.add_argument("--pack-id")
    p_lang.add_argument("--payload")
    p_lang.add_argument("--name")
    p_lang.add_argument("--description")
    p_lang.add_argument("--enabled", type=int)
    p_lang.add_argument("--workspace")
    p_lang.set_defaults(func=pack_cmds.cmd_language_packs)

    p_mem = sub.add_parser("memory")
    p_mem.add_argument("--workspace-id")
    p_mem.add_argument("--workspace")
    p_mem.set_defaults(func=pack_cmds.cmd_memory)

    p_exp = sub.add_parser("experience-packs")
    p_exp.add_argument("--action", required=True, choices=["list", "get", "import", "import-workspace", "export", "delete", "update"])
    p_exp.add_argument("--workspace-id")
    p_exp.add_argument("--workspace")
    p_exp.add_argument("--pack-id")
    p_exp.add_argument("--payload")
    p_exp.add_argument("--name")
    p_exp.add_argument("--description")
    p_exp.add_argument("--enabled", type=int)
    p_exp.add_argument("--from-workspace-id")
    p_exp.add_argument("--include-rules", action="store_true")
    p_exp.add_argument("--include-checks", action="store_true")
    p_exp.add_argument("--include-lessons", action="store_true")
    p_exp.add_argument("--include-patterns", action="store_true")
    p_exp.set_defaults(func=pack_cmds.cmd_experience_packs)

    p_rules = sub.add_parser("rules")
    p_rules.add_argument("--action", required=True, choices=["add", "delete"])
    p_rules.add_argument("--workspace-id")
    p_rules.add_argument("--workspace")
    p_rules.add_argument("--rule-id")
    p_rules.add_argument("--content")
    p_rules.add_argument("--scope")
    p_rules.add_argument("--category")
    p_rules.set_defaults(func=pack_cmds.cmd_rules)

    p_checks = sub.add_parser("checks")
    p_checks.add_argument("--action", required=True, choices=["add", "delete"])
    p_checks.add_argument("--workspace-id")
    p_checks.add_argument("--workspace")
    p_checks.add_argument("--check-id")
    p_checks.add_argument("--payload")
    p_checks.add_argument("--scope")
    p_checks.set_defaults(func=pack_cmds.cmd_checks)

    p_lessons = sub.add_parser("lessons")
    p_lessons.add_argument("--action", required=True, choices=["delete", "clear"])
    p_lessons.add_argument("--workspace-id")
    p_lessons.add_argument("--workspace")
    p_lessons.add_argument("--lesson-id")
    p_lessons.set_defaults(func=pack_cmds.cmd_lessons)

    p_graph = sub.add_parser("code-graph")
    graph_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)

    p_graph_build = graph_sub.add_parser("build")
    p_graph_build.add_argument("--workspace", required=True)
    p_graph_build.add_argument("--output")
    p_graph_build.add_argument("--watch", action="store_true")
    p_graph_build.set_defaults(func=graph_cmds.cmd_code_graph_build)

    p_graph_related = graph_sub.add_parser("related")
    p_graph_related.add_argument("--workspace", required=True)
    p_graph_related.add_argument("--file", required=True)
    p_graph_related.add_argument("--graph")
    p_graph_related.add_argument("--max-hops", type=int, default=2)
    p_graph_related.set_defaults(func=graph_cmds.cmd_code_graph_related)

    return parser
