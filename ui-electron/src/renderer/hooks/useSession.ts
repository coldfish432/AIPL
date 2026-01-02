import { useEffect, useMemo, useState } from "react";
import { loadJson, saveDebounced } from "../lib/storage";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  kind?: "text" | "plan" | "confirm";
  planId?: string | null;
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
  createdAt: number;
  updatedAt: number;
};

const SESSION_KEY = "aipl.pilot.sessions";
const ACTIVE_KEY = "aipl.pilot.active";

function makeSessionTitle(index: number): string {
  return `对话 ${index}`;
}

function createEmptySession(index: number): ChatSession {
  const now = Date.now();
  return {
    id: `chat-${now}`,
    title: makeSessionTitle(index),
    messages: [],
    planId: null,
    planText: "",
    pendingPlanMessages: null,
    awaitingConfirm: false,
    finalPlanText: "",
    createdAt: now,
    updatedAt: now
  };
}

function loadSessions(): ChatSession[] {
  const sessions = loadJson<ChatSession[]>(SESSION_KEY, []);
  if (!Array.isArray(sessions) || sessions.length === 0) {
    return [createEmptySession(1)];
  }
  return sessions.filter((session) => session && session.id && session.title);
}

export function useSession() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeId, setActiveIdState] = useState<string | null>(() => {
    const storedActive = localStorage.getItem(ACTIVE_KEY);
    if (storedActive) return storedActive;
    return sessions[0]?.id || null;
  });

  useEffect(() => {
    saveDebounced(SESSION_KEY, sessions);
  }, [sessions]);

  useEffect(() => {
    if (activeId) {
      localStorage.setItem(ACTIVE_KEY, activeId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  }, [activeId]);

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
    const next = [createEmptySession(sessions.length + 1), ...sessions];
    updateSessions(next);
    setActiveIdState(next[0].id);
  };

  const updateSession = (sessionId: string, updater: (session: ChatSession) => ChatSession) => {
    updateSessions(
      sessions.map((session) => (session.id === sessionId ? updater(session) : session))
    );
  };

  const deleteSession = (sessionId: string) => {
    const next = sessions.filter((session) => session.id !== sessionId);
    if (next.length === 0) {
      const fallback = createEmptySession(1);
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
