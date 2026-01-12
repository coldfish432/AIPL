/**
 * Packages 组件
 */

import React, { useRef, useState } from "react";
import {
  Download,
  FileText,
  Package,
  Trash2,
  Upload,
  Eye,
  X,
} from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { PackItem, PackType } from "../hooks/usePackages";
import type { PackRecord } from "@/apis/types";

// ============================================================
// Pack Card
// ============================================================

interface PackCardProps {
  pack: PackItem;
  onView: (pack: PackItem) => void;
  onExport: (pack: PackItem) => void;
  onDelete: (pack: PackItem) => void;
  loading?: boolean;
}

export function PackCard({
  pack,
  onView,
  onExport,
  onDelete,
  loading,
}: PackCardProps) {
  const { t } = useI18n();

  const formatTime = (value: string | number | undefined) => {
    if (!value) return "-";
    const date = typeof value === "number" ? new Date(value) : new Date(value);
    return date.toLocaleDateString();
  };

  return (
    <div className="pack-card">
      <div className="pack-card-icon">
        <Package size={24} />
      </div>
      <div className="pack-card-content">
        <div className="pack-card-name">{pack.name}</div>
        {pack.description && (
          <div className="pack-card-description">{pack.description}</div>
        )}
        <div className="pack-card-meta">
          {pack.version && <span>v{pack.version}</span>}
          <span>{formatTime(pack.updatedAt)}</span>
        </div>
      </div>
      <div className="pack-card-actions">
        <button
          className="button-icon"
          onClick={() => onView(pack)}
          title={t.buttons.view}
          disabled={loading}
        >
          <Eye size={16} />
        </button>
        <button
          className="button-icon"
          onClick={() => onExport(pack)}
          title={t.buttons.export}
          disabled={loading}
        >
          <Download size={16} />
        </button>
        <button
          className="button-icon danger"
          onClick={() => onDelete(pack)}
          title={t.buttons.delete}
          disabled={loading}
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
}

// ============================================================
// Pack List
// ============================================================

interface PackListProps {
  title: string;
  icon: React.ReactNode;
  packs: PackItem[];
  emptyMessage: string;
  onView: (pack: PackItem) => void;
  onExport: (pack: PackItem) => void;
  onDelete: (pack: PackItem) => void;
  onImport: () => void;
  loading?: boolean;
}

export function PackList({
  title,
  icon,
  packs,
  emptyMessage,
  onView,
  onExport,
  onDelete,
  onImport,
  loading,
}: PackListProps) {
  const { t } = useI18n();

  return (
    <div className="pack-list-panel">
      <div className="pack-list-header">
        <div className="pack-list-title">
          {icon}
          <span>{title}</span>
          <span className="pack-list-count">({packs.length})</span>
        </div>
        <button
          className="button-secondary"
          onClick={onImport}
          disabled={loading}
        >
          <Upload size={14} />
          {t.buttons.import}
        </button>
      </div>
      <div className="pack-list-content">
        {packs.length === 0 ? (
          <div className="pack-list-empty">
            <Package size={32} />
            <span>{emptyMessage}</span>
          </div>
        ) : (
          <div className="pack-grid">
            {packs.map((pack) => (
              <PackCard
                key={pack.id}
                pack={pack}
                onView={onView}
                onExport={onExport}
                onDelete={onDelete}
                loading={loading}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Import Dialog
// ============================================================

interface ImportDialogProps {
  type: PackType;
  onImport: (pack: PackRecord) => Promise<void>;
  onClose: () => void;
  loading?: boolean;
}

export function ImportDialog({
  type,
  onImport,
  onClose,
  loading,
}: ImportDialogProps) {
  const { t } = useI18n();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [jsonText, setJsonText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      setJsonText(text);
      setError(null);
    } catch {
      setError("读取文件失败");
    }
  };

  const handleImport = async () => {
    if (!jsonText.trim()) {
      setError("请输入或上传包数据");
      return;
    }

    try {
      const pack = JSON.parse(jsonText);
      await onImport(pack);
      onClose();
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError("JSON 格式错误");
      } else {
        setError(err instanceof Error ? err.message : "导入失败");
      }
    }
  };

  const title = type === "language" ? t.titles.languagePacks : t.titles.experiencePacks;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2 className="dialog-title">
            {t.buttons.import} {title}
          </h2>
          <button className="button-icon" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="dialog-body">
          <div className="form-field">
            <label className="form-label">{t.labels.uploadFile}</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileChange}
              className="file-input"
            />
          </div>
          <div className="form-field">
            <label className="form-label">{t.labels.orPasteJson}</label>
            <textarea
              className="page-textarea"
              rows={10}
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              placeholder='{"name": "my-pack", ...}'
            />
          </div>
          {error && <div className="form-error">{error}</div>}
        </div>
        <div className="dialog-footer">
          <button className="button-secondary" onClick={onClose}>
            {t.buttons.cancel}
          </button>
          <button
            className="button-primary"
            onClick={handleImport}
            disabled={loading || !jsonText.trim()}
          >
            {loading ? t.messages.loading : t.buttons.import}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// View Dialog
// ============================================================

interface ViewDialogProps {
  pack: PackItem | null;
  content: PackRecord | null;
  onClose: () => void;
}

export function ViewDialog({ pack, content, onClose }: ViewDialogProps) {
  const { t } = useI18n();

  if (!pack) return null;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog large" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2 className="dialog-title">{pack.name}</h2>
          <button className="button-icon" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="dialog-body">
          {pack.description && (
            <p className="pack-view-description">{pack.description}</p>
          )}
          <div className="pack-view-content">
            <pre className="pre">
              {content ? JSON.stringify(content, null, 2) : t.messages.loading}
            </pre>
          </div>
        </div>
        <div className="dialog-footer">
          <button className="button-secondary" onClick={onClose}>
            {t.buttons.close}
          </button>
        </div>
      </div>
    </div>
  );
}
