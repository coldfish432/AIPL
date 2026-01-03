import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  applyRun,
  cancelRun,
  deleteRun,
  discardRun,
  getRunEvents,
  openRunFile,
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
import VerificationReasons, { VerificationReason } from "../components/VerificationReasons";
import DiffViewer from "../components/DiffViewer";
import RunActionBar from "./run-detail/RunActionBar";
import RunInfoCard from "./run-detail/RunInfoCard";
import {
  StreamState,
  extractEvents,
  formatEventType,
  getEventKey,
  getEventStepId
} from "../lib/events";
import { getStatusDisplayText, needsReview, resolveStatus, UnifiedStatus } from "../lib/status";
import { useI18n } from "../lib/useI18n";
import { usePlanLock } from "../hooks/usePlanLock";

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

function describeWorkflowStage(events: RunEvent[], status: UnifiedStatus, labels: Record<string, string>): string {
  if (needsReview(status)) return labels.awaitingReviewReady;
  if (status.execution === "failed") return labels.runFailed;
  if (status.execution === "canceled") return labels.runCanceled;
  if (status.execution === "discarded") return labels.runDiscarded;
  if (status.execution === "completed") return labels.runCompleted;

  for (let i = events.length - 1; i >= 0; i -= 1) {
    const evt = events[i];
    const type = formatEventType(evt);
    if (type === "codex_timeout") return labels.codexTimeout;
    if (type === "codex_failed") return labels.codexFailed;
    if (type === "codex_start") return labels.codexStart;
    if (type === "codex_done") return labels.codexDone;
    if (type === "subagent_start") return labels.subagentStart;
    if (type === "subagent_done") return labels.subagentDone;
    if (type === "step_round_verified") return labels.verificationDone;
    if (type === "workspace_stage_ready") return labels.stageReady;
    if (type === "run_init") return labels.runInit;
    if (type === "patchset_ready") return labels.patchsetReady;
    if (type === "awaiting_review") return labels.awaitingReview;
    if (type === "apply_start") return labels.applyStart;
    if (type === "apply_done") return labels.applyDone;
    if (type === "discard_done") return labels.discardDone;
    if (type === "run_done") return labels.runDone;
    if (type === "step_round_start") {
      const round = (evt as { round?: number | string }).round;
      return round !== undefined ? `${labels.stepRound} ${round}` : labels.stepRoundRunning;
    }
  }
  return labels.running;
}

export default function RunDetail({ runId, planId, onBack }: Props) {
  const { language, t } = useI18n();
  const { removePendingReview } = usePlanLock();
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
        const message = err instanceof Error ? err.message : t.messages.loadRunFailed;
        setError(message || t.messages.loadRunFailed);
      }
    })();

    void (async () => {
      try {
        const history = await getRunEvents(runId, planId, 0, 500);
        const next = extractEvents(history as unknown);
        if (!Array.isArray(next) || next.length === 0) return;
        setEvents(() => {
          const merged: RunEvent[] = [];
          const seen = new Set<string>();
          for (const item of next) {
            const key = getEventKey(item);
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push(item);
          }
          seenRef.current = seen;
          return merged;
        });
      } catch {
        // ignore history fetch errors
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
  const statusText =
    (unifiedStatus.execution === "completed" && unifiedStatus.review
      ? t.status[unifiedStatus.review]
      : t.status[unifiedStatus.execution]) || getStatusDisplayText(unifiedStatus);
  const workflowStage = useMemo(
    () =>
      describeWorkflowStage(events, unifiedStatus, {
        awaitingReviewReady: t.messages.awaitingReviewReady,
        runFailed: t.messages.runFailed,
        runCanceled: t.messages.runCanceled,
        runDiscarded: t.messages.runDiscarded,
        runCompleted: t.messages.runCompleted,
        codexTimeout: t.messages.codexTimeout,
        codexFailed: t.messages.codexFailed,
        codexStart: t.messages.codexStart,
        codexDone: t.messages.codexDone,
        subagentStart: t.messages.subagentStart,
        subagentDone: t.messages.subagentDone,
        verificationDone: t.messages.verificationDone,
        stageReady: t.messages.stageReady,
        runInit: t.messages.runInit,
        patchsetReady: t.messages.patchsetReady,
        awaitingReview: t.messages.awaitingReview,
        applyStart: t.messages.applyStart,
        applyDone: t.messages.applyDone,
        discardDone: t.messages.discardDone,
        runDone: t.messages.runDone,
        stepRound: t.messages.stepRound,
        stepRoundRunning: t.messages.stepRoundRunning,
        running: t.messages.running
      }),
    [events, unifiedStatus, t]
  );
  const currentStep = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const stepId = getEventStepId(events[i]);
      if (stepId) return stepId;
    }
    return "step-01";
  }, [events]);
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
        const message = err instanceof Error ? err.message : t.messages.loadPlanFailed;
        if (active) setPlanError(message || t.messages.loadPlanFailed);
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
        const message = err instanceof Error ? err.message : t.messages.loadPatchsetFailed;
        if (active) setReviewError(message || t.messages.loadPatchsetFailed);
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
        const summaryPath = items.find((item) =>
          item.path.endsWith(language === "en" ? "failure_reason_en.txt" : "failure_reason_zh.txt")
        )?.path;
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
        const message = err instanceof Error ? err.message : t.messages.loadFailureDetailFailed;
        if (active) setFailureError(message || t.messages.loadFailureDetailFailed);
      }
    })();
    return () => {
      active = false;
    };
  }, [failed, runId, planId]);

  function handleInlineRework(stepId: string | null) {
    if (!stepId) {
      setInlineNotice(t.messages.reworkNeedStep);
      return;
    }
    setInlineNotice(t.messages.reworkPrepared.replace("{stepId}", stepId));
    setReworkFeedback((prev) => prev || `${t.buttons.rework}: ${stepId}`);
  }

  async function handleApply() {
    setActionLoading(true);
    setReviewError(null);
    try {
      if (!window.confirm(t.messages.confirmApply)) {
        setActionLoading(false);
        return;
      }
      await applyRun(runId, planId);
      removePendingReview(runId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.applyFailed;
      setReviewError(message || t.messages.applyFailed);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteRun() {
    if (!window.confirm(t.messages.confirmDeleteRun)) {
      return;
    }
    setActionLoading(true);
    setReviewError(null);
    try {
      await deleteRun(runId, planId);
      onBack();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setReviewError(message || t.messages.deleteFailed);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!window.confirm(t.messages.confirmCancelRun)) return;
    setActionLoading(true);
    setReviewError(null);
    try {
      await cancelRun(runId, planId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.cancelFailed;
      setReviewError(message || t.messages.cancelFailed);
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
      const message = err instanceof Error ? err.message : t.messages.retryFailed;
      setReviewError(message || t.messages.retryFailed);
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
      const message = err instanceof Error ? err.message : t.messages.reworkFailed;
      setReviewError(message || t.messages.reworkFailed);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDiscard() {
    setActionLoading(true);
    setReviewError(null);
    try {
      await discardRun(runId, planId);
      removePendingReview(runId);
      const refreshed = await getRun(runId, planId);
      setRun(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.discardFailed;
      setReviewError(message || t.messages.discardFailed);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleOpenChangedFile(filePath: string) {
    setReviewError(null);
    try {
      await openRunFile(runId, filePath, planId);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.openFileFailed;
      setReviewError(message || t.messages.openFileFailed);
    }
  }

  return (
    <section className="stack">
      <RunActionBar
        onBack={onBack}
        onDeleteRun={handleDeleteRun}
        onCancel={handleCancel}
        onRetry={handleRetry}
        actionLoading={actionLoading}
        isRunning={isRunning}
        canRetry={canRetry}
        retryMenuOpen={retryMenuOpen}
        onToggleRetryMenu={() => setRetryMenuOpen((prev) => !prev)}
        streamState={streamState}
        error={error}
        inlineNotice={inlineNotice}
      />
      {autoPrompt && (
        <div className="banner success">{t.messages.runCompletedApplyHint}</div>
      )}
      <RunInfoCard
        runId={runId}
        planId={resolvedPlanId}
        unifiedStatus={unifiedStatus}
        statusText={statusText}
        workflowStage={workflowStage}
        policy={runInfo?.policy || "-"}
        task={task}
        updated={updated || "-"}
      />
      {hasPlanId && (
        <div className="card">
          <h2>{t.titles.taskChainProgress}</h2>
          {planLoading && <div className="muted">{t.messages.taskChainLoading}</div>}
          {planError && <div className="error">{planError}</div>}
          {!planLoading && planTasks.length > 0 && (
            <>
              <div className="progress large">
                <div className="progress-bar" style={{ width: `${taskProgress}%` }} />
              </div>
              <div className="row">
                <span className="pill">{taskProgress}%</span>
                <span className="pill subtle">{t.labels.tasksDone} {taskStats.done}/{taskStats.total}</span>
                {taskStats.doing > 0 && <span className="pill warn">{t.labels.tasksDoing} {taskStats.doing}</span>}
                {taskStats.failed > 0 && <span className="pill error">{t.labels.tasksFailed} {taskStats.failed}</span>}
              </div>
              <div className="list">
                {planTasks.map((taskItem, idx) => {
                  const taskId = taskItem.step_id || taskItem.id || taskItem.task_id || `task-${idx + 1}`;
                  const title = taskItem.title || taskItem.name || `${t.labels.task} ${idx + 1}`;
                  const status = String(taskItem.status || "todo").toLowerCase();
                  const statusLabel = t.status[status as keyof typeof t.status] || status;
                  return (
                    <div key={taskId} className="list-item task-item">
                      <div>
                        <div className="title">{title}</div>
                        <div className="meta">{t.labels.taskId} {taskId}</div>
                        {taskItem.description && <div className="meta">{taskItem.description}</div>}
                      </div>
                      <div className={`pill ${status}`}>{statusLabel}</div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
          {!planLoading && planTasks.length === 0 && !planError && (
            <div className="muted">{t.messages.taskChainEmptyData}</div>
          )}
        </div>
      )}
      {awaitingReview && (
        <div className="card">
          <h2>{t.titles.reviewApply}</h2>
          {reviewLoading && <div className="muted">{t.messages.reviewLoading}</div>}
          {reviewError && <div className="error">{reviewError}</div>}
          {changedFiles.length > 0 && (
            <div className="list">
              {changedFiles.map((item, idx) => (
                <div key={`${item.path}-${idx}`} className="list-item">
                  <button className="file-link" onClick={() => handleOpenChangedFile(item.path)}>
                    {item.path}
                  </button>
                  <div className="pill">{item.status}</div>
                </div>
              ))}
            </div>
          )}
          {patchsetText && <DiffViewer diffText={patchsetText} changedFiles={changedFiles} />}
          <div className="row">
            <button onClick={handleApply} disabled={actionLoading}>{t.buttons.applyReview}</button>
            <button onClick={handleDiscard} disabled={actionLoading}>{t.buttons.discardChanges}</button>
          </div>
        </div>
      )}

      {failed && (
        <div className="card">
          <h2>{t.titles.rework}</h2>
          {failureError && <div className="error">{failureError}</div>}
          {failureInfo?.summaryText && <pre className="pre">{failureInfo.summaryText}</pre>}
          {failureInfo?.reasons && failureInfo.reasons.length > 0 && (
            <VerificationReasons reasons={failureInfo.reasons} />
          )}
          {failureInfo?.reportText && <pre className="pre">{failureInfo.reportText}</pre>}
          <textarea
            className="textarea"
            placeholder={t.messages.reworkFeedbackPlaceholder}
            value={reworkFeedback}
            onChange={(e) => setReworkFeedback(e.target.value)}
            rows={3}
          />
          <div className="row">
            <button onClick={handleRework} disabled={actionLoading}>{t.buttons.reworkStep}</button>
          </div>
        </div>
      )}
      <div className="card">
        <h2>{t.titles.events}</h2>
        <EventTimeline
          events={events}
          streamState={streamState}
          autoScroll
          emptyLabel={streamState === "disconnected" ? t.messages.eventStreamDisconnected : undefined}
          onRework={handleInlineRework}
        />
      </div>
    </section>
  );
}
