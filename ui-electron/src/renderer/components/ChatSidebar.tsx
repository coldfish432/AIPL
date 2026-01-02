import React, { useState } from "react";
import { ChatSession } from "../hooks/useSession";

type Props = {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
};

export default function ChatSidebar({ sessions, activeId, onSelect, onRename, onDelete }: Props) {
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
      <div className="pilot-sidebar-title">对话</div>
      <div className="pilot-chat-list">
        {sessions.map((session) => (
          <div key={session.id} className={`pilot-chat-item ${session.id === activeId ? "active" : ""}`}>
            {editingId === session.id ? (
              <div className="pilot-chat-edit">
                <input
                  className="pilot-chat-input"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  placeholder="对话名称"
                />
                <div className="pilot-chat-actions">
                  <button className="pilot-chat-action" onClick={() => saveRename(session.id)}>保存</button>
                  <button className="pilot-chat-action danger" onClick={cancelRename}>取消</button>
                </div>
              </div>
            ) : (
              <>
                <button className="pilot-chat-title" onClick={() => onSelect(session.id)}>
                  <span>{session.title}</span>
                </button>
                <div className="pilot-chat-actions">
                  <button className="pilot-chat-action" onClick={() => startRename(session)}>重命名</button>
                  <button className="pilot-chat-action danger" onClick={() => onDelete(session.id)}>删除</button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
