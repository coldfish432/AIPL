/**
 * Packages 页面
 */

import React, { useState } from "react";
import { Globe, Package, RefreshCw } from "lucide-react";

import { usePackages, PackType, PackItem } from "./hooks/usePackages";
import { useI18n } from "@/hooks/useI18n";
import {
  PackList,
  ImportDialog,
  ViewDialog,
} from "./components";
import type { PackRecord } from "@/apis/types";

export default function Packages() {
  const { t } = useI18n();
  const {
    languagePacks,
    experiencePacks,
    loading,
    error,
    refresh,
    importPack,
    exportPack,
    deletePack,
    getPack,
  } = usePackages();

  // Dialog state
  const [importType, setImportType] = useState<PackType | null>(null);
  const [viewPack, setViewPack] = useState<PackItem | null>(null);
  const [viewContent, setViewContent] = useState<PackRecord | null>(null);

  // Handlers
  const handleView = async (pack: PackItem) => {
    setViewPack(pack);
    setViewContent(null);
    const content = await getPack(pack.type, pack.id);
    setViewContent(content);
  };

  const handleExport = async (pack: PackItem) => {
    const content = await exportPack(pack.type, pack.id);
    if (content) {
      const blob = new Blob([JSON.stringify(content, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${pack.name || pack.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleDelete = async (pack: PackItem) => {
    const confirmMsg =
      pack.type === "language"
        ? t.messages.confirmDeleteLanguagePack
        : t.messages.confirmDeleteExperiencePack;
    if (!window.confirm(confirmMsg || `确定删除 ${pack.name}?`)) return;
    await deletePack(pack.type, pack.id);
  };

  const handleImport = async (pack: PackRecord) => {
    if (!importType) return;
    await importPack(importType, pack);
  };

  return (
    <section className="page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">{t.titles.packages}</h1>
          <p className="page-subtitle">{t.messages.packagesIntro}</p>
        </div>
        <div className="page-actions">
          <button
            className="button-secondary"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            {t.buttons.refresh}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && <div className="page-alert">{error}</div>}

      {/* Language Packs */}
      <PackList
        title={t.titles.languagePacks}
        icon={<Globe size={18} />}
        packs={languagePacks}
        emptyMessage={t.messages.noLanguagePacks}
        onView={handleView}
        onExport={handleExport}
        onDelete={handleDelete}
        onImport={() => setImportType("language")}
        loading={loading}
      />

      {/* Experience Packs */}
      <PackList
        title={t.titles.experiencePacks}
        icon={<Package size={18} />}
        packs={experiencePacks}
        emptyMessage={t.messages.noExperiencePacks}
        onView={handleView}
        onExport={handleExport}
        onDelete={handleDelete}
        onImport={() => setImportType("experience")}
        loading={loading}
      />

      {/* Import Dialog */}
      {importType && (
        <ImportDialog
          type={importType}
          onImport={handleImport}
          onClose={() => setImportType(null)}
          loading={loading}
        />
      )}

      {/* View Dialog */}
      {viewPack && (
        <ViewDialog
          pack={viewPack}
          content={viewContent}
          onClose={() => {
            setViewPack(null);
            setViewContent(null);
          }}
        />
      )}
    </section>
  );
}
