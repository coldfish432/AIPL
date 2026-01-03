import React, { useEffect, useState } from "react";
import { approveProfile, getProfile, proposeProfile, rejectProfile, ProfileData } from "../apiClient";
import { useI18n } from "../lib/useI18n";
import { STORAGE_KEYS } from "../config/settings";

export default function Profile() {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function formatJson(value: unknown) {
    if (value === undefined || value === null) return "(empty)";
    const text = JSON.stringify(value, null, 2);
    return text && text !== "{}" ? text : "{}";
  }

  async function load() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getProfile(workspace);
      setProfile(data);
      localStorage.setItem(STORAGE_KEYS.workspaceKey, workspace);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function act(kind: "propose" | "approve" | "reject") {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const fn = kind === "propose" ? proposeProfile : kind === "approve" ? approveProfile : rejectProfile;
      const data = await fn(workspace);
      setProfile(data);
      localStorage.setItem(STORAGE_KEYS.workspaceKey, workspace);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  function confirmAndAct(kind: "propose" | "approve" | "reject") {
    if (kind === "approve") {
      if (!window.confirm(t.messages.confirmApproveProfile)) return;
    }
    if (kind === "reject") {
      if (!window.confirm(t.messages.confirmRejectProfile)) return;
    }
    void act(kind);
  }

  useEffect(() => {
    if (workspace) {
      void load();
    }
  }, []);

  useEffect(() => {
    const syncWorkspace = () => {
      setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  return (
    <section className="stack">
      <div className="row">
        <div className="meta">{t.labels.workspace}：{workspace || "-"}</div>
        <button onClick={load} disabled={loading || !workspace}>{loading ? t.messages.loading : t.buttons.load}</button>
        <button onClick={() => confirmAndAct("propose")} disabled={loading || !workspace}>{t.buttons.propose}</button>
        <button onClick={() => confirmAndAct("approve")} disabled={loading || !workspace}>{t.buttons.approve}</button>
        <button onClick={() => confirmAndAct("reject")} disabled={loading || !workspace}>{t.buttons.reject}</button>
        {error && <span className="error">{error}</span>}
      </div>
      {!profile && <div className="muted">{t.messages.noProfile}</div>}
      <div className="grid">
        <div className="card">
          <h2>{t.titles.hardPolicy}</h2>
          <pre className="pre">{formatJson(profile?.effective_hard || profile?.hard_policy)}</pre>
        </div>
        <div className="card">
          <h2>{t.titles.softDraft}</h2>
          <pre className="pre">{formatJson(profile?.soft_draft)}</pre>
        </div>
        <div className="card">
          <h2>{t.titles.softApproved}</h2>
          <pre className="pre">{formatJson(profile?.soft_approved)}</pre>
        </div>
      </div>
    </section>
  );
}
