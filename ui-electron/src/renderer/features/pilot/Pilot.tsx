/**
 * Pilot 导航页面 - 统一对话 + 智能触发
 *
 * 交互流程：
 * 1. 用户可以自由提问（关于工作区的问题）
 * 2. AI 识别到任务意图时，显示确认卡片
 * 3. 用户确认后生成详细任务计划
 * 4. 预览任务计划后开始执行
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "@/styles/pilot.css";
import {
  Send,
  Sparkles,
  Plus,
  Trash2,
  MessageSquare,
  X,
  Play,
  FileCode,
  FolderTree,
  CheckCircle,
  AlertCircle,
  Loader2,
  Edit3,
} from "lucide-react";

import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useExecution } from "@/contexts/ExecutionContext";
import { useI18n } from "@/hooks/useI18n";
import {
  assistantChat,
  assistantPlan,
  assistantConfirm,
  ChatMessage,
} from "@/services/api";
import { STORAGE_KEYS } from "@/config/settings";

// ============================================================
// Types
// ============================================================

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  // AI 返回的额外信息
  intent?: "task" | "question" | null;
  taskSummary?: string;
  taskFiles?: string[];
  taskOperations?: string[];
}

interface TaskPlan {
  summary: string;
  analysis?: string;
  tasks: TaskItem[];
  verification?: string;
  taskChainText?: string;
}

interface TaskItem {
  id: string;
  stepId?: string;
  title: string;
  operation?: string;
  targetFile?: string;
  description: string;
  changes?: TaskChange[];
  dependencies?: string[];
}

interface TaskChange {
  location: string;
  action: string;
  detail: string;
}

interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

type PilotMode =
  | "chat"              // 普通对话
  | "task_detected"     // 检测到任务，等待确认
  | "planning"          // 正在生成计划
  | "preview"           // 预览任务计划
  | "confirming"        // 确认执行中
  | "executing";        // 已开始执行

// ============================================================
// Storage Helpers
// ============================================================

function getSessionsKey(workspace: string): string {
  return `${STORAGE_KEYS.pilotSessionsKey || "aipl-pilot-sessions"}_${workspace}`;
}

function loadSessions(workspace: string): Session[] {
  try {
    const raw = localStorage.getItem(getSessionsKey(workspace));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSessions(workspace: string, sessions: Session[]): void {
  localStorage.setItem(getSessionsKey(workspace), JSON.stringify(sessions));
}

// ============================================================
// Component
// ============================================================

export default function Pilot() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { workspace } = useWorkspace();
  const { startExecution } = useExecution();

  // 会话状态
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  // UI 状态
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<PilotMode>("chat");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // 任务相关状态
  const [pendingTaskSummary, setPendingTaskSummary] = useState<string>("");
  const [pendingTaskFiles, setPendingTaskFiles] = useState<string[]>([]);
  const [pendingTaskOperations, setPendingTaskOperations] = useState<string[]>([]);
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [generatedPlanId, setGeneratedPlanId] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 加载会话
  useEffect(() => {
    if (workspace) {
      const loaded = loadSessions(workspace);
      setSessions(loaded);
      if (loaded.length > 0) {
        const latest = loaded[0];
        setCurrentSessionId(latest.id);
        setMessages(latest.messages);
      } else {
        createNewSession();
      }
    } else {
      setSessions([]);
      setMessages([]);
      setCurrentSessionId(null);
    }
  }, [workspace]);

  // 保存会话
  useEffect(() => {
    if (workspace && currentSessionId && messages.length > 0) {
      setSessions((prev) => {
        const updated = prev.map((s) =>
          s.id === currentSessionId
            ? { ...s, messages, updatedAt: Date.now() }
            : s
        );
        saveSessions(workspace, updated);
        return updated;
      });
    }
  }, [workspace, currentSessionId, messages]);

  // 创建新会话
  const createNewSession = useCallback(() => {
    const newSession: Session = {
      id: `session_${Date.now()}`,
      title: "新对话",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setSessions((prev) => {
      const updated = [newSession, ...prev];
      if (workspace) saveSessions(workspace, updated);
      return updated;
    });

    setCurrentSessionId(newSession.id);
    setMessages([]);
    setMode("chat");
    setTaskPlan(null);
    setError(null);
  }, [workspace]);

  // 切换会话
  const switchSession = useCallback((sessionId: string) => {
    const session = sessions.find((s) => s.id === sessionId);
    if (session) {
      setCurrentSessionId(sessionId);
      setMessages(session.messages);
      setMode("chat");
      setTaskPlan(null);
      setError(null);
    }
  }, [sessions]);

  // 删除会话
  const deleteSession = useCallback((sessionId: string) => {
    setSessions((prev) => {
      const updated = prev.filter((s) => s.id !== sessionId);
      if (workspace) saveSessions(workspace, updated);

      if (sessionId === currentSessionId) {
        if (updated.length > 0) {
          setCurrentSessionId(updated[0].id);
          setMessages(updated[0].messages);
        } else {
          createNewSession();
        }
      }

      return updated;
    });
  }, [workspace, currentSessionId, createNewSession]);

  // 发送消息
  const sendMessage = useCallback(async () => {
    if (!input.trim() || !workspace || loading) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      // 构建消息历史
      const chatMessages: ChatMessage[] = [
        ...messages.map((m) => ({ role: m.role, content: m.content })),
        { role: "user" as const, content: userMessage.content },
      ];

      // 调用 AI
      const response = await assistantChat(chatMessages, workspace) as {
        reply?: string;
        message?: string;
        intent?: string;
        task_summary?: string;
        task_files?: string[];
        task_operations?: string[];
      };

      const reply = response.reply || response.message || "";
      const intent = response.intent as "task" | "question" | undefined;
      const taskSummary = response.task_summary || "";
      const taskFiles = response.task_files || [];
      const taskOperations = response.task_operations || [];

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        role: "assistant",
        content: reply,
        timestamp: Date.now(),
        intent: intent || null,
        taskSummary,
        taskFiles,
        taskOperations,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // 如果检测到任务意图
      if (intent === "task" && taskSummary) {
        setPendingTaskSummary(taskSummary);
        setPendingTaskFiles(taskFiles);
        setPendingTaskOperations(taskOperations);
        setMode("task_detected");
      }

      // 更新会话标题（使用第一条用户消息）
      if (messages.length === 0) {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === currentSessionId
              ? { ...s, title: userMessage.content.slice(0, 30) + (userMessage.content.length > 30 ? "..." : "") }
              : s
          )
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }, [input, workspace, loading, messages, currentSessionId]);

  // 开始规划
  const startPlanning = useCallback(async () => {
    if (!workspace) return;

    setMode("planning");
    setLoading(true);
    setError(null);

    try {
      const chatMessages: ChatMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await assistantPlan(chatMessages, workspace);

      const planId = response.plan_id || response.planId;
      const taskChainText = response.task_chain_text || "";
      const tasksCount = response.tasks_count || 0;

      if (planId) {
        setGeneratedPlanId(planId);

        // 构建任务计划对象
        setTaskPlan({
          summary: pendingTaskSummary || "任务计划",
          tasks: [],  // 从后端获取详细任务列表
          taskChainText,
        });

        setMode("preview");

        // 添加系统消息
        const planMessage: Message = {
          id: `msg_${Date.now()}_plan`,
          role: "assistant",
          content: `已生成任务计划，包含 ${tasksCount} 个任务。请查看下方预览并确认执行。`,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, planMessage]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "规划失败");
      setMode("chat");
    } finally {
      setLoading(false);
    }
  }, [workspace, messages, pendingTaskSummary]);

  // 取消任务
  const cancelTask = useCallback(() => {
    setMode("chat");
    setPendingTaskSummary("");
    setPendingTaskFiles([]);
    setPendingTaskOperations([]);
    setTaskPlan(null);
    setGeneratedPlanId(null);

    const cancelMessage: Message = {
      id: `msg_${Date.now()}_cancel`,
      role: "assistant",
      content: "已取消任务规划。你可以继续描述需求或提出问题。",
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, cancelMessage]);
  }, []);

  // 确认执行
  const confirmExecution = useCallback(async () => {
    if (!workspace || !generatedPlanId) return;

    setMode("confirming");
    setLoading(true);
    setError(null);

    try {
      const response = await assistantConfirm(generatedPlanId, workspace);
      const runId = response.run_id || response.runId;

      if (runId) {
        // 更新执行状态
        if (startExecution) {
          startExecution(generatedPlanId, runId);
        }

        setMode("executing");

        // 添加执行消息
        const execMessage: Message = {
          id: `msg_${Date.now()}_exec`,
          role: "assistant",
          content: `任务已开始执行 (Run: ${runId.slice(0, 8)}...)。正在跳转到执行详情页面...`,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, execMessage]);

        // 跳转到执行详情
        setTimeout(() => {
          navigate(`/runs/${encodeURIComponent(runId)}?planId=${encodeURIComponent(generatedPlanId)}`);
        }, 1500);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败");
      setMode("preview");
    } finally {
      setLoading(false);
    }
  }, [workspace, generatedPlanId, startExecution, navigate]);

  // 手动触发规划（提议按钮）
  const handlePropose = useCallback(() => {
    if (messages.length === 0) {
      setError("请先描述你的需求");
      return;
    }

    // 获取最后一条用户消息作为任务摘要
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      setPendingTaskSummary(lastUserMsg.content);
      setMode("task_detected");
    }
  }, [messages]);

  // 键盘事件
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }, [sendMessage]);

  // 渲染操作类型标签
  const renderOperationBadge = (operation: string) => {
    const colors: Record<string, string> = {
      CREATE: "badge-success",
      MODIFY: "badge-warning",
      DELETE: "badge-error",
      RENAME: "badge-info",
      COMMAND: "badge-primary",
    };

    const labels: Record<string, string> = {
      CREATE: "创建",
      MODIFY: "修改",
      DELETE: "删除",
      RENAME: "重命名",
      COMMAND: "命令",
    };

    return (
      <span className={`pilot-operation-badge ${colors[operation] || "badge-default"}`}>
        {labels[operation] || operation}
      </span>
    );
  };

  return (
    <div className="pilot-page">
      {/* 左侧边栏 - 会话列表 */}
      <aside className={`pilot-sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="pilot-sidebar-header">
          <h2>{t.titles?.chat || "对话"}</h2>
          <button
            type="button"
            className="pilot-new-btn"
            onClick={createNewSession}
            title="新建对话"
          >
            <Plus size={18} />
          </button>
        </div>

        <div className="pilot-sessions">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`pilot-session-item ${session.id === currentSessionId ? "active" : ""}`}
              onClick={() => switchSession(session.id)}
            >
              <MessageSquare size={16} />
              <span className="pilot-session-title">{session.title}</span>
              <button
                type="button"
                className="pilot-session-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* 中间 - 对话区域 */}
      <main className="pilot-main">
        <div className="pilot-header">
          <h1>{t.titles?.pilot || "导航"}</h1>
          {mode !== "chat" && (
            <span className="pilot-mode-badge">
              {mode === "task_detected" && "🎯 任务确认"}
              {mode === "planning" && "⏳ 生成计划中..."}
              {mode === "preview" && "📋 计划预览"}
              {mode === "confirming" && "🚀 启动执行中..."}
              {mode === "executing" && "▶️ 执行中"}
            </span>
          )}
        </div>

        {/* 消息列表 */}
        <div className="pilot-messages">
          {messages.length === 0 ? (
            <div className="pilot-welcome">
              <FolderTree size={48} strokeWidth={1.5} />
              <h2>开始新对话</h2>
              <p>描述你想要完成的任务，或询问关于工作区的问题。</p>
              <p className="pilot-welcome-hint">
                AI 会分析你的需求，并在需要时自动建议生成任务计划。
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`pilot-message ${msg.role}`}>
                <div className="pilot-message-content">
                  {msg.content}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 任务检测卡片 */}
        {mode === "task_detected" && (
          <div className="pilot-task-card">
            <div className="pilot-task-card-header">
              <Sparkles size={18} />
              <span>检测到任务需求</span>
            </div>
            <div className="pilot-task-card-body">
              <p className="pilot-task-summary">{pendingTaskSummary}</p>
              {pendingTaskFiles.length > 0 && (
                <div className="pilot-task-files">
                  <strong>涉及文件：</strong>
                  {pendingTaskFiles.map((file, i) => (
                    <code key={i}>{file}</code>
                  ))}
                </div>
              )}
              {pendingTaskOperations.length > 0 && (
                <div className="pilot-task-operations">
                  <strong>操作类型：</strong>
                  {pendingTaskOperations.map((op, i) => (
                    <span key={i}>{renderOperationBadge(op)}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="pilot-task-card-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={cancelTask}
              >
                继续对话
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={startPlanning}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    生成计划中...
                  </>
                ) : (
                  <>
                    <FileCode size={16} />
                    生成任务计划
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* 任务计划预览 */}
        {(mode === "preview" || mode === "confirming") && taskPlan && (
          <div className="pilot-plan-preview">
            <div className="pilot-plan-preview-header">
              <h3>📋 任务计划预览</h3>
              <button
                type="button"
                className="pilot-plan-close"
                onClick={cancelTask}
              >
                <X size={18} />
              </button>
            </div>
            <div className="pilot-plan-preview-content">
              {taskPlan.taskChainText ? (
                <pre className="pilot-task-chain-text">{taskPlan.taskChainText}</pre>
              ) : (
                <p className="pilot-plan-summary">{taskPlan.summary}</p>
              )}
            </div>
            <div className="pilot-plan-preview-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={cancelTask}
                disabled={loading}
              >
                <Edit3 size={16} />
                修改需求
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={confirmExecution}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    启动中...
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    确认执行
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <div className="pilot-error">
            <AlertCircle size={16} />
            {error}
            <button onClick={() => setError(null)}>
              <X size={14} />
            </button>
          </div>
        )}

        {/* 输入区域 */}
        <div className="pilot-input-area">
          <textarea
            ref={inputRef}
            className="pilot-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              !workspace
                ? "请先选择工作区..."
                : mode === "preview"
                ? "修改需求或补充说明..."
                : "输入消息... (Shift+Enter 换行)"
            }
            disabled={!workspace || loading || mode === "confirming" || mode === "executing"}
            rows={1}
          />
          <div className="pilot-input-actions">
            <button
              type="button"
              className="pilot-propose-btn"
              onClick={handlePropose}
              disabled={!workspace || loading || messages.length === 0 || mode !== "chat"}
              title="将当前对话转为任务计划"
            >
              <Sparkles size={16} />
              {t.buttons?.propose || "提议"}
            </button>
            <button
              type="button"
              className="pilot-send-btn"
              onClick={sendMessage}
              disabled={!workspace || loading || !input.trim()}
            >
              <Send size={16} />
              {t.buttons?.send || "发送"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
