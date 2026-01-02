export type NormalizedRun = {
  id: string;
  planId?: string;
  status: string;
  task: string;
  updatedAt?: number | string;
  mode?: string;
  policy?: string;
  patchsetPath?: string;
  changedFilesCount?: number;
  workspaceMainRoot?: string;
  workspaceStageRoot?: string;
};

export type NormalizedPlan = {
  id: string;
  inputTask: string;
  tasksCount?: number;
  updatedAt?: number | string;
};

export function normalizeRun(raw: Record<string, unknown>): NormalizedRun {
  return {
    id: String(raw.run_id ?? raw.runId ?? raw.id ?? ""),
    planId: raw.plan_id ?? raw.planId ? String(raw.plan_id ?? raw.planId) : undefined,
    status: String(raw.status ?? raw.state ?? "unknown"),
    task: String(raw.input_task ?? raw.task ?? ""),
    updatedAt: (raw.updated_at ?? raw.updatedAt ?? raw.ts) as number | string | undefined,
    mode: raw.mode ? String(raw.mode) : undefined,
    policy: raw.policy ? String(raw.policy) : undefined,
    patchsetPath: raw.patchset_path ? String(raw.patchset_path) : undefined,
    changedFilesCount: raw.changed_files_count as number | undefined,
    workspaceMainRoot: raw.workspace_main_root ? String(raw.workspace_main_root) : undefined,
    workspaceStageRoot: raw.workspace_stage_root ? String(raw.workspace_stage_root) : undefined
  };
}

export function normalizePlan(raw: Record<string, unknown>): NormalizedPlan {
  return {
    id: String(raw.plan_id ?? raw.planId ?? raw.id ?? ""),
    inputTask: String(raw.input_task ?? raw.inputTask ?? raw.task ?? ""),
    tasksCount: (raw.tasks_count ?? raw.tasksCount) as number | undefined,
    updatedAt: (raw.updated_at ?? raw.updatedAt ?? raw.ts) as number | string | undefined
  };
}

export function formatTimestamp(value: unknown): string {
  if (!value) return "";
  const ts = typeof value === "number" ? value : Date.parse(String(value));
  if (Number.isNaN(ts)) return String(value);
  return new Date(ts).toLocaleString();
}
