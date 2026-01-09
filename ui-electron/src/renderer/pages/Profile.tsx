import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  FileCheck,
  Info,
  RefreshCw,
  Save,
  Shield,
  Terminal,
  X
} from "lucide-react";
import {
  addWorkspaceCheck,
  addWorkspaceRule,
  deleteWorkspaceCheck,
  deleteWorkspaceRule,
  getProfile,
  getWorkspaceMemory,
  ProfileData,
  updateProfile
} from "../apiClient";
import { useI18n } from "../lib/useI18n";
import { STORAGE_KEYS } from "../config/settings";

export default function Profile() {
  const { t } = useI18n();
  const [workspace, setWorkspace] = useState(() => localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [rules, setRules] = useState<any[]>([]);
  const [extraChecks, setExtraChecks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"policy" | "checks" | "rules">("policy");
  const [ruleContent, setRuleContent] = useState("");
  const [ruleScope, setRuleScope] = useState("");
  const [ruleCategory, setRuleCategory] = useState("");
  const [checkJson, setCheckJson] = useState("");
  const [checkScope, setCheckScope] = useState("");
  const [allowWriteTags, setAllowWriteTags] = useState<string[]>([]);
  const [denyWriteTags, setDenyWriteTags] = useState<string[]>([]);
  const [allowedCommandsTags, setAllowedCommandsTags] = useState<string[]>([]);
  const [commandTimeoutInput, setCommandTimeoutInput] = useState("");
  const [maxConcurrencyInput, setMaxConcurrencyInput] = useState("");

  function formatList(value: unknown) {
    if (!Array.isArray(value)) return "-";
    const items = value.map((item) => String(item)).filter((item) => item.trim());
    return items.length ? items.join(", ") : "-";
  }

  function formatValue(value: unknown) {
    if (value === undefined || value === null || value === "") return "-";
    if (Array.isArray(value)) return formatList(value);
    return String(value);
  }

  function formatReason(reason: any) {
    if (!reason || typeof reason !== "object") return "-";
    const type = reason.type ? String(reason.type) : "-";
    const field = reason.field ? ` (${reason.field})` : "";
    const value = reason.value !== undefined ? `: ${String(reason.value)}` : "";
    return `${type}${field}${value}`;
  }

  async function load(targetWorkspace?: string) {
    const effectiveWorkspace = targetWorkspace ?? workspace;
    if (!effectiveWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getProfile(effectiveWorkspace);
      setProfile(data);
      localStorage.setItem(STORAGE_KEYS.workspaceKey, effectiveWorkspace);
      setWorkspace(effectiveWorkspace);
      const id = typeof (data as any)?.workspace_id === "string" ? (data as any).workspace_id : null;
      setWorkspaceId(id);
      if (id) {
        const mem = await getWorkspaceMemory(id);
        const custom = (mem as any)?.custom_rules;
        const ruleList = Array.isArray(custom?.rules) ? custom.rules : [];
        const checkList = Array.isArray(custom?.extra_checks) ? custom.extra_checks : [];
        setRules(ruleList);
        setExtraChecks(checkList);
      } else {
        setRules([]);
        setExtraChecks([]);
      }
      const userHard = (data as any)?.user_hard;
      const effectiveHard = (data as any)?.effective_hard || (data as any)?.hard_policy;
      const base = typeof userHard === "object" && userHard ? userHard : effectiveHard;
      if (base) {
        setAllowWriteTags(Array.isArray(base.allow_write) ? base.allow_write.map(String) : []);
        setDenyWriteTags(Array.isArray(base.deny_write) ? base.deny_write.map(String) : []);
        setAllowedCommandsTags(Array.isArray(base.allowed_commands) ? base.allowed_commands.map(String) : []);
        setCommandTimeoutInput(base.command_timeout ? String(base.command_timeout) : "");
        setMaxConcurrencyInput(base.max_concurrency ? String(base.max_concurrency) : "");
      } else {
        setAllowWriteTags([]);
        setDenyWriteTags([]);
        setAllowedCommandsTags([]);
        setCommandTimeoutInput("");
        setMaxConcurrencyInput("");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const syncWorkspace = () => {
      setWorkspace(localStorage.getItem(STORAGE_KEYS.workspaceKey) || "");
    };
    window.addEventListener("aipl-workspace-changed", syncWorkspace);
    return () => window.removeEventListener("aipl-workspace-changed", syncWorkspace);
  }, []);

  useEffect(() => {
    if (workspace) {
      void load(workspace);
    }
  }, [workspace]);

  const effective = (profile as any)?.effective_hard || (profile as any)?.hard_policy;
  const reasons = Array.isArray((profile as any)?.hard_validation_reasons)
    ? (profile as any).hard_validation_reasons
    : [];

  async function saveDefaults() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const userHard: Record<string, unknown> = {
        allow_write: allowWriteTags,
        deny_write: denyWriteTags,
        allowed_commands: allowedCommandsTags
      };
      const commandTimeout = parseInt(commandTimeoutInput, 10);
      const maxConcurrency = parseInt(maxConcurrencyInput, 10);
      if (!Number.isNaN(commandTimeout)) userHard.command_timeout = commandTimeout;
      if (!Number.isNaN(maxConcurrency)) userHard.max_concurrency = maxConcurrency;
      const data = await updateProfile(workspace, userHard);
      setProfile(data);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function addCheck() {
    if (!workspaceId || !checkJson.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = JSON.parse(checkJson);
      await addWorkspaceCheck(workspaceId, { check: payload, scope: checkScope || undefined });
      setCheckJson("");
      setCheckScope("");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function removeCheck(checkId: string) {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      await deleteWorkspaceCheck(workspaceId, checkId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setError(message || t.messages.deleteFailed);
    } finally {
      setLoading(false);
    }
  }

  async function addRule() {
    if (!workspaceId || !ruleContent.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await addWorkspaceRule(workspaceId, { content: ruleContent, scope: ruleScope || undefined, category: ruleCategory || undefined });
      setRuleContent("");
      setRuleScope("");
      setRuleCategory("");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function removeRule(ruleId: string) {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      await deleteWorkspaceRule(workspaceId, ruleId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setError(message || t.messages.deleteFailed);
    } finally {
      setLoading(false);
    }
  }

  async function resetDefaults() {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await updateProfile(workspace, null);
      setProfile(data);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadFailed;
      setError(message || t.messages.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  const tabs = useMemo(
    () => [
      {
        id: "policy" as const,
        label: t.labels.policyConfig,
        description: t.labels.policyConfigDescription,
        icon: Shield
      },
      {
        id: "checks" as const,
        label: t.labels.extraChecks,
        description: t.labels.checksDescription,
        icon: FileCheck
      },
      {
        id: "rules" as const,
        label: t.labels.rules,
        description: t.labels.rulesDescription,
        icon: BookOpen
      }
    ],
    [t.labels.checksDescription, t.labels.extraChecks, t.labels.policyConfig, t.labels.policyConfigDescription, t.labels.rules, t.labels.rulesDescription]
  );

  const activeTabConfig = tabs.find((tab) => tab.id === activeTab);

  const TagInput = ({
    tags,
    onChange,
    placeholder,
    variant,
    disabled
  }: {
    tags: string[];
    onChange: (next: string[]) => void;
    placeholder: string;
    variant: "allow" | "deny" | "command";
    disabled?: boolean;
  }) => {
    const [draft, setDraft] = useState("");

    const addTags = (value: string) => {
      const nextItems = value
        .split(/[,;\n]/)
        .map((item) => item.trim())
        .filter((item) => item);
      if (nextItems.length === 0) return;
      const next = [...tags];
      for (const item of nextItems) {
        if (!next.includes(item)) {
          next.push(item);
        }
      }
      onChange(next);
      setDraft("");
    };

    return (
      <div className={`tag-input ${disabled ? "disabled" : ""}`}>
        {tags.map((tag, index) => (
          <span key={`${tag}-${index}`} className={`tag-pill ${variant}`}>
            <code>{tag}</code>
            <button type="button" className="tag-remove" onClick={() => onChange(tags.filter((_, idx) => idx !== index))} disabled={disabled}>
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={draft}
          disabled={disabled}
          placeholder={tags.length === 0 ? placeholder : t.labels.tagInputHint}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTags(draft);
            }
          }}
          onBlur={() => addTags(draft)}
        />
      </div>
    );
  };

  const FormField = ({
    label,
    description,
    required,
    children
  }: {
    label: string;
    description?: string;
    required?: boolean;
    children: React.ReactNode;
  }) => (
    <div className="config-field">
      <div className="config-field-label">
        <div className="config-field-title">
          <span>{label}</span>
          {required && <span className="config-required">*</span>}
        </div>
        {description && (
          <div className="config-help">
            <Info size={14} />
            <div className="config-tooltip">{description}</div>
          </div>
        )}
      </div>
      {children}
    </div>
  );

  const ConfigCard = ({
    icon: Icon,
    title,
    description,
    children,
    className
  }: {
    icon: React.ComponentType<{ size?: number | string | undefined }>;
    title: string;
    description?: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <div className={`config-card ${className ?? ""}`.trim()}>
      <div className="config-card-header">
        <div className="config-card-icon">
          <Icon size={18} />
        </div>
        <div>
          <div className="config-card-title">{title}</div>
          {description && <div className="config-card-description">{description}</div>}
        </div>
      </div>
      <div className="config-card-body">{children}</div>
    </div>
  );

  return (
    <section className="page config-page">
      <div className="page-header config-header">
        <div>
          <p className="page-subtitle">{t.labels.profileSubtitle}</p>
        </div>
        <div className="page-actions">
          <button className="button-secondary" onClick={() => load()} disabled={loading || !workspace}>
            {loading ? t.messages.loading : t.buttons.refresh}
          </button>
          {activeTab === "policy" && (
            <>
              <button className="button-secondary" onClick={resetDefaults} disabled={loading || !workspace}>
                <RefreshCw size={14} />
                {t.buttons.resetDefaults}
              </button>
              <button className="button-primary" onClick={saveDefaults} disabled={loading || !profile}>
                <Save size={14} />
                {t.buttons.save}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="page-alert">{error}</div>}

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

      {activeTab === "policy" && (
        <div className="config-stack">
          <div className="config-info-banner">
            <Info size={16} />
            <span>{t.messages.policyNotice}</span>
          </div>
          <ConfigCard icon={Shield} title={t.labels.fileAccessPolicy} description={t.labels.fileAccessPolicyDescription}>
            <FormField label={t.labels.hardPolicyAllowWrite} description={t.labels.allowWriteHelp} required>
              <TagInput
                tags={allowWriteTags}
                onChange={setAllowWriteTags}
                placeholder={t.labels.allowWritePlaceholder}
                variant="allow"
                disabled={loading}
              />
            </FormField>
            <FormField label={t.labels.hardPolicyDenyWrite} description={t.labels.denyWriteHelp}>
              <TagInput
                tags={denyWriteTags}
                onChange={setDenyWriteTags}
                placeholder={t.labels.denyWritePlaceholder}
                variant="deny"
                disabled={loading}
              />
            </FormField>
          </ConfigCard>
          <ConfigCard icon={Terminal} title={t.labels.commandPolicy} description={t.labels.commandPolicyDescription}>
            <FormField label={t.labels.hardPolicyAllowedCommands} description={t.labels.allowedCommandsHelp} required>
              <TagInput
                tags={allowedCommandsTags}
                onChange={setAllowedCommandsTags}
                placeholder={t.labels.allowedCommandsPlaceholder}
                variant="command"
                disabled={loading}
              />
            </FormField>
          </ConfigCard>
          <ConfigCard icon={CheckCircle} title={t.labels.executionPolicy} description={t.labels.executionPolicyDescription}>
            <div className="config-grid policy-params">
              <FormField label={t.labels.hardPolicyCommandTimeout} description={t.labels.commandTimeoutHelp} required>
                <div className="config-inline-input">
                  <input
                    className="page-input"
                    type="number"
                    value={commandTimeoutInput}
                    onChange={(e) => setCommandTimeoutInput(e.target.value)}
                  />
                  <span>{t.labels.secondsUnit}</span>
                </div>
              </FormField>
              <FormField label={t.labels.hardPolicyMaxConcurrency} description={t.labels.maxConcurrencyHelp} required>
                <input
                  className="page-input"
                  type="number"
                  value={maxConcurrencyInput}
                  onChange={(e) => setMaxConcurrencyInput(e.target.value)}
                />
              </FormField>
            </div>
          </ConfigCard>
          {reasons.length > 0 && (
            <ConfigCard icon={AlertTriangle} title={t.labels.hardPolicyReasons}>
              <div className="reasons-list">
                {reasons.map((reason: any, idx: number) => (
                  <span key={`${reason?.type || "reason"}-${idx}`} className="reason-pill">
                    {formatReason(reason)}
                  </span>
                ))}
              </div>
            </ConfigCard>
          )}
        </div>
      )}

      {activeTab === "checks" && (
        <div className="config-stack">
          <div className="panel">
            <div className="panel-header">
              <h2 className="panel-title">{t.labels.extraChecks}</h2>
              <div className="panel-meta">{t.labels.checksPanelMeta}</div>
            </div>
            <div className="card-list compact">
              {extraChecks.map((c: any) => (
                <div key={c.id} className="card-item">
                  <div className="card-item-main">
                    <div className="card-item-title">{c.check?.cmd || JSON.stringify(c.check || {})}</div>
                    <div className="card-item-meta">{c.scope || "-"}</div>
                  </div>
                  <div className="card-item-actions">
                    <button className="button-danger" onClick={() => removeCheck(c.id)} disabled={loading}>{t.buttons.delete}</button>
                  </div>
                </div>
              ))}
              {!extraChecks.length && (
                <div className="config-empty-state">
                  <FileCheck size={32} />
                  <div>{t.messages.noChecks}</div>
                </div>
              )}
            </div>
          </div>
          <div className="panel">
            <div className="panel-header">
              <h2 className="panel-title">{t.labels.addCheck}</h2>
              <div className="panel-meta">{t.labels.checksFormMeta}</div>
            </div>
            <div className="form-stack">
              <textarea className="page-textarea" rows={4} value={checkJson} onChange={(e) => setCheckJson(e.target.value)} placeholder={t.labels.checkJsonPlaceholder} />
              <input className="page-input" value={checkScope} onChange={(e) => setCheckScope(e.target.value)} placeholder={t.labels.scopeOptional} />
              <button className="button-primary" onClick={addCheck} disabled={loading || !checkJson.trim()}>{t.buttons.addCheck}</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === "rules" && (
        <div className="config-stack">
          <div className="panel">
            <div className="panel-header">
              <h2 className="panel-title">{t.labels.rules}</h2>
              <div className="panel-meta">{t.labels.rulesPanelMeta}</div>
            </div>
            <div className="card-list compact">
              {rules.map((r: any) => (
                <div key={r.id} className="card-item">
                  <div className="card-item-main">
                    <div className="card-item-title">{r.content}</div>
                    <div className="card-item-meta">{r.scope || "-"} {r.category ? `· ${r.category}` : ""}</div>
                  </div>
                  <div className="card-item-actions">
                    <button className="button-danger" onClick={() => removeRule(r.id)} disabled={loading}>{t.buttons.delete}</button>
                  </div>
                </div>
              ))}
              {!rules.length && (
                <div className="config-empty-state">
                  <BookOpen size={32} />
                  <div>{t.messages.noRules}</div>
                </div>
              )}
            </div>
          </div>
          <div className="panel">
            <div className="panel-header">
              <h2 className="panel-title">{t.labels.addRule}</h2>
              <div className="panel-meta">{t.labels.rulesFormMeta}</div>
            </div>
            <div className="form-stack">
              <input className="page-input" value={ruleContent} onChange={(e) => setRuleContent(e.target.value)} placeholder={t.labels.ruleContent} />
              <input className="page-input" value={ruleScope} onChange={(e) => setRuleScope(e.target.value)} placeholder={t.labels.scopeOptional} />
              <input className="page-input" value={ruleCategory} onChange={(e) => setRuleCategory(e.target.value)} placeholder={t.labels.categoryOptional} />
              <button className="button-primary" onClick={addRule} disabled={loading || !ruleContent.trim()}>{t.buttons.addRule}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
