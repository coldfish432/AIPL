/**
 * Session Hook
 * 管理聊天会话
 */

import { useCallback, useEffect, useState } from "react";
import { STORAGE_KEYS, FEATURES } from "@/config/settings";
import type { ChatMessage } from "@/apis/types";

// ============================================================
// Types
// ============================================================

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface UseSessionReturn {
  sessions: ChatSession[];
  activeSession: ChatSession | null;
  activeSessionId: string | null;
  
  // Actions
  createSession: () => ChatSession;
  selectSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, title: string) => void;
  addMessage: (message: ChatMessage) => void;
  clearMessages: () => void;
}

// ============================================================
// Storage Helpers
// ============================================================

function generateId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.sessionsKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]): void {
  try {
    const limited = sessions.slice(0, FEATURES.maxSessions);
    localStorage.setItem(STORAGE_KEYS.sessionsKey, JSON.stringify(limited));
  } catch {
    // Ignore storage errors
  }
}

function loadActiveSessionId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEYS.activeSessionKey);
  } catch {
    return null;
  }
}

function saveActiveSessionId(sessionId: string | null): void {
  try {
    if (sessionId) {
      localStorage.setItem(STORAGE_KEYS.activeSessionKey, sessionId);
    } else {
      localStorage.removeItem(STORAGE_KEYS.activeSessionKey);
    }
  } catch {
    // Ignore storage errors
  }
}

// ============================================================
// Hook
// ============================================================

export function useSession(): UseSessionReturn {
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() =>
    loadActiveSessionId()
  );

  // 持久化 sessions
  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  // 持久化 activeSessionId
  useEffect(() => {
    saveActiveSessionId(activeSessionId);
  }, [activeSessionId]);

  // 获取当前会话
  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  // 创建新会话
  const createSession = useCallback((): ChatSession => {
    const newSession: ChatSession = {
      id: generateId(),
      title: `对话 ${sessions.length + 1}`,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);

    return newSession;
  }, [sessions.length]);

  // 选择会话
  const selectSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
  }, []);

  // 删除会话
  const deleteSession = useCallback(
    (sessionId: string) => {
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));

      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.id !== sessionId);
        setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
      }
    },
    [activeSessionId, sessions]
  );

  // 重命名会话
  const renameSession = useCallback((sessionId: string, title: string) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s
      )
    );
  }, []);

  // 添加消息
  const addMessage = useCallback(
    (message: ChatMessage) => {
      if (!activeSessionId) return;

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? {
                ...s,
                messages: [...s.messages, message],
                updatedAt: Date.now(),
                // 自动设置标题
                title:
                  s.messages.length === 0 && message.role === "user"
                    ? message.content.slice(0, 30) + (message.content.length > 30 ? "..." : "")
                    : s.title,
              }
            : s
        )
      );
    },
    [activeSessionId]
  );

  // 清除当前会话消息
  const clearMessages = useCallback(() => {
    if (!activeSessionId) return;

    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, messages: [], updatedAt: Date.now() }
          : s
      )
    );
  }, [activeSessionId]);

  return {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    selectSession,
    deleteSession,
    renameSession,
    addMessage,
    clearMessages,
  };
}
