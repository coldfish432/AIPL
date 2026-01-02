import React, { useEffect, useState } from "react";
import { approveProfile, getProfile, proposeProfile, rejectProfile, ProfileData } from "../apiClient";

export default function Profile() {
  const [workspace, setWorkspace] = useState(() => localStorage.getItem("aipl.workspace") || "");
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
      localStorage.setItem("aipl.workspace", workspace);
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载配置失败";
      setError(message || "加载配置失败");
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
      localStorage.setItem("aipl.workspace", workspace);
    } catch (err) {
      const message = err instanceof Error ? err.message : "更新配置失败";
      setError(message || "更新配置失败");
    } finally {
      setLoading(false);
    }
  }

  function confirmAndAct(kind: "propose" | "approve" | "reject") {
    if (kind === "approve") {
      if (!window.confirm("确认通过这个配置吗？")) return;
    }
    if (kind === "reject") {
      if (!window.confirm("确认拒绝这个配置吗？")) return;
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
      setWorkspace(localStorage.getItem("aipl.workspace") || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  return (
    <section className="stack">
      <div className="row">
        <div className="meta">工作区：{workspace || "-"}</div>
        <button onClick={load} disabled={loading || !workspace}>{loading ? "加载中..." : "加载"}</button>
        <button onClick={() => confirmAndAct("propose")} disabled={loading || !workspace}>提议</button>
        <button onClick={() => confirmAndAct("approve")} disabled={loading || !workspace}>通过</button>
        <button onClick={() => confirmAndAct("reject")} disabled={loading || !workspace}>拒绝</button>
        {error && <span className="error">{error}</span>}
      </div>
      {!profile && <div className="muted">暂无配置。</div>}
      <div className="grid">
        <div className="card">
          <h2>硬策略</h2>
          <pre className="pre">{formatJson(profile?.effective_hard || profile?.hard_policy)}</pre>
        </div>
        <div className="card">
          <h2>软策略草案</h2>
          <pre className="pre">{formatJson(profile?.soft_draft)}</pre>
        </div>
        <div className="card">
          <h2>软策略已通过</h2>
          <pre className="pre">{formatJson(profile?.soft_approved)}</pre>
        </div>
      </div>
    </section>
  );
}
