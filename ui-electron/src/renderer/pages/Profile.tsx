import React, { useEffect, useState } from "react";
import { approveProfile, getProfile, proposeProfile, rejectProfile } from "../apiclient";

export default function Profile() {
  const [workspace, setWorkspace] = useState(() => localStorage.getItem("aipl.workspace") || "");
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getProfile(workspace);
      setProfile(data);
      localStorage.setItem("aipl.workspace", workspace);
    } catch (err: any) {
      setError(err?.message || "Failed to load profile");
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
    } catch (err: any) {
      setError(err?.message || "Failed to update profile");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (workspace) {
      void load();
    }
  }, []);

  return (
    <section className="stack">
      <div className="row">
        <input
          className="input"
          placeholder="Workspace path"
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value)}
        />
        <button onClick={load} disabled={loading || !workspace}>{loading ? "Loading..." : "Load"}</button>
        <button onClick={() => act("propose")} disabled={loading || !workspace}>Propose</button>
        <button onClick={() => act("approve")} disabled={loading || !workspace}>Approve</button>
        <button onClick={() => act("reject")} disabled={loading || !workspace}>Reject</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>Hard Policy</h2>
          <pre className="pre">{JSON.stringify(profile?.effective_hard || profile?.hard_policy, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>Soft Draft</h2>
          <pre className="pre">{JSON.stringify(profile?.soft_draft, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>Soft Approved</h2>
          <pre className="pre">{JSON.stringify(profile?.soft_approved, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}
