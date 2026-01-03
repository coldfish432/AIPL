import React from "react";
import { ChatSession } from "../hooks/useSession";
import { useI18n } from "../lib/useI18n";

type Props = {
  session: ChatSession | null;
  loading: boolean;
  confirmLoading: boolean;
  onEnqueuePlan: (planId: string, planText: string) => void;
  onStartFlow: () => void;
  onConfirmPlan: () => void;
  onCancelPlan: () => void;
  onUpdateFinalPlan: (value: string) => void;
};

function getRoleLabel(role: string, labels: { roleSystem: string; roleUser: string; roleAssistant: string }): string {
  if (role === "system") return labels.roleSystem;
  return role === "user" ? labels.roleUser : labels.roleAssistant;
}

export default function ChatPanel({
  session,
  loading,
  confirmLoading,
  onEnqueuePlan,
  onStartFlow,
  onConfirmPlan,
  onCancelPlan,
  onUpdateFinalPlan
}: Props) {
  const { t } = useI18n();

  if (!session) {
    return <div className="muted">{t.messages.needCreateChat}</div>;
  }

  return (
    <div className="chat">
      {session.messages.length === 0 && (
        <div className="muted">{t.messages.needDescribeTask}</div>
      )}
      {session.messages.map((msg, idx) => (
        <div key={idx} className={`chat-msg ${msg.role}`}>
          <div className="chat-role">{getRoleLabel(msg.role, t.labels)}</div>
          <div className="chat-content">{msg.content}</div>
          {msg.kind === "plan" && (
            <div className="chat-actions">
              <button
                onClick={() => {
                  const planId = msg.planId || session.planId;
                  if (!planId) return;
                  onEnqueuePlan(planId, session.planText || "");
                }}
                disabled={confirmLoading || !session.planId}
              >
                {t.buttons.addQueue}
              </button>
              <button onClick={onStartFlow} disabled={loading}>
                {loading ? t.messages.planLoading : t.buttons.replan}
              </button>
            </div>
          )}
          {msg.kind === "confirm" && session.awaitingConfirm && (
            <div className="chat-actions">
              <textarea
                className="textarea"
                placeholder={t.labels.finalPlan}
                value={session.finalPlanText || ""}
                onChange={(e) => onUpdateFinalPlan(e.target.value)}
                rows={2}
              />
              <button onClick={onConfirmPlan} disabled={loading}>
                {loading ? t.messages.planLoading : t.buttons.confirm}
              </button>
              <button className="danger" onClick={onCancelPlan} disabled={loading}>
                {t.buttons.cancel}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
