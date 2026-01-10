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
      sessionKey: string;
      sessionActiveKey: string;
      baseWorkspaceKey: string;
      runOrderKey: string;
      workspaceHistoryKey: string;
    };
}

const defaultConfig: AppConfig = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : "http://127.0.0.1:18088"),
    timeout: 30000
  },
  ui: {
    pollInterval: 1000,
    maxEventsDisplay: 500,
    dateLocale: "zh-CN"
  },
    storage: {
      workspaceKey: "aipl.workspace",
      sessionKey: "aipl.pilot.sessions",
      sessionActiveKey: "aipl.pilot.active",
      baseWorkspaceKey: "aipl.pilot.baseWorkspace",
      runOrderKey: "aipl.dashboard.runOrder",
      workspaceHistoryKey: "aipl.workspace.history"
    }
  };

function loadConfig(): AppConfig {
  return {
    ...defaultConfig,
    api: {
      ...defaultConfig.api,
      baseUrl: import.meta.env.VITE_API_BASE_URL || defaultConfig.api.baseUrl
    }
  };
}

export const config = loadConfig();
export const API_BASE_URL = config.api.baseUrl;
export const UI_CONFIG = config.ui;
export const STORAGE_KEYS = config.storage;
