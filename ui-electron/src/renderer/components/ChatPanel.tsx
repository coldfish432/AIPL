import React from "react";
import { ChatSession } from "../hooks/useSession";

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

function getRoleLabel(role: string): string {
  if (role === "system") return "系统";
  return role === "user" ? "用户" : "助手";
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
  if (!session) {
    return <div className="muted">请先创建对话。</div>;
  }

  return (
    <div className="chat">
      {session.messages.length === 0 && (
        <div className="muted">请先描述你要执行的任务。</div>
      )}
      {session.messages.map((msg, idx) => (
        <div key={idx} className={`chat-msg ${msg.role}`}>
          <div className="chat-role">{getRoleLabel(msg.role)}</div>
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
                加入队列
              </button>
              <button onClick={onStartFlow} disabled={loading}>
                {loading ? "生成中..." : "重新规划"}
              </button>
            </div>
          )}
          {msg.kind === "confirm" && session.awaitingConfirm && (
            <div className="chat-actions">
              <textarea
                className="textarea"
                placeholder="请输入最终计划内容"
                value={session.finalPlanText || ""}
                onChange={(e) => onUpdateFinalPlan(e.target.value)}
                rows={2}
              />
              <button onClick={onConfirmPlan} disabled={loading}>
                {loading ? "生成中..." : "确认"}
              </button>
              <button className="danger" onClick={onCancelPlan} disabled={loading}>
                取消
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
