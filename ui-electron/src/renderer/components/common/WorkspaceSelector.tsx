/**
 * Workspace Selector 组件
 * 工作区选择器
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Folder, X, Clock } from "lucide-react";
import { STORAGE_KEYS, FEATURES } from "@/config/settings";
import { useI18n } from "@/hooks/useI18n";

interface WorkspaceSelectorProps {
  className?: string;
}

export function WorkspaceSelector({ className = "" }: WorkspaceSelectorProps) {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() =>
    localStorage.getItem(STORAGE_KEYS.workspaceKey) || ""
  );
  const [inputValue, setInputValue] = useState(workspace);
  const [isOpen, setIsOpen] = useState(false);
  const [history, setHistory] = useState<string[]>(() => loadHistory());

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 加载历史记录
  function loadHistory(): string[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.workspaceHistoryKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  // 保存历史记录
  function saveHistory(newHistory: string[]) {
    try {
      const limited = newHistory.slice(0, FEATURES.maxWorkspaceHistory);
      localStorage.setItem(
        STORAGE_KEYS.workspaceHistoryKey,
        JSON.stringify(limited)
      );
      setHistory(limited);
    } catch {
      // Ignore storage errors
    }
  }

  // 添加到历史
  function addToHistory(path: string) {
    if (!path.trim()) return;
    const filtered = history.filter((h) => h !== path);
    saveHistory([path, ...filtered]);
  }

  // 应用工作区
  const applyWorkspace = useCallback((path: string) => {
    const trimmed = path.trim();
    setWorkspace(trimmed);
    setInputValue(trimmed);
    localStorage.setItem(STORAGE_KEYS.workspaceKey, trimmed);
    if (trimmed) {
      addToHistory(trimmed);
    }
    window.dispatchEvent(new Event("aipl-workspace-changed"));
    setIsOpen(false);
  }, [history]);

  // 清除工作区
  const clearWorkspace = useCallback(() => {
    setWorkspace("");
    setInputValue("");
    localStorage.removeItem(STORAGE_KEYS.workspaceKey);
    window.dispatchEvent(new Event("aipl-workspace-changed"));
  }, []);

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      applyWorkspace(inputValue);
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setInputValue(workspace);
    }
  };

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
        setInputValue(workspace);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen, workspace]);

  // 同步外部变化
  useEffect(() => {
    const syncWorkspace = () => {
      const current = localStorage.getItem(STORAGE_KEYS.workspaceKey) || "";
      setWorkspace(current);
      setInputValue(current);
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  return (
    <div
      ref={containerRef}
      className={`workspace-selector ${className} ${isOpen ? "open" : ""}`}
    >
      {/* 触发按钮 */}
      <button
        className="workspace-trigger"
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) {
            setTimeout(() => inputRef.current?.focus(), 50);
          }
        }}
      >
        <Folder size={14} />
        <span className="workspace-value">
          {workspace || t.labels.workspace}
        </span>
        <ChevronDown size={14} />
      </button>

      {/* 清除按钮 */}
      {workspace && (
        <button
          className="workspace-clear"
          onClick={(e) => {
            e.stopPropagation();
            clearWorkspace();
          }}
          title="清除"
        >
          <X size={14} />
        </button>
      )}

      {/* 下拉面板 */}
      {isOpen && (
        <div className="workspace-dropdown">
          <div className="workspace-input-wrap">
            <input
              ref={inputRef}
              type="text"
              className="workspace-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入工作区路径..."
            />
          </div>

          {/* 历史记录 */}
          {history.length > 0 && (
            <div className="workspace-history">
              <div className="workspace-history-header">
                <Clock size={12} />
                <span>最近使用</span>
              </div>
              <ul className="workspace-history-list">
                {history.map((path) => (
                  <li key={path}>
                    <button
                      className="workspace-history-item"
                      onClick={() => applyWorkspace(path)}
                    >
                      <Folder size={12} />
                      <span>{path}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
