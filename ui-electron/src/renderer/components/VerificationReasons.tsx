import React from "react";
import { useI18n } from "../lib/useI18n";

export type VerificationReason = {
  type: string;
  cmd?: string;
  file?: string;
  expected?: string;
  actual?: string;
  hint?: string;
};

type Props = {
  reasons: VerificationReason[];
  onViewLog?: (logPath: string) => void;
};

export default function VerificationReasons({ reasons }: Props) {
  const { language, t } = useI18n();
  const typeLabels: Record<string, string> =
    language === "zh"
      ? {
          command_failed: "命令执行失败",
          command_timeout: "命令执行超时",
          command_not_executed: "命令未执行",
          missing_file: "文件缺失",
          content_mismatch: "内容不匹配",
          schema_mismatch: "Schema 不匹配",
          invalid_path: "无效路径"
        }
      : {
          command_failed: "Command failed",
          command_timeout: "Command timeout",
          command_not_executed: "Command not executed",
          missing_file: "Missing file",
          content_mismatch: "Content mismatch",
          schema_mismatch: "Schema mismatch",
          invalid_path: "Invalid path"
        };

  if (!reasons || reasons.length === 0) {
    return <div className="muted">{t.messages.noVerificationFailures}</div>;
  }

  return (
    <div className="verification-reasons">
      {reasons.map((reason, idx) => (
        <div key={`${reason.type}-${idx}`} className="reason-card">
          <div className="reason-header">
            <span className="reason-icon">⚠</span>
            <span className="reason-type">{typeLabels[reason.type] || reason.type}</span>
          </div>
          <div className="reason-body">
            {reason.cmd && (
              <div className="reason-row">
                <span className="reason-label">{t.labels.command}:</span>
                <code className="reason-value">{reason.cmd}</code>
              </div>
            )}
            {reason.file && (
              <div className="reason-row">
                <span className="reason-label">{t.labels.file}:</span>
                <code className="reason-value">{reason.file}</code>
              </div>
            )}
            {reason.expected && (
              <div className="reason-row">
                <span className="reason-label">{t.labels.expected}:</span>
                <span className="reason-value">{reason.expected}</span>
              </div>
            )}
            {reason.actual && (
              <div className="reason-row">
                <span className="reason-label">{t.labels.actual}:</span>
                <span className="reason-value error">{reason.actual}</span>
              </div>
            )}
            {reason.hint && (
              <div className="reason-row">
                <span className="reason-label">{t.labels.hint}:</span>
                <span className="reason-value muted">{reason.hint}</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
