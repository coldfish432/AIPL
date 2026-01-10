import React, { useCallback, useEffect, useRef, useState } from "react";
import { assistantChat, assistantConfirm, assistantPlan, discardRun, getPlan, getRun, listRuns } from "../apiClient";
import ChatSidebar from "../components/ChatSidebar";
import ChatPanel from "../components/ChatPanel";
import { PlanLockStatus } from "../components/PlanLockStatus";
import PilotComposer from "./pilot/PilotComposer";
import PilotHeader from "./pilot/PilotHeader";
import { usePlanLock } from "../hooks/usePlanLock";
import { useSession, ChatMessage as SessionChatMessage, ChatSession, appendStoredMessage, getStoredSession, setStoredPending, updateStoredSession } from "../hooks/useSession";
import { useVisibilityPolling } from "../hooks/useVisibilityPolling";
import { resolveStatus, isFinished } from "../lib/status";
import { useI18n } from "../lib/useI18n";
import { STORAGE_KEYS } from "../config/settings";
import { useNavigate } from "react-router-dom";
import type { ChatMessage as ApiChatMessage } from "../apiClient";

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

function toApiMessage(message: SessionChatMessage): ApiChatMessage {
  return {
    role: message.role,
    content: message.content
  };
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
    forceUnlock,
    setActiveRunId
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

  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [baseWorkspace, setBaseWorkspace] = useState(() => localStorage.getItem(BASE_WORKSPACE_KEY) || "");
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  const workspaceRef = useRef(workspace);
  const baseWorkspaceRef = useRef(baseWorkspace);
  const currentRunIdRef = useRef(currentRunId);

  const pending = activeSession?.pending ?? null;
  const loading = Boolean(pending);
  const loadingKind = pending?.kind ?? null;
  const canSend = input.trim().length > 0 && !loading;
  const isLocked = lock.status !== "idle";

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
    currentRunIdRef.current = currentRunId;
  }, [currentRunId]);

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

  const startPlanExecution = useCallback(async (planId: string) => {
    setError(null);
    const allowed = canStartNewPlan();
    if (!allowed.allowed) {
      setError(allowed.reason || t.messages.planLocked);
      return;
    }
    lockForPlan(planId);
    const candidate =
      normalizeWorkspaceCandidate(baseWorkspaceRef.current) ||
      normalizeWorkspaceCandidate(workspaceRef.current.trim());
    if (candidate) {
      setBaseWorkspace(candidate);
    }
    try {
      const workspaceBase = candidate || undefined;
      const res = await assistantConfirm({
        planId,
        workspace: workspaceBase,
        mode: "autopilot"
      });
      let runId = res.run_id || res.runId;
      if (!runId) {
        runId = await resolveRunIdFromList(planId);
      }
      if (!runId) {
        // eslint-disable-next-line no-throw-literal
        throw new Error(t.messages.startRunFailedNoId);
      }
      setCurrentRunId(runId);
      setActiveRunId(runId);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.planFailed;
      setError(message || t.messages.planFailed);
      forceUnlock();
      setCurrentRunId(null);
    }
  }, [
    canStartNewPlan,
    forceUnlock,
    lockForPlan,
    resolveRunIdFromList,
    setActiveRunId,
    t.messages.planFailed,
    t.messages.planLocked,
    t.messages.startRunFailedNoId
  ]);

  const pollCurrentRun = useCallback(async () => {
    const runId = currentRunIdRef.current;
    if (!runId) return;
    const planId = lock.activePlanId || undefined;
    try {
      const res = await getRun(runId, planId);
      const errResponse = res as { ok?: boolean; error?: string };
      if (errResponse.ok === false || (errResponse.error || "").toLowerCase().includes("not found")) {
        setError(t.messages.planLocked);
        forceUnlock();
        setCurrentRunId(null);
        return;
      }
      let snapshotTasks: Array<{ status?: string }> = [];
      if (planId) {
        try {
          snapshotTasks = (await getPlan(planId))?.snapshot?.tasks || [];
        } catch {
          snapshotTasks = [];
        }
      }
      const unified = resolveStatus(res.run?.status || res.status || res.state || "running", snapshotTasks);
      const mainRoot = res.run?.workspace_main_root || res.workspace_main_root;
      if (mainRoot) {
        setBaseWorkspace(mainRoot);
      }
      if (isFinished(unified.execution)) {
        if (unified.review === "pending") {
          addPendingReview(runId);
        } else {
          completeWithoutReview();
        }
        setCurrentRunId(null);
      }
    } catch {
      // swallow transient failures
    }
  }, [addPendingReview, completeWithoutReview, forceUnlock, lock.activePlanId, resolveStatus, t.messages.planLocked]);

  useVisibilityPolling(() => {
    void pollCurrentRun();
  }, 5000, true);

  async function createPlanFromConversation(messageList: SessionChatMessage[]): Promise<{ planId: string | null; planText: string } | null> {
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
      const payloadMessages: ApiChatMessage[] = [
        { role: "system", content: t.prompts.systemLanguage },
        ...messageList.map(toApiMessage)
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
    const userMessage: SessionChatMessage = { role: "user", content: message, kind: "text" };
    appendStoredMessage(sessionId, userMessage);
    setStoredPending(sessionId, { kind: "chat", startedAt: Date.now(), requestId });
    setError(null);
    try {
      const payloadMessages = activeSession.messages.concat(userMessage);
      const res = await assistantChat({
        messages: [
          { role: "system", content: t.prompts.systemLanguage },
          ...payloadMessages.map(toApiMessage)
        ],
        workspace: workspaceRef.current.trim() || undefined
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
    setCurrentRunId(null);
  }, [forceUnlock, lock.activePlanId, lock.pendingReviewRuns, removePendingReview]);

  const handleTerminatePending = (sessionId?: string | null) => {
    if (!sessionId) return;
    setStoredPending(sessionId, null);
  };

  const handleStartRun = useCallback(
    (planId: string, planText: string) => {
      void startPlanExecution(planId);
    },
    [startPlanExecution]
  );

  return (
    <section className="stack">
      <div className="card">
        <h2>{t.titles.pilot}</h2>
        <PlanLockStatus lock={lock} onGoToReview={handleGoToReview} onForceUnlock={handleForceUnlock} />
        <PilotHeader
          workspace={workspace}
          onStartFlow={handleStartFlow}
          onNewChat={createNewSession}
          loading={loading}
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
            {workspace && (
              <div className="pilot-workspace-hint">
                <span>{t.messages.workspaceIntro}</span>
                <strong>{workspace}</strong>
              </div>
            )}
            <ChatPanel
              session={activeSession}
              loading={loading}
              onStartRun={handleStartRun}
              locked={isLocked}
              onStartFlow={handleStartFlow}
              onConfirmPlan={confirmPlan}
              onCancelPlan={cancelPlan}
              onUpdateFinalPlan={handleUpdateFinalPlan}
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
