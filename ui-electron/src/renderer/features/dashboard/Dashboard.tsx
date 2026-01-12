import React, { useEffect, useMemo, useState } from "react";
import { Activity, CheckCircle, FileText, Play } from "lucide-react";
import { listPlans, listRuns, PlanSummary, RunSummary } from "@/services/api";
import { useI18n } from "@/hooks/useI18n";
import { normalizeBackendStatus, getStatusDisplayText, UnifiedStatus } from "@/lib/status";
import { STORAGE_KEYS } from "@/config/settings";

type Props = {
  onSelectRun: (runId: string, planId?: string) => void;
  onSelectPlan: (planId: string) => void;
};

function formatTimestamp(value: unknown): string {
  if (!value) return "";
  let ts: number;
  if (typeof value === "number") {
    ts = value > 9999999999 ? value : value * 1000;
  } else {
    ts = Date.parse(String(value));
  }
  if (Number.isNaN(ts)) return "";
  return new Date(ts).toLocaleString();
}

export default function Dashboard({ onSelectRun, onSelectPlan }: Props) {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const ws = workspace || undefined;
      const [p, r] = await Promise.all([listPlans(ws), listRuns(ws)]);
      setPlans(p);
      setRuns(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const sync = () => setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    window.addEventListener("aipl-workspace-changed", sync);
    return () => window.removeEventListener("aipl-workspace-changed", sync);
  }, []);

  useEffect(() => {
    void load();
  }, [workspace]);

  const normalizedPlans = useMemo(
    () =>
      plans
        .map((p) => ({
          id: String(p.plan_id ?? p.planId ?? p.id ?? ""),
          inputTask: String(p.input_task ?? p.inputTask ?? p.task ?? ""),
          tasksCount: (p.tasks_count ?? p.tasksCount ?? 0) as number,
          updatedAt: (p.updated_at ?? p.updatedAt ?? p.ts) as number,
        }))
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
    [plans]
  );

  const normalizedRuns = useMemo(
    () =>
      runs
        .map((r) => ({
          id: String(r.run_id ?? r.runId ?? r.id ?? ""),
          planId: String(r.plan_id ?? r.planId ?? ""),
          status: String(r.status ?? r.state ?? "unknown"),
          task: String(r.task ?? r.input_task ?? ""),
          updatedAt: (r.updated_at ?? r.updatedAt ?? r.ts) as number,
        }))
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
    [runs]
  );

  const stats = useMemo(() => {
    const totalPlans = normalizedPlans.length;
    const totalRuns = normalizedRuns.length;
    const totalTasks = normalizedPlans.reduce((sum, p) => sum + (p.tasksCount || 0), 0);

    let runningRuns = 0;
    let completedRuns = 0;
    for (const run of normalizedRuns) {
      const unified = normalizeBackendStatus(run.status);
      if (["queued", "starting", "running", "retrying"].includes(unified.execution)) {
        runningRuns += 1;
      }
      if (unified.execution === "completed") {
        completedRuns += 1;
      }
    }

    const successRate = totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0;
    return { totalPlans, totalRuns, totalTasks, runningRuns, completedRuns, successRate };
  }, [normalizedPlans, normalizedRuns]);

  const getStatusText = (status: UnifiedStatus) => {
    if (status.execution === "completed" && status.review) {
      return t.status[status.review] || getStatusDisplayText(status);
    }
    return t.status[status.execution] || getStatusDisplayText(status);
  };

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
            <span className="dashboard-hero-badge">
              {t.labels.tasks} {stats.totalTasks}
            </span>
          </div>
          <div className="dashboard-hero-value">{stats.totalPlans}</div>
          <div className="dashboard-hero-label">{t.titles.plans}</div>
        </div>
        <div className="dashboard-hero-card runs">
          <div className="dashboard-hero-header">
            <div className="dashboard-hero-icon runs">
              <Play size={18} />
            </div>
            <span className="dashboard-hero-badge">
              {stats.runningRuns} {t.status.running}
            </span>
          </div>
          <div className="dashboard-hero-value">{stats.totalRuns}</div>
          <div className="dashboard-hero-label">{t.titles.runs}</div>
        </div>
        <div className="dashboard-hero-card completed">
          <div className="dashboard-hero-header">
            <div className="dashboard-hero-icon completed">
              <CheckCircle size={18} />
            </div>
            <span className="dashboard-hero-badge">
              {stats.totalRuns ? `${stats.successRate}%` : "-"}
            </span>
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
            {normalizedPlans.length === 0 && <div className="dashboard-muted">{t.messages.noPlans}</div>}
            {normalizedPlans.map((plan) => (
              <button key={plan.id} type="button" className="dashboard-list-item" onClick={() => onSelectPlan(plan.id)}>
                <div className="dashboard-list-main">
                  <div className="dashboard-list-title">{plan.inputTask || `${t.labels.plan} ${plan.id}`}</div>
                  <div className="dashboard-list-meta">
                    {t.labels.updated} {formatTimestamp(plan.updatedAt)}
                  </div>
                </div>
                <div className="dashboard-list-tail">
                  <span className="dashboard-pill">{t.labels.tasks} {plan.tasksCount}</span>
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
            {normalizedRuns.length === 0 && <div className="dashboard-muted">{t.messages.noRuns}</div>}
            {normalizedRuns.map((run) => {
              const unified = normalizeBackendStatus(run.status);
              return (
                <button
                  key={run.id}
                  type="button"
                  className="dashboard-list-item"
                  onClick={() => onSelectRun(run.id, run.planId)}
                >
                  <div className="dashboard-list-main">
                    <div className="dashboard-list-title">{run.task || `${t.labels.run} ${run.id}`}</div>
                    <div className="dashboard-list-meta">
                      {t.labels.updated} {formatTimestamp(run.updatedAt)}
                    </div>
                  </div>
                  <div className="dashboard-list-tail">
                    <span className={`dashboard-pill status-${unified.execution}`}>
                      {getStatusText(unified)}
                    </span>
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
          <div className="dashboard-metric">
            <div className="dashboard-metric-header">
              <span>{t.labels.successRate}</span>
              <span className="dashboard-metric-value">{stats.successRate}%</span>
            </div>
            <div className="dashboard-metric-bar">
              <div className="dashboard-metric-bar-fill success" style={{ width: `${stats.successRate}%` }} />
            </div>
          </div>
          <div className="dashboard-metric">
            <div className="dashboard-metric-header">
              <span>{t.labels.activeRuns}</span>
              <span className="dashboard-metric-value">{stats.runningRuns}/{stats.totalRuns}</span>
            </div>
            <div className="dashboard-metric-bar">
              <div
                className="dashboard-metric-bar-fill running"
                style={{ width: `${stats.totalRuns > 0 ? (stats.runningRuns / stats.totalRuns) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
