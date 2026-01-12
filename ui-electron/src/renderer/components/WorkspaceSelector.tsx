/**
 * WorkspaceSelector - 侧边栏工作区选择器
 * 
 * 功能：
 * 1. 显示当前工作区
 * 2. 下拉显示历史记录
 * 3. 浏览本地目录
 * 4. 复制/粘贴地址
 * 5. 验证地址有效性
 */

import React, { useState, useRef, useEffect } from "react";
import { Folder, FolderOpen, Copy, Trash2, X, Check, AlertCircle } from "lucide-react";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useI18n } from "@/hooks/useI18n";

export default function WorkspaceSelector() {
  const { t } = useI18n();
  const {
    workspace,
    workspaceInfo,
    history,
    loading,
    error,
    setWorkspace,
    browseWorkspace,
    validateWorkspace,
    removeFromHistory,
  } = useWorkspace();

  const [open, setOpen] = useState(false);
  const [inputMode, setInputMode] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setInputMode(false);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  // 输入模式自动聚焦
  useEffect(() => {
    if (inputMode && inputRef.current) {
      inputRef.current.focus();
    }
  }, [inputMode]);

  // 显示名称
  const displayName = workspace
    ? workspace.split(/[/\\]/).pop() || workspace
    : t.labels.selectWorkspace || "选择工作区";

  // 选择历史记录
  const handleSelectHistory = async (path: string) => {
    setOpen(false);
    await setWorkspace(path);
  };

  // 浏览本地目录
  const handleBrowse = async () => {
    setOpen(false);
    await browseWorkspace();
  };

  // 进入输入模式
  const handleStartInput = () => {
    setInputMode(true);
    setInputValue("");
    setInputError(null);
  };

  // 确认输入
  const handleConfirmInput = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed) {
      setInputError("请输入工作区路径");
      return;
    }

    setValidating(true);
    setInputError(null);

    const isValid = await validateWorkspace(trimmed);
    setValidating(false);

    if (!isValid) {
      setInputError("无法访问该路径，请检查是否正确");
      return;
    }

    const success = await setWorkspace(trimmed);
    if (success) {
      setInputMode(false);
      setOpen(false);
    } else {
      setInputError("设置工作区失败");
    }
  };

  // 取消输入
  const handleCancelInput = () => {
    setInputMode(false);
    setInputValue("");
    setInputError(null);
  };

  // 复制当前路径
  const handleCopy = async () => {
    if (workspace) {
      await navigator.clipboard.writeText(workspace);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // 键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleConfirmInput();
    } else if (e.key === "Escape") {
      handleCancelInput();
    }
  };

  return (
    <div className="workspace-selector" ref={rootRef}>
      {/* 触发按钮 */}
      <button
        type="button"
        className={`workspace-trigger ${open ? "open" : ""} ${loading ? "loading" : ""}`}
        onClick={() => setOpen(!open)}
      >
        <span className="workspace-trigger-icon">
          {open ? <FolderOpen size={16} /> : <Folder size={16} />}
        </span>
        <span className="workspace-trigger-text" title={workspace || undefined}>
          {displayName}
        </span>
        <span className="workspace-trigger-caret">{open ? "▴" : "▾"}</span>
      </button>

      {/* 下拉面板 */}
      {open && (
        <div className="workspace-dropdown">
          {/* 当前工作区信息 */}
          {workspace && (
            <div className="workspace-current">
              <div className="workspace-current-label">当前工作区</div>
              <div className="workspace-current-path">
                <span title={workspace}>{workspace}</span>
                <button
                  type="button"
                  className="workspace-copy-btn"
                  onClick={handleCopy}
                  title="复制路径"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
              {workspaceInfo && !workspaceInfo.isValid && (
                <div className="workspace-current-error">
                  <AlertCircle size={12} />
                  {workspaceInfo.error || "工作区不可用"}
                </div>
              )}
            </div>
          )}

          {/* 输入模式 */}
          {inputMode ? (
            <div className="workspace-input-area">
              <input
                ref={inputRef}
                type="text"
                className={`workspace-input ${inputError ? "error" : ""}`}
                placeholder="输入或粘贴工作区路径..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={validating}
              />
              {inputError && (
                <div className="workspace-input-error">{inputError}</div>
              )}
              <div className="workspace-input-actions">
                <button
                  type="button"
                  className="workspace-input-btn confirm"
                  onClick={handleConfirmInput}
                  disabled={validating || !inputValue.trim()}
                >
                  {validating ? "验证中..." : "确认"}
                </button>
                <button
                  type="button"
                  className="workspace-input-btn cancel"
                  onClick={handleCancelInput}
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* 操作按钮 */}
              <div className="workspace-actions">
                <button
                  type="button"
                  className="workspace-action-btn"
                  onClick={handleBrowse}
                >
                  <Folder size={14} />
                  浏览本地目录
                </button>
                <button
                  type="button"
                  className="workspace-action-btn"
                  onClick={handleStartInput}
                >
                  <Copy size={14} />
                  输入/粘贴路径
                </button>
              </div>

              {/* 历史记录 */}
              {history.length > 0 && (
                <div className="workspace-history">
                  <div className="workspace-history-label">历史记录</div>
                  <div className="workspace-history-list">
                    {history.map((path) => (
                      <div
                        key={path}
                        className={`workspace-history-item ${path === workspace ? "active" : ""}`}
                      >
                        <button
                          type="button"
                          className="workspace-history-path"
                          onClick={() => handleSelectHistory(path)}
                          title={path}
                        >
                          {path.split(/[/\\]/).pop() || path}
                        </button>
                        <button
                          type="button"
                          className="workspace-history-remove"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFromHistory(path);
                          }}
                          title="从历史中移除"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* 错误提示 */}
          {error && (
            <div className="workspace-error">
              <AlertCircle size={14} />
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
