/**
 * App 入口组件
 * 
 * 整合：
 * 1. WorkspaceProvider - 工作区全局状态
 * 2. ExecutionProvider - 执行状态全局共享
 * 3. 路由配置
 * 4. 全局布局（侧边栏工作区选择器）
 */

import React from "react";
import {
  HashRouter,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

// Contexts
import { WorkspaceProvider } from "@/contexts/WorkspaceContext";
import { ExecutionProvider } from "@/contexts/ExecutionContext";

// Components
import WorkspaceSelector from "@/components/WorkspaceSelector";
import ExecutionStatusBar from "@/components/ExecutionStatusBar";

// Features
import Dashboard from "@/features/dashboard/Dashboard";
import Pilot from "@/features/pilot/Pilot";
import RunDetail from "@/features/runs/RunDetail";
import PlanDetail from "@/features/plans/PlanDetail";
import Profile from "@/features/profile/Profile";
import Packages from "@/features/packages/Packages";

// Hooks
import { useI18n } from "@/hooks/useI18n";

// Icons
import {
  LayoutDashboard,
  Navigation,
  Package,
  Settings,
  Globe,
} from "lucide-react";

// ============================================================
// Language Switch
// ============================================================

function LanguageSwitch() {
  const { language, toggleLanguage } = useI18n();

  return (
    <button
      type="button"
      className="nav-language-btn"
      onClick={toggleLanguage}
      title={language === "zh" ? "Switch to English" : "切换到中文"}
    >
      <Globe size={16} />
      <span>{language === "zh" ? "EN" : "中"}</span>
    </button>
  );
}

// ============================================================
// Layout
// ============================================================

function AppLayout() {
  const { t } = useI18n();

  return (
    <div className="app-container">
      {/* 侧边栏 */}
      <aside className="app-sidebar">
        {/* Logo */}
        <div className="app-logo">
          <span className="app-logo-icon">AIPL</span>
        </div>

        {/* 工作区选择器 */}
        <WorkspaceSelector />

        {/* 导航菜单 */}
        <nav className="app-nav">
          <NavLink to="/dashboard" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
            <LayoutDashboard size={18} />
            <span>{t.titles.dashboard || "仪表盘"}</span>
          </NavLink>
          <NavLink to="/pilot" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
            <Navigation size={18} />
            <span>{t.titles.pilot || "导航"}</span>
          </NavLink>
          <NavLink to="/packages" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
            <Package size={18} />
            <span>{t.titles.packages || "包管理"}</span>
          </NavLink>
          <NavLink to="/profile" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
            <Settings size={18} />
            <span>{t.titles.profile || "配置"}</span>
          </NavLink>
        </nav>

        {/* 底部 */}
        <div className="app-sidebar-footer">
          <LanguageSwitch />
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="app-main">
        {/* 全局执行状态栏 */}
        <ExecutionStatusBar />
        
        {/* 页面内容 */}
        <div className="app-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

// ============================================================
// App
// ============================================================

export default function App() {
  return (
    <HashRouter>
      <WorkspaceProvider>
        <ExecutionProvider>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="pilot" element={<Pilot />} />
              <Route path="runs/:runId" element={<RunDetail />} />
              <Route path="plans/:planId" element={<PlanDetail />} />
              <Route path="profile" element={<Profile />} />
              <Route path="packages" element={<Packages />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Routes>
        </ExecutionProvider>
      </WorkspaceProvider>
    </HashRouter>
  );
}
