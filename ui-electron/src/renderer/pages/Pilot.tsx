import React, { useCallback, useEffect, useRef, useState } from "react";
import { assistantChat, assistantConfirm, assistantPlan, getPlan, getRun, listRuns } from "../apiClient";
import ChatSidebar from "../components/ChatSidebar";
import ChatPanel from "../components/ChatPanel";
import QueuePanel from "../components/QueuePanel";
import { useQueue, QueueItem, QueueStatus } from "../hooks/useQueue";
import { useSession, ChatMessage } from "../hooks/useSession";
import { useVisibilityPolling } from "../hooks/useVisibilityPolling";
import { resolveStatus, isFinished } from "../lib/status";

const BASE_WORKSPACE_KEY = "aipl.pilot.baseWorkspace";

function buildTextFromTasks(tasks: Array<{ step_id?: string; id?: string; title?: string; dependencies?: string[] }>): string {
  if (!Array.isArray(tasks) || tasks.length === 0) {
    return "任务链：(空)";
  }
  const lines = tasks.map((task, idx) => {
    const stepId = task.step_id || task.id || `task-${idx + 1}`;
    const title = task.title || `任务 ${idx + 1}`;
    const deps = Array.isArray(task.dependencies) && task.dependencies.length > 0 ? task.dependencies.join(", ") : "-";
    return `${idx + 1}. ${title} [${stepId}] (依赖: ${deps})`;
  });
  return ["任务链：", ...lines].join("\n");
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
  const {
    sessions,
    activeSession,
    activeId,
    setActiveId,
    createNewSession,
    updateSession,
    deleteSession,
    renameSession,
    addMessage
  } = useSession();
  const { queue, paused, setPaused, updateItem, updateQueue, cancelAll, clearQueue } = useQueue();

  const [workspace, setWorkspace] = useState(() => localStorage.getItem("aipl.workspace") || "");
  const [policy, setPolicy] = useState(() => localStorage.getItem("aipl.policy") || "guarded");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingKind, setLoadingKind] = useState<"chat" | "plan" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [baseWorkspace, setBaseWorkspace] = useState(() => localStorage.getItem(BASE_WORKSPACE_KEY) || "");

  const queueRef = useRef(queue);
  const workspaceRef = useRef(workspace);
  const policyRef = useRef(policy);
  const pausedRef = useRef(paused);
  const baseWorkspaceRef = useRef(baseWorkspace);

  const canSend = input.trim().length > 0 && !loading;

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(() => {
    workspaceRef.current = workspace;
    const trimmed = workspace.trim();
    if (trimmed) {
      localStorage.setItem("aipl.workspace", trimmed);
    } else {
      localStorage.removeItem("aipl.workspace");
    }
    window.dispatchEvent(new Event("aipl-workspace-changed"));
  }, [workspace]);

  useEffect(() => {
    policyRef.current = policy;
    localStorage.setItem("aipl.policy", policy);
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
      setWorkspace(localStorage.getItem("aipl.workspace") || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  const enqueuePlan = useCallback(
    (planId: string, planText: string, session?: typeof activeSession | null) => {
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
    [updateQueue]
  );

  const startNextQueued = useCallback(async (queueOverride?: QueueItem[]) => {
    if (pausedRef.current) return;
    const currentQueue = queueOverride || queueRef.current;
    if (currentQueue.some((item) => ["running", "starting", "retrying"].includes(item.status))) {
      return;
    }
    const next = currentQueue.find((item) => item.status === "queued");
    if (!next) return;
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
      const runId = res.run_id || res.runId;
      if (workspaceBase) {
        setBaseWorkspace(workspaceBase);
      }
      if (!runId) {
        setError("启动执行失败：未返回 run_id");
        updateItem(next.id, (item) => ({ ...item, status: "failed", finishedAt: Date.now() }));
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
      } catch {
        // ignore immediate refresh errors
      }
    } catch {
      updateItem(next.id, (item) => ({ ...item, status: "failed", reviewStatus: null, finishedAt: Date.now() }));
    }
  }, [updateItem]);

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
  }, [startNextQueued, updateItem]);

  useVisibilityPolling(() => {
    void pollQueue();
  }, 5000, true);

  async function createPlanFromConversation(messageList: ChatMessage[]): Promise<{ planId: string | null; planText: string } | null> {
    if (!activeSession) {
      setError("请先创建对话。");
      return null;
    }
    setLoadingKind("plan");
    setLoading(true);
    setError(null);
    try {
      if (messageList.length === 0) {
        setError("请先在对话中描述任务。");
        return null;
      }
      const payloadMessages = messageList.map((msg) => ({ role: msg.role, content: msg.content }));
      const res = await assistantPlan({ messages: payloadMessages, workspace: workspaceRef.current.trim() || undefined });
      const nextPlanId = res.plan_id || res.planId || null;
      let planTextValue = "";
      if (nextPlanId) {
        const planDetail = await getPlan(nextPlanId);
        const fallbackText = buildTextFromTasks(planDetail?.snapshot?.tasks || planDetail?.plan?.raw_plan?.tasks || []);
        planTextValue = planDetail?.task_chain_text || planDetail?.plan?.task_chain_text || fallbackText;
      }
      const summary = [nextPlanId ? `计划已生成：${nextPlanId}` : "计划已生成。", planTextValue || "任务链：(空)"]
        .filter(Boolean)
        .join("\n");
      updateSession(activeSession.id, (session) => ({
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
      const messageText = err instanceof Error ? err.message : "生成计划失败";
      setError(messageText || "生成计划失败");
      return null;
    } finally {
      setLoading(false);
      setLoadingKind(null);
    }
  }

  async function handleSend() {
    if (!canSend || !activeSession) return;
    const message = input.trim();
    setInput("");
    addMessage(activeSession.id, { role: "user", content: message, kind: "text" });
    setLoadingKind("chat");
    setLoading(true);
    setError(null);
    try {
      const payloadMessages = activeSession.messages.concat({ role: "user", content: message });
      const res = await assistantChat({
        messages: payloadMessages.map((msg) => ({ role: msg.role, content: msg.content })),
        workspace: workspaceRef.current.trim() || undefined,
        policy: policyRef.current
      });
      const reply = res.reply || res.message || "OK";
      addMessage(activeSession.id, { role: "assistant", content: reply, kind: "text" });
    } catch (err) {
      const messageText = err instanceof Error ? err.message : "对话失败";
      setError(messageText || "对话失败");
    } finally {
      setLoading(false);
      setLoadingKind(null);
    }
  }

  async function handleStartFlow() {
    if (!activeSession) {
      setError("请先创建对话。");
      return;
    }
    let nextMessages = activeSession.messages;
    const draft = input.trim();
    if (draft) {
      const appended = activeSession.messages.concat({ role: "user", content: draft, kind: "text" });
      nextMessages = appended;
      updateSession(activeSession.id, (session) => ({
        ...session,
        messages: appended,
        updatedAt: Date.now(),
        title: session.title.startsWith("对话 ") && draft ? draft.slice(0, 20) : session.title
      }));
      setInput("");
    }
    if (nextMessages.length === 0) {
      setError("请先在对话中描述任务。");
      return;
    }
    const lastUser = [...nextMessages].reverse().find((msg) => msg.role === "user");
    updateSession(activeSession.id, (session) => ({
      ...session,
      messages: session.messages.filter((msg) => msg.kind !== "confirm").concat({
        role: "assistant",
        content: "请确认最终计划内容（可编辑）：",
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
    const pendingPlan = activeSession.pendingPlanMessages;
    if (!pendingPlan) {
      updateSession(activeSession.id, (session) => ({
        ...session,
        pendingPlanMessages: null,
        awaitingConfirm: false,
        finalPlanText: ""
      }));
      return;
    }
    const trimmed = (activeSession.finalPlanText || "").trim();
    const merged = trimmed
      ? pendingPlan.concat({ role: "user", content: `最终计划：${trimmed}`, kind: "text" })
      : pendingPlan;
    await createPlanFromConversation(merged);
  }

  function cancelPlan() {
    if (!activeSession) return;
    updateSession(activeSession.id, (session) => ({
      ...session,
      pendingPlanMessages: null,
      awaitingConfirm: false,
      finalPlanText: ""
    }));
  }

  const handleUpdateFinalPlan = (value: string) => {
    if (!activeSession) return;
    updateSession(activeSession.id, (session) => ({
      ...session,
      finalPlanText: value
    }));
  };

  return (
    <section className="stack">
      <div className="card">
        <h2>导航</h2>
        <div className="row">
          <div className="meta">工作区：{workspace || "-"}</div>
          <label className="pill-toggle">
            <span>策略</span>
            <select value={policy} onChange={(e) => setPolicy(e.target.value)}>
              <option value="safe">安全</option>
              <option value="guarded">守护</option>
              <option value="full">完全</option>
            </select>
          </label>
          <button onClick={handleStartFlow} disabled={loading || confirmLoading}>
            {loading ? "生成中..." : "开始流程"}
          </button>
          <button onClick={createNewSession} disabled={loading || confirmLoading}>新建对话</button>
        </div>

        <div className="pilot-layout">
          <ChatSidebar
            sessions={sessions}
            activeId={activeId}
            onSelect={setActiveId}
            onRename={renameSession}
            onDelete={(id) => {
              if (!window.confirm("确定删除这个对话吗？")) return;
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

            <div className="row">
              <textarea
                className="textarea"
                placeholder="描述你要执行的任务"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={3}
              />
            </div>
            <div className="row">
              <button onClick={handleSend} disabled={!canSend}>{loading ? "发送中..." : "发送"}</button>
              {error && <span className="error">{error}</span>}
              {loadingKind === "plan" && <span className="muted">Codex 生成计划中...</span>}
              {loadingKind === "chat" && <span className="muted">对话中</span>}
            </div>
          </div>
        </div>
      </div>
      {activeSession?.planId && (
        <div className="card">
          <h2>计划预览</h2>
          <pre className="pre">{activeSession.planText || "任务链：(空)"}</pre>
        </div>
      )}
    </section>
  );
}
