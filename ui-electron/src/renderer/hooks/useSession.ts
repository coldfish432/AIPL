import { useEffect, useMemo, useRef, useState } from "react";
import { loadJson, saveDebounced } from "../lib/storage";
import { STORAGE_KEYS } from "../config/settings";
import { useI18n } from "../lib/useI18n";

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  kind?: "text" | "plan" | "confirm";
  planId?: string | null;
};

export type ChatPending = {
  kind: "chat" | "plan";
  startedAt: number;
  requestId?: string;
};

export type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  planId: string | null;
  planText: string;
  pendingPlanMessages: ChatMessage[] | null;
  awaitingConfirm: boolean;
  finalPlanText: string;
  pending?: ChatPending | null;
  createdAt: number;
  updatedAt: number;
};

const SESSION_KEY = STORAGE_KEYS.sessionKey;
const ACTIVE_KEY = STORAGE_KEYS.sessionActiveKey;
const SESSIONS_UPDATED_EVENT = "aipl-sessions-updated";

const SESSION_TITLE_PREFIX: Record<"zh" | "en", string> = {
  zh: "对话",
  en: "Chat"
};

function makeSessionTitle(index: number, prefix: string): string {
  return `${prefix} ${index}`;
}

function createEmptySession(index: number, prefix: string): ChatSession {
  const now = Date.now();
  return {
    id: `chat-${now}`,
    title: makeSessionTitle(index, prefix),
    messages: [],
    planId: null,
    planText: "",
    pendingPlanMessages: null,
    awaitingConfirm: false,
    finalPlanText: "",
    pending: null,
    createdAt: now,
    updatedAt: now
  };
}

function normalizeSessionTitle(title: string, nextPrefix: string): string {
  const match = title.match(/^(对话|Chat)\s+(\d+)$/);
  if (!match) return title;
  return `${nextPrefix} ${match[2]}`;
}

export function loadStoredSessions(): ChatSession[] {
  const sessions = loadJson<ChatSession[]>(SESSION_KEY, []);
  if (!Array.isArray(sessions)) return [];
  return sessions.filter((session) => session && session.id && session.title);
}

export function getStoredSession(sessionId: string): ChatSession | null {
  const sessions = loadStoredSessions();
  return sessions.find((session) => session.id === sessionId) || null;
}

export function saveStoredSessions(sessions: ChatSession[]): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(sessions));
  window.dispatchEvent(new Event(SESSIONS_UPDATED_EVENT));
}

export function updateStoredSessions(
  updater: (sessions: ChatSession[]) => ChatSession[]
): ChatSession[] {
  const current = loadStoredSessions();
  const next = updater(current);
  saveStoredSessions(next);
  return next;
}

export function updateStoredSession(
  sessionId: string,
  updater: (session: ChatSession) => ChatSession
): ChatSession[] {
  return updateStoredSessions((sessions) =>
    sessions.map((session) => (session.id === sessionId ? updater(session) : session))
  );
}

export function appendStoredMessage(sessionId: string, message: ChatMessage): ChatSession[] {
  return updateStoredSession(sessionId, (session) => ({
    ...session,
    messages: session.messages.concat(message),
    updatedAt: Date.now()
  }));
}

export function setStoredPending(sessionId: string, pending: ChatPending | null): ChatSession[] {
  return updateStoredSession(sessionId, (session) => ({
    ...session,
    pending,
    updatedAt: Date.now()
  }));
}

function loadSessions(prefix: string): ChatSession[] {
  const sessions = loadStoredSessions();
  if (!Array.isArray(sessions) || sessions.length === 0) {
    return [createEmptySession(1, prefix)];
  }
  return sessions.filter((session) => session && session.id && session.title);
}

export function useSession() {
  const { language, t } = useI18n();
  const titlePrefix = t.titles.chat;
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions(titlePrefix));
  const [activeId, setActiveIdState] = useState<string | null>(() => {
    const storedActive = localStorage.getItem(ACTIVE_KEY);
    if (storedActive) return storedActive;
    return sessions[0]?.id || null;
  });
  const seededRef = useRef(false);

  useEffect(() => {
    saveDebounced(SESSION_KEY, sessions);
  }, [sessions]);

  useEffect(() => {
    if (seededRef.current) return;
    const storedRaw = localStorage.getItem(SESSION_KEY);
    if (!storedRaw && sessions.length > 0) {
      saveStoredSessions(sessions);
    }
    seededRef.current = true;
  }, [sessions]);

  useEffect(() => {
    if (activeId) {
      localStorage.setItem(ACTIVE_KEY, activeId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  }, [activeId]);

  useEffect(() => {
    const syncSessions = () => {
      const stored = loadStoredSessions();
      if (stored.length === 0) return;
      setSessions(stored);
    };
    window.addEventListener(SESSIONS_UPDATED_EVENT, syncSessions);
    return () => window.removeEventListener(SESSIONS_UPDATED_EVENT, syncSessions);
  }, []);

  useEffect(() => {
    const nextPrefix = SESSION_TITLE_PREFIX[language];
    let changed = false;
    const nextSessions = sessions.map((session) => {
      const nextTitle = normalizeSessionTitle(session.title, nextPrefix);
      if (nextTitle !== session.title) {
        changed = true;
        return { ...session, title: nextTitle };
      }
      return session;
    });
    if (changed) {
      setSessions(nextSessions);
    }
  }, [language, sessions]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeId) || sessions[0] || null,
    [sessions, activeId]
  );

  const setActiveId = (id: string) => {
    setActiveIdState(id);
  };

  const updateSessions = (next: ChatSession[]) => {
    setSessions(next);
    if (activeId && !next.some((session) => session.id === activeId)) {
      const fallback = next[0]?.id || null;
      setActiveIdState(fallback);
    }
  };

  const createNewSession = () => {
    if (sessions.length > 0 && sessions[0].messages.length === 0) {
      setActiveIdState(sessions[0].id);
      return;
    }
    const next = [createEmptySession(sessions.length + 1, titlePrefix), ...sessions];
    updateSessions(next);
    setActiveIdState(next[0].id);
  };

  const updateSession = (sessionId: string, updater: (session: ChatSession) => ChatSession) => {
    setSessions((prev) => {
      const next = prev.map((session) => (session.id === sessionId ? updater(session) : session));
      if (activeId && !next.some((session) => session.id === activeId)) {
        const fallback = next[0]?.id || null;
        setActiveIdState(fallback);
      }
      return next;
    });
  };

  const deleteSession = (sessionId: string) => {
    const next = sessions.filter((session) => session.id !== sessionId);
    if (next.length === 0) {
      const fallback = createEmptySession(1, titlePrefix);
      updateSessions([fallback]);
      setActiveIdState(fallback.id);
      return;
    }
    updateSessions(next);
  };

  const renameSession = (sessionId: string, title: string) => {
    updateSession(sessionId, (session) => ({ ...session, title, updatedAt: Date.now() }));
  };

  const addMessage = (sessionId: string, message: ChatMessage) => {
    updateSession(sessionId, (session) => ({
      ...session,
      messages: session.messages.concat(message),
      updatedAt: Date.now()
    }));
  };

  return {
    sessions,
    activeSession,
    activeId,
    setActiveId,
    createNewSession,
    updateSession,
    deleteSession,
    renameSession,
    addMessage
  };
}
