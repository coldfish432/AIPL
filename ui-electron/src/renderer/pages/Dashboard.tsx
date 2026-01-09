import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  CheckCircle,
  FileText,
  Play,
  XCircle
} from "lucide-react";
import { getPlan, listPlans, listRuns, PlanSummary, RunSummary } from "../apiClient";
import { useI18n } from "../lib/useI18n";
import { formatTimestamp, normalizePlan, normalizeRun } from "../lib/normalize";
import { getStatusDisplayText, normalizeBackendStatus, resolveStatus, UnifiedStatus } from "../lib/status";
import { STORAGE_KEYS } from "../config/settings";

type Props = {
  onSelectRun: (runId: string, planId?: string) => void;
  onSelectPlan: (planId: string) => void;
};

function getRunKey(run: RunSummary): string {
  return String(run.run_id ?? run.runId ?? run.id ?? "");
}

function loadRunOrder(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.runOrderKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
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

function normalizeWorkspacePath(value: string): string {
  return value.replace(/\\/g, "/").trim().toLowerCase();
}

export default function Dashboard({ onSelectRun, onSelectPlan }: Props) {
  const { t } = useI18n();
  const [workspaceKey, setWorkspaceKey] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, { status: UnifiedStatus; progress?: number }>>({});
  const statusOverridesRef = useRef<Record<string, { status: UnifiedStatus; progress?: number }>>({});

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const workspace = workspaceKey || undefined;
      const [p, r] = await Promise.all([listPlans(workspace), listRuns(workspace)]);
      setPlans(p);
      setRuns((prev) => {
        if (prev.length === 0) return r;
        const order = loadRunOrder();
        const nextById = new Map(r.map((item) => [getRunKey(item), item]));
        const merged: RunSummary[] = [];
        const seen = new Set<string>();
        const base = order.length > 0 ? order : prev.map((item) => getRunKey(item)).filter((key) => key);
        for (const key of base) {
          const nextItem = nextById.get(key);
          if (nextItem) {
            merged.push(nextItem);
            seen.add(key);
          }
        }
        if (base.length === 0) {
          for (const item of prev) {
          const key = getRunKey(item);
          const nextItem = nextById.get(key);
          if (nextItem) {
            merged.push(nextItem);
            seen.add(key);
          } else {
            merged.push(item);
            seen.add(key);
          }
          }
        }
        for (const item of r) {
          const key = getRunKey(item);
          if (seen.has(key)) continue;
          merged.push(item);
        }
        const nextOrder = merged.map((item) => getRunKey(item)).filter((key) => key);
        localStorage.setItem(STORAGE_KEYS.runOrderKey, JSON.stringify(nextOrder));
        return merged;
      });
      setStatusOverrides({});
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const syncWorkspace = () => {
      setWorkspaceKey(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  useEffect(() => {
    if (workspaceKey) {
      void load();
    }
  }, [workspaceKey]);

  useEffect(() => {
    statusOverridesRef.current = statusOverrides;
  }, [statusOverrides]);

  const normalizedPlans = useMemo(
    () => plans.map((plan) => normalizePlan(plan as Record<string, unknown>)),
    [plans]
  );
  const normalizedRuns = useMemo(
    () => runs.map((run) => normalizeRun(run as Record<string, unknown>)),
    [runs]
  );

  const sortedPlans = useMemo(() => {
    return [...normalizedPlans].sort((a, b) => getTimestamp(b.updatedAt) - getTimestamp(a.updatedAt));
  }, [normalizedPlans]);

  const sortedRuns = useMemo(() => {
    return [...normalizedRuns].sort((a, b) => getTimestamp(b.updatedAt) - getTimestamp(a.updatedAt));
  }, [normalizedRuns]);

  const allRuns = useMemo(() => {
    if (!workspaceKey) return sortedRuns;
    const normalizedWorkspace = normalizeWorkspacePath(workspaceKey);
    return sortedRuns.filter((run) => {
      const main = run.workspaceMainRoot ? normalizeWorkspacePath(run.workspaceMainRoot) : "";
      const stage = run.workspaceStageRoot ? normalizeWorkspacePath(run.workspaceStageRoot) : "";
      return (main && main.startsWith(normalizedWorkspace)) || (stage && stage.startsWith(normalizedWorkspace));
    });
  }, [sortedRuns, workspaceKey]);

  const allPlans = useMemo(() => {
    if (!workspaceKey) return sortedPlans;
    const normalizedWorkspace = normalizeWorkspacePath(workspaceKey);
    const planIdsFromRuns = new Set(allRuns.map((run) => run.planId).filter((id): id is string => Boolean(id)));
    return sortedPlans.filter((plan) => {
      if (plan.workspacePath) {
        return normalizeWorkspacePath(plan.workspacePath).startsWith(normalizedWorkspace);
      }
      return planIdsFromRuns.has(plan.id);
    });
  }, [sortedPlans, allRuns, workspaceKey]);

  useEffect(() => {
    let active = true;
    const runsToCheck = allRuns.filter((run) => run.planId && !statusOverridesRef.current[run.id]);
    if (runsToCheck.length === 0) return () => {
      active = false;
    };
    void (async () => {
      const updates: Record<string, { status: UnifiedStatus; progress?: number }> = {};
      for (const run of runsToCheck) {
        try {
          const plan = await getPlan(String(run.planId));
          const snapshotTasks = plan?.snapshot?.tasks || [];
          if (!snapshotTasks.length) continue;
          const unified = resolveStatus(run.status || "unknown", snapshotTasks);
          const total = snapshotTasks.length;
          const done = snapshotTasks.filter((task: { status?: string }) => String(task.status || "").toLowerCase() === "done").length;
          const progress = total > 0 ? Math.round((done / total) * 100) : undefined;
          updates[run.id] = { status: unified, progress };
        } catch {
          // ignore fetch errors
        }
      }
      if (active && Object.keys(updates).length > 0) {
        setStatusOverrides((prev) => ({ ...prev, ...updates }));
      }
    })();
    return () => {
      active = false;
    };
  }, [allRuns]);

  const getLocalizedStatusText = (status: UnifiedStatus) => {
    if (status.execution === "completed" && status.review) {
      return t.status[status.review] || getStatusDisplayText(status);
    }
    return t.status[status.execution] || getStatusDisplayText(status);
  };

  const stats = useMemo(() => {
    const totalPlans = normalizedPlans.length;
    const totalRuns = normalizedRuns.length;
    const totalTasks = normalizedPlans.reduce((sum, plan) => sum + (plan.tasksCount || 0), 0);
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
    const successRate = totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0;
    return {
      totalPlans,
      totalRuns,
      totalTasks,
      runningRuns,
      completedRuns,
      successRate
    };
  }, [normalizedPlans, normalizedRuns]);



  const metrics = useMemo(() => {
    const runningRatio = stats.totalRuns > 0 ? Math.round((stats.runningRuns / stats.totalRuns) * 100) : 0;
    return [
      {
        id: "success",
        label: t.labels.successRate,
        value: stats.successRate,
        display: `${stats.successRate}%`,
        variant: "success"
      },
      {
        id: "running",
        label: t.labels.activeRuns,
        value: runningRatio,
        display: `${stats.runningRuns}/${stats.totalRuns || 0}`,
        variant: "running"
      }
    ];
  }, [stats, t]);

  return (
    <section className="dashboard dashboard-v2">
      <div className="dashboard-header">
        <div className="dashboard-title-group">
          <p className="dashboard-subtitle">
            {t.labels.stats} / {t.titles.plans} / {t.titles.runs}
          </p>
        </div>
        <div className="dashboard-actions">
          <button className="dashboard-primary" onClick={load} disabled={loading}>
            {loading ? t.messages.loading : t.buttons.refresh}
          </button>
        </div>
      </div>

      {error && <div className="dashboard-alert">{error}</div>}

      <div className="dashboard-hero-grid">
        <div className="dashboard-hero-card plans">
          <div className="dashboard-hero-header">
            <div className="dashboard-hero-icon plans">
              <FileText size={18} />
            </div>
            <span className="dashboard-hero-badge">{t.labels.tasks} {stats.totalTasks}</span>
          </div>
          <div className="dashboard-hero-value">{stats.totalPlans}</div>
          <div className="dashboard-hero-label">{t.titles.plans}</div>
        </div>
        <div className="dashboard-hero-card runs">
          <div className="dashboard-hero-header">
            <div className="dashboard-hero-icon runs">
              <Play size={18} />
            </div>
            <span className="dashboard-hero-badge">{stats.runningRuns} {t.status.running}</span>
          </div>
          <div className="dashboard-hero-value">{stats.totalRuns}</div>
          <div className="dashboard-hero-label">{t.titles.runs}</div>
        </div>
        <div className="dashboard-hero-card completed">
          <div className="dashboard-hero-header">
            <div className="dashboard-hero-icon completed">
              <CheckCircle size={18} />
            </div>
            <span className="dashboard-hero-badge">{stats.totalRuns ? `${stats.successRate}%` : "-"}</span>
          </div>
          <div className="dashboard-hero-value">{stats.completedRuns}</div>
          <div className="dashboard-hero-label">{t.status.completed}</div>
        </div>
      </div>

      <div className="dashboard-main-grid dashboard-main-grid-half">
        <div className="dashboard-panel">
          <div className="dashboard-panel-title-row">
            <div className="dashboard-panel-title">
              <FileText size={16} />
              <span>{t.titles.plans}</span>
            </div>
          </div>
          <div className="dashboard-list dashboard-scroll-list">
            {allPlans.length === 0 && <div className="dashboard-muted">{t.messages.noPlans}</div>}
            {allPlans.map((plan) => (
              <button
                key={plan.id}
                type="button"
                className="dashboard-list-item"
                onClick={() => onSelectPlan(plan.id)}
              >
                <div className="dashboard-list-main">
                  <div className="dashboard-list-title">{plan.inputTask || `${t.labels.plan} ${plan.id}`}</div>
                  <div className="dashboard-list-meta">{t.labels.updated} {formatTimestamp(plan.updatedAt) || "-"}</div>
                </div>
                <div className="dashboard-list-tail">
                  <span className="dashboard-pill">{t.labels.tasks} {plan.tasksCount ?? "-"}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="dashboard-panel">
          <div className="dashboard-panel-title-row">
            <div className="dashboard-panel-title">
              <Play size={16} />
              <span>{t.titles.runs}</span>
            </div>
          </div>
          <div className="dashboard-list dashboard-scroll-list">
            {allRuns.length === 0 && <div className="dashboard-muted">{t.messages.noRuns}</div>}
            {allRuns.map((run) => {
              const unified = normalizeBackendStatus(run.status || "unknown");
              const statusText = getLocalizedStatusText(unified);
              return (
                <button
                  key={run.id}
                  type="button"
                  className="dashboard-list-item"
                  onClick={() => onSelectRun(run.id, run.planId)}
                >
                  <div className="dashboard-list-main">
                    <div className="dashboard-list-title">{run.task || `${t.labels.run} ${run.id}`}</div>
                    <div className="dashboard-list-meta">{t.labels.updated} {formatTimestamp(run.updatedAt) || "-"}</div>
                  </div>
                  <div className="dashboard-list-tail">
                    <span className={`dashboard-pill status-${unified.execution}`}>{statusText}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="dashboard-panel">
        <div className="dashboard-panel-title-row">
          <div className="dashboard-panel-title">
            <Activity size={16} />
            <span>{t.labels.systemResources}</span>
          </div>
        </div>
        <div className="dashboard-metrics-grid">
          {metrics.map((metric) => (
            <div key={metric.id} className="dashboard-metric">
              <div className="dashboard-metric-header">
                <span>{metric.label}</span>
                <span className="dashboard-metric-value">{metric.display}</span>
              </div>
              <div className="dashboard-metric-bar">
                <div className={`dashboard-metric-bar-fill ${metric.variant}`} style={{ width: `${metric.value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
