import React, { useMemo, useState } from "react";

type Props = {
  diffText: string;
  changedFiles?: Array<{ path: string; status: string }>;
};

type FileDiff = {
  path: string;
  additions: number;
  deletions: number;
  hunks: string[];
};

function parseDiff(text: string): FileDiff[] {
  const files: FileDiff[] = [];
  const lines = text.split("\n");
  let current: FileDiff | null = null;
  let hunkLines: string[] = [];

  const pushHunk = () => {
    if (current && hunkLines.length > 0) {
      current.hunks.push(hunkLines.join("\n"));
      hunkLines = [];
    }
  };

  for (let idx = 0; idx < lines.length; idx += 1) {
    const line = lines[idx];
    const nextLine = lines[idx + 1] || "";
    if (line.startsWith("diff --git")) {
      pushHunk();
      const match = line.match(/diff --git a\/(.*) b\/(.*)/);
      current = {
        path: match?.[2] || "unknown",
        additions: 0,
        deletions: 0,
        hunks: []
      };
      files.push(current);
      continue;
    }
    if (line.startsWith("--- ") && nextLine.startsWith("+++ ")) {
      continue;
    }
    if (!current) continue;

    if (line.startsWith("@@")) {
      pushHunk();
      hunkLines = [line];
      continue;
    }

    if (hunkLines.length > 0 || line.startsWith("+") || line.startsWith("-") || line.startsWith(" ")) {
      hunkLines.push(line);
      if (line.startsWith("+") && !line.startsWith("+++")) current.additions += 1;
      if (line.startsWith("-") && !line.startsWith("---")) current.deletions += 1;
    }
  }

  pushHunk();
  return files;
}

export default function DiffViewer({ diffText }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const files = useMemo(() => parseDiff(diffText), [diffText]);

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  if (!diffText) {
    return null;
  }

  if (files.length === 0) {
    return <pre className="pre">{diffText}</pre>;
  }

  return (
    <div className="diff-viewer">
      {files.map((file) => (
        <div key={file.path} className="diff-file">
          <button type="button" className="diff-file-header" onClick={() => toggle(file.path)}>
            <span className="diff-expand">{expanded.has(file.path) ? "▾" : "▸"}</span>
            <span className="diff-path">{file.path}</span>
            <span className="diff-stats">
              <span className="diff-add">+{file.additions}</span>
              <span className="diff-del">-{file.deletions}</span>
            </span>
          </button>
          {expanded.has(file.path) && (
            <div className="diff-content">
              {file.hunks.map((hunk, idx) => (
                <pre key={`${file.path}-${idx}`} className="diff-hunk">
                  {hunk.split("\n").map((line, lineIdx) => (
                    <div
                      key={`${file.path}-${idx}-${lineIdx}`}
                      className={
                        line.startsWith("+")
                          ? "diff-line-add"
                          : line.startsWith("-")
                            ? "diff-line-del"
                            : line.startsWith("@@")
                              ? "diff-line-info"
                              : "diff-line"
                      }
                    >
                      {line}
                    </div>
                  ))}
                </pre>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
