/**
 * Profile Hook
 * 管理工作区配置
 */

import { useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { STORAGE_KEYS } from "@/config/settings";
import {
  getProfile,
  updateProfile,
  getWorkspaceMemory,
  addWorkspaceRule,
  deleteWorkspaceRule,
  addWorkspaceCheck,
  deleteWorkspaceCheck,
} from "@/services/api";
import type { ProfileData, ProfilePolicy } from "@/apis/types";

// ============================================================
// Types
// ============================================================

export interface WorkspaceRule {
  id: string;
  content: string;
  scope?: string;
  category?: string;
}

export interface WorkspaceCheck {
  id: string;
  check: Record<string, unknown>;
  scope?: string;
}

export interface UseProfileReturn {
  workspace: string;
  workspaceId: string | null;
  profile: ProfileData | null;
  rules: WorkspaceRule[];
  checks: WorkspaceCheck[];
  policy: ProfilePolicy;
  loading: boolean;
  error: string | null;

  // Actions
  load: (workspace?: string) => Promise<void>;
  savePolicy: (policy: ProfilePolicy) => Promise<void>;
  addRule: (content: string, scope?: string, category?: string) => Promise<void>;
  removeRule: (ruleId: string) => Promise<void>;
  addCheck: (check: Record<string, unknown>, scope?: string) => Promise<void>;
  removeCheck: (checkId: string) => Promise<void>;
}

// ============================================================
// Default Values
// ============================================================

const DEFAULT_POLICY: ProfilePolicy = {
  allow_write: [],
  deny_write: [],
  allowed_commands: [],
  command_timeout: 300,
  max_concurrency: 4,
};

// ============================================================
// Hook
// ============================================================

export function useProfile(): UseProfileReturn {
  const { workspace } = useWorkspace();
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [rules, setRules] = useState<WorkspaceRule[]>([]);
  const [checks, setChecks] = useState<WorkspaceCheck[]>([]);
  const [policy, setPolicy] = useState<ProfilePolicy>(DEFAULT_POLICY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 加载配置
   */
  const load = useCallback(async (targetWorkspace?: string) => {
    const effectiveWorkspace = targetWorkspace ?? workspace;
    if (!effectiveWorkspace) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getProfile(effectiveWorkspace);
      setProfile(data);

      // Extract workspace ID
      const id = typeof (data as any)?.workspace_id === "string"
        ? (data as any).workspace_id
        : null;
      setWorkspaceId(id);

      // Load rules and checks
      if (id) {
        const mem = await getWorkspaceMemory(id);
        const custom = (mem as any)?.custom_rules;
        setRules(Array.isArray(custom?.rules) ? custom.rules : []);
        setChecks(Array.isArray(custom?.extra_checks) ? custom.extra_checks : []);
      } else {
        setRules([]);
        setChecks([]);
      }

      // Extract policy
      const userHard = (data as any)?.user_hard;
      const effectiveHard = (data as any)?.effective_hard || (data as any)?.hard_policy;
      const base = typeof userHard === "object" && userHard ? userHard : effectiveHard;

      if (base) {
        setPolicy({
          allow_write: Array.isArray(base.allow_write) ? base.allow_write.map(String) : [],
          deny_write: Array.isArray(base.deny_write) ? base.deny_write.map(String) : [],
          allowed_commands: Array.isArray(base.allowed_commands) ? base.allowed_commands.map(String) : [],
          command_timeout: base.command_timeout || DEFAULT_POLICY.command_timeout,
          max_concurrency: base.max_concurrency || DEFAULT_POLICY.max_concurrency,
        });
      } else {
        setPolicy(DEFAULT_POLICY);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载配置失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  // Initial load
  useEffect(() => {
    if (workspace) {
      load(workspace);
    }
  }, [workspace, load]);

  /**
   * 保存策略
   */
  const savePolicy = useCallback(async (newPolicy: ProfilePolicy) => {
    if (!workspace) return;

    setLoading(true);
    setError(null);

    try {
      const userHard: Record<string, unknown> = {
        allow_write: newPolicy.allow_write,
        deny_write: newPolicy.deny_write,
        allowed_commands: newPolicy.allowed_commands,
      };

      if (newPolicy.command_timeout) {
        userHard.command_timeout = newPolicy.command_timeout;
      }
      if (newPolicy.max_concurrency) {
        userHard.max_concurrency = newPolicy.max_concurrency;
      }

      const data = await updateProfile(workspace, userHard);
      setProfile(data);
      setPolicy(newPolicy);
    } catch (err) {
      const message = err instanceof Error ? err.message : "保存策略失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  /**
   * 添加规则
   */
  const addRule = useCallback(async (content: string, scope?: string, category?: string) => {
    if (!workspaceId || !content.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await addWorkspaceRule(workspaceId, { content, scope, category });
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "添加规则失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [workspaceId, load]);

  /**
   * 删除规则
   */
  const removeRule = useCallback(async (ruleId: string) => {
    if (!workspaceId) return;

    setLoading(true);
    setError(null);

    try {
      await deleteWorkspaceRule(workspaceId, ruleId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除规则失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [workspaceId, load]);

  /**
   * 添加检查项
   */
  const addCheck = useCallback(async (check: Record<string, unknown>, scope?: string) => {
    if (!workspaceId) return;

    setLoading(true);
    setError(null);

    try {
      await addWorkspaceCheck(workspaceId, { check, scope });
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "添加检查项失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [workspaceId, load]);

  /**
   * 删除检查项
   */
  const removeCheck = useCallback(async (checkId: string) => {
    if (!workspaceId) return;

    setLoading(true);
    setError(null);

    try {
      await deleteWorkspaceCheck(workspaceId, checkId);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除检查项失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [workspaceId, load]);

  return {
    workspace,
    workspaceId,
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
  };
}
