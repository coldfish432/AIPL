import React from "react";
import { useI18n } from "../../lib/useI18n";

type Props = {
  workspace: string;
  policy: string;
  onPolicyChange: (value: string) => void;
  onStartFlow: () => void;
  onNewChat: () => void;
  loading: boolean;
  confirmLoading: boolean;
  locked?: boolean;
};

export default function PilotHeader({
  workspace,
  policy,
  onPolicyChange,
  onStartFlow,
  onNewChat,
  loading,
  confirmLoading,
  locked = false
}: Props) {
  const { t } = useI18n();

  return (
    <div className="row">
      <div className="meta">{t.labels.workspace} {workspace || "-"}</div>
      <label className="pill-toggle">
        <span>{t.labels.policy}</span>
        <select value={policy} onChange={(e) => onPolicyChange(e.target.value)}>
          <option value="safe">{t.labels.policySafe}</option>
          <option value="guarded">{t.labels.policyGuarded}</option>
          <option value="full">{t.labels.policyFull}</option>
        </select>
      </label>
      <button onClick={onStartFlow} disabled={loading || confirmLoading || locked}>
        {loading ? t.messages.planLoading : t.buttons.startFlow}
      </button>
      <button onClick={onNewChat} disabled={loading || confirmLoading}>
        {t.buttons.newChat}
      </button>
    </div>
  );
}
