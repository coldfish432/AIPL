/**
 * App Layout 组件
 */

import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Navigation,
  Settings,
  Globe,
  Package,
} from "lucide-react";
import { useI18n } from "@/hooks/useI18n";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { t, language, toggleLanguage } = useI18n();
  const location = useLocation();

  const navItems = [
    { path: "/", label: t.titles.dashboard, icon: LayoutDashboard },
    { path: "/pilot", label: t.titles.pilot, icon: Navigation },
    { path: "/packages", label: t.titles.packages, icon: Package },
    { path: "/profile", label: t.titles.profile, icon: Settings },
  ];

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div className="app-logo">
          <span className="app-logo-text">AIPL</span>
        </div>

        <nav className="app-nav">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`app-nav-item ${isActive ? "active" : ""}`}
              >
                <item.icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="app-sidebar-footer">
          <button
            className="app-lang-toggle"
            onClick={toggleLanguage}
            title={language === "zh" ? "Switch to English" : "切换到中文"}
          >
            <Globe size={16} />
            <span>{language === "zh" ? "EN" : "中"}</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">{children}</main>
    </div>
  );
}
