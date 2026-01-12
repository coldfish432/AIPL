/**
 * Review Panel 组件
 * 显示审核面板
 */

import React, { useEffect, useState } from "react";
import { getRunArtifacts, downloadArtifactText, openRunFile } from "@/apis";
import { useI18n } from "@/hooks/useI18n";
import { DiffViewer } from "@/components/common/DiffViewer";

interface ChangedFile {
  path: string;
  status: string;
}

interface ReviewPanelProps {
  runId: string;
  planId?: string;
  onApply: () => Promise<void>;
  onDiscard: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

export function ReviewPanel({
  runId,
  planId,
  onApply,
  onDiscard,
  loading,
  error,
}: ReviewPanelProps) {
  const { t } = useI18n();
  const [changedFiles, setChangedFiles] = useState<ChangedFile[]>([]);
  const [patchsetText, setPatchsetText] = useState("");
  const [reviewLoading, setReviewLoading] = useState(true);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // 加载变更文件和 patchset
  useEffect(() => {
    async function loadReviewData() {
      setReviewLoading(true);
      setReviewError(null);
      
      try {
        const artifacts = await getRunArtifacts(runId, planId);

        // 解析变更文件
        const files = parseChangedFiles(artifacts);
        setChangedFiles(files);

        // 加载 patchset
        const patchset = artifacts.items?.find((item) =>
          item.path.endsWith("patchset.diff")
        );
        if (patchset) {
          const text = await downloadArtifactText(runId, patchset.path, planId);
          setPatchsetText(text);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : t.messages.loadPatchsetFailed;
        setReviewError(message);
      } finally {
        setReviewLoading(false);
      }
    }

    loadReviewData();
  }, [runId, planId, t]);

  const handleOpenFile = async (filePath: string) => {
    try {
      await openRunFile(runId, filePath, planId);
    } catch (err) {
      console.error("Failed to open file:", err);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.titles.reviewApply}</h2>
      </div>

      {reviewLoading && (
        <div className="page-muted">{t.messages.reviewLoading}</div>
      )}

      {(error || reviewError) && (
        <div className="page-alert">{error || reviewError}</div>
      )}

      {!reviewLoading && changedFiles.length > 0 && (
        <div className="card-list">
          {changedFiles.map((file, idx) => (
            <div key={`${file.path}-${idx}`} className="card-item">
              <button
                className="file-link"
                onClick={() => handleOpenFile(file.path)}
              >
                {file.path}
              </button>
              <div className="status-pill">{file.status}</div>
            </div>
          ))}
        </div>
      )}

      {patchsetText && (
        <DiffViewer diffText={patchsetText} changedFiles={changedFiles} />
      )}

      <div className="panel-actions">
        <button
          className="button-primary"
          onClick={onApply}
          disabled={loading}
        >
          {t.buttons.applyReview}
        </button>
        <button
          className="button-secondary"
          onClick={onDiscard}
          disabled={loading}
        >
          {t.buttons.discardChanges}
        </button>
      </div>
    </div>
  );
}

// 解析变更文件
function parseChangedFiles(artifacts: any): ChangedFile[] {
  const files: ChangedFile[] = [];

  // 从 items 中解析
  if (Array.isArray(artifacts.items)) {
    for (const item of artifacts.items) {
      if (item.path && !item.path.endsWith(".diff")) {
        files.push({
          path: item.path,
          status: "modified",
        });
      }
    }
  }

  return files;
}
