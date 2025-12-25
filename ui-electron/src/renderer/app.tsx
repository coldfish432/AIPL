import React, { useMemo, useState } from "react";
import Dashboard from "./pages/Dashboard";
import RunDetail from "./pages/RunDetail";
import Profile from "./pages/Profile";
import PlanDetail from "./pages/PlanDetail";

export type Page = "dashboard" | "run" | "profile" | "plan";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [runId, setRunId] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);

  const title = useMemo(() => {
    if (page === "run" && runId) return "Run " + runId;
    if (page === "plan" && planId) return "Plan " + planId;
    if (page === "profile") return "Profile";
    return "Dashboard";
  }, [page, runId, planId]);

  return (
    <div className="app">
      <aside className="nav">
        <div className="brand">AIPL Console</div>
        <button className={page === "dashboard" ? "active" : ""} onClick={() => setPage("dashboard")}>Dashboard</button>
        <button className={page === "profile" ? "active" : ""} onClick={() => setPage("profile")}>Profile</button>
      </aside>
      <main className="content">
        <header className="header">
          <h1>{title}</h1>
        </header>
        {page === "dashboard" && (
          <Dashboard
            onSelectRun={(id, pid) => {
              setRunId(id);
              setPlanId(pid || null);
              setPage("run");
            }}
            onSelectPlan={(id) => {
              setPlanId(id);
              setPage("plan");
            }}
          />
        )}
        {page === "run" && runId && (
          <RunDetail runId={runId} planId={planId || undefined} onBack={() => setPage("dashboard")} />
        )}
        {page === "plan" && planId && (
          <PlanDetail planId={planId} onBack={() => setPage("dashboard")} />
        )}
        {page === "profile" && <Profile />}
      </main>
    </div>
  );
}
