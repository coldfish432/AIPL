/**
 * TaskBriefing component displays current execution lock summary
 */

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Play,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
  Eye,
  XCircle,
} from "lucide-react";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { getPlan, getRun, listRuns } from "@/services/api";
import type { ExecutionLock, ExecutionLockStatus } from "@/types/lock";
import "@/styles/task-briefing.css";

interface TaskBriefingProps {
  executionLock: ExecutionLock;
  onForceUnlock?: () => void;
}

interface TaskDetails {
  planId: string;
  task: string | null;
  tasksCount: number;
  runId: string | null;
  runStatus: string | null;
  progress: {
    currentStep: number;
    totalSteps: number;
    currentStepTitle?: string;
  } | null;
  updatedAt: number | null;
}

const STATUS_CONFIG: Record<
  ExecutionLockStatus,
  { icon: React.ElementType; label: string; color: string }
> = {
  idle: { icon: CheckCircle, label: "当前空闲", color: "var(--color-text-muted)" },
  planning: { icon: Loader2, label: "生成计划中", color: "var(--color-primary)" },
  confirming: { icon: Clock, label: "待确认执行", color: "var(--color-warning)" },
  running: { icon: Play, label: "执行中", color: "var(--color-success)" },
  reviewing: { icon: AlertCircle, label: "等待审查", color: "var(--color-warning)" },
};

function formatRelativeTime(ts: number | null): string {
  if (!ts) return "";
  const diff = Date.now() - ts;
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  return `${Math.floor(diff / 86400000)} 天前`;
}

function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max)}...`;
}

export default function TaskBriefing({ executionLock, onForceUnlock }: TaskBriefingProps) {
  const navigate = useNavigate();
  const { workspace } = useWorkspace();

  const [details, setDetails] = useState<TaskDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (!executionLock.planId || executionLock.status === "idle") {
      setDetails(null);
      return;
    }

    const loadDetails = async () => {
      setLoading(true);
      try {
        const planData = await getPlan(executionLock.planId!);
        const tasksCount =
          planData?.snapshot?.tasks?.length ||
          planData?.plan?.raw_plan?.tasks?.length ||
          0;

        let runId = executionLock.runId;
        let runStatus: string | null = null;
        let updatedAt = executionLock.lockedAt;

        if (runId) {
          try {
            const runData = await getRun(runId, executionLock.planId!);
            runStatus = runData?.run?.status || runData?.status || runStatus;
            updatedAt =
              runData?.run?.updated_at || runData?.run?.updatedAt || updatedAt;
          } catch {
            // ignore
          }
        } else if (workspace) {
          try {
            const runs = await listRuns(workspace);
            const related = runs.find(
              (r) => (r.plan_id || r.planId) === executionLock.planId
            );
            if (related) {
              runId = related.run_id || related.runId || related.id || runId;
              runStatus = related.status || related.state || runStatus;
              updatedAt =
                related.updated_at || related.updatedAt || updatedAt;
            }
          } catch {
            // ignore
          }
        }

        setDetails({
          planId: executionLock.planId!,
          task: executionLock.task,
          tasksCount,
          runId,
          runStatus,
          progress: executionLock.progress || null,
          updatedAt,
        });
      } catch {
        setDetails({
          planId: executionLock.planId!,
          task: executionLock.task,
          tasksCount: 0,
          runId: executionLock.runId,
          runStatus: null,
          progress: executionLock.progress || null,
          updatedAt: executionLock.lockedAt,
        });
      } finally {
        setLoading(false);
      }
    };

    loadDetails();
  }, [executionLock, workspace]);

  if (executionLock.status === "idle") {
    return null;
  }

  const config = STATUS_CONFIG[executionLock.status];
  const StatusIcon = config.icon;

  const goToPlan = () => details?.planId && navigate(`/plans/${details.planId}`);
  const goToRun = () =>
    details?.runId && details?.planId && navigate(`/runs/${details.planId}/${details.runId}`);

  const progressPercent =
    details?.progress && details.progress.totalSteps > 0
      ? (details.progress.currentStep / details.progress.totalSteps) * 100
      : 0;

  return (
    <div className={`task-briefing status-${executionLock.status}`}>
      <div className="task-briefing-header" onClick={() => setExpanded((prev) => !prev)}>
        <div className="task-briefing-status">
          <StatusIcon size={16} style={{ color: config.color }} />
          <span style={{ color: config.color, fontWeight: 600 }}>{config.label}</span>
        </div>
        <div className="task-briefing-meta">
          {details?.updatedAt && (
            <span className="task-briefing-time">
              {formatRelativeTime(details.updatedAt)}
            </span>
          )}
          <ChevronRight size={16} className={expanded ? "rotated" : ""} />
        </div>
      </div>

      {expanded && (
        <div className="task-briefing-content">
          {loading ? (
            <div className="task-briefing-loading">
              <Loader2 size={20} className="spin" />
              <span>加载中...</span>
            </div>
          ) : (
            <>
              <div className="task-briefing-task">
                <p>{details?.task ? truncate(details.task, 100) : "未知任务"}</p>
              </div>

              <div className="task-briefing-info">
                <div className="task-briefing-info-item">
                  <FileText size={14} />
                  <span>Plan: {details?.planId?.slice(0, 12)}...</span>
                </div>
                {details?.tasksCount && details.tasksCount > 0 && (
                  <div className="task-briefing-info-item">
                    <span>{details.tasksCount} 个步骤</span>
                  </div>
                )}
                {details?.runId && (
                  <div className="task-briefing-info-item">
                    <Play size={14} />
                    <span>Run: {details.runId.slice(0, 8)}...</span>
                  </div>
                )}
              </div>

              {details?.progress && (
                <div className="task-briefing-progress">
                  <div className="task-briefing-progress-header">
                    <span>
                      步骤 {details.progress.currentStep}/{details.progress.totalSteps}
                    </span>
                    {details.progress.currentStepTitle && (
                      <span className="task-briefing-progress-title">
                        {truncate(details.progress.currentStepTitle, 30)}
                      </span>
                    )}
                  </div>
                  <div className="task-briefing-progress-bar">
                    <div
                      className="task-briefing-progress-fill"
                      style={{
                        width: `${progressPercent}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              <div className="task-briefing-actions">
                <button className="task-briefing-btn secondary" onClick={goToPlan}>
                  <FileText size={14} />
                  <span>查看计划</span>
                </button>
                {details?.runId && (
                  <button className="task-briefing-btn primary" onClick={goToRun}>
                    <Eye size={14} />
                    <span>查看执行</span>
                  </button>
                )}
                {executionLock.status === "confirming" && (
                  <button className="task-briefing-btn primary" onClick={goToPlan}>
                    <Play size={14} />
                    <span>确认执行</span>
                  </button>
                )}
                {onForceUnlock && (
                  <button
                    className="task-briefing-btn danger"
                    onClick={() => {
                      if (window.confirm("确定要强制解锁当前任务吗？")) {
                        onForceUnlock();
                      }
                    }}
                  >
                    <XCircle size={14} />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
