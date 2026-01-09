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
      <div className="assistant-composer">
        <textarea
          className="assistant-textarea"
          placeholder={placeholder || t.messages.taskInputPlaceholder}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          disabled={disabled || loading}
          rows={3}
        />
        <div className="assistant-footer">
          <button className="button-primary" onClick={onSend} disabled={!canSend}>
          {loading ? t.messages.sendLoading : t.buttons.send}
        </button>
        {loading && (
            <button className="button-danger" onClick={onTerminate}>
            {loadingKind === "plan" ? t.buttons.terminatePlan : t.buttons.terminateChat}
          </button>
        )}
          {error && <span className="page-inline-error">{error}</span>}
          {loadingKind === "plan" && <span className="page-inline-note">{t.messages.planLoading}</span>}
          {loadingKind === "chat" && <span className="page-inline-note">{t.messages.chatLoading}</span>}
        </div>
      </div>
    </>
  );
}
