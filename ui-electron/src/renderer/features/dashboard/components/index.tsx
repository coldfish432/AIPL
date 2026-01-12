/**
 * Dashboard 组件
 */

import React from "react";
import { Activity, CheckCircle, FileText, Play } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import { formatTimestamp } from "@/lib/normalize";
import { normalizeBackendStatus, getStatusDisplayText } from "@/lib/status";
import type { NormalizedPlan, NormalizedRun } from "@/lib/normalize";

// ============================================================
// Stats Grid
// ============================================================

interface StatsGridProps {
  totalPlans: number;
  totalRuns: number;
  totalTasks: number;
  runningRuns: number;
  completedRuns: number;
  successRate: number;
}

export function StatsGrid({
  totalPlans,
  totalRuns,
  totalTasks,
  runningRuns,
  completedRuns,
  successRate,
}: StatsGridProps) {
  const { t } = useI18n();

  return (
    <div className="dashboard-hero-grid">
      <div className="dashboard-hero-card plans">
        <div className="dashboard-hero-header">
          <div className="dashboard-hero-icon plans">
            <FileText size={18} />
          </div>
          <span className="dashboard-hero-badge">
            {t.labels.tasks} {totalTasks}
          </span>
        </div>
        <div className="dashboard-hero-value">{totalPlans}</div>
        <div className="dashboard-hero-label">{t.titles.plans}</div>
      </div>

      <div className="dashboard-hero-card runs">
        <div className="dashboard-hero-header">
          <div className="dashboard-hero-icon runs">
            <Play size={18} />
          </div>
          <span className="dashboard-hero-badge">
            {runningRuns} {t.status.running}
          </span>
        </div>
        <div className="dashboard-hero-value">{totalRuns}</div>
        <div className="dashboard-hero-label">{t.titles.runs}</div>
      </div>

      <div className="dashboard-hero-card completed">
        <div className="dashboard-hero-header">
          <div className="dashboard-hero-icon completed">
            <CheckCircle size={18} />
          </div>
          <span className="dashboard-hero-badge">
            {totalRuns ? `${successRate}%` : "-"}
          </span>
        </div>
        <div className="dashboard-hero-value">{completedRuns}</div>
        <div className="dashboard-hero-label">{t.status.completed}</div>
      </div>
    </div>
  );
}

// ============================================================
// Plan List
// ============================================================

interface PlanListProps {
  plans: NormalizedPlan[];
  onSelect: (planId: string) => void;
}

export function PlanList({ plans, onSelect }: PlanListProps) {
  const { t } = useI18n();

  return (
    <div className="dashboard-panel">
      <div className="dashboard-panel-title-row">
        <div className="dashboard-panel-title">
          <FileText size={16} />
          <span>{t.titles.plans}</span>
        </div>
      </div>
      <div className="dashboard-list dashboard-scroll-list">
        {plans.length === 0 && (
          <div className="dashboard-muted">{t.messages.noPlans}</div>
        )}
        {plans.map((plan) => (
          <button
            key={plan.id}
            type="button"
            className="dashboard-list-item"
            onClick={() => onSelect(plan.id)}
          >
            <div className="dashboard-list-main">
              <div className="dashboard-list-title">
                {plan.inputTask || `${t.labels.plan} ${plan.id}`}
              </div>
              <div className="dashboard-list-meta">
                {t.labels.updated} {formatTimestamp(plan.updatedAt) || "-"}
              </div>
            </div>
            <div className="dashboard-list-tail">
              <span className="dashboard-pill">
                {t.labels.tasks} {plan.tasksCount ?? "-"}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// Run List
// ============================================================

interface RunListProps {
  runs: NormalizedRun[];
  onSelect: (runId: string, planId?: string) => void;
}

export function RunList({ runs, onSelect }: RunListProps) {
  const { t } = useI18n();

  const getLocalizedStatusText = (status: string) => {
    const unified = normalizeBackendStatus(status);
    if (unified.execution === "completed" && unified.review) {
      return t.status[unified.review] || getStatusDisplayText(unified);
    }
    return t.status[unified.execution] || getStatusDisplayText(unified);
  };

  return (
    <div className="dashboard-panel">
      <div className="dashboard-panel-title-row">
        <div className="dashboard-panel-title">
          <Play size={16} />
          <span>{t.titles.runs}</span>
        </div>
      </div>
      <div className="dashboard-list dashboard-scroll-list">
        {runs.length === 0 && (
          <div className="dashboard-muted">{t.messages.noRuns}</div>
        )}
        {runs.map((run) => {
          const unified = normalizeBackendStatus(run.status || "unknown");
          const statusText = getLocalizedStatusText(run.status || "unknown");

          return (
            <button
              key={run.id}
              type="button"
              className="dashboard-list-item"
              onClick={() => onSelect(run.id, run.planId)}
            >
              <div className="dashboard-list-main">
                <div className="dashboard-list-title">
                  {run.task || `${t.labels.run} ${run.id}`}
                </div>
                <div className="dashboard-list-meta">
                  {t.labels.updated} {formatTimestamp(run.updatedAt) || "-"}
                </div>
              </div>
              <div className="dashboard-list-tail">
                <span className={`dashboard-pill status-${unified.execution}`}>
                  {statusText}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// Metrics Panel
// ============================================================

interface MetricsPanelProps {
  successRate: number;
  runningRuns: number;
  totalRuns: number;
}

export function MetricsPanel({
  successRate,
  runningRuns,
  totalRuns,
}: MetricsPanelProps) {
  const { t } = useI18n();

  const runningRatio =
    totalRuns > 0 ? Math.round((runningRuns / totalRuns) * 100) : 0;

  const metrics = [
    {
      id: "success",
      label: t.labels.successRate,
      value: successRate,
      display: `${successRate}%`,
      variant: "success",
    },
    {
      id: "running",
      label: t.labels.activeRuns,
      value: runningRatio,
      display: `${runningRuns}/${totalRuns || 0}`,
      variant: "running",
    },
  ];

  return (
    <div className="dashboard-panel">
      <div className="dashboard-panel-title-row">
        <div className="dashboard-panel-title">
          <Activity size={16} />
          <span>{t.labels.systemResources}</span>
        </div>
      </div>
      <div className="dashboard-metrics-grid">
        {metrics.map((metric) => (
          <div key={metric.id} className="dashboard-metric">
            <div className="dashboard-metric-header">
              <span>{metric.label}</span>
              <span className="dashboard-metric-value">{metric.display}</span>
            </div>
            <div className="dashboard-metric-bar">
              <div
                className={`dashboard-metric-bar-fill ${metric.variant}`}
                style={{ width: `${metric.value}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
