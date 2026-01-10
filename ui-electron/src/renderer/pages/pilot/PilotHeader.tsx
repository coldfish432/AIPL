import React from "react";
import { useI18n } from "../../lib/useI18n";

type Props = {
  workspace: string;
  onStartFlow: () => void;
  onNewChat: () => void;
  loading: boolean;
  locked?: boolean;
};

export default function PilotHeader({
  workspace,
  onStartFlow,
  onNewChat,
  loading,
  locked = false
}: Props) {
  const { t } = useI18n();

  return (
    <div className="assistant-controls">
      <button className="button-primary" onClick={onStartFlow} disabled={loading || locked}>
        {loading ? t.messages.planLoading : t.buttons.startFlow}
      </button>
      <button className="button-secondary" onClick={onNewChat} disabled={loading}>
        {t.buttons.newChat}
      </button>
    </div>
  );
}
