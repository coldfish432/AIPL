import React from "react";
import { ChatSession } from "../hooks/useSession";
import { useI18n } from "../lib/useI18n";

type FlowState = "idle" | "planning" | "awaiting_confirm" | "executing" | "done" | "error";

type Props = {
  session: ChatSession | null;
  loading: boolean;
  confirmLoading?: boolean;
  flowState?: FlowState;
  canConfirmPlan?: boolean;
  onStartRun: (planId: string, planText: string) => void;
  onStartFlow: () => void;
  onConfirmPlan: () => void;
  onCancelPlan: () => void;
  onUpdateFinalPlan: (value: string) => void;
  onEnqueuePlan?: (planId: string | null, planText: string, session: ChatSession | null) => void;
  locked?: boolean;
};

function getRoleLabel(role: string, labels: { roleSystem: string; roleUser: string; roleAssistant: string }): string {
  if (role === "system") return labels.roleSystem;
  return role === "user" ? labels.roleUser : labels.roleAssistant;
}

export default function ChatPanel({
  session,
  loading,
  confirmLoading,
  canConfirmPlan,
  onStartRun,
  onStartFlow,
  onConfirmPlan,
  onCancelPlan,
  onUpdateFinalPlan,
  onEnqueuePlan,
  locked,
}: Props) {
  const { t } = useI18n();
  const confirmBusy = confirmLoading ?? loading;

  if (!session) {
    return <div className="page-muted">{t.messages.needCreateChat}</div>;
  }

  return (
    <div className="assistant-chat">
      {session.messages.length === 0 && (
        <div className="page-muted">{t.messages.needDescribeTask}</div>
      )}
      {session.messages.map((msg, idx) => (
        <div key={idx} className={`assistant-message ${msg.role}`}>
          <div className="assistant-role">{getRoleLabel(msg.role, t.labels)}</div>
          <div className="assistant-bubble">{msg.content}</div>
          {msg.kind === "plan" && (
            <div className="assistant-actions">
              <button
                className="button-secondary"
                onClick={() => {
                  const planId = msg.planId || session.planId;
                  const planText = msg.content || session.planText || "";
                  if (!planId) return;
                  onStartRun(planId, planText);
                }}
                disabled={
                  !session.planId ||
                  confirmBusy ||
                  (canConfirmPlan === false) ||
                  !!locked
                }
              >
                {t.labels.run}
              </button>
              <button className="button-secondary" onClick={onStartFlow} disabled={loading || !!locked}>
                {loading ? t.messages.planLoading : t.buttons.replan}
              </button>
              {onEnqueuePlan && (
                <button
                  className="button-secondary"
                  onClick={() => onEnqueuePlan(msg.planId || session.planId, msg.content, session)}
                  disabled={
                    !session.planId ||
                    confirmBusy ||
                    (canConfirmPlan === false) ||
                    !!locked
                  }
                >
                  {t.buttons.addQueue}
                </button>
              )}
            </div>
          )}
          {msg.kind === "confirm" && session.awaitingConfirm && (
            <div className="assistant-actions">
              <textarea
                className="assistant-textarea compact"
                placeholder={t.labels.finalPlan}
                value={session.finalPlanText || ""}
                onChange={(e) => onUpdateFinalPlan(e.target.value)}
                rows={2}
              />
              <button className="button-primary" onClick={onConfirmPlan} disabled={confirmBusy || !!locked}>
                {confirmBusy ? t.messages.planLoading : t.buttons.confirm}
              </button>
              <button className="button-danger" onClick={onCancelPlan} disabled={confirmBusy || !!locked}>
                {t.buttons.cancel}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
