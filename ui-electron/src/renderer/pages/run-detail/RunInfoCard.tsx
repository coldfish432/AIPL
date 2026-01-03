import React from "react";
import { useI18n } from "../../lib/useI18n";
import { getStatusClassName, UnifiedStatus } from "../../lib/status";

type Props = {
  runId: string;
  planId: string;
  unifiedStatus: UnifiedStatus;
  statusText: string;
  workflowStage: string;
  policy: string;
  task: string;
  updated: string;
};

export default function RunInfoCard({
  runId,
  planId,
  unifiedStatus,
  statusText,
  workflowStage,
  policy,
  task,
  updated
}: Props) {
  const { t } = useI18n();

  return (
    <div className="card">
      <h2>{t.titles.runInfo}</h2>
      <div className="list">
        <div className="list-item">
          <div className="title">{t.labels.runId}</div>
          <div className="meta">{runId}</div>
        </div>
        <div className="list-item">
          <div className="title">{t.labels.planId}</div>
          <div className="meta">{planId}</div>
        </div>
        <div className="list-item">
          <div>
            <div className="title">{t.labels.status}</div>
            <div className="meta">{statusText}</div>
          </div>
          <div className={`pill ${getStatusClassName(unifiedStatus)}`}>{statusText}</div>
        </div>
        <div className="list-item">
          <div className="title">{t.labels.currentStage}</div>
          <div className="meta">{workflowStage}</div>
        </div>
        <div className="list-item">
          <div className="title">{t.labels.policy}</div>
          <div className="meta">{policy}</div>
        </div>
        <div className="list-item">
          <div className="title">{t.labels.task}</div>
          <div className="meta">{task}</div>
        </div>
        <div className="list-item">
          <div className="title">{t.labels.updated}</div>
          <div className="meta">{updated}</div>
        </div>
      </div>
    </div>
  );
}
