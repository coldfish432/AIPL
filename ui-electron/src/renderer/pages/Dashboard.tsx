import React, { useEffect, useMemo, useRef, useState } from "react";
import { getPlan, listPlans, listRuns, PlanSummary, RunSummary } from "../apiClient";
import { LABELS } from "../lib/i18n";
import { formatTimestamp, normalizePlan, normalizeRun } from "../lib/normalize";
import { selectProgressFromRun } from "../lib/progress";
import { getStatusClassName, getStatusDisplayText, normalizeBackendStatus, resolveStatus, UnifiedStatus } from "../lib/status";

type Props = {
  onSelectRun: (runId: string, planId?: string) => void;
  onSelectPlan: (planId: string) => void;
};

function matchesQuery(value: unknown, query: string) {
  if (!query) return true;
  return String(value ?? "").toLowerCase().includes(query);
}

export default function Dashboard({ onSelectRun, onSelectPlan }: Props) {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState(() => localStorage.getItem("aipl.workspace") || "");
  const [planQuery, setPlanQuery] = useState("");
  const [runQuery, setRunQuery] = useState("");
  const [planPage, setPlanPage] = useState(1);
  const [runPage, setRunPage] = useState(1);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, { status: UnifiedStatus; progress?: number }>>({});
  const statusOverridesRef = useRef<Record<string, { status: UnifiedStatus; progress?: number }>>({});
  const pageSize = 6;

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [p, r] = await Promise.all([listPlans(), listRuns()]);
      setPlans(p);
      setRuns(r);
      setStatusOverrides({});
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载失败";
      setError(message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    statusOverridesRef.current = statusOverrides;
  }, [statusOverrides]);

  useEffect(() => {
    const trimmed = workspace.trim();
    if (trimmed) {
      localStorage.setItem("aipl.workspace", trimmed);
    } else {
      localStorage.removeItem("aipl.workspace");
    }
    window.dispatchEvent(new Event("aipl-workspace-changed"));
  }, [workspace]);

  useEffect(() => {
    setPlanPage(1);
  }, [planQuery]);

  useEffect(() => {
    setRunPage(1);
  }, [runQuery]);

  const normalizedPlans = useMemo(
    () => plans.map((plan) => normalizePlan(plan as Record<string, unknown>)),
    [plans]
  );
  const normalizedRuns = useMemo(
    () => runs.map((run) => normalizeRun(run as Record<string, unknown>)),
    [runs]
  );

  const filteredPlans = useMemo(() => {
    const query = planQuery.trim().toLowerCase();
    if (!query) return normalizedPlans;
    return normalizedPlans.filter((plan) => {
      return matchesQuery(plan.id, query) || matchesQuery(plan.inputTask, query);
    });
  }, [planQuery, normalizedPlans]);

  const filteredRuns = useMemo(() => {
    const query = runQuery.trim().toLowerCase();
    if (!query) return normalizedRuns;
    return normalizedRuns.filter((run) => {
      return matchesQuery(run.id, query) || matchesQuery(run.task, query) || matchesQuery(run.status, query);
    });
  }, [runQuery, normalizedRuns]);

  const planTotalPages = Math.max(1, Math.ceil(filteredPlans.length / pageSize));
  const runTotalPages = Math.max(1, Math.ceil(filteredRuns.length / pageSize));

  useEffect(() => {
    if (planPage > planTotalPages) {
      setPlanPage(planTotalPages);
    }
  }, [planPage, planTotalPages]);

  useEffect(() => {
    if (runPage > runTotalPages) {
      setRunPage(runTotalPages);
    }
  }, [runPage, runTotalPages]);

  const planPageSafe = Math.min(planPage, planTotalPages);
  const runPageSafe = Math.min(runPage, runTotalPages);

  const pagedPlans = filteredPlans.slice((planPageSafe - 1) * pageSize, planPageSafe * pageSize);
  const pagedRuns = filteredRuns.slice((runPageSafe - 1) * pageSize, runPageSafe * pageSize);

  useEffect(() => {
    let active = true;
    const runsToCheck = pagedRuns.filter((run) => run.planId && !statusOverridesRef.current[run.id]);
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
          if (["queued", "starting", "running"].includes(unified.execution)) {
            updates[run.id] = { status: unified, progress };
          }
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
  }, [pagedRuns]);

  return (
    <section className="stack">
      <div className="row">
        <input
          className="input"
          placeholder="工作区路径"
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value)}
        />
        <button onClick={load} disabled={loading}>{loading ? "加载中..." : LABELS.buttons.refresh}</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>计划</h2>
          <div className="row">
            <input
              className="input compact"
              placeholder="搜索计划"
              value={planQuery}
              onChange={(e) => setPlanQuery(e.target.value)}
            />
            <div className="row">
              <button onClick={() => setPlanPage((prev) => Math.max(1, prev - 1))} disabled={planPageSafe <= 1}>
                上一页
              </button>
              <button onClick={() => setPlanPage((prev) => Math.min(planTotalPages, prev + 1))} disabled={planPageSafe >= planTotalPages}>
                下一页
              </button>
              <span className="muted">{planPageSafe} / {planTotalPages}</span>
            </div>
          </div>
          <div className="list">
            {plans.length === 0 && <div className="muted">{LABELS.messages.noPlans}</div>}
            {plans.length > 0 && filteredPlans.length === 0 && <div className="muted">没有匹配的计划。</div>}
            {pagedPlans.map((plan) => {
              const updated = formatTimestamp(plan.updatedAt);
              const tasksCount = plan.tasksCount;
              return (
                <button key={String(plan.id)} className="list-item button" onClick={() => onSelectPlan(String(plan.id))}>
                  <div>
                    <div className="title">{String(plan.id)}</div>
                    {updated && <div className="meta">更新 {updated}</div>}
                  </div>
                  {typeof tasksCount === "number" && <div className="pill">{tasksCount} 任务</div>}
                </button>
              );
            })}
          </div>
        </div>
        <div className="card">
          <h2>执行</h2>
          <div className="row">
            <input
              className="input compact"
              placeholder="搜索执行"
              value={runQuery}
              onChange={(e) => setRunQuery(e.target.value)}
            />
            <div className="row">
              <button onClick={() => setRunPage((prev) => Math.max(1, prev - 1))} disabled={runPageSafe <= 1}>
                上一页
              </button>
              <button onClick={() => setRunPage((prev) => Math.min(runTotalPages, prev + 1))} disabled={runPageSafe >= runTotalPages}>
                下一页
              </button>
              <span className="muted">{runPageSafe} / {runTotalPages}</span>
            </div>
          </div>
          <div className="list">
            {runs.length === 0 && <div className="muted">{LABELS.messages.noRuns}</div>}
            {runs.length > 0 && filteredRuns.length === 0 && <div className="muted">没有匹配的执行。</div>}
            {pagedRuns.map((run) => {
              const override = statusOverrides[run.id];
              const unified = override ? override.status : normalizeBackendStatus(run.status || "unknown");
              const statusText = getStatusDisplayText(unified);
              const updated = formatTimestamp(run.updatedAt);
              const progress = override?.progress ?? selectProgressFromRun(run as unknown as Record<string, unknown>);
              return (
                <button key={String(run.id)} className="list-item button" onClick={() => onSelectRun(String(run.id), run.planId || undefined)}>
                  <div>
                    <div className="title">{String(run.id)}</div>
                    <div className="meta">状态 {statusText}</div>
                    {updated && <div className="meta">更新 {updated}</div>}
                    {progress !== null && (
                      <div className="progress">
                        <div className="progress-bar" style={{ width: `${progress}%` }} />
                      </div>
                    )}
                  </div>
                  <div className={`pill ${getStatusClassName(unified)}`}>{statusText}</div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
