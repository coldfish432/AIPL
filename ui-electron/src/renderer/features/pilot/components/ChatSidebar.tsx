/**
 * Chat Sidebar 组件
 * 会话列表侧边栏
 */

import React from "react";
import { Plus, MessageSquare, Trash2, Edit2, Check, X } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import { formatRelativeTime } from "@/lib/normalize";
import type { ChatSession } from "../hooks/useSession";

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
  onDelete: (sessionId: string) => void;
  onRename: (sessionId: string, title: string) => void;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  onDelete,
  onRename,
}: ChatSidebarProps) {
  const { t } = useI18n();
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingTitle, setEditingTitle] = React.useState("");

  const handleStartEdit = (session: ChatSession) => {
    setEditingId(session.id);
    setEditingTitle(session.title);
  };

  const handleSaveEdit = (sessionId: string) => {
    if (editingTitle.trim()) {
      onRename(sessionId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(t.messages.confirmDeleteChat)) {
      onDelete(sessionId);
    }
  };

  return (
    <div className="chat-sidebar">
      {/* Header */}
      <div className="chat-sidebar-header">
        <h3 className="chat-sidebar-title">{t.titles.chat}</h3>
        <button className="button-icon" onClick={onCreate} title={t.buttons.newChat}>
          <Plus size={16} />
        </button>
      </div>

      {/* Session List */}
      <div className="chat-session-list">
        {sessions.length === 0 && (
          <div className="chat-empty">
            <MessageSquare size={24} />
            <span>暂无对话</span>
          </div>
        )}

        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          const isEditing = session.id === editingId;

          return (
            <div
              key={session.id}
              className={`chat-session-item ${isActive ? "active" : ""}`}
              onClick={() => !isEditing && onSelect(session.id)}
            >
              {isEditing ? (
                <div className="chat-session-edit">
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveEdit(session.id);
                      if (e.key === "Escape") handleCancelEdit();
                    }}
                    autoFocus
                    className="chat-session-edit-input"
                  />
                  <button
                    className="button-icon sm"
                    onClick={() => handleSaveEdit(session.id)}
                  >
                    <Check size={14} />
                  </button>
                  <button
                    className="button-icon sm"
                    onClick={handleCancelEdit}
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <div className="chat-session-content">
                    <div className="chat-session-title">{session.title}</div>
                    <div className="chat-session-meta">
                      {session.messages.length} 条消息 ·{" "}
                      {formatRelativeTime(session.updatedAt)}
                    </div>
                  </div>
                  <div className="chat-session-actions">
                    <button
                      className="button-icon sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStartEdit(session);
                      }}
                      title={t.buttons.rename}
                    >
                      <Edit2 size={12} />
                    </button>
                    <button
                      className="button-icon sm danger"
                      onClick={(e) => handleDelete(session.id, e)}
                      title={t.buttons.delete}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
