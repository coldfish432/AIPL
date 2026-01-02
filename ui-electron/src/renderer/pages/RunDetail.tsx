import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  applyRun,
  cancelRun,
  deleteRun,
  discardRun,
  reworkRun,
  retryRun,
  RetryOptions,
  downloadArtifactText,
  getRun,
  getRunArtifacts,
  getPlan,
  streamRunEvents,
  PlanTask,
  RunDetailResponse,
  RunEvent
} from "../apiClient";
import EventTimeline from "../components/EventTimeline";
import ProgressPanel from "../components/ProgressPanel";
import VerificationReasons, { VerificationReason } from "../components/VerificationReasons";
import DiffViewer from "../components/DiffViewer";
import {
  StreamState,
  extractEvents,
  formatEventType,
  getEventKey,
  getEventLevel,
  getEventStepId
} from "../lib/events";
import { computeProgress } from "../lib/progress";
import { getStatusClassName, getStatusDisplayText, needsReview, resolveStatus } from "../lib/status";

type Props = {
  runId: string;
  planId?: string;
  onBack: () => void;
};

type ChangedFile = {
  path: string;
  status: string;
};

type FailureInfo = {
  reportText?: string;
  reasons?: VerificationReason[];
  summaryText?: string;
};

function formatUpdated(updated: unknown) {
  if (!updated) return null;
  if (typeof updated === "number") {
    const dt = new Date(updated);
    if (!Number.isNaN(dt.getTime())) {
      return dt.toLocaleString();
    }
  }
  return String(updated);
}

function describeWorkflowStage(events: RunEvent[], status: { execution: string; review: string | null }): string {
  if (needsReview(status)) return "等待审核（补丁集已就绪）";
  if (status.execution === "failed") return "执行失败";
  if (status.execution === "canceled") return "已取消";
  if (status.execution === "discarded") return "已丢弃";
  if (status.execution === "completed") return "已完成";

  for (let i = events.length - 1; i >= 0; i -= 1) {
    const evt = events[i];
    const type = formatEventType(evt);
    if (type === "codex_timeout") return "Codex 超时";
    if (type === "codex_failed") return "Codex 失败";
    if (type === "codex_start") return "Codex 生成中";
    if (type === "codex_done") return "Codex 已响应";
    if (type === "subagent_start") return "子代理运行中";
    if (type === "subagent_done") return "验证器运行中";
    if (type === "step_round_verified") return "验证完成";
    if (type === "workspace_stage_ready") return "Stage 工作区就绪";
    if (type === "run_init") return "执行初始化";
    if (type === "patchset_ready") return "补丁集就绪";
    if (type === "awaiting_review") return "等待审核";
    if (type === "apply_start") return "正在应用变更";
    if (type === "apply_done") return "变更已应用";
    if (type === "discard_done") return "变更已丢弃";
    if (type === "run_done") return "执行完成";
    if (type === "step_round_start") {
      const round = (evt as { round?: number | string }).round;
      return round !== undefined ? `步骤轮次 ${round}` : "步骤轮次进行中";
    }
  }
  return "运行中";
}

function progressFromStatus(status: { execution: string; review: string | null }): number {
  if (needsReview(status)) return 90;
  if (status.execution === "completed") return 100;
  if (["failed", "canceled", "discarded"].includes(status.execution)) return 100;
  if (["running", "starting", "queued", "retrying"].includes(status.execution)) return 20;
  return 0;
}

export default function RunDetail({ runId, planId, onBack }: Props) {
  const [run, setRun] = useState<RunDetailResponse | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [streamState, setStreamState] = useState<StreamState>("connecting");
  const [patchsetText, setPatchsetText] = useState<string>("");
  const [changedFiles, setChangedFiles] = useState<ChangedFile[]>([]);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [failureInfo, setFailureInfo] = useState<FailureInfo | null>(null);
  const [failureError, setFailureError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [retryMenuOpen, setRetryMenuOpen] = useState(false);
  const [reworkFeedback, setReworkFeedback] = useState("");
  const [inlineNotice, setInlineNotice] = useState<string | null>(null);
  const [autoPrompt, setAutoPrompt] = useState(false);
  const [planTasks, setPlanTasks] = useState<PlanTask[]>([]);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const seenRef = useRef<Set<string>>(new Set());

  const runInfo = run?.run || run || null;

  useEffect(() => {
    setEvents([]);
    setError(null);
    setStreamState("connecting");
    setInlineNotice(null);
    setAutoPrompt(false);
    seenRef.current = new Set();

    void (async () => {
      try {
        const data = await getRun(runId, planId);
        setRun(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载执行失败";
        setError(message || "加载执行失败");
      }
    })();

    let active = true;
    let es: EventSource | null = null;
    let reconnectTimer: number | null = null;

    const connect = () => {
      if (!active) return;
      setStreamState("connecting");
      es = streamRunEvents(runId, planId);
      es.onopen = () => {
        if (!active) return;
        setStreamState("connected");
      };
      es.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data) as unknown;
          const next = extractEvents(payload);
          if (next.length > 0) {
            setEvents((prev) => {
              const merged = [...prev];
              const seen = seenRef.current;
              for (const item of next) {
                const key = getEventKey(item);
                if (seen.has(key)) continue;
                seen.add(key);
                merged.push(item);
              }
              return merged;
            });
          }
        } catch {
          // ignore parse errors
        }
      };
      es.onerror = () => {
        if (!active) return;
        setStreamState("disconnected");
        es?.close();
        if (reconnectTimer) window.clearTimeout(reconnectTimer);
        reconnectTimer = window.setTimeout(connect, 1500);
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [runId, planId]);

  const resolvedPlanId = planId || runInfo?.plan_id || runInfo?.planId || "-";
  const rawStatus = runInfo?.status || runInfo?.state || "unknown";
  const task = runInfo?.input_task || runInfo?.task || "-";
  const updated = formatUpdated(runInfo?.updated_at || runInfo?.updatedAt || runInfo?.ts);
  const unifiedStatus = useMemo(
    () => resolveStatus(rawStatus, planTasks),
    [rawStatus, planTasks]
  );
  const normalizedStatus = unifiedStatus.execution;
  const statusText = getStatusDisplayText(unifiedStatus);
  const progress = useMemo(
    () => Math.max(computeProgress(events), progressFromStatus(unifiedStatus)),
    [events, unifiedStatus]
  );
  const workflowStage = useMemo(() => describeWorkflowStage(events, unifiedStatus), [events, unifiedStatus]);
  const currentStep = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const stepId = getEventStepId(events[i]);
      if (stepId) return stepId;
    }
    return "step-01";
  }, [events]);
  const latestEvents = useMemo(() => events.slice(-5).reverse(), [events]);
  const warningCount = useMemo(() => events.filter((evt) => getEventLevel(evt) === "warning").length, [events]);
  const errorCount = useMemo(() => events.filter((evt) => getEventLevel(evt) === "error").length, [events]);
  const awaitingReview = needsReview(unifiedStatus);
  const failed = normalizedStatus === "failed";
  const isRunning = normalizedStatus === "running" || normalizedStatus === "starting";
  const canRetry = normalizedStatus === "failed" || normalizedStatus === "canceled";
  const isRunDone = normalizedStatus === "completed" || events.some((evt) => formatEventType(evt).toLowerCase() === "run_done");
  const hasPlanId = resolvedPlanId && resolvedPlanId !== "-";

  useEffect(() => {
    if (!hasPlanId) {
      setPlanTasks([]);
      setPlanError(null);
      return;
    }
    let active = true;
    setPlanLoading(true);
    setPlanError(null);
    void (async () => {
      try {
        const data = await getPlan(resolvedPlanId);
        const snapshot = data?.snapshot?.tasks || [];
        const rawTasks = data?.plan?.raw_plan?.tasks || [];
        const nextTasks = snapshot.length > 0 ? snapshot : rawTasks;
        if (active) {
          setPlanTasks(nextTasks);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载计划失败";
        if (active) setPlanError(message || "加载计划失败");
      } finally {
        if (active) setPlanLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [hasPlanId, resolvedPlanId]);

  const taskStats = useMemo(() => {
    const stats = { total: 0, done: 0, doing: 0, failed: 0, todo: 0 };
    if (!planTasks || planTasks.length === 0) return stats;
    stats.total = planTasks.length;
    planTasks.forEach((taskItem) => {
      const state = String(taskItem.status || "todo").toLowerCase();
      if (state === "done") stats.done += 1;
      else if (state === "doing") stats.doing += 1;
      else if (state === "failed") stats.failed += 1;
      else stats.todo += 1;
    });
    return stats;
  }, [planTasks]);
  const taskProgress = taskStats.total > 0 ? Math.round((taskStats.done / taskStats.total) * 100) : 0;

  useEffect(() => {
    if (isRunDone) {
      setAutoPrompt(true);
    }
  }, [isRunDone]);

  useEffect(() => {
    if (!awaitingReview) return;
    let active = true;
    setReviewLoading(true);
    setReviewError(null);
    void (async () => {
      try {
        const artifacts = await getRunArtifacts(runId, planId);
        const items = artifacts.items || [];
        const patchsetPath = runInfo?.patchset_path || items.find((item) => item.path.endsWith("patchset.diff"))?.path;
        const changedPath = items.find((item) => item.path.endsWith("changed_files.json"))?.path;
        if (patchsetPath) {
          const text = await downloadArtifactText(runId, patchsetPath, planId);
          if (active) setPatchsetText(text);
        }
        if (changedPath) {
          const raw = await downloadArtifactText(runId, changedPath, planId);
          const parsed = JSON.parse(raw || "{}");
          if (active && Array.isArray(parsed.changed_files)) {
            setChangedFiles(parsed.changed_files as ChangedFile[]);
          }
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载补丁集失败";
        if (active) setReviewError(message || "加载补丁集失败");
      } finally {
        if (active) setReviewLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [awaitingReview, runId, planId, runInfo?.patchset_path]);

  useEffect(() => {
    if (!failed) {
      setFailureInfo(null);
      setFailureError(null);
      return;
    }
    let active = true;
    setFailureInfo(null);
    setFailureError(null);
    void (async () => {
      try {
        const artifacts = await getRunArtifacts(runId, planId);
        const items = artifacts.items || [];
        const reportPath = items.find((item) => item.path.endsWith("verification_report.md"))?.path;
        const resultPath = items.find((item) => item.path.endsWith("verification_result.json"))?.path;
        const summaryPath = items.find((item) => item.path.endsWith("failure_reason_zh.txt"))?.path;
        let reportText = "";
        let reasonsList: VerificationReason[] = [];
        let summaryText = "";
        if (summaryPath) {
          summaryText = await downloadArtifactText(runId, summaryPath, planId);
        }
        if (reportPath) {
          reportText = await downloadArtifactText(runId, reportPath, planId);
        }
        if (!reportText && resultPath) {
          const raw = await downloadArtifactText(runId, resultPath, planId);
          const parsed = JSON.parse(raw || "{}");
          const reasons = Array.isArray(parsed.reasons) ? parsed.reasons : [];
          reasonsList = reasons as VerificationReason[];
        }
        if (active) {
          setFailureInfo({
            reportText: reportText || undefined,
            reasons: reasonsList.length > 0 ? reasonsList : undefined,
            summaryText: summaryText || undefined
          });
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载失败详情失败";
        if (active) setFailureError(message || "加载失败详情失败");
      }
    })();
    return () => {
      active = false;
    };
  }, [failed, runId, planId]);

  function handleInlineRework(stepId: string | null) {
    if (!stepId) {
      setInlineNotice("获取到步骤 ID 后才能返工。");
      return;
    }
    setInlineNotice(`已为 ${stepId} 准备返工，请在返工面板提交。`);
    setReworkFeedback((prev) => prev || `请求返工：${stepId}。`);
  }

  async function handleApply() {
    setActionLoading(true);
    setReviewError(null);
    try {
      if (!window.confirm("确认通过审核并应用到目标目录吗？")) {
        setActionLoading(false);
        return;
      }
      await applyRun(runId, planId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "应用失败";
      setReviewError(message || "应用失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteRun() {
    if (!window.confirm("确认删除这个 run 吗？相关 artifacts 也会被删除。")) {
      return;
    }
    setActionLoading(true);
    setReviewError(null);
    try {
      await deleteRun(runId, planId);
      onBack();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除失败";
      setReviewError(message || "删除失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!window.confirm("确认取消当前执行吗？")) return;
    setActionLoading(true);
    setReviewError(null);
    try {
      await cancelRun(runId, planId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "取消失败";
      setReviewError(message || "取消失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRetry(options?: RetryOptions) {
    setRetryMenuOpen(false);
    setActionLoading(true);
    setReviewError(null);
    try {
      const res = await retryRun(runId, options, planId);
      const newRunId = res.run_id || res.runId;
      if (newRunId && newRunId !== runId) {
        window.location.hash = `#/runs/${newRunId}${planId ? `?planId=${planId}` : ""}`;
      } else {
        const refreshed = await getRun(runId, planId);
        setRun(refreshed);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "重试失败";
      setReviewError(message || "重试失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRework() {
    setActionLoading(true);
    setReviewError(null);
    try {
      await reworkRun(runId, { stepId: currentStep, feedback: reworkFeedback }, planId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "返工失败";
      setReviewError(message || "返工失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDiscard() {
    setActionLoading(true);
    setReviewError(null);
    try {
      await discardRun(runId, planId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "丢弃失败";
      setReviewError(message || "丢弃失败");
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <section className="stack">
      <div className="row">
        <button onClick={onBack}>返回</button>
        <button onClick={handleDeleteRun} disabled={actionLoading}>删除执行</button>
        {isRunning && (
          <button onClick={handleCancel} disabled={actionLoading} className="danger">
            取消执行
          </button>
        )}
        {canRetry && (
          <div className="dropdown">
            <button onClick={() => setRetryMenuOpen((prev) => !prev)} disabled={actionLoading}>
              重试 ▾
            </button>
            {retryMenuOpen && (
              <div className="dropdown-menu">
                <button onClick={() => handleRetry()}>快速重试</button>
                <button onClick={() => handleRetry({ retryDeps: true })}>重试并包含依赖</button>
                <button onClick={() => handleRetry({ force: true })}>强制重试</button>
              </div>
            )}
          </div>
        )}
        <span className={`pill ${streamState}`}>流 {streamState}</span>
        {error && <span className="error">{error}</span>}
        {inlineNotice && <span className="muted">{inlineNotice}</span>}
      </div>
      {autoPrompt && (
        <div className="banner success">执行完成。如需修改请审核并应用。</div>
      )}
      <div className="card">
        <h2>执行信息</h2>
        <div className="list">
          <div className="list-item">
            <div className="title">执行 ID</div>
            <div className="meta">{runId}</div>
          </div>
          <div className="list-item">
            <div className="title">计划 ID</div>
            <div className="meta">{resolvedPlanId}</div>
          </div>
          <div className="list-item">
            <div>
              <div className="title">状态</div>
              <div className="meta">{statusText}</div>
            </div>
            <div className={`pill ${getStatusClassName(unifiedStatus)}`}>{statusText}</div>
          </div>
          <div className="list-item">
            <div className="title">当前阶段</div>
            <div className="meta">{workflowStage}</div>
          </div>
          <div className="list-item">
            <div className="title">策略</div>
            <div className="meta">{runInfo?.policy || "-"}</div>
          </div>
          <div className="list-item">
            <div className="title">任务</div>
            <div className="meta">{task}</div>
          </div>
          <div className="list-item">
            <div className="title">更新时间</div>
            <div className="meta">{updated || "-"}</div>
          </div>
        </div>
      </div>
      {hasPlanId && (
        <div className="card">
          <h2>任务链进度</h2>
          {planLoading && <div className="muted">加载任务链中...</div>}
          {planError && <div className="error">{planError}</div>}
          {!planLoading && planTasks.length > 0 && (
            <>
              <div className="progress large">
                <div className="progress-bar" style={{ width: `${taskProgress}%` }} />
              </div>
              <div className="row">
                <span className="pill">{taskProgress}%</span>
                <span className="pill subtle">完成 {taskStats.done}/{taskStats.total}</span>
                {taskStats.doing > 0 && <span className="pill warn">执行中 {taskStats.doing}</span>}
                {taskStats.failed > 0 && <span className="pill error">失败 {taskStats.failed}</span>}
              </div>
              <div className="list">
                {planTasks.map((taskItem, idx) => {
                  const taskId = taskItem.step_id || taskItem.id || taskItem.task_id || `task-${idx + 1}`;
                  const title = taskItem.title || taskItem.name || `Task ${idx + 1}`;
                  const status = String(taskItem.status || "todo").toLowerCase();
                  return (
                    <div key={taskId} className="list-item task-item">
                      <div>
                        <div className="title">{title}</div>
                        <div className="meta">id {taskId}</div>
                        {taskItem.description && <div className="meta">{taskItem.description}</div>}
                      </div>
                      <div className={`pill ${status}`}>{status}</div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
          {!planLoading && planTasks.length === 0 && !planError && (
            <div className="muted">暂无任务链数据。</div>
          )}
        </div>
      )}
      <div className="card">
        <h2>进度</h2>
        <ProgressPanel
          progress={progress}
          currentStep={currentStep}
          latestEvents={latestEvents}
          warningCount={warningCount}
          errorCount={errorCount}
        />
      </div>
      {awaitingReview && (
        <div className="card">
          <h2>审核与应用</h2>
          {reviewLoading && <div className="muted">加载补丁集中...</div>}
          {reviewError && <div className="error">{reviewError}</div>}
          {changedFiles.length > 0 && (
            <div className="list">
              {changedFiles.map((item, idx) => (
                <div key={`${item.path}-${idx}`} className="list-item">
                  <div className="title">{item.path}</div>
                  <div className="pill">{item.status}</div>
                </div>
              ))}
            </div>
          )}
          {patchsetText && <DiffViewer diffText={patchsetText} changedFiles={changedFiles} />}
          <div className="row">
            <button onClick={handleApply} disabled={actionLoading}>通过审核并应用</button>
            <button onClick={handleDiscard} disabled={actionLoading}>丢弃</button>
          </div>
        </div>
      )}

      {failed && (
        <div className="card">
          <h2>返工</h2>
          {failureError && <div className="error">{failureError}</div>}
          {failureInfo?.summaryText && <pre className="pre">{failureInfo.summaryText}</pre>}
          {failureInfo?.reasons && failureInfo.reasons.length > 0 && (
            <VerificationReasons reasons={failureInfo.reasons} />
          )}
          {failureInfo?.reportText && <pre className="pre">{failureInfo.reportText}</pre>}
          <textarea
            className="textarea"
            placeholder="可选：返工反馈"
            value={reworkFeedback}
            onChange={(e) => setReworkFeedback(e.target.value)}
            rows={3}
          />
          <div className="row">
            <button onClick={handleRework} disabled={actionLoading}>返工当前步骤</button>
          </div>
        </div>
      )}
      <div className="card">
        <h2>事件</h2>
        <EventTimeline
          events={events}
          streamState={streamState}
          autoScroll
          emptyLabel={streamState === "disconnected" ? "事件流已断开。" : undefined}
          onRework={handleInlineRework}
        />
      </div>
    </section>
  );
}
