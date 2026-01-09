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
    <div className="assistant-controls">
      <button className="button-primary" onClick={onStartFlow} disabled={loading || confirmLoading || locked}>
        {loading ? t.messages.planLoading : t.buttons.startFlow}
      </button>
      <div className="assistant-policy">
        <label htmlFor="policy-select">{t.labels.policy}</label>
        <select
          id="policy-select"
          value={policy}
          onChange={(event) => onPolicyChange(event.target.value)}
        >
          <option value="safe">{t.labels.policySafe}</option>
          <option value="guarded">{t.labels.policyGuarded}</option>
          <option value="full">{t.labels.policyFull}</option>
        </select>
      </div>
      <button className="button-secondary" onClick={onNewChat} disabled={loading || confirmLoading}>
        {t.buttons.newChat}
      </button>
    </div>
  );
}
