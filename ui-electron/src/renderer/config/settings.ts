/**
 * 应用配置
 */

export interface AppConfig {
  api: {
    baseUrl: string;
    timeout: number;
  };
  ui: {
    pollInterval: number;
    maxEventsDisplay: number;
    dateLocale: string;
  };
  storage: {
    workspaceKey: string;
    baseWorkspaceKey: string;
    runOrderKey: string;
    workspaceHistoryKey: string;
    sessionsKey: string;
    activeSessionKey: string;
    languageKey: string;
    pilotSessionsKey?: string;
    executionLockKey: string;
    chatStateKey: string;
    pendingRequestKey: string;
  };
}

const defaultConfig: AppConfig = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : "http://127.0.0.1:18088"),
    timeout: 30000,
  },
  ui: {
    pollInterval: 1000,
    maxEventsDisplay: 500,
    dateLocale: "zh-CN",
  },
  storage: {
    workspaceKey: "aipl.workspace",
    baseWorkspaceKey: "aipl.pilot.baseWorkspace",
    runOrderKey: "aipl.dashboard.runOrder",
    workspaceHistoryKey: "aipl.workspace.history",
    sessionsKey: "aipl.pilot.sessions",
    activeSessionKey: "aipl.pilot.active",
    languageKey: "aipl.language",
    pilotSessionsKey: "aipl-pilot-sessions",
    executionLockKey: "aipl-lock_exec",
    chatStateKey: "aipl-lock_chat",
    pendingRequestKey: "aipl-lock_pending",
  },
};

function loadConfig(): AppConfig {
  return {
    ...defaultConfig,
    api: {
      ...defaultConfig.api,
      baseUrl: import.meta.env.VITE_API_BASE_URL || defaultConfig.api.baseUrl,
    },
  };
}

export const config = loadConfig();
export const API_BASE_URL = config.api.baseUrl;
export const UI_CONFIG = config.ui;
export const STORAGE_KEYS = config.storage;
const DEFAULT_MAX_SESSIONS = 20;
const DEFAULT_MAX_WORKSPACE_HISTORY = 10;
export const FEATURES = {
  pollingInterval: config.ui.pollInterval,
  maxEventsDisplay: config.ui.maxEventsDisplay,
  maxSessions: DEFAULT_MAX_SESSIONS,
  maxWorkspaceHistory: DEFAULT_MAX_WORKSPACE_HISTORY,
};

export const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;
