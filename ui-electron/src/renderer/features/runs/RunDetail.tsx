/**
 * RunDetail - 执行详情页
 * 
 * 功能：
 * 1. 显示执行状态和进度
 * 2. 执行历史时间线（带 [XX] 前缀）
 * 3. 变更文件列表
 * 4. 操作按钮（应用/丢弃/终止）
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  FileCode,
  Terminal,
  MessageSquare,
  Loader2,
  RefreshCw,
  Check,
  X,
  Square,
  Activity,
} from "lucide-react";

import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useExecution } from "@/contexts/ExecutionContext";
import { useI18n } from "@/hooks/useI18n";
import { useVisibilityPolling } from "@/hooks/useVisibilityPolling";
import {
  getRun,
  getRunEvents,
  streamRunEvents,
  applyRun,
  discardRun,
  cancelRun,
  RunDetailResponse,
  RunEvent,
} from "@/services/api";

// ============================================================
// Types
// ============================================================

interface EventItem {
  id: string;
  timestamp: number;
  type: string;
  prefix: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
  detail?: string;
}

/**
 * 标准化时间戳 —— 自动识别秒级时间并转换为毫秒
 */
function normalizeTimestamp(ts: unknown): number {
  if (typeof ts === "number") {
    if (ts > 0 && ts < 10000000000) {
      return ts * 1000;
    }
    return ts;
  }
  if (typeof ts === "string") {
    const parsed = Date.parse(ts);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
    const num = Number(ts);
    if (!Number.isNaN(num) && num > 0) {
      return num < 10000000000 ? num * 1000 : num;
    }
  }
  return Date.now();
}

// ============================================================
// Event Processing
// ============================================================

/**
 * 将后端事件转换为带前缀的显示格式
 */
function processEvent(event: RunEvent): EventItem {
  const type = event.type || event.event || event.name || "unknown";
  const normalizedType = type.toLowerCase().replace(/-/g, "_");
  
  // 确定前缀和消息
  let prefix = "INFO";
  let message = event.message || event.detail || type;
  let level: EventItem["level"] = "info";

  switch (normalizedType) {
    // 初始化
    case "run_init":
    case "init":
      prefix = "初始化";
      message = "执行任务初始化";
      level = "info";
      break;

    // 工作区
    case "workspace_stage_ready":
    case "stage_ready":
      prefix = "工作区";
      message = "工作区准备就绪";
      level = "success";
      break;

    // Codex 相关
    case "codex_start":
    case "subagent_start":
      prefix = "CODEX";
      message = event.task_title || "调用 Codex 处理任务...";
      level = "info";
      break;
    case "codex_done":
    case "subagent_done":
      prefix = "CODEX";
      message = event.task_title ? `${event.task_title} 完成` : "Codex 处理完成";
      level = "success";
      break;
    case "codex_timeout":
      prefix = "CODEX";
      message = "Codex 响应超时";
      level = "warning";
      break;
    case "codex_failed":
    case "subagent_failed":
      prefix = "CODEX";
      message = event.message || "Codex 处理失败";
      level = "error";
      break;

    // 步骤执行
    case "step_round_start":
      prefix = "步骤";
      message = `开始执行第 ${event.round || "?"} 轮`;
      level = "info";
      break;
    case "step_round_verified":
    case "step_verified":
      prefix = "验证";
      message = "步骤验证完成";
      level = "success";
      break;
    case "step_failed":
      prefix = "步骤";
      message = event.message || "步骤执行失败";
      level = "error";
      break;

    // 补丁
    case "patchset_ready":
      prefix = "补丁";
      message = "代码补丁已生成";
      level = "success";
      break;
    case "patchset_applied":
      prefix = "补丁";
      message = "代码补丁已应用";
      level = "success";
      break;

    // 文件操作
    case "file_modified":
    case "file_changed":
      prefix = "文件";
      message = `修改文件: ${event.detail || event.message || ""}`;
      level = "info";
      break;
    case "file_created":
    case "file_added":
      prefix = "文件";
      message = `新增文件: ${event.detail || event.message || ""}`;
      level = "info";
      break;
    case "file_deleted":
      prefix = "文件";
      message = `删除文件: ${event.detail || event.message || ""}`;
      level = "warning";
      break;

    // 审核
    case "awaiting_review":
      prefix = "审核";
      message = "等待审核确认";
      level = "warning";
      break;

    // 应用/丢弃
    case "apply_start":
      prefix = "应用";
      message = "开始应用变更...";
      level = "info";
      break;
    case "apply_done":
      prefix = "应用";
      message = "变更已应用到工作区";
      level = "success";
      break;
    case "discard_start":
      prefix = "丢弃";
      message = "开始丢弃变更...";
      level = "info";
      break;
    case "discard_done":
      prefix = "丢弃";
      message = "变更已丢弃";
      level = "warning";
      break;

    // 完成
    case "run_done":
    case "completed":
      prefix = "完成";
      message = "执行完成";
      level = "success";
      break;
    case "run_failed":
    case "failed":
      prefix = "失败";
      message = event.message || "执行失败";
      level = "error";
      break;
    case "run_canceled":
    case "canceled":
    case "terminated":
      prefix = "终止";
      message = "执行已终止";
      level = "error";
      break;

    // 日志
    case "log":
    case "info":
      prefix = "日志";
      message = event.message || event.detail || "";
      level = "info";
      break;
    case "warning":
    case "warn":
      prefix = "警告";
      message = event.message || event.detail || "";
      level = "warning";
      break;
    case "error":
      prefix = "错误";
      message = event.message || event.detail || "";
      level = "error";
      break;

    default:
      prefix = type.toUpperCase().slice(0, 8);
      message = event.message || event.detail || type;
      level = "info";
  }

  // 生成稳定的事件 ID（避免依赖外部索引）
  const stableId =
    event.event_id ||
    `${normalizedType}-${event.ts || ""}-${event.step_id || event.step || ""}-${event.round ?? ""}-${event.task_id || ""}`;

  return {
    id: stableId,
    timestamp: normalizeTimestamp(event.ts),
    type: normalizedType,
    prefix,
    message,
    level,
    detail: event.detail,
  };
}

function getStatusInfo(status: string): { text: string; icon: React.ElementType; className: string } {
  const normalized = status?.toLowerCase().replace(/-/g, "_") || "unknown";
  
  switch (normalized) {
    case "completed":
    case "done":
    case "applied":
      return { text: "已完成", icon: CheckCircle, className: "status-completed" };
    case "failed":
    case "error":
      return { text: "失败", icon: XCircle, className: "status-failed" };
    case "running":
    case "executing":
    case "doing":
      return { text: "执行中", icon: Activity, className: "status-running" };
    case "queued":
    case "todo":
    case "starting":
      return { text: "排队中", icon: Clock, className: "status-queued" };
    case "awaiting_review":
    case "awaitingreview":
      return { text: "待审核", icon: AlertTriangle, className: "status-review" };
    case "canceled":
    case "cancelled":
    case "terminated":
      return { text: "已终止", icon: Square, className: "status-canceled" };
    case "discarded":
      return { text: "已丢弃", icon: XCircle, className: "status-discarded" };
    default:
      return { text: status || "未知", icon: Clock, className: "status-unknown" };
  }
}

// ============================================================
// Component
// ============================================================

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const planId = searchParams.get("planId") || undefined;
  const navigate = useNavigate();
  
  const { t } = useI18n();
  const { workspace } = useWorkspace();
  const { execution, markCompleted, markAwaitingReview } = useExecution();

  const [runData, setRunData] = useState<RunDetailResponse | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const eventsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const seenEventIds = useRef<Set<string>>(new Set());

  // 加载 Run 数据
  const loadRun = useCallback(async () => {
    if (!runId) return;

    try {
      const data = await getRun(runId, planId);
      setRunData(data);

      // 检查状态变化
      const status = data?.run?.status || data?.status || "";
      const normalized = status.toLowerCase().replace(/-/g, "_");
      
      if (normalized === "awaiting_review") {
        markAwaitingReview();
      } else if (["completed", "done", "applied", "failed", "canceled", "discarded"].includes(normalized)) {
        markCompleted();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    }
  }, [runId, planId, markAwaitingReview, markCompleted]);

  // 加载事件
  const loadEvents = useCallback(async () => {
    if (!runId) return;

    try {
      const data = await getRunEvents(runId, planId, 0, 500);
      const rawEvents = data.events || [];
      const processed = rawEvents
        .map((e) => processEvent(e))
        .filter((e) => {
          if (seenEventIds.current.has(e.id)) return false;
          seenEventIds.current.add(e.id);
          return true;
        });
      
      if (processed.length > 0) {
        setEvents((prev) => [...prev, ...processed].sort((a, b) => a.timestamp - b.timestamp));
      }
    } catch (err) {
      console.error("加载事件失败:", err);
    }
  }, [runId, planId]);

  // 初始加载
  useEffect(() => {
    if (runId) {
      setLoading(true);
      setEvents([]);
      seenEventIds.current.clear();
      
      Promise.all([loadRun(), loadEvents()])
        .finally(() => setLoading(false));
    }
  }, [runId, loadRun, loadEvents]);

  // SSE 事件流
  useEffect(() => {
    if (!runId) return;

    const status = runData?.run?.status || runData?.status || "";
    const normalized = status.toLowerCase().replace(/-/g, "_");
    
    // 只在运行中时连接 SSE
    if (!["running", "executing", "doing", "queued", "starting"].includes(normalized)) {
      return;
    }

    try {
      eventSourceRef.current = streamRunEvents(runId, planId);
      
      eventSourceRef.current.onmessage = (e) => {
        try {
          const event: RunEvent = JSON.parse(e.data);
          const processed = processEvent(event);
          
          if (!seenEventIds.current.has(processed.id)) {
            seenEventIds.current.add(processed.id);
            setEvents((prev) => [...prev, processed].sort((a, b) => a.timestamp - b.timestamp));
          }
        } catch {
          // 忽略解析错误
        }
      };

      eventSourceRef.current.onerror = () => {
        eventSourceRef.current?.close();
      };
    } catch {
      // SSE 不可用，使用轮询
    }

    return () => {
      eventSourceRef.current?.close();
    };
  }, [runId, planId, runData]);

  // 轮询刷新
  useVisibilityPolling(() => {
    loadRun();
    loadEvents();
  }, 3000);

  // 滚动到底部
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  // 应用变更
  const handleApply = async () => {
    if (!runId || !window.confirm("确定要应用变更吗？")) return;
    
    setActionLoading(true);
    try {
      await applyRun(runId, planId);
      markCompleted();
      await loadRun();
    } catch (err) {
      setError(err instanceof Error ? err.message : "应用失败");
    } finally {
      setActionLoading(false);
    }
  };

  // 丢弃变更
  const handleDiscard = async () => {
    if (!runId || !window.confirm("确定要丢弃变更吗？所有修改将被撤销。")) return;
    
    setActionLoading(true);
    try {
      await discardRun(runId, planId);
      markCompleted();
      await loadRun();
    } catch (err) {
      setError(err instanceof Error ? err.message : "丢弃失败");
    } finally {
      setActionLoading(false);
    }
  };

  // 终止执行
  const handleTerminate = async () => {
    if (!runId || !window.confirm("确定要终止执行吗？")) return;
    
    setActionLoading(true);
    try {
      await cancelRun(runId, planId);
      markCompleted();
      await loadRun();
    } catch (err) {
      setError(err instanceof Error ? err.message : "终止失败");
    } finally {
      setActionLoading(false);
    }
  };

  // 返回
  const handleBack = () => {
    navigate("/dashboard");
  };

  // 解析数据
  const run = runData?.run || runData;
  const status = run?.status || run?.state || "unknown";
  const statusInfo = getStatusInfo(status);
  const StatusIcon = statusInfo.icon;
  const task = run?.task || run?.input_task || "";
  const isRunning = ["running", "executing", "doing"].includes(status.toLowerCase().replace(/-/g, "_"));
  const isAwaitingReview = status.toLowerCase().replace(/-/g, "_") === "awaiting_review";
  const isFinished = ["completed", "done", "applied", "failed", "canceled", "discarded", "terminated"].includes(status.toLowerCase().replace(/-/g, "_"));

  if (loading) {
    return (
      <div className="run-detail-page loading">
        <Loader2 size={24} className="spin" />
        <p>加载中...</p>
      </div>
    );
  }

  return (
    <div className="run-detail-page">
      {/* 头部 */}
      <header className="run-detail-header">
        <button type="button" className="run-detail-back" onClick={handleBack}>
          <ArrowLeft size={20} />
          返回
        </button>
        <div className="run-detail-title">
          <h1>执行详情</h1>
          <span className="run-detail-id">Run: {runId?.slice(0, 12)}...</span>
        </div>
        <button
          type="button"
          className="run-detail-refresh"
          onClick={() => { loadRun(); loadEvents(); }}
        >
          <RefreshCw size={16} />
        </button>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="run-detail-error">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* 状态卡片 */}
      <div className="run-detail-status-card">
        <div className={`run-detail-status-badge ${statusInfo.className}`}>
          <StatusIcon size={20} />
          <span>{statusInfo.text}</span>
        </div>
        {task && (
          <div className="run-detail-task">
            <strong>任务：</strong>
            {task}
          </div>
        )}
        {planId && (
          <div className="run-detail-plan">
            <strong>Plan：</strong>
            <button
              type="button"
              className="run-detail-plan-link"
              onClick={() => navigate(`/plans/${encodeURIComponent(planId)}`)}
            >
              {planId.slice(0, 16)}...
            </button>
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      {(isRunning || isAwaitingReview) && (
        <div className="run-detail-actions">
          {isAwaitingReview && (
            <>
              <button
                type="button"
                className="run-action-btn apply"
                onClick={handleApply}
                disabled={actionLoading}
              >
                <Check size={16} />
                {actionLoading ? "处理中..." : "应用变更"}
              </button>
              <button
                type="button"
                className="run-action-btn discard"
                onClick={handleDiscard}
                disabled={actionLoading}
              >
                <X size={16} />
                丢弃变更
              </button>
            </>
          )}
          <button
            type="button"
            className="run-action-btn terminate"
            onClick={handleTerminate}
            disabled={actionLoading}
          >
            <Square size={16} />
            终止执行
          </button>
        </div>
      )}

      {/* 执行历史时间线 */}
      <section className="run-detail-timeline">
        <h2>
          <Clock size={18} />
          执行历史
        </h2>
        <div className="run-timeline">
          {events.length === 0 ? (
            <div className="run-timeline-empty">
              {isRunning ? "等待事件..." : "暂无执行记录"}
            </div>
          ) : (
            events.map((event) => {
              const EventIcon = {
                info: MessageSquare,
                success: CheckCircle,
                warning: AlertTriangle,
                error: XCircle,
              }[event.level] || MessageSquare;

              return (
                <div key={event.id} className={`run-timeline-item ${event.level}`}>
                  <div className="run-timeline-icon">
                    <EventIcon size={14} />
                  </div>
                  <div className="run-timeline-content">
                    <div className="run-timeline-header">
                      <span className="run-timeline-prefix">[{event.prefix}]</span>
                      <span className="run-timeline-message">{event.message}</span>
                    </div>
                    {event.detail && (
                      <div className="run-timeline-detail">{event.detail}</div>
                    )}
                    <div className="run-timeline-time">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={eventsEndRef} />
        </div>
      </section>
    </div>
  );
}
