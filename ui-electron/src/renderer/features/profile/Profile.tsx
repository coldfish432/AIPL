/**
 * Profile 页面
 * 重构后的版本
 */

import React, { useMemo, useState } from "react";
import { BookOpen, FileCheck, RefreshCw, Save, Shield } from "lucide-react";

import { useProfile } from "./hooks/useProfile";
import { useI18n } from "@/hooks/useI18n";
import { PolicyPanel, RulesPanel, ChecksPanel } from "./components";
import type { ProfilePolicy } from "@/apis/types";

type TabId = "policy" | "checks" | "rules";

export default function Profile() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<TabId>("policy");
  const [localPolicy, setLocalPolicy] = useState<ProfilePolicy | null>(null);

  const {
    workspace,
    profile,
    rules,
    checks,
    policy,
    loading,
    error,
    load,
    savePolicy,
    addRule,
    removeRule,
    addCheck,
    removeCheck,
  } = useProfile();

  // Merge local edits with loaded policy
  const effectivePolicy = localPolicy || policy;

  // Extract validation reasons
  const reasons = useMemo(() => {
    return Array.isArray((profile as any)?.hard_validation_reasons)
      ? (profile as any).hard_validation_reasons
      : [];
  }, [profile]);

  // Tab definitions
  const tabs = [
    { id: "policy" as const, label: t.titles.hardPolicy, icon: Shield },
    { id: "checks" as const, label: t.labels.extraChecks, icon: FileCheck },
    { id: "rules" as const, label: t.labels.rules, icon: BookOpen },
  ];

  // Handlers
  const handlePolicyChange = (newPolicy: ProfilePolicy) => {
    setLocalPolicy(newPolicy);
  };

  const handleSavePolicy = async () => {
    if (!localPolicy) return;
    await savePolicy(localPolicy);
    setLocalPolicy(null);
  };

  const handleResetDefaults = () => {
    setLocalPolicy(null);
  };

  const handleRefresh = () => {
    setLocalPolicy(null);
    load();
  };

  return (
    <section className="page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">{t.titles.profile}</h1>
          <p className="page-subtitle">{t.labels.profileSubtitle}</p>
        </div>
        <div className="page-actions">
          <button
            className="button-secondary"
            onClick={handleRefresh}
            disabled={loading || !workspace}
          >
            {loading ? t.messages.loading : t.buttons.refresh}
          </button>

          {activeTab === "policy" && (
            <>
              <button
                className="button-secondary"
                onClick={handleResetDefaults}
                disabled={loading || !workspace}
              >
                <RefreshCw size={14} />
                {t.buttons.resetDefaults}
              </button>
              <button
                className="button-primary"
                onClick={handleSavePolicy}
                disabled={loading || !profile}
              >
                <Save size={14} />
                {t.buttons.save}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Error */}
      {error && <div className="page-alert">{error}</div>}

      {/* Tabs */}
      <div className="config-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`config-tab-button ${activeTab === tab.id ? "active" : ""}`}
          >
            <tab.icon size={16} />
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "policy" && (
        <PolicyPanel
          policy={effectivePolicy}
          onChange={handlePolicyChange}
          loading={loading}
          reasons={reasons}
        />
      )}

      {activeTab === "checks" && (
        <ChecksPanel
          checks={checks}
          onAdd={addCheck}
          onRemove={removeCheck}
          loading={loading}
        />
      )}

      {activeTab === "rules" && (
        <RulesPanel
          rules={rules}
          onAdd={addRule}
          onRemove={removeRule}
          loading={loading}
        />
      )}
    </section>
  );
}
