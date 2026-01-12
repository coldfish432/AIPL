/**
 * Run Info Card 组件
 * 显示 Run 基本信息
 */

import React from "react";
import { useI18n } from "@/hooks/useI18n";
import { getStatusDisplayText, getStatusClassName } from "@/lib/status";
import { formatTimestamp } from "@/lib/normalize";
import type { UnifiedStatus } from "@/apis/types";

interface RunInfoCardProps {
  runId: string;
  planId: string;
  status: UnifiedStatus;
  workflowStage?: string;
  task?: string;
  updated?: string | number;
}

export function RunInfoCard({
  runId,
  planId,
  status,
  workflowStage,
  task,
  updated,
}: RunInfoCardProps) {
  const { t } = useI18n();

  const statusText = t.status[status.execution] || getStatusDisplayText(status);
  const statusClass = getStatusClassName(status);

  return (
    <div className="run-info-card">
      <div className="run-info-grid">
        <div className="run-info-item">
          <span className="run-info-label">{t.labels.runId}</span>
          <span className="run-info-value">{runId}</span>
        </div>

        <div className="run-info-item">
          <span className="run-info-label">{t.labels.planId}</span>
          <span className="run-info-value">{planId}</span>
        </div>

        <div className="run-info-item">
          <span className="run-info-label">{t.labels.status}</span>
          <span className={`status-pill ${statusClass}`}>{statusText}</span>
        </div>

        {workflowStage && (
          <div className="run-info-item">
            <span className="run-info-label">阶段</span>
            <span className="run-info-value">{workflowStage}</span>
          </div>
        )}

        {task && (
          <div className="run-info-item full-width">
            <span className="run-info-label">{t.labels.task}</span>
            <span className="run-info-value">{task}</span>
          </div>
        )}

        <div className="run-info-item">
          <span className="run-info-label">{t.labels.updated}</span>
          <span className="run-info-value">
            {formatTimestamp(updated) || "-"}
          </span>
        </div>
      </div>
    </div>
  );
}
