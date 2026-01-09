import React, { useEffect, useState } from "react";
import {
  deleteLanguagePack,
  exportLanguagePack,
  getLanguagePack,
  importLanguagePack,
  listLanguagePacks,
  updateLanguagePack
} from "../apiClient";
import { PackViewer } from "../components/PackViewer";
import { PackDropZone, PackDropResult } from "../components/PackDropZone";
import { STORAGE_KEYS } from "../config/settings";
import { saveJsonFile } from "../lib/fileSystem";
import { useI18n } from "../lib/useI18n";

type PackList = {
  builtin?: any[];
  user?: any[];
  learned?: any;
  active?: string[];
};

export default function LanguagePacks() {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [packs, setPacks] = useState<PackList>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<any | null>(null);
  const [importFileName, setImportFileName] = useState("");
  const [activeTab, setActiveTab] = useState<"builtin" | "user" | "learned">("builtin");

  async function load() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listLanguagePacks(workspace);
      setPacks(data as PackList);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function openPack(packId: string) {
    try {
      const data = await getLanguagePack(packId);
      setSelected(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  async function togglePack(pack: any) {
    try {
      await updateLanguagePack(pack.id, !pack.enabled);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  async function removePack(packId: string) {
    try {
      await deleteLanguagePack(packId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setError(message || t.messages.deleteFailed);
    }
  }

  async function exportPack(packId: string) {
    try {
      const data = await exportLanguagePack(packId);
      const fileName = toJsonFileName(data?.name as string, "language-pack");
      await saveJsonFile(data, { suggestedName: fileName, description: "Language pack" });
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  useEffect(() => {
    if (workspace) {
      void load();
    }
  }, [workspace]);

  useEffect(() => {
    const syncWorkspace = () => setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  const active = packs.active || [];
  const tabItems = [
    { key: "builtin" as const, label: t.labels.builtin },
    { key: "user" as const, label: t.labels.user },
    { key: "learned" as const, label: t.labels.learned }
  ];

  function toJsonFileName(value: string, fallback: string) {
    const base = (value || "").trim() || fallback;
    const sanitized = base.replace(/[\\/:*?"<>|]+/g, "_");
    return sanitized.endsWith(".json") ? sanitized : `${sanitized}.json`;
  }

  const handlePackDrop = async (result: PackDropResult) => {
    if (!workspace) {
      setError(t.messages.loadFailed);
      return;
    }
    if (!result.success) {
      setError(result.error);
      return;
    }
    setError(null);
    setImportFileName(result.fileName || "");
    try {
      await importLanguagePack(result.data);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  };

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="page-subtitle">{t.labels.active}: {active.join(", ") || "-"}</p>
        </div>
        <div className="page-actions">
          <button className="button-primary" onClick={load} disabled={loading || !workspace}>
            {loading ? t.messages.loading : t.buttons.load}
          </button>
        </div>
      </div>

      {error && <div className="page-alert">{error}</div>}

      <div className="tabs">
        {tabItems.map((item) => (
          <button
            key={item.key}
            className={`tab-button ${activeTab === item.key ? "active" : ""}`}
            onClick={() => setActiveTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{tabItems.find((item) => item.key === activeTab)?.label}</h2>
          <div className="panel-meta">
            {activeTab === "builtin" && (packs.builtin || []).length}
            {activeTab === "user" && (packs.user || []).length}
            {activeTab === "learned" && (packs.learned ? 1 : 0)}
          </div>
        </div>
        <div className="card-list">
          {activeTab === "builtin" && (
            <>
              {(packs.builtin || []).map((pack) => (
                <div key={pack.id} className="card-item">
                  <div className="card-item-main">
                    <div className="card-item-title">{pack.name}</div>
                    <div className="card-item-meta">{pack.id}</div>
                  </div>
                  <div className="card-item-actions">
                    <button className="button-secondary" onClick={() => openPack(pack.id)}>{t.buttons.viewList}</button>
                    <button className="button-secondary" onClick={() => exportPack(pack.id)}>{t.buttons.export}</button>
                  </div>
                </div>
              ))}
              {!packs.builtin?.length && <div className="page-muted">{t.messages.noBuiltinPacks}</div>}
            </>
          )}

          {activeTab === "user" && (
            <>
              {(packs.user || []).map((pack) => (
                <div key={pack.id} className="card-item">
                  <div className="card-item-main">
                    <div className="card-item-title">{pack.name}</div>
                    <div className="card-item-meta">{pack.id}</div>
                  </div>
                  <div className="card-item-actions">
                    <button className="button-secondary" onClick={() => openPack(pack.id)}>{t.buttons.viewList}</button>
                    <button className="button-secondary" onClick={() => togglePack(pack)}>
                      {pack.enabled ? t.buttons.disable : t.buttons.enable}
                    </button>
                    <button className="button-secondary" onClick={() => exportPack(pack.id)}>{t.buttons.export}</button>
                    <button className="button-danger" onClick={() => removePack(pack.id)}>{t.buttons.delete}</button>
                  </div>
                </div>
              ))}
              {!packs.user?.length && <div className="page-muted">{t.messages.noUserPacks}</div>}
            </>
          )}

          {activeTab === "learned" && (
            <>
              {packs.learned ? (
                <div className="card-item">
                  <div className="card-item-main">
                    <div className="card-item-title">{packs.learned.name}</div>
                    <div className="card-item-meta">{packs.learned.id}</div>
                  </div>
                  <div className="card-item-actions">
                    <button className="button-secondary" onClick={() => openPack(packs.learned.id)}>{t.buttons.viewList}</button>
                    <button className="button-secondary" onClick={() => togglePack(packs.learned)}>
                      {packs.learned.enabled ? t.buttons.disable : t.buttons.enable}
                    </button>
                    <button className="button-secondary" onClick={() => exportPack(packs.learned.id)}>{t.buttons.export}</button>
                  </div>
                </div>
              ) : (
                <div className="page-muted">{t.messages.noLearnedPack}</div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.importPack}</h2>
          {importFileName && <div className="panel-meta">{t.labels.selectedFile}: {importFileName}</div>}
        </div>
        <PackDropZone
          acceptType="language"
          onDrop={handlePackDrop}
          onError={(message) => setError(message)}
          showValidation
          placeholder={t.labels.dragPackHere}
          buttonLabel={t.buttons.chooseFile}
        />
        <p className="page-inline-note" style={{ marginTop: "16px" }}>
          {t.labels.dropFileHint}
        </p>
      </div>

      {selected && (
        <PackViewer
          data={selected}
          type="language"
          onClose={() => setSelected(null)}
          onExport={() => exportPack(selected.id)}
        />
      )}
    </section>
  );
}
