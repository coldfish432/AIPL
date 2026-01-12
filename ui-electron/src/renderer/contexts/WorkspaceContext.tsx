/**
 * WorkspaceContext - 全局工作区状态管理
 *
 * 功能：
 * 1. 工作区切换后所有界面同步更新
 * 2. 工作区历史记录
 * 3. 本地目录选择
 * 4. 工作区验证
 */

import React, { createContext, useCallback, useContext, useEffect, useState, useMemo } from "react";
import { STORAGE_KEYS, FEATURES } from "@/config/settings";
import { detectWorkspace, getWorkspaceInfo } from "@/services/api";

// ============================================================
// Types
// ============================================================

export interface WorkspaceInfo {
  path: string;
  name: string;
  isValid: boolean;
  error?: string;
}

export interface WorkspaceContextValue {
  // 当前工作区
  workspace: string;
  workspaceInfo: WorkspaceInfo | null;

  // 工作区历史
  history: string[];

  // 状态
  loading: boolean;
  error: string | null;

  // 操作
  setWorkspace: (path: string) => Promise<boolean>;
  browseWorkspace: () => Promise<string | null>;
  validateWorkspace: (path: string) => Promise<boolean>;
  removeFromHistory: (path: string) => void;
  clearHistory: () => void;
  refresh: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

// ============================================================
// Error Messages (双语支持)
// ============================================================

const ERROR_MESSAGES: Record<string, Record<string, string>> = {
  zh: {
    PATH_NOT_FOUND: "路径不存在",
    NOT_A_DIRECTORY: "路径不是目录",
    UNKNOWN: "无法访问工作区，请检查路径是否正确",
    EMPTY_PATH: "请输入工作区路径",
    SET_FAILED: "设置工作区失败",
    ACCESS_DENIED: "无法访问该路径",
  },
  en: {
    PATH_NOT_FOUND: "Path does not exist",
    NOT_A_DIRECTORY: "Path is not a directory",
    UNKNOWN: "Cannot access workspace, please check if the path is correct",
    EMPTY_PATH: "Please enter workspace path",
    SET_FAILED: "Failed to set workspace",
    ACCESS_DENIED: "Cannot access this path",
  },
};

function getErrorMessage(code: string): string {
  const lang = localStorage.getItem("aipl-language") || "zh";
  return ERROR_MESSAGES[lang]?.[code] || ERROR_MESSAGES[lang]?.UNKNOWN || ERROR_MESSAGES.zh.UNKNOWN;
}

// ============================================================
// Storage Helpers
// ============================================================

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.workspaceHistoryKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    const safe = Array.isArray(parsed)
      ? parsed.filter((p) => typeof p === "string" && p.trim())
      : [];
    return safe.slice(0, FEATURES.maxWorkspaceHistory);
  } catch {
    return [];
  }
}

function saveHistory(history: string[]): void {
  const limited = history.slice(0, FEATURES.maxWorkspaceHistory);
  localStorage.setItem(STORAGE_KEYS.workspaceHistoryKey, JSON.stringify(limited));
}

function loadCurrentWorkspace(): string {
  return localStorage.getItem(STORAGE_KEYS.workspaceKey) || "";
}

function saveCurrentWorkspace(path: string): void {
  if (path) {
    localStorage.setItem(STORAGE_KEYS.workspaceKey, path);
  } else {
    localStorage.removeItem(STORAGE_KEYS.workspaceKey);
  }
}

// ============================================================
// Provider
// ============================================================

interface WorkspaceProviderProps {
  children: React.ReactNode;
}

export function WorkspaceProvider({ children }: WorkspaceProviderProps) {
  const [workspace, setWorkspaceState] = useState<string>(() => loadCurrentWorkspace());
  const [workspaceInfo, setWorkspaceInfo] = useState<WorkspaceInfo | null>(null);
  const [history, setHistory] = useState<string[]>(() => loadHistory());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 验证工作区是否存在且可访问
  const validateWorkspace = useCallback(async (path: string): Promise<boolean> => {
    if (!path.trim()) {
      setError(getErrorMessage("EMPTY_PATH"));
      return false;
    }

    try {
      const result = await detectWorkspace(path) as {
        valid?: boolean;
        reason?: string;
        exists?: boolean;
      };

      // 检查 valid 字段
      if (result && result.valid === true) {
        setError(null);
        return true;
      }

      // 根据错误代码获取翻译
      if (result && result.reason) {
        setError(getErrorMessage(result.reason));
      } else {
        setError(getErrorMessage("UNKNOWN"));
      }

      return false;
    } catch (err) {
      console.error("validateWorkspace error:", err);
      setError(getErrorMessage("UNKNOWN"));
      return false;
    }
  }, []);

  // 加载工作区信息
  const loadWorkspaceInfo = useCallback(async (path: string): Promise<WorkspaceInfo | null> => {
    if (!path.trim()) return null;

    try {
      const info = await getWorkspaceInfo(path);
      return {
        path,
        name: (info as any)?.name || path.split(/[/\\]/).pop() || path,
        isValid: true,
      };
    } catch (err) {
      return {
        path,
        name: path.split(/[/\\]/).pop() || path,
        isValid: false,
        error: err instanceof Error ? err.message : getErrorMessage("ACCESS_DENIED"),
      };
    }
  }, []);

  // 设置工作区
  const setWorkspace = useCallback(async (path: string): Promise<boolean> => {
    const trimmed = path.trim();

    if (!trimmed) {
      setWorkspaceState("");
      setWorkspaceInfo(null);
      saveCurrentWorkspace("");
      setError(null);
      return true;
    }

    setLoading(true);
    setError(null);

    try {
      // 验证工作区
      const isValid = await validateWorkspace(trimmed);

      if (!isValid) {
        // validateWorkspace 已经设置了 error
        setLoading(false);
        return false;
      }

      // 加载工作区信息
      const info = await loadWorkspaceInfo(trimmed);

      // 更新状态
      setWorkspaceState(trimmed);
      setWorkspaceInfo(info);
      saveCurrentWorkspace(trimmed);

      // 更新历史记录
      setHistory((prev) => {
        const filtered = prev.filter((p) => p !== trimmed);
        const updated = [trimmed, ...filtered].slice(0, FEATURES.maxWorkspaceHistory);
        saveHistory(updated);
        return updated;
      });

      // 广播工作区变更事件
      window.dispatchEvent(new CustomEvent("aipl-workspace-changed", { detail: { workspace: trimmed } }));

      setLoading(false);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : getErrorMessage("SET_FAILED"));
      setLoading(false);
      return false;
    }
  }, [validateWorkspace, loadWorkspaceInfo]);

  // 浏览本地目录
  const browseWorkspace = useCallback(async (): Promise<string | null> => {
    try {
      if (typeof window !== "undefined" && (window as any).electronAPI?.pickWorkspace) {
        const selected = await (window as any).electronAPI.pickWorkspace();
        if (selected) {
          const success = await setWorkspace(selected);
          return success ? selected : null;
        }
      }
      return null;
    } catch {
      return null;
    }
  }, [setWorkspace]);

  // 从历史中移除
  const removeFromHistory = useCallback((path: string) => {
    setHistory((prev) => {
      const updated = prev.filter((p) => p !== path);
      saveHistory(updated);
      return updated;
    });
  }, []);

  // 清空历史
  const clearHistory = useCallback(() => {
    setHistory([]);
    saveHistory([]);
  }, []);

  // 刷新当前工作区信息
  const refresh = useCallback(async () => {
    if (workspace) {
      setLoading(true);
      const info = await loadWorkspaceInfo(workspace);
      setWorkspaceInfo(info);
      setLoading(false);
    }
  }, [workspace, loadWorkspaceInfo]);

  // 初始化加载
  useEffect(() => {
    if (workspace) {
      loadWorkspaceInfo(workspace).then(setWorkspaceInfo);
    }
  }, []);

  // 监听外部工作区变更
  useEffect(() => {
    const handler = () => {
      const current = loadCurrentWorkspace();
      if (current !== workspace) {
        setWorkspaceState(current);
        if (current) {
          loadWorkspaceInfo(current).then(setWorkspaceInfo);
        } else {
          setWorkspaceInfo(null);
        }
      }
    };

    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [workspace, loadWorkspaceInfo]);

  // 监听语言变更，更新错误信息
  useEffect(() => {
    const handler = () => {
      // 语言变更时，如果有错误，重新获取翻译后的错误信息
      // 这里简单处理：清空错误让用户重试
    };
    window.addEventListener("aipl-language-changed", handler);
    return () => window.removeEventListener("aipl-language-changed", handler);
  }, []);

  const value = useMemo<WorkspaceContextValue>(() => ({
    workspace,
    workspaceInfo,
    history,
    loading,
    error,
    setWorkspace,
    browseWorkspace,
    validateWorkspace,
    removeFromHistory,
    clearHistory,
    refresh,
  }), [
    workspace,
    workspaceInfo,
    history,
    loading,
    error,
    setWorkspace,
    browseWorkspace,
    validateWorkspace,
    removeFromHistory,
    clearHistory,
    refresh,
  ]);

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

// ============================================================
// Hook
// ============================================================

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return context;
}
