/**
 * Diff Viewer 组件
 * 显示代码差异
 */

import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, File, Plus, Minus, Edit } from "lucide-react";

interface ChangedFile {
  path: string;
  status: string;
}

interface DiffViewerProps {
  diffText: string;
  changedFiles?: ChangedFile[];
  defaultExpanded?: boolean;
}

interface FileDiff {
  path: string;
  status: "added" | "removed" | "modified";
  hunks: DiffHunk[];
}

interface DiffHunk {
  header: string;
  lines: DiffLine[];
}

interface DiffLine {
  type: "add" | "remove" | "context" | "header";
  content: string;
  oldLine?: number;
  newLine?: number;
}

export function DiffViewer({
  diffText,
  changedFiles = [],
  defaultExpanded = true,
}: DiffViewerProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(
    defaultExpanded ? new Set(["__all__"]) : new Set()
  );

  // 解析 diff 文本
  const fileDiffs = useMemo(() => parseDiff(diffText), [diffText]);

  const toggleFile = (path: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (expandedFiles.has("__all__")) {
      setExpandedFiles(new Set());
    } else {
      const all = new Set(fileDiffs.map((f) => f.path));
      all.add("__all__");
      setExpandedFiles(all);
    }
  };

  if (!diffText && changedFiles.length === 0) {
    return <div className="diff-empty">No changes</div>;
  }

  return (
    <div className="diff-viewer">
      {/* Header */}
      <div className="diff-header">
        <button className="diff-toggle-all" onClick={toggleAll}>
          {expandedFiles.has("__all__") ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronRight size={14} />
          )}
          <span>
            {fileDiffs.length} file{fileDiffs.length !== 1 ? "s" : ""} changed
          </span>
        </button>
      </div>

      {/* File List */}
      <div className="diff-files">
        {fileDiffs.map((file) => {
          const isExpanded =
            expandedFiles.has("__all__") || expandedFiles.has(file.path);

          return (
            <div key={file.path} className="diff-file">
              {/* File Header */}
              <button
                className="diff-file-header"
                onClick={() => toggleFile(file.path)}
              >
                {isExpanded ? (
                  <ChevronDown size={14} />
                ) : (
                  <ChevronRight size={14} />
                )}
                <FileStatusIcon status={file.status} />
                <span className="diff-file-path">{file.path}</span>
              </button>

              {/* File Content */}
              {isExpanded && (
                <div className="diff-file-content">
                  {file.hunks.map((hunk, hunkIdx) => (
                    <div key={hunkIdx} className="diff-hunk">
                      <div className="diff-hunk-header">{hunk.header}</div>
                      <div className="diff-lines">
                        {hunk.lines.map((line, lineIdx) => (
                          <div
                            key={lineIdx}
                            className={`diff-line diff-line-${line.type}`}
                          >
                            <span className="diff-line-num old">
                              {line.oldLine ?? ""}
                            </span>
                            <span className="diff-line-num new">
                              {line.newLine ?? ""}
                            </span>
                            <span className="diff-line-prefix">
                              {line.type === "add"
                                ? "+"
                                : line.type === "remove"
                                  ? "-"
                                  : " "}
                            </span>
                            <span className="diff-line-content">
                              {line.content}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// 文件状态图标
function FileStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "added":
      return <Plus size={14} className="diff-status-added" />;
    case "removed":
      return <Minus size={14} className="diff-status-removed" />;
    case "modified":
      return <Edit size={14} className="diff-status-modified" />;
    default:
      return <File size={14} />;
  }
}

// 解析 diff 文本
function parseDiff(text: string): FileDiff[] {
  if (!text) return [];

  const files: FileDiff[] = [];
  const lines = text.split("\n");

  let currentFile: FileDiff | null = null;
  let currentHunk: DiffHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  for (const line of lines) {
    // 新文件开始
    if (line.startsWith("diff --git") || line.startsWith("--- ")) {
      if (currentFile && currentHunk) {
        currentFile.hunks.push(currentHunk);
      }
      if (currentFile) {
        files.push(currentFile);
      }

      const pathMatch = line.match(/(?:a|b)\/(.+)$/);
      currentFile = {
        path: pathMatch ? pathMatch[1] : "unknown",
        status: "modified",
        hunks: [],
      };
      currentHunk = null;
      continue;
    }

    // 检测文件状态
    if (line.startsWith("new file")) {
      if (currentFile) currentFile.status = "added";
      continue;
    }
    if (line.startsWith("deleted file")) {
      if (currentFile) currentFile.status = "removed";
      continue;
    }

    // Hunk 开始
    if (line.startsWith("@@")) {
      if (currentFile && currentHunk) {
        currentFile.hunks.push(currentHunk);
      }

      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      oldLine = match ? parseInt(match[1], 10) : 1;
      newLine = match ? parseInt(match[2], 10) : 1;

      currentHunk = {
        header: line,
        lines: [],
      };
      continue;
    }

    // 跳过其他元信息
    if (
      line.startsWith("index ") ||
      line.startsWith("+++ ") ||
      line.startsWith("--- ")
    ) {
      continue;
    }

    // 解析行
    if (currentHunk) {
      if (line.startsWith("+")) {
        currentHunk.lines.push({
          type: "add",
          content: line.slice(1),
          newLine: newLine++,
        });
      } else if (line.startsWith("-")) {
        currentHunk.lines.push({
          type: "remove",
          content: line.slice(1),
          oldLine: oldLine++,
        });
      } else if (line.startsWith(" ") || line === "") {
        currentHunk.lines.push({
          type: "context",
          content: line.slice(1) || "",
          oldLine: oldLine++,
          newLine: newLine++,
        });
      }
    }
  }

  // 添加最后的文件和 hunk
  if (currentFile && currentHunk) {
    currentFile.hunks.push(currentHunk);
  }
  if (currentFile) {
    files.push(currentFile);
  }

  return files;
}
