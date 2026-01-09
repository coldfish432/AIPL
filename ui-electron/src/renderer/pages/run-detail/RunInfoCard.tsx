import React from "react";
import { useI18n } from "../../lib/useI18n";
import { getStatusClassName, UnifiedStatus } from "../../lib/status";

type Props = {
  runId: string;
  planId: string;
  unifiedStatus: UnifiedStatus;
  statusText: string;
  workflowStage: string;
  task: string;
  updated: string;
};

export default function RunInfoCard({
  runId,
  planId,
  unifiedStatus,
  statusText,
  workflowStage,
  task,
  updated
}: Props) {
  const { t } = useI18n();

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.titles.runInfo}</h2>
        <div className={`status-pill ${getStatusClassName(unifiedStatus)}`}>{statusText}</div>
      </div>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">{t.labels.runId}</div>
          <div className="info-value">{runId}</div>
        </div>
        <div className="info-item">
          <div className="info-label">{t.labels.planId}</div>
          <div className="info-value">{planId}</div>
        </div>
        <div className="info-item">
          <div className="info-label">{t.labels.status}</div>
          <div className="info-value">{statusText}</div>
        </div>
        <div className="info-item">
          <div className="info-label">{t.labels.currentStage}</div>
          <div className="info-value">{workflowStage}</div>
        </div>
        <div className="info-item">
          <div className="info-label">{t.labels.task}</div>
          <div className="info-value">{task}</div>
        </div>
        <div className="info-item">
          <div className="info-label">{t.labels.updated}</div>
          <div className="info-value">{updated}</div>
        </div>
      </div>
    </div>
  );
}
