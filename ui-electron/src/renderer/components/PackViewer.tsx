import React, { useMemo } from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { parsePack, PackType } from "../utils/parsers";
import { useI18n } from "../lib/useI18n";

type PackViewerProps = {
  data: any;
  type: PackType;
  onClose: () => void;
  onExport?: () => void;
};

export function PackViewer({ data, type, onClose, onExport }: PackViewerProps) {
  const { t } = useI18n();
  const parsed = useMemo(() => parsePack(data, type), [data, type]);

  const copyContent = () => {
    navigator.clipboard.writeText(parsed.markdown);
  };

  return (
    <div className="pack-viewer-overlay">
      <div className="pack-viewer-modal">
        <div className="header">
          <h2>{data.name || "Pack Viewer"}</h2>
          <button className="close" onClick={onClose}>{t.buttons.close}</button>
        </div>

        <div className="content">
          <MarkdownRenderer content={parsed.markdown} />
        </div>

        <div className="actions">
          <button onClick={copyContent}>{t.buttons.copy}</button>
          <button onClick={onClose}>{t.buttons.close}</button>
        </div>
      </div>
    </div>
  );
}
