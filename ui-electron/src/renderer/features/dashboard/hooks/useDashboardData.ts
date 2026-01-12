/**
 * Dashboard Data Hook
 * 管理仪表盘数据加载
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listPlans, listRuns, getPlan } from "@/apis";
import { normalizePlan, normalizeRun, normalizeWorkspacePath } from "@/lib/normalize";
import { normalizeBackendStatus, resolveStatus } from "@/lib/status";
import { STORAGE_KEYS } from "@/config/settings";
import type { PlanSummary, RunSummary, UnifiedStatus } from "@/apis/types";
import type { NormalizedPlan, NormalizedRun } from "@/lib/normalize";

// ============================================================
// Types
// ============================================================

interface DashboardStats {
  totalPlans: number;
  totalRuns: number;
  totalTasks: number;
  runningRuns: number;
  completedRuns: number;
  successRate: number;
}

interface StatusOverride {
  status: UnifiedStatus;
  progress?: number;
}

interface UseDashboardDataReturn {
  plans: NormalizedPlan[];
  runs: NormalizedRun[];
  stats: DashboardStats;
  statusOverrides: Record<string, StatusOverride>;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

// ============================================================
// Helpers
// ============================================================

function getRunKey(run: RunSummary): string {
  return String(run.run_id ?? run.runId ?? run.id ?? "");
}

function loadRunOrder(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.runOrderKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((item) => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function getTimestamp(value: unknown): number {
  if (!value) return 0;
  if (typeof value === "number") return value;
  const parsed = Date.parse(String(value));
  return Number.isNaN(parsed) ? 0 : parsed;
}

// ============================================================
// Hook
// ============================================================

export function useDashboardData(): UseDashboardDataReturn {
  const [rawPlans, setRawPlans] = useState<PlanSummary[]>([]);
  const [rawRuns, setRawRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, StatusOverride>>({});
  const [workspace, setWorkspace] = useState(() =>
    localStorage.getItem(STORAGE_KEYS.workspaceKey) || ""
  );

  const statusOverridesRef = useRef<Record<string, StatusOverride>>({});

  // Sync workspace
  useEffect(() => {
    const syncWorkspace = () => {
      setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  // Load data
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const ws = workspace || undefined;
      const [p, r] = await Promise.all([listPlans(ws), listRuns(ws)]);
      setRawPlans(p);

      // Merge runs with order preservation
      setRawRuns((prev) => {
        if (prev.length === 0) return r;

        const order = loadRunOrder();
        const nextById = new Map(r.map((item) => [getRunKey(item), item]));
        const merged: RunSummary[] = [];
        const seen = new Set<string>();

        // Add items in order
        const base =
          order.length > 0
            ? order
            : prev.map((item) => getRunKey(item)).filter((key) => key);

        for (const key of base) {
          const nextItem = nextById.get(key);
          if (nextItem) {
            merged.push(nextItem);
            seen.add(key);
          }
        }

        // Add new items
        for (const item of r) {
          const key = getRunKey(item);
          if (!seen.has(key)) {
            merged.push(item);
          }
        }

        // Save order
        const nextOrder = merged.map((item) => getRunKey(item)).filter((key) => key);
        localStorage.setItem(STORAGE_KEYS.runOrderKey, JSON.stringify(nextOrder));

        return merged;
      });

      setStatusOverrides({});
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  // Initial load
  useEffect(() => {
    load();
  }, [load]);

  // Sync status overrides ref
  useEffect(() => {
    statusOverridesRef.current = statusOverrides;
  }, [statusOverrides]);

  // Normalize data
  const normalizedPlans = useMemo(
    () => rawPlans.map((plan) => normalizePlan(plan as Record<string, unknown>)),
    [rawPlans]
  );

  const normalizedRuns = useMemo(
    () => rawRuns.map((run) => normalizeRun(run as Record<string, unknown>)),
    [rawRuns]
  );

  // Sort by updated time
  const sortedPlans = useMemo(
    () => [...normalizedPlans].sort((a, b) => getTimestamp(b.updatedAt) - getTimestamp(a.updatedAt)),
    [normalizedPlans]
  );

  const sortedRuns = useMemo(
    () => [...normalizedRuns].sort((a, b) => getTimestamp(b.updatedAt) - getTimestamp(a.updatedAt)),
    [normalizedRuns]
  );

  // Filter by workspace
  const filteredRuns = useMemo(() => {
    if (!workspace) return sortedRuns;
    const normalizedWorkspace = normalizeWorkspacePath(workspace);
    return sortedRuns.filter((run) => {
      const main = run.workspaceMainRoot
        ? normalizeWorkspacePath(run.workspaceMainRoot)
        : "";
      const stage = run.workspaceStageRoot
        ? normalizeWorkspacePath(run.workspaceStageRoot)
        : "";
      return (
        (main && main.startsWith(normalizedWorkspace)) ||
        (stage && stage.startsWith(normalizedWorkspace))
      );
    });
  }, [sortedRuns, workspace]);

  const filteredPlans = useMemo(() => {
    if (!workspace) return sortedPlans;
    const normalizedWorkspace = normalizeWorkspacePath(workspace);
    const planIdsFromRuns = new Set(
      filteredRuns.map((run) => run.planId).filter((id): id is string => Boolean(id))
    );
    return sortedPlans.filter((plan) => {
      if (plan.workspacePath) {
        return normalizeWorkspacePath(plan.workspacePath).startsWith(normalizedWorkspace);
      }
      return planIdsFromRuns.has(plan.id);
    });
  }, [sortedPlans, filteredRuns, workspace]);

  // Load status overrides for runs with planId
  useEffect(() => {
    let active = true;
    const runsToCheck = filteredRuns.filter(
      (run) => run.planId && !statusOverridesRef.current[run.id]
    );

    if (runsToCheck.length === 0) {
      return () => {
        active = false;
      };
    }

    (async () => {
      const updates: Record<string, StatusOverride> = {};

      for (const run of runsToCheck) {
        try {
          const plan = await getPlan(String(run.planId));
          const snapshotTasks = plan?.snapshot?.tasks || [];
          if (!snapshotTasks.length) continue;

          const unified = resolveStatus(run.status || "unknown", snapshotTasks);
          const total = snapshotTasks.length;
          const done = snapshotTasks.filter(
            (task: { status?: string }) =>
              String(task.status || "").toLowerCase() === "done"
          ).length;
          const progress = total > 0 ? Math.round((done / total) * 100) : undefined;

          updates[run.id] = { status: unified, progress };
        } catch {
          // Ignore fetch errors
        }
      }

      if (active && Object.keys(updates).length > 0) {
        setStatusOverrides((prev) => ({ ...prev, ...updates }));
      }
    })();

    return () => {
      active = false;
    };
  }, [filteredRuns]);

  // Calculate stats
  const stats = useMemo<DashboardStats>(() => {
    const totalPlans = normalizedPlans.length;
    const totalRuns = normalizedRuns.length;
    const totalTasks = normalizedPlans.reduce(
      (sum, plan) => sum + (plan.tasksCount || 0),
      0
    );

    let runningRuns = 0;
    let completedRuns = 0;

    for (const run of normalizedRuns) {
      const unified = normalizeBackendStatus(run.status || "unknown");
      if (["queued", "starting", "running", "retrying"].includes(unified.execution)) {
        runningRuns += 1;
      }
      if (unified.execution === "completed") {
        completedRuns += 1;
      }
    }

    const successRate =
      totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0;

    return {
      totalPlans,
      totalRuns,
      totalTasks,
      runningRuns,
      completedRuns,
      successRate,
    };
  }, [normalizedPlans, normalizedRuns]);

  return {
    plans: filteredPlans,
    runs: filteredRuns,
    stats,
    statusOverrides,
    loading,
    error,
    refresh: load,
  };
}
