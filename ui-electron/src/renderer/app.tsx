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
import LanguagePacks from "./pages/LanguagePacks";
import Memory from "./pages/Memory";
import { useI18n } from "./lib/useI18n";
import LanguageSwitch from "./components/LanguageSwitch";
import { pickWorkspaceDirectory } from "./lib/fileSystem";
import WorkspaceSelector from "./components/WorkspaceSelector";
import { addWorkspaceToHistory, loadWorkspaceHistory } from "./lib/workspaceHistory";
import { STORAGE_KEYS } from "./config/settings";
import PackagesLayout, { PackagesHome } from "./pages/Packages";
import ExecutionStatusBar from "./components/ExecutionStatusBar";

function Layout() {
  const location = useLocation();
  const params = useParams();
  const { language, t, toggleLanguage } = useI18n();
  const [workspace, setWorkspace] = React.useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [workspaceHistory, setWorkspaceHistory] = React.useState<string[]>(() => loadWorkspaceHistory());

  React.useEffect(() => {
    const sync = () => {
      setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
      setWorkspaceHistory(loadWorkspaceHistory());
    };
    window.addEventListener("aipl-workspace-changed", sync);
    return () => window.removeEventListener("aipl-workspace-changed", sync);
  }, []);

  const updateWorkspace = React.useCallback((value: string) => {
    if (!value) return;
    const trimmed = value.trim();
    if (!trimmed) return;
    localStorage.setItem(STORAGE_KEYS.workspaceKey, trimmed);
    setWorkspace(trimmed);
    addWorkspaceToHistory(trimmed);
    setWorkspaceHistory(loadWorkspaceHistory());
    window.dispatchEvent(new Event("aipl-workspace-changed"));
  }, []);

  const handleBrowseWorkspace = React.useCallback(async () => {
    const selected = await pickWorkspaceDirectory();
    if (selected) {
      updateWorkspace(selected);
    }
  }, [updateWorkspace]);
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
      <aside className="nav nav-modern">
        <div className="nav-brand">
          <div className="nav-brand-icon">AI</div>
          <div className="nav-brand-text">AIPL Console</div>
        </div>
        <WorkspaceSelector
          current={workspace}
          label={t.labels.workspace}
          history={workspaceHistory}
          onSelect={updateWorkspace}
          onBrowse={handleBrowseWorkspace}
        />
        <div className="nav-menu">
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/dashboard" end>
            {t.titles.dashboard}
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/pilot" end>
            {t.titles.pilot}
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/profile" end>
            {t.titles.profile}
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/packages" end>
            {t.titles.packages}
          </NavLink>
        </div>
        <div className="nav-language nav-language-bottom">
          <LanguageSwitch language={language} onToggle={toggleLanguage} />
        </div>
      </aside>
      <main className="content">
        <header className="header">
          <h1>{title}</h1>
          <ExecutionStatusBar />
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
          <Route path="packages" element={<PackagesLayout />}>
            <Route index element={<Navigate to="language" replace />} />
            <Route path="language" element={<LanguagePacks />} />
            <Route path="experience" element={<Memory />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
