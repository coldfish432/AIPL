import React from "react";
import { useI18n } from "../../lib/useI18n";

type Props = {
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  canSend: boolean;
  loading: boolean;
  loadingKind: "chat" | "plan" | null;
  error: string | null;
  onTerminate: () => void;
  disabled?: boolean;
  placeholder?: string;
};

export default function PilotComposer({
  input,
  onInputChange,
  onSend,
  canSend,
  loading,
  loadingKind,
  error,
  onTerminate,
  disabled = false,
  placeholder
}: Props) {
  const { t } = useI18n();

  return (
    <>
      <div className="row">
        <textarea
          className="textarea"
          placeholder={placeholder || t.messages.taskInputPlaceholder}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          disabled={disabled || loading}
          rows={3}
        />
      </div>
      <div className="row">
        <button onClick={onSend} disabled={!canSend}>
          {loading ? t.messages.sendLoading : t.buttons.send}
        </button>
        {loading && (
          <button className="danger" onClick={onTerminate}>
            {loadingKind === "plan" ? t.buttons.terminatePlan : t.buttons.terminateChat}
          </button>
        )}
        {error && <span className="error">{error}</span>}
        {loadingKind === "plan" && <span className="muted">{t.messages.planLoading}</span>}
        {loadingKind === "chat" && <span className="muted">{t.messages.chatLoading}</span>}
      </div>
    </>
  );
}
