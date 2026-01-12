/**
 * Profile 组件
 */

import React, { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  FileCheck,
  Info,
  Shield,
  Terminal,
  X,
} from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { ProfilePolicy } from "@/apis/types";

// ============================================================
// Types
// ============================================================

interface WorkspaceRule {
  id: string;
  content: string;
  scope?: string;
  category?: string;
}

interface WorkspaceCheck {
  id: string;
  check: Record<string, unknown>;
  scope?: string;
}

// ============================================================
// Tag Input Component
// ============================================================

interface TagInputProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  variant?: "allow" | "deny" | "command";
  disabled?: boolean;
}

export function TagInput({
  tags,
  onChange,
  placeholder,
  variant = "allow",
  disabled,
}: TagInputProps) {
  const [input, setInput] = useState("");

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      if (!tags.includes(input.trim())) {
        onChange([...tags, input.trim()]);
      }
      setInput("");
    }
  };

  const handleRemove = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  return (
    <div className={`tag-input ${variant}`}>
      <div className="tag-list">
        {tags.map((tag) => (
          <span key={tag} className={`tag ${variant}`}>
            {tag}
            <button
              type="button"
              className="tag-remove"
              onClick={() => handleRemove(tag)}
              disabled={disabled}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="tag-input-field"
      />
    </div>
  );
}

// ============================================================
// Config Card Component
// ============================================================

interface ConfigCardProps {
  icon: React.ComponentType<{ size?: number | string }>;
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function ConfigCard({ icon: Icon, title, description, children }: ConfigCardProps) {
  return (
    <div className="config-card">
      <div className="config-card-header">
        <Icon size={20} />
        <div className="config-card-header-text">
          <h3 className="config-card-title">{title}</h3>
          {description && <p className="config-card-description">{description}</p>}
        </div>
      </div>
      <div className="config-card-content">{children}</div>
    </div>
  );
}

// ============================================================
// Form Field Component
// ============================================================

interface FormFieldProps {
  label: string;
  description?: string;
  required?: boolean;
  children: React.ReactNode;
}

export function FormField({ label, description, required, children }: FormFieldProps) {
  return (
    <div className="form-field">
      <label className="form-label">
        {label}
        {required && <span className="form-required">*</span>}
      </label>
      {description && <p className="form-description">{description}</p>}
      {children}
    </div>
  );
}

// ============================================================
// Policy Panel Component
// ============================================================

interface PolicyPanelProps {
  policy: ProfilePolicy;
  onChange: (policy: ProfilePolicy) => void;
  loading: boolean;
  reasons?: Array<{ type?: string; field?: string; value?: unknown }>;
}

export function PolicyPanel({ policy, onChange, loading, reasons }: PolicyPanelProps) {
  const { t } = useI18n();

  const formatReason = (reason: { type?: string; field?: string; value?: unknown }) => {
    const type = reason.type ? String(reason.type) : "-";
    const field = reason.field ? ` (${reason.field})` : "";
    const value = reason.value !== undefined ? `: ${String(reason.value)}` : "";
    return `${type}${field}${value}`;
  };

  return (
    <div className="config-stack">
      <div className="config-info-banner">
        <Info size={16} />
        <span>{t.messages.policyNotice}</span>
      </div>

      <ConfigCard
        icon={Shield}
        title={t.labels.fileAccessPolicy}
        description={t.labels.fileAccessPolicyDescription}
      >
        <FormField
          label={t.labels.hardPolicyAllowWrite}
          description={t.labels.allowWriteHelp}
          required
        >
          <TagInput
            tags={policy.allow_write || []}
            onChange={(tags) => onChange({ ...policy, allow_write: tags })}
            placeholder={t.labels.allowWritePlaceholder}
            variant="allow"
            disabled={loading}
          />
        </FormField>

        <FormField
          label={t.labels.hardPolicyDenyWrite}
          description={t.labels.denyWriteHelp}
        >
          <TagInput
            tags={policy.deny_write || []}
            onChange={(tags) => onChange({ ...policy, deny_write: tags })}
            placeholder={t.labels.denyWritePlaceholder}
            variant="deny"
            disabled={loading}
          />
        </FormField>
      </ConfigCard>

      <ConfigCard
        icon={Terminal}
        title={t.labels.commandPolicy}
        description={t.labels.commandPolicyDescription}
      >
        <FormField
          label={t.labels.hardPolicyAllowedCommands}
          description={t.labels.allowedCommandsHelp}
          required
        >
          <TagInput
            tags={policy.allowed_commands || []}
            onChange={(tags) => onChange({ ...policy, allowed_commands: tags })}
            placeholder={t.labels.allowedCommandsPlaceholder}
            variant="command"
            disabled={loading}
          />
        </FormField>
      </ConfigCard>

      <ConfigCard
        icon={CheckCircle}
        title={t.labels.executionPolicy}
        description={t.labels.executionPolicyDescription}
      >
        <div className="config-grid policy-params">
          <FormField
            label={t.labels.hardPolicyCommandTimeout}
            description={t.labels.commandTimeoutHelp}
            required
          >
            <div className="config-inline-input">
              <input
                className="page-input"
                type="number"
                value={policy.command_timeout || ""}
                onChange={(e) =>
                  onChange({
                    ...policy,
                    command_timeout: parseInt(e.target.value, 10) || undefined,
                  })
                }
                disabled={loading}
              />
              <span>{t.labels.secondsUnit}</span>
            </div>
          </FormField>

          <FormField
            label={t.labels.hardPolicyMaxConcurrency}
            description={t.labels.maxConcurrencyHelp}
            required
          >
            <input
              className="page-input"
              type="number"
              value={policy.max_concurrency || ""}
              onChange={(e) =>
                onChange({
                  ...policy,
                  max_concurrency: parseInt(e.target.value, 10) || undefined,
                })
              }
              disabled={loading}
            />
          </FormField>
        </div>
      </ConfigCard>

      {reasons && reasons.length > 0 && (
        <ConfigCard icon={AlertTriangle} title={t.labels.hardPolicyReasons}>
          <div className="reasons-list">
            {reasons.map((reason, idx) => (
              <span
                key={`${reason?.type || "reason"}-${idx}`}
                className="reason-pill"
              >
                {formatReason(reason)}
              </span>
            ))}
          </div>
        </ConfigCard>
      )}
    </div>
  );
}

// ============================================================
// Rules Panel Component
// ============================================================

interface RulesPanelProps {
  rules: WorkspaceRule[];
  onAdd: (content: string, scope?: string, category?: string) => Promise<void>;
  onRemove: (ruleId: string) => Promise<void>;
  loading: boolean;
}

export function RulesPanel({ rules, onAdd, onRemove, loading }: RulesPanelProps) {
  const { t } = useI18n();
  const [content, setContent] = useState("");
  const [scope, setScope] = useState("");
  const [category, setCategory] = useState("");

  const handleAdd = async () => {
    if (!content.trim()) return;
    await onAdd(content.trim(), scope || undefined, category || undefined);
    setContent("");
    setScope("");
    setCategory("");
  };

  return (
    <div className="config-stack">
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.rules}</h2>
          <div className="panel-meta">{t.labels.rulesPanelMeta}</div>
        </div>

        <div className="card-list compact">
          {rules.map((rule) => (
            <div key={rule.id} className="card-item">
              <div className="card-item-main">
                <div className="card-item-title">{rule.content}</div>
                <div className="card-item-meta">
                  {rule.scope || "-"} {rule.category ? `· ${rule.category}` : ""}
                </div>
              </div>
              <div className="card-item-actions">
                <button
                  className="button-danger"
                  onClick={() => onRemove(rule.id)}
                  disabled={loading}
                >
                  {t.buttons.delete}
                </button>
              </div>
            </div>
          ))}
          {rules.length === 0 && (
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
          <input
            className="page-input"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={t.labels.ruleContent}
          />
          <input
            className="page-input"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder={t.labels.scopeOptional}
          />
          <input
            className="page-input"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder={t.labels.categoryOptional}
          />
          <button
            className="button-primary"
            onClick={handleAdd}
            disabled={loading || !content.trim()}
          >
            {t.buttons.addRule}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Checks Panel Component
// ============================================================

interface ChecksPanelProps {
  checks: WorkspaceCheck[];
  onAdd: (check: Record<string, unknown>, scope?: string) => Promise<void>;
  onRemove: (checkId: string) => Promise<void>;
  loading: boolean;
}

export function ChecksPanel({ checks, onAdd, onRemove, loading }: ChecksPanelProps) {
  const { t } = useI18n();
  const [checkJson, setCheckJson] = useState("");
  const [scope, setScope] = useState("");

  const handleAdd = async () => {
    if (!checkJson.trim()) return;
    try {
      const check = JSON.parse(checkJson);
      await onAdd(check, scope || undefined);
      setCheckJson("");
      setScope("");
    } catch {
      // Invalid JSON
    }
  };

  return (
    <div className="config-stack">
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.labels.extraChecks}</h2>
          <div className="panel-meta">{t.labels.checksPanelMeta}</div>
        </div>

        <div className="card-list compact">
          {checks.map((check) => (
            <div key={check.id} className="card-item">
              <div className="card-item-main">
                <div className="card-item-title">
                  {(check.check as any)?.cmd || JSON.stringify(check.check || {})}
                </div>
                <div className="card-item-meta">{check.scope || "-"}</div>
              </div>
              <div className="card-item-actions">
                <button
                  className="button-danger"
                  onClick={() => onRemove(check.id)}
                  disabled={loading}
                >
                  {t.buttons.delete}
                </button>
              </div>
            </div>
          ))}
          {checks.length === 0 && (
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
          <textarea
            className="page-textarea"
            rows={4}
            value={checkJson}
            onChange={(e) => setCheckJson(e.target.value)}
            placeholder={t.labels.checkJsonPlaceholder}
          />
          <input
            className="page-input"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder={t.labels.scopeOptional}
          />
          <button
            className="button-primary"
            onClick={handleAdd}
            disabled={loading || !checkJson.trim()}
          >
            {t.buttons.addCheck}
          </button>
        </div>
      </div>
    </div>
  );
}
