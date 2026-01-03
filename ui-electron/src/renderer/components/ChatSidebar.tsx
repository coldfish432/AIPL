import React, { useState } from "react";
import { ChatSession } from "../hooks/useSession";
import { useI18n } from "../lib/useI18n";

type Props = {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
};

export default function ChatSidebar({ sessions, activeId, onSelect, onRename, onDelete }: Props) {
  const { t } = useI18n();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  function startRename(session: ChatSession) {
    setEditingId(session.id);
    setEditingTitle(session.title);
  }

  function cancelRename() {
    setEditingId(null);
    setEditingTitle("");
  }

  function saveRename(sessionId: string) {
    const nextTitle = editingTitle.trim();
    if (!nextTitle) {
      cancelRename();
      return;
    }
    onRename(sessionId, nextTitle);
    cancelRename();
  }

  return (
    <aside className="pilot-sidebar">
      <div className="pilot-sidebar-title">{t.titles.chat}</div>
      <div className="pilot-chat-list">
        {sessions.map((session) => (
          <div key={session.id} className={`pilot-chat-item ${session.id === activeId ? "active" : ""}`}>
            {editingId === session.id ? (
              <div className="pilot-chat-edit">
                <input
                  className="pilot-chat-input"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  placeholder={t.labels.chatTitle}
                />
                <div className="pilot-chat-actions">
                  <button className="pilot-chat-action" onClick={() => saveRename(session.id)}>{t.buttons.save}</button>
                  <button className="pilot-chat-action danger" onClick={cancelRename}>{t.buttons.cancel}</button>
                </div>
              </div>
            ) : (
              <>
                <button className="pilot-chat-title" onClick={() => onSelect(session.id)}>
                  <span>{session.title}</span>
                </button>
                <div className="pilot-chat-actions">
                  <button className="pilot-chat-action" onClick={() => startRename(session)}>{t.buttons.rename}</button>
                  <button className="pilot-chat-action danger" onClick={() => onDelete(session.id)}>{t.buttons.delete}</button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
