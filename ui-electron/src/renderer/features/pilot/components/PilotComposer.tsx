/**
 * Pilot Composer 组件
 * 输入区域
 */

import React, { useCallback, useRef, useState } from "react";
import { Send, Wand2, Play, X } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { FlowStage, PlanPreview } from "../hooks/usePilotFlow";

interface PilotComposerProps {
  stage: FlowStage;
  loading: boolean;
  planPreview: PlanPreview | null;
  disabled?: boolean;
  onSend: (text: string) => void;
  onPlan: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PilotComposer({
  stage,
  loading,
  planPreview,
  disabled,
  onSend,
  onPlan,
  onConfirm,
  onCancel,
}: PilotComposerProps) {
  const { t } = useI18n();
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || loading || disabled) return;

    onSend(text);
    setInput("");

    // 重置 textarea 高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, loading, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 自动调整高度
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    const textarea = e.target;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  };

  // 确认阶段 UI
  if (stage === "confirming" && planPreview) {
    return (
      <div className="pilot-composer confirm-stage">
        <div className="plan-preview">
          <div className="plan-preview-info">
            <span className="plan-preview-label">{t.titles.planPreview}</span>
            <span className="plan-preview-count">
              {planPreview.tasksCount} {t.labels.tasks}
            </span>
          </div>
          <div className="plan-preview-id">
            {t.labels.planId}: {planPreview.planId}
          </div>
        </div>
        <div className="composer-actions">
          <button
            className="button-secondary"
            onClick={onCancel}
            disabled={loading}
          >
            <X size={14} />
            {t.buttons.cancel}
          </button>
          <button
            className="button-primary"
            onClick={onConfirm}
            disabled={loading}
          >
            <Play size={14} />
            {t.buttons.confirm}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pilot-composer">
      <div className="composer-input-wrap">
        <textarea
          ref={textareaRef}
          className="composer-input"
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          disabled={loading || disabled}
          rows={1}
        />
      </div>
      <div className="composer-actions">
        <button
          className="button-secondary"
          onClick={onPlan}
          disabled={loading || disabled || !input.trim()}
          title="生成计划"
        >
          <Wand2 size={14} />
          {t.buttons.propose}
        </button>
        <button
          className="button-primary"
          onClick={handleSend}
          disabled={loading || disabled || !input.trim()}
        >
          <Send size={14} />
          {t.buttons.send}
        </button>
      </div>
    </div>
  );
}
