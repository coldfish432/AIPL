/**
 * Verification Reasons 组件
 * 显示验证失败原因
 */

import React from "react";
import { AlertTriangle, CheckCircle, XCircle, Info } from "lucide-react";

export interface VerificationReason {
  type?: string;
  category?: string;
  message?: string;
  detail?: string;
  severity?: "error" | "warning" | "info";
  passed?: boolean;
}

interface VerificationReasonsProps {
  reasons: VerificationReason[];
  title?: string;
}

export function VerificationReasons({
  reasons,
  title = "验证结果",
}: VerificationReasonsProps) {
  if (!reasons || reasons.length === 0) {
    return null;
  }

  const failedReasons = reasons.filter((r) => !r.passed);
  const passedReasons = reasons.filter((r) => r.passed);

  return (
    <div className="verification-reasons">
      <h4 className="verification-title">{title}</h4>

      {/* 失败原因 */}
      {failedReasons.length > 0 && (
        <div className="verification-section failed">
          <div className="verification-section-header">
            <XCircle size={14} />
            <span>失败 ({failedReasons.length})</span>
          </div>
          <ul className="verification-list">
            {failedReasons.map((reason, idx) => (
              <ReasonItem key={idx} reason={reason} />
            ))}
          </ul>
        </div>
      )}

      {/* 通过的检查 */}
      {passedReasons.length > 0 && (
        <div className="verification-section passed">
          <div className="verification-section-header">
            <CheckCircle size={14} />
            <span>通过 ({passedReasons.length})</span>
          </div>
          <ul className="verification-list collapsed">
            {passedReasons.map((reason, idx) => (
              <ReasonItem key={idx} reason={reason} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// 单个原因项
function ReasonItem({ reason }: { reason: VerificationReason }) {
  const severity = reason.severity || (reason.passed ? "info" : "error");

  return (
    <li className={`verification-item ${severity}`}>
      <div className="verification-item-icon">
        <SeverityIcon severity={severity} passed={reason.passed} />
      </div>
      <div className="verification-item-content">
        <div className="verification-item-header">
          {reason.type && (
            <span className="verification-type">{reason.type}</span>
          )}
          {reason.category && (
            <span className="verification-category">{reason.category}</span>
          )}
        </div>
        {reason.message && (
          <div className="verification-message">{reason.message}</div>
        )}
        {reason.detail && (
          <div className="verification-detail">{reason.detail}</div>
        )}
      </div>
    </li>
  );
}

// 严重程度图标
function SeverityIcon({
  severity,
  passed,
}: {
  severity: string;
  passed?: boolean;
}) {
  if (passed) {
    return <CheckCircle size={14} className="icon-success" />;
  }

  switch (severity) {
    case "error":
      return <XCircle size={14} className="icon-error" />;
    case "warning":
      return <AlertTriangle size={14} className="icon-warning" />;
    default:
      return <Info size={14} className="icon-info" />;
  }
}
