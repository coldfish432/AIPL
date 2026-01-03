import React, { useCallback, useEffect, useRef, useState } from "react";
import { assistantChat, assistantConfirm, assistantPlan, discardRun, getPlan, getRun, listRuns } from "../apiClient";
import ChatSidebar from "../components/ChatSidebar";
import ChatPanel from "../components/ChatPanel";
import QueuePanel from "../components/QueuePanel";
import { PlanLockStatus } from "../components/PlanLockStatus";
import PilotComposer from "./pilot/PilotComposer";
import PilotHeader from "./pilot/PilotHeader";
import { useQueue, QueueItem, QueueStatus } from "../hooks/useQueue";
import { usePlanLock } from "../hooks/usePlanLock";
import { useSession, ChatMessage, appendStoredMessage, getStoredSession, setStoredPending, updateStoredSession } from "../hooks/useSession";
import { useVisibilityPolling } from "../hooks/useVisibilityPolling";
import { resolveStatus, isFinished } from "../lib/status";
import { useI18n } from "../lib/useI18n";
import { STORAGE_KEYS } from "../config/settings";
import { useNavigate } from "react-router-dom";

const BASE_WORKSPACE_KEY = STORAGE_KEYS.baseWorkspaceKey;

function makeRequestId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function buildTextFromTasks(
  tasks: Array<{ step_id?: string; id?: string; title?: string; dependencies?: string[] }>,
  labels: { taskChain: string; task: string; dependencies: string; taskChainEmpty: string }
): string {
  if (!Array.isArray(tasks) || tasks.length === 0) {
    return labels.taskChainEmpty;
  }
  const lines = tasks.map((task, idx) => {
    const stepId = task.step_id || task.id || `task-${idx + 1}`;
    const title = task.title || `${labels.task} ${idx + 1}`;
    const deps = Array.isArray(task.dependencies) && task.dependencies.length > 0 ? task.dependencies.join(", ") : "-";
    return `${idx + 1}. ${title} [${stepId}] (${labels.dependencies}: ${deps})`;
  });
  return [`${labels.taskChain}:`, ...lines].join("\n");
}

function normalizeWorkspaceCandidate(value?: string): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const norm = trimmed.replace(/\\/g, "/").toLowerCase();
  if (norm.includes("artifacts/") && (norm.includes("/stages/") || norm.includes("/runs/") || norm.endsWith("/stage"))) {
    return undefined;
  }
  return trimmed;
}

export default function Pilot() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const {
    lock,
    canStartNewPlan,
    lockForPlan,
    addPendingReview,
    removePendingReview,
    completeWithoutReview,
    forceUnlock
  } = usePlanLock();
  const {
    sessions,
    activeSession,
    activeId,
    setActiveId,
    createNewSession,
    deleteSession,
    renameSession
  } = useSession();
  const { queue, paused, setPaused, updateItem, updateQueue, cancelAll, clearQueue } = useQueue();

  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [policy, setPolicy] = useState(() => localStorage.getItem(STORAGE_KEYS.policyKey) || "guarded");
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [baseWorkspace, setBaseWorkspace] = useState(() => localStorage.getItem(BASE_WORKSPACE_KEY) || "");

  const queueRef = useRef(queue);
  const workspaceRef = useRef(workspace);
  const policyRef = useRef(policy);
  const pausedRef = useRef(paused);
  const baseWorkspaceRef = useRef(baseWorkspace);

  const pending = activeSession?.pending ?? null;
  const loading = Boolean(pending);
  const loadingKind = pending?.kind ?? null;
  const canSend = input.trim().length > 0 && !loading;
  const isLocked = lock.status !== "idle";

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(() => {
    workspaceRef.current = workspace;
    const trimmed = workspace.trim();
    if (trimmed) {
      localStorage.setItem(STORAGE_KEYS.workspaceKey, trimmed);
    } else {
      localStorage.removeItem(STORAGE_KEYS.workspaceKey);
    }
    window.dispatchEvent(new Event("aipl-workspace-changed"));
  }, [workspace]);

  useEffect(() => {
    policyRef.current = policy;
    localStorage.setItem(STORAGE_KEYS.policyKey, policy);
  }, [policy]);

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  useEffect(() => {
    baseWorkspaceRef.current = baseWorkspace;
    localStorage.setItem(BASE_WORKSPACE_KEY, baseWorkspace);
  }, [baseWorkspace]);

  useEffect(() => {
    const syncWorkspace = () => {
      setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  const enqueuePlan = useCallback(
    (planId: string, planText: string, session?: typeof activeSession | null) => {
      const allowed = canStartNewPlan();
      if (!allowed.allowed) {
        setError(allowed.reason || t.messages.planLocked);
        return;
      }
      updateQueue((prev) => {
        const exists = prev.some((item) => item.planId === planId && !["failed", "canceled"].includes(item.status));
        if (exists) return prev;
        const base =
          normalizeWorkspaceCandidate(baseWorkspaceRef.current) ||
          normalizeWorkspaceCandidate(workspaceRef.current.trim());
        if (!baseWorkspaceRef.current && base) {
          setBaseWorkspace(base);
        }
        const item: QueueItem = {
          id: `queue-${Date.now()}`,
          planId,
          planText,
          status: "queued",
          queuedAt: Date.now(),
          baseWorkspace: base || undefined,
          chatId: session?.id,
          chatTitle: session?.title
        };
        const nextQueue = prev.concat(item);
        setTimeout(() => {
          void startNextQueued(nextQueue);
        }, 0);
        return nextQueue;
      });
    },
    [canStartNewPlan, t.messages.planLocked, updateQueue]
  );

  const resolveRunIdFromList = useCallback(async (planId: string | undefined) => {
    if (!planId) return undefined;
    try {
      const runs = await listRuns();
      const match = runs.find((run) => (run.plan_id || run.planId) === planId);
      return match ? (match.run_id || match.runId) : undefined;
    } catch {
      return undefined;
    }
  }, []);

  const startNextQueued = useCallback(async (queueOverride?: QueueItem[]) => {
    if (pausedRef.current) return;
    const currentQueue = queueOverride || queueRef.current;
    if (currentQueue.some((item) => ["running", "starting", "retrying"].includes(item.status))) {
      return;
    }
    const next = currentQueue.find((item) => item.status === "queued");
    if (!next) return;
    lockForPlan(next.planId);
    updateItem(next.id, (item) => ({ ...item, status: "starting", startedAt: Date.now() }));
    try {
      const workspaceBase =
        normalizeWorkspaceCandidate(next.baseWorkspace) ||
        normalizeWorkspaceCandidate(baseWorkspaceRef.current) ||
        normalizeWorkspaceCandidate(workspaceRef.current.trim()) ||
        undefined;
      const res = await assistantConfirm({
        planId: next.planId,
        workspace: workspaceBase,
        mode: "autopilot",
        policy: policyRef.current
      });
      let runId = res.run_id || res.runId;
      if (!runId) {
        runId = await resolveRunIdFromList(next.planId);
      }
      if (workspaceBase) {
        setBaseWorkspace(workspaceBase);
      }
      if (!runId) {
        setError(t.messages.startRunFailedNoId);
        updateItem(next.id, (item) => ({ ...item, status: "failed", finishedAt: Date.now() }));
        forceUnlock();
        return;
      }
        updateItem(next.id, (item) => ({ ...item, status: "running", runId, reviewStatus: null }));
      try {
        const runRes = await getRun(runId, next.planId);
        const unified = resolveStatus(runRes.run?.status || runRes.status || runRes.state || "running");
        updateItem(next.id, (item) => ({
          ...item,
          status: unified.execution as QueueStatus,
          reviewStatus: unified.review,
          finishedAt: isFinished(unified.execution) ? Date.now() : item.finishedAt
        }));
        if (isFinished(unified.execution)) {
          if (unified.review === "pending" && runId) {
            addPendingReview(runId);
          } else {
            completeWithoutReview();
          }
        }
      } catch {
        // ignore immediate refresh errors
      }
    } catch {
      const fallbackRunId = await resolveRunIdFromList(next.planId);
      if (fallbackRunId) {
        updateItem(next.id, (item) => ({ ...item, status: "running", runId: fallbackRunId, reviewStatus: null }));
        return;
      }
      updateItem(next.id, (item) => ({ ...item, status: "failed", reviewStatus: null, finishedAt: Date.now() }));
      forceUnlock();
    }
  }, [addPendingReview, completeWithoutReview, forceUnlock, lockForPlan, resolveRunIdFromList, updateItem]);

  const pollQueue = useCallback(async () => {
    const currentQueue = queueRef.current;
    const activeItems = currentQueue.filter((item) => ["running", "starting", "retrying", "failed", "canceled", "discarded"].includes(item.status));
    let runsCache: Array<{ run_id?: string; runId?: string; plan_id?: string; planId?: string }> | null = null;
    const resolveRunId = async (planId: string) => {
      if (!runsCache) {
        runsCache = await listRuns().catch(() => []);
      }
      const match = runsCache.find((run) => (run.plan_id || run.planId) === planId);
      return match ? (match.run_id || match.runId) : undefined;
    };

    for (const item of activeItems) {
      let runId = item.runId;
      let latestRunId: string | undefined;
      if (item.planId) {
        latestRunId = await resolveRunId(item.planId);
      }
      if (latestRunId && latestRunId != runId) {
        runId = latestRunId;
        updateItem(item.id, (q) => ({ ...q, runId, status: "retrying", reviewStatus: null, finishedAt: undefined }));
        continue;
      }
      if (!runId) continue;
      try {
        const res = await getRun(runId, item.planId);
        const resAny = res as { ok?: boolean; error?: string };
        if (resAny.ok === false || (resAny.error || "").toLowerCase().includes("not found")) {
          updateItem(item.id, (q) => ({ ...q, status: "failed", finishedAt: Date.now() }));
          continue;
        }
        let snapshotTasks: Array<{ status?: string }> = [];
        if (item.planId) {
          try {
            snapshotTasks = (await getPlan(item.planId))?.snapshot?.tasks || [];
          } catch {
            snapshotTasks = [];
          }
        }
        const unified = resolveStatus(res.run?.status || res.status || res.state || "running", snapshotTasks);
        const mainRoot = res.run?.workspace_main_root || res.workspace_main_root;
        if (mainRoot) {
          setBaseWorkspace(mainRoot);
        }
        updateItem(item.id, (q) => ({
          ...q,
          runId,
          status: unified.execution as QueueStatus,
          reviewStatus: unified.review,
          finishedAt: isFinished(unified.execution) ? Date.now() : q.finishedAt
        }));
        if (isFinished(unified.execution) && item.planId === lock.activePlanId) {
          if (unified.review === "pending" && runId) {
            addPendingReview(runId);
          } else {
            completeWithoutReview();
          }
        }
      } catch {
        updateItem(item.id, (q) => ({ ...q, status: "failed", reviewStatus: null, finishedAt: Date.now() }));
      }
    }

    if (!pausedRef.current) {
      const stillRunning = currentQueue.some((item) => ["running", "starting", "retrying"].includes(item.status));
      const hasQueued = currentQueue.some((item) => item.status === "queued");
      if (!stillRunning && hasQueued) {
        void startNextQueued();
      }
    }
  }, [addPendingReview, completeWithoutReview, lock.activePlanId, startNextQueued, updateItem]);

  useVisibilityPolling(() => {
    void pollQueue();
  }, 5000, true);

  async function createPlanFromConversation(messageList: ChatMessage[]): Promise<{ planId: string | null; planText: string } | null> {
    if (!activeSession) {
      setError(t.messages.needCreateChat);
      return null;
    }
    const allowed = canStartNewPlan();
    if (!allowed.allowed) {
      setError(allowed.reason || t.messages.planLocked);
      return null;
    }
    if (messageList.length === 0) {
      setError(t.messages.needDescribeTask);
      return null;
    }
    const sessionId = activeSession.id;
    const requestId = makeRequestId();
    setStoredPending(sessionId, { kind: "plan", startedAt: Date.now(), requestId });
    setError(null);
    try {
      const payloadMessages = [
        { role: "system", content: t.prompts.systemLanguage },
        ...messageList.map((msg) => ({ role: msg.role, content: msg.content }))
      ];
      const res = await assistantPlan({ messages: payloadMessages, workspace: workspaceRef.current.trim() || undefined });
      const nextPlanId = res.plan_id || res.planId || null;
      let planTextValue = "";
      if (nextPlanId) {
        const planDetail = await getPlan(nextPlanId);
        const fallbackText = buildTextFromTasks(
          planDetail?.snapshot?.tasks || planDetail?.plan?.raw_plan?.tasks || [],
          {
            taskChain: t.labels.taskChain,
            task: t.labels.task,
            dependencies: t.labels.dependencies,
            taskChainEmpty: t.messages.taskChainEmpty
          }
        );
        planTextValue = planDetail?.task_chain_text || planDetail?.plan?.task_chain_text || fallbackText;
      }
      const summary = [
        nextPlanId ? `${t.messages.planGenerated}: ${nextPlanId}` : t.messages.planGeneratedNoId,
        planTextValue || t.messages.taskChainEmpty
      ].join("\n");
      const current = getStoredSession(sessionId);
      if (!current?.pending || current.pending.requestId !== requestId) {
        return null;
      }
      updateStoredSession(sessionId, (session) => ({
        ...session,
        planId: nextPlanId,
        planText: planTextValue,
        pendingPlanMessages: null,
        awaitingConfirm: false,
        finalPlanText: "",
        messages: session.messages.concat({ role: "assistant", content: summary, kind: "plan", planId: nextPlanId }),
        updatedAt: Date.now()
      }));
      return { planId: nextPlanId, planText: planTextValue };
    } catch (err) {
      const current = getStoredSession(sessionId);
      if (current?.pending?.requestId === requestId) {
        const messageText = err instanceof Error ? err.message : t.messages.planFailed;
        setError(messageText || t.messages.planFailed);
      }
      return null;
    } finally {
      const current = getStoredSession(sessionId);
      if (current?.pending?.requestId === requestId) {
        setStoredPending(sessionId, null);
      }
    }
  }

  async function handleSend() {
    if (!canSend || !activeSession) return;
    const message = input.trim();
    const sessionId = activeSession.id;
    const requestId = makeRequestId();
    setInput("");
    appendStoredMessage(sessionId, { role: "user", content: message, kind: "text" });
    setStoredPending(sessionId, { kind: "chat", startedAt: Date.now(), requestId });
    setError(null);
    try {
      const payloadMessages = activeSession.messages.concat({ role: "user", content: message });
      const res = await assistantChat({
        messages: [
          { role: "system", content: t.prompts.systemLanguage },
          ...payloadMessages.map((msg) => ({ role: msg.role, content: msg.content }))
        ],
        workspace: workspaceRef.current.trim() || undefined,
        policy: policyRef.current
      });
      const current = getStoredSession(sessionId);
      if (!current?.pending || current.pending.requestId !== requestId) {
        return;
      }
      const reply = res.reply || res.message || "OK";
      appendStoredMessage(sessionId, { role: "assistant", content: reply, kind: "text" });
    } catch (err) {
      const current = getStoredSession(sessionId);
      if (current?.pending?.requestId === requestId) {
        const messageText = err instanceof Error ? err.message : t.messages.chatFailed;
        setError(messageText || t.messages.chatFailed);
      }
    } finally {
      const current = getStoredSession(sessionId);
      if (current?.pending?.requestId === requestId) {
        setStoredPending(sessionId, null);
      }
    }
  }

  async function handleStartFlow() {
    if (!activeSession) {
      setError(t.messages.needCreateChat);
      return;
    }
    const allowed = canStartNewPlan();
    if (!allowed.allowed) {
      setError(allowed.reason || t.messages.planLocked);
      return;
    }
    let nextMessages = activeSession.messages;
    const draft = input.trim();
    if (draft) {
      const appended = activeSession.messages.concat({ role: "user", content: draft, kind: "text" });
      nextMessages = appended;
      updateStoredSession(activeSession.id, (session) => ({
        ...session,
        messages: appended,
        updatedAt: Date.now(),
        title: /^(对话|Chat)\s+\d+$/.test(session.title) && draft ? draft.slice(0, 20) : session.title
      }));
      setInput("");
    }
    if (nextMessages.length === 0) {
      setError(t.messages.needDescribeTask);
      return;
    }
    const lastUser = [...nextMessages].reverse().find((msg) => msg.role === "user");
    updateStoredSession(activeSession.id, (session) => ({
      ...session,
      messages: session.messages.filter((msg) => msg.kind !== "confirm").concat({
        role: "assistant",
        content: t.messages.finalPlanPrompt,
        kind: "confirm"
      }),
      pendingPlanMessages: nextMessages,
      awaitingConfirm: true,
      finalPlanText: lastUser?.content || "",
      updatedAt: Date.now()
    }));
  }

  async function confirmPlan() {
    if (!activeSession) return;
    const allowed = canStartNewPlan();
    if (!allowed.allowed) {
      setError(allowed.reason || t.messages.planLocked);
      return;
    }
    const pendingPlan = activeSession.pendingPlanMessages;
    if (!pendingPlan) {
      updateStoredSession(activeSession.id, (session) => ({
        ...session,
        pendingPlanMessages: null,
        awaitingConfirm: false,
        finalPlanText: ""
      }));
      return;
    }
    const trimmed = (activeSession.finalPlanText || "").trim();
    const merged = trimmed
      ? pendingPlan.concat({ role: "user", content: `${t.prompts.finalPlanPrefix}${trimmed}`, kind: "text" })
      : pendingPlan;
    await createPlanFromConversation(merged);
  }

  function cancelPlan() {
    if (!activeSession) return;
    updateStoredSession(activeSession.id, (session) => ({
      ...session,
      pendingPlanMessages: null,
      awaitingConfirm: false,
      finalPlanText: ""
    }));
  }

  const handleUpdateFinalPlan = (value: string) => {
    if (!activeSession) return;
    updateStoredSession(activeSession.id, (session) => ({
      ...session,
      finalPlanText: value
    }));
  };

  const handleGoToReview = useCallback(() => {
    if (lock.activePlanId) {
      navigate(`/plans/${lock.activePlanId}`);
    }
  }, [lock.activePlanId, navigate]);

  const handleForceUnlock = useCallback(async () => {
    if (!lock.activePlanId) return;
    const confirmed = window.confirm(
      `确定要丢弃任务链 ${lock.activePlanId} 的所有待审核任务吗？`
    );
    if (!confirmed) return;
    for (const runId of lock.pendingReviewRuns) {
      try {
        await discardRun(runId, lock.activePlanId || undefined);
        removePendingReview(runId);
      } catch {
        // ignore discard failures
      }
    }
    forceUnlock();
  }, [forceUnlock, lock.activePlanId, lock.pendingReviewRuns, removePendingReview]);

  const handleTerminatePending = (sessionId?: string | null) => {
    if (!sessionId) return;
    setStoredPending(sessionId, null);
  };

  return (
    <section className="stack">
      <div className="card">
        <h2>{t.titles.pilot}</h2>
        <PlanLockStatus lock={lock} onGoToReview={handleGoToReview} onForceUnlock={handleForceUnlock} />
        <PilotHeader
          workspace={workspace}
          policy={policy}
          onPolicyChange={setPolicy}
          onStartFlow={handleStartFlow}
          onNewChat={createNewSession}
          loading={loading}
          confirmLoading={confirmLoading}
          locked={isLocked}
        />

        <div className="pilot-layout">
          <ChatSidebar
            sessions={sessions}
            activeId={activeId}
            onSelect={setActiveId}
            onRename={renameSession}
            onDelete={(id) => {
              if (!window.confirm(t.messages.confirmDeleteChat)) return;
              handleTerminatePending(id);
              deleteSession(id);
            }}
          />

          <div className="pilot-main">
            <ChatPanel
              session={activeSession}
              loading={loading}
              confirmLoading={confirmLoading}
              onEnqueuePlan={(planId, planText) => enqueuePlan(planId, planText, activeSession)}
              onStartFlow={handleStartFlow}
              onConfirmPlan={confirmPlan}
              onCancelPlan={cancelPlan}
              onUpdateFinalPlan={handleUpdateFinalPlan}
            />

            <QueuePanel
              queue={queue}
              paused={paused}
              onPauseToggle={() => setPaused(!paused)}
              onTerminate={cancelAll}
              onClear={clearQueue}
            />

            <PilotComposer
              input={input}
              onInputChange={setInput}
              onSend={handleSend}
              canSend={canSend && !isLocked}
              loading={loading}
              loadingKind={loadingKind}
              error={error}
              onTerminate={() => handleTerminatePending(activeSession?.id)}
              disabled={isLocked}
              placeholder={isLocked ? "请先完成当前任务链的审核..." : undefined}
            />
          </div>
        </div>
      </div>
      {activeSession?.planId && (
        <div className="card">
          <h2>{t.titles.planPreview}</h2>
          <pre className="pre">{activeSession.planText || t.messages.taskChainEmpty}</pre>
        </div>
      )}
    </section>
  );
}
