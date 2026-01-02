import React from "react";

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

const TYPE_LABELS: Record<string, string> = {
  command_failed: "命令执行失败",
  command_timeout: "命令执行超时",
  command_not_executed: "命令未执行",
  missing_file: "文件缺失",
  content_mismatch: "内容不匹配",
  schema_mismatch: "Schema 不匹配",
  invalid_path: "无效路径"
};

export default function VerificationReasons({ reasons }: Props) {
  if (!reasons || reasons.length === 0) {
    return <div className="muted">无验证失败信息。</div>;
  }

  return (
    <div className="verification-reasons">
      {reasons.map((reason, idx) => (
        <div key={`${reason.type}-${idx}`} className="reason-card">
          <div className="reason-header">
            <span className="reason-icon">⚠</span>
            <span className="reason-type">{TYPE_LABELS[reason.type] || reason.type}</span>
          </div>
          <div className="reason-body">
            {reason.cmd && (
              <div className="reason-row">
                <span className="reason-label">命令:</span>
                <code className="reason-value">{reason.cmd}</code>
              </div>
            )}
            {reason.file && (
              <div className="reason-row">
                <span className="reason-label">文件:</span>
                <code className="reason-value">{reason.file}</code>
              </div>
            )}
            {reason.expected && (
              <div className="reason-row">
                <span className="reason-label">期望:</span>
                <span className="reason-value">{reason.expected}</span>
              </div>
            )}
            {reason.actual && (
              <div className="reason-row">
                <span className="reason-label">实际:</span>
                <span className="reason-value error">{reason.actual}</span>
              </div>
            )}
            {reason.hint && (
              <div className="reason-row">
                <span className="reason-label">提示:</span>
                <span className="reason-value muted">{reason.hint}</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
