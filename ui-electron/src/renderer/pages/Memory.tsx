import React, { useEffect, useRef, useState } from "react";
import {
  clearWorkspaceLessons,
  deleteExperiencePack,
  deleteWorkspaceLesson,
  exportExperiencePack,
  getExperiencePack,
  getProfile,
  getWorkspaceMemory,
  importExperiencePack,
  listExperiencePacks,
  updateExperiencePack
} from "../apiClient";
import { PackDropZone, PackDropResult } from "../components/PackDropZone";
import { PackViewer } from "../components/PackViewer";
import { STORAGE_KEYS } from "../config/settings";
import { saveJsonFile } from "../lib/fileSystem";
import { useI18n } from "../lib/useI18n";
import { validatePack } from "../utils/packValidation";

export default function Memory() {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [memory, setMemory] = useState<any>(null);
  const [packs, setPacks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<any | null>(null);
  const [importFileName, setImportFileName] = useState("");
  const [exportName, setExportName] = useState("");
  const [exportDescription, setExportDescription] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const importInputRef = useRef<HTMLInputElement | null>(null);

  async function loadProfile() {
    if (!workspace) return null;
    const profile = await getProfile(workspace);
    const id = typeof profile.workspace_id === "string" ? profile.workspace_id : null;
    setWorkspaceId(id);
    return id;
  }

  async function load() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const id = workspaceId || (await loadProfile());
      if (!id) {
        setError(t.messages.workspaceIdNotFound);
        return;
      }
      const mem = await getWorkspaceMemory(id);
      const list = await listExperiencePacks(id);
      setMemory(mem);
      setPacks(Array.isArray(list) ? list : []);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function openPack(packId: string) {
    if (!workspaceId) return;
    try {
      const data = await getExperiencePack(workspaceId, packId);
      setSelected(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  async function togglePack(pack: any) {
    if (!workspaceId) return;
    try {
      await updateExperiencePack(workspaceId, pack.id, !pack.enabled);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  async function removePack(packId: string) {
    if (!workspaceId) return;
    try {
      await deleteExperiencePack(workspaceId, packId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setError(message || t.messages.deleteFailed);
    }
  }

  async function exportPack() {
    if (!workspaceId) return;
    try {
      const data = await exportExperiencePack(workspaceId, {
        name: exportName,
        description: exportDescription,
        includeRules: false,
        includeChecks: true,
        includeLessons: true,
        includePatterns: true
      });
      const fileName = toJsonFileName(exportName, "experience-pack");
      await saveJsonFile(data, { suggestedName: fileName, description: "Experience pack" });
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  }

  async function removeLesson(lessonId: string) {
    if (!workspaceId) return;
    await deleteWorkspaceLesson(workspaceId, lessonId);
    await load();
  }

  async function clearLessons() {
    if (!workspaceId) return;
    await clearWorkspaceLessons(workspaceId);
    await load();
  }

  useEffect(() => {
    if (workspace) {
      setWorkspaceId(null);
      void load();
    }
  }, [workspace]);

  useEffect(() => {
    const syncWorkspace = () => setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  const lessons = memory?.lessons || [];
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredLessons = normalizedQuery
    ? lessons.filter((lesson: any) => String(lesson.lesson || "").toLowerCase().includes(normalizedQuery))
    : lessons;
  const filteredPacks = normalizedQuery
    ? packs.filter((pack) => String(pack.name || pack.id || "").toLowerCase().includes(normalizedQuery))
    : packs;

  function toJsonFileName(value: string, fallback: string) {
    const base = value.trim() || fallback;
    const sanitized = base.replace(/[\\/:*?"<>|]+/g, "_");
    return sanitized.endsWith(".json") ? sanitized : `${sanitized}.json`;
  }

  const importPack = async (data: Record<string, unknown>, fileName?: string) => {
    if (!workspaceId) return;
    try {
      await importExperiencePack(workspaceId, data);
      setImportFileName(fileName || "");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    }
  };

  const handlePackDrop = async (result: PackDropResult) => {
    if (!workspaceId) {
      setError(t.messages.loadFailed);
      return;
    }
    if (!result.success) {
      setError(result.error);
      return;
    }
    if (result.packType !== "experience-pack") {
      setError(t.messages.packFormatInvalid);
      return;
    }
    setError(null);
    await importPack(result.data, result.fileName);
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    event.target.value = "";
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const validation = validatePack(data);
      if (!validation.valid || validation.packType !== "experience-pack") {
        setError(t.messages.packFormatInvalid);
        return;
      }
      setError(null);
      await importPack(validation.data, file.name);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.packParseFailed;
      setError(message || t.messages.packParseFailed);
    }
  };

  return (
    <section className="page">
      <input
        ref={importInputRef}
        type="file"
        accept=".json,application/json"
        style={{ display: "none" }}
        onChange={handleImportFile}
      />
      <div className="page-header">
        <div>
          <p className="page-subtitle">{t.labels.importedPacks} & {t.labels.lessons}</p>
        </div>
        <div className="page-actions">
          <button className="button-primary" onClick={load} disabled={loading || !workspace}>
            {loading ? t.messages.loading : t.buttons.load}
          </button>
          <button className="button-secondary" onClick={() => importInputRef.current?.click()} disabled={loading || !workspaceId}>
            {t.buttons.importJson}
          </button>
        </div>
      </div>

      {error && <div className="page-alert">{error}</div>}

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.stats}</h2>
          <input
            className="page-search"
            placeholder={t.labels.searchPlans}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="card-list">
          <div className="card-item">
            <div className="card-item-main">
              <div className="card-item-title">{t.labels.lessons}</div>
              <div className="card-item-meta">{filteredLessons.length}</div>
            </div>
            <div className="card-item-main">
              <div className="card-item-title">{t.labels.importedPacks}</div>
              <div className="card-item-meta">{filteredPacks.length}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.lessons}</h2>
          <div className="panel-actions">
            <button className="button-danger" onClick={clearLessons} disabled={!lessons.length}>
              {t.buttons.delete}
            </button>
          </div>
        </div>
        <div className="card-list">
          {filteredLessons.map((l: any) => (
            <div key={l.id} className="card-item">
              <div className="card-item-main">
                <div className="card-item-title">{l.lesson}</div>
                <div className="card-item-meta">
                  {l.triggers?.length ? l.triggers.map((t: any) => t.value || t.type).join(", ") : "-"}
                </div>
              </div>
              <div className="card-item-actions">
                <button className="button-danger" onClick={() => removeLesson(l.id)}>{t.buttons.delete}</button>
              </div>
            </div>
          ))}
          {!filteredLessons.length && <div className="page-muted">{t.messages.noLessons}</div>}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.importedPacks}</h2>
        </div>
        <div className="card-list">
          {filteredPacks.map((p) => (
            <div key={p.id} className="card-item">
              <div className="card-item-main">
                <div className="card-item-title">{p.name}</div>
                <div className="card-item-meta">{p.id}</div>
              </div>
              <div className="card-item-actions">
                <button className="button-secondary" onClick={() => openPack(p.id)}>{t.buttons.viewList}</button>
                <button className="button-secondary" onClick={() => togglePack(p)}>{p.enabled ? t.buttons.disable : t.buttons.enable}</button>
                <button className="button-danger" onClick={() => removePack(p.id)}>{t.buttons.delete}</button>
              </div>
            </div>
          ))}
          {!filteredPacks.length && <div className="page-muted">{t.messages.noImportedPacks}</div>}
        </div>
      </div>

      <div className="panel-grid">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">{t.labels.importPack}</h2>
            {importFileName && <div className="panel-meta">{t.labels.selectedFile}: {importFileName}</div>}
          </div>
          <PackDropZone
            acceptType="experience"
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
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">{t.labels.exportMemory}</h2>
          </div>
          <div className="form-stack">
            <input
              className="page-input"
              value={exportName}
              onChange={(e) => setExportName(e.target.value)}
              placeholder={t.labels.exportName}
            />
            <input
              className="page-input"
              value={exportDescription}
              onChange={(e) => setExportDescription(e.target.value)}
              placeholder={t.labels.description}
            />
            <button className="button-primary" onClick={exportPack} disabled={!exportName.trim()}>
              {t.buttons.exportFile}
            </button>
          </div>
        </div>
      </div>

      {selected && (
        <PackViewer
          data={selected}
          type="experience"
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
