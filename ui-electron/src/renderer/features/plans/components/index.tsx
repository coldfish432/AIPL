/**
 * Plan 组件
 */

import React from "react";
import { CheckCircle, Circle, AlertCircle } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { PlanTask } from "@/apis/types";

// ============================================================
// Task Graph Component
// ============================================================

interface TaskGraphProps {
  tasks: PlanTask[];
  onTaskClick?: (taskId: string) => void;
}

export function TaskGraph({ tasks, onTaskClick }: TaskGraphProps) {
  const { t } = useI18n();

  if (tasks.length === 0) {
    return <div className="page-muted">{t.messages.taskChainEmpty}</div>;
  }

  return (
    <div className="task-graph">
      {tasks.map((task, idx) => {
        const taskId = task.step_id || task.id || task.task_id || `task-${idx}`;
        const title = task.title || task.name || `${t.labels.task} ${idx + 1}`;
        const status = String(task.status || "todo").toLowerCase();
        const StatusIcon = getStatusIcon(status);

        return (
          <div
            key={taskId}
            className={`task-node ${status}`}
            onClick={() => onTaskClick?.(taskId)}
          >
            <div className="task-node-icon">
              <StatusIcon size={16} />
            </div>
            <div className="task-node-content">
              <div className="task-node-title">{title}</div>
              {task.description && (
                <div className="task-node-description">{task.description}</div>
              )}
            </div>
            {idx < tasks.length - 1 && <div className="task-connector" />}
          </div>
        );
      })}
    </div>
  );
}

function getStatusIcon(status: string) {
  switch (status) {
    case "done":
      return CheckCircle;
    case "failed":
      return AlertCircle;
    default:
      return Circle;
  }
}

// ============================================================
// Task List Component
// ============================================================

interface TaskListProps {
  tasks: PlanTask[];
  onTaskClick?: (taskId: string) => void;
}

export function TaskList({ tasks, onTaskClick }: TaskListProps) {
  const { t } = useI18n();

  if (tasks.length === 0) {
    return <div className="page-muted">{t.messages.taskChainEmpty}</div>;
  }

  return (
    <div className="card-list">
      {tasks.map((task, idx) => {
        const taskId = task.step_id || task.id || task.task_id || `task-${idx}`;
        const title = task.title || task.name || `${t.labels.task} ${idx + 1}`;
        const status = String(task.status || "todo").toLowerCase();
        const statusLabel = t.status[status as keyof typeof t.status] || status;

        return (
          <div
            key={taskId}
            className="card-item"
            onClick={() => onTaskClick?.(taskId)}
          >
            <div className="card-item-main">
              <div className="card-item-title">{title}</div>
              {task.description && (
                <div className="card-item-meta">{task.description}</div>
              )}
              {task.dependencies && task.dependencies.length > 0 && (
                <div className="card-item-meta">
                  {t.labels.dependencies}: {task.dependencies.join(", ")}
                </div>
              )}
            </div>
            <div className={`status-pill ${status}`}>{statusLabel}</div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// Plan Text Component
// ============================================================

interface PlanTextProps {
  text: string;
}

export function PlanText({ text }: PlanTextProps) {
  const { t } = useI18n();

  if (!text) {
    return <div className="page-muted">{t.messages.planEmpty}</div>;
  }

  return <pre className="pre">{text}</pre>;
}

// ============================================================
// Plan Info Card Component
// ============================================================

interface PlanInfoCardProps {
  planId: string;
  inputTask?: string;
  tasksCount: number;
  updatedAt?: string | number;
}

export function PlanInfoCard({
  planId,
  inputTask,
  tasksCount,
  updatedAt,
}: PlanInfoCardProps) {
  const { t } = useI18n();

  const formatTime = (value: string | number | undefined) => {
    if (!value) return "-";
    const date = typeof value === "number" ? new Date(value) : new Date(value);
    return date.toLocaleString();
  };

  return (
    <div className="plan-info-card">
      <div className="plan-info-grid">
        <div className="plan-info-item">
          <span className="plan-info-label">{t.labels.planId}</span>
          <span className="plan-info-value">{planId}</span>
        </div>
        <div className="plan-info-item">
          <span className="plan-info-label">{t.labels.tasks}</span>
          <span className="plan-info-value">{tasksCount}</span>
        </div>
        {inputTask && (
          <div className="plan-info-item full-width">
            <span className="plan-info-label">{t.labels.task}</span>
            <span className="plan-info-value">{inputTask}</span>
          </div>
        )}
        <div className="plan-info-item">
          <span className="plan-info-label">{t.labels.updated}</span>
          <span className="plan-info-value">{formatTime(updatedAt)}</span>
        </div>
      </div>
    </div>
  );
}
