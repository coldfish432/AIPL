/**
 * Rework Panel 组件
 * 显示返工面板
 */

import React, { useEffect, useState } from "react";
import { getRunArtifacts, downloadArtifactText } from "@/apis";
import { useI18n } from "@/hooks/useI18n";
import { VerificationReasons, VerificationReason } from "@/components/common/VerificationReasons";

interface FailureInfo {
  reportText?: string;
  reasons?: VerificationReason[];
  summaryText?: string;
}

interface ReworkPanelProps {
  runId: string;
  planId?: string;
  onRework: (feedback: string, stepId?: string) => Promise<void>;
  loading: boolean;
  error: string | null;
  currentStep?: string;
}

export function ReworkPanel({
  runId,
  planId,
  onRework,
  loading,
  error,
  currentStep,
}: ReworkPanelProps) {
  const { t } = useI18n();
  const [failureInfo, setFailureInfo] = useState<FailureInfo | null>(null);
  const [failureError, setFailureError] = useState<string | null>(null);
  const [reworkFeedback, setReworkFeedback] = useState("");

  // 加载失败详情
  useEffect(() => {
    async function loadFailureInfo() {
      try {
        const artifacts = await getRunArtifacts(runId, planId);
        const info: FailureInfo = {};

        // 查找失败报告
        const reportItem = artifacts.items?.find(
          (item) =>
            item.path.includes("failure") || item.path.includes("error")
        );
        if (reportItem) {
          info.reportText = await downloadArtifactText(
            runId,
            reportItem.path,
            planId
          );
        }

        // 查找验证原因
        const reasonsItem = artifacts.items?.find((item) =>
          item.path.includes("verification")
        );
        if (reasonsItem) {
          const text = await downloadArtifactText(
            runId,
            reasonsItem.path,
            planId
          );
          try {
            const parsed = JSON.parse(text);
            if (Array.isArray(parsed.reasons)) {
              info.reasons = parsed.reasons;
            }
          } catch {
            // 忽略解析错误
          }
        }

        // 查找摘要
        const summaryItem = artifacts.items?.find((item) =>
          item.path.includes("summary")
        );
        if (summaryItem) {
          info.summaryText = await downloadArtifactText(
            runId,
            summaryItem.path,
            planId
          );
        }

        setFailureInfo(info);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : t.messages.loadFailureDetailFailed;
        setFailureError(message);
      }
    }

    loadFailureInfo();
  }, [runId, planId, t]);

  const handleRework = async () => {
    await onRework(reworkFeedback, currentStep);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.titles.rework}</h2>
      </div>

      {(error || failureError) && (
        <div className="page-alert">{error || failureError}</div>
      )}

      {failureInfo?.summaryText && (
        <pre className="pre">{failureInfo.summaryText}</pre>
      )}

      {failureInfo?.reasons && failureInfo.reasons.length > 0 && (
        <VerificationReasons reasons={failureInfo.reasons} />
      )}

      {failureInfo?.reportText && (
        <pre className="pre">{failureInfo.reportText}</pre>
      )}

      <textarea
        className="page-textarea"
        placeholder={t.messages.reworkFeedbackPlaceholder}
        value={reworkFeedback}
        onChange={(e) => setReworkFeedback(e.target.value)}
        rows={3}
      />

      <div className="panel-actions">
        <button
          className="button-primary"
          onClick={handleRework}
          disabled={loading}
        >
          {t.buttons.reworkStep}
        </button>
      </div>
    </div>
  );
}
