import React, { useEffect, useMemo } from "react";
import {
  HashRouter,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams
} from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import RunDetail from "./pages/RunDetail";
import Profile from "./pages/Profile";
import PlanDetail from "./pages/PlanDetail";
import Pilot from "./pages/Pilot";
import { useI18n } from "./lib/useI18n";

function Layout() {
  const location = useLocation();
  const params = useParams();
  const { language, t } = useI18n();
  const title = useMemo(() => {
    if (params.runId) return `${t.labels.run} ${params.runId}`;
    if (params.planId) return `${t.labels.plan} ${params.planId}`;
    if (location.pathname.startsWith("/pilot")) return t.titles.pilot;
    if (location.pathname.startsWith("/profile")) return t.titles.profile;
    return t.titles.dashboard;
  }, [location.pathname, params.planId, params.runId, t]);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.setAttribute("data-lang", language);
    document.body.setAttribute("data-lang", language);
  }, [language]);

  return (
    <div className="app">
      <aside className="nav">
        <div className="brand">AIPL Console</div>
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/dashboard" end>
          {t.titles.dashboard}
        </NavLink>
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/pilot" end>
          {t.titles.pilot}
        </NavLink>
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/profile" end>
          {t.titles.profile}
        </NavLink>
      </aside>
      <main className="content">
        <header className="header">
          <h1>{title}</h1>
        </header>
        <Outlet />
      </main>
    </div>
  );
}

function DashboardRoute() {
  const navigate = useNavigate();

  return (
    <Dashboard
      onSelectRun={(id, pid) => {
        const search = pid ? `?planId=${encodeURIComponent(pid)}` : "";
        navigate(`/runs/${encodeURIComponent(id)}${search}`);
      }}
      onSelectPlan={(id) => {
        navigate(`/plans/${encodeURIComponent(id)}`);
      }}
    />
  );
}

function RunDetailRoute() {
  const { runId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const planId = searchParams.get("planId") || undefined;

  if (!runId) return <Navigate to="/dashboard" replace />;

  return <RunDetail runId={runId} planId={planId} onBack={() => navigate("/dashboard")} />;
}

function PlanDetailRoute() {
  const { planId } = useParams();
  const navigate = useNavigate();

  if (!planId) return <Navigate to="/dashboard" replace />;

  return <PlanDetail planId={planId} onBack={() => navigate("/dashboard")} />;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardRoute />} />
          <Route path="runs/:runId" element={<RunDetailRoute />} />
          <Route path="pilot" element={<Pilot />} />
          <Route path="plans/:planId" element={<PlanDetailRoute />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
