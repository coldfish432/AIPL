/**
 * Packages Hook
 * 管理语言包和体验包
 */

import { useCallback, useEffect, useState } from "react";
import {
  listLanguagePacks,
  getLanguagePack,
  importLanguagePack,
  exportLanguagePack,
  deleteLanguagePack,
  listExperiencePacks,
  getExperiencePack,
  importExperiencePack,
  exportExperiencePack,
  deleteExperiencePack,
} from "@/apis";
import type { PackRecord } from "@/apis/types";

// ============================================================
// Types
// ============================================================

export type PackType = "language" | "experience";

export interface PackItem {
  id: string;
  name: string;
  description?: string;
  version?: string;
  type: PackType;
  updatedAt?: string | number;
  meta?: Record<string, unknown>;
}

export interface UsePackagesReturn {
  languagePacks: PackItem[];
  experiencePacks: PackItem[];
  loading: boolean;
  error: string | null;
  
  // Actions
  refresh: () => Promise<void>;
  importPack: (type: PackType, pack: PackRecord) => Promise<void>;
  exportPack: (type: PackType, id: string) => Promise<PackRecord | null>;
  deletePack: (type: PackType, id: string) => Promise<void>;
  getPack: (type: PackType, id: string) => Promise<PackRecord | null>;
}

// ============================================================
// Hook
// ============================================================

export function usePackages(): UsePackagesReturn {
  const [languagePacks, setLanguagePacks] = useState<PackItem[]>([]);
  const [experiencePacks, setExperiencePacks] = useState<PackItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 标准化包数据
   */
  const normalizePack = (raw: PackRecord, type: PackType): PackItem => {
    return {
      id: String(raw.id || raw.pack_id || raw.name || ""),
      name: String(raw.name || raw.title || raw.id || "未命名"),
      description: raw.description ? String(raw.description) : undefined,
      version: raw.version ? String(raw.version) : undefined,
      type,
      updatedAt: raw.updated_at || raw.updatedAt || raw.ts,
      meta: raw,
    };
  };

  /**
   * 加载所有包
   */
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [langData, expData] = await Promise.all([
        listLanguagePacks().catch(() => []),
        listExperiencePacks().catch(() => []),
      ]);

      const langList = Array.isArray(langData) ? langData : [];
      const expList = Array.isArray(expData) ? expData : [];

      setLanguagePacks(langList.map((p) => normalizePack(p, "language")));
      setExperiencePacks(expList.map((p) => normalizePack(p, "experience")));
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载包列表失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    refresh();
  }, [refresh]);

  /**
   * 导入包
   */
  const importPack = useCallback(
    async (type: PackType, pack: PackRecord) => {
      setLoading(true);
      setError(null);

      try {
        if (type === "language") {
          await importLanguagePack({ pack });
        } else {
          await importExperiencePack({ pack });
        }
        await refresh();
      } catch (err) {
        const message = err instanceof Error ? err.message : "导入包失败";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [refresh]
  );

  /**
   * 导出包
   */
  const exportPack = useCallback(
    async (type: PackType, id: string): Promise<PackRecord | null> => {
      setLoading(true);
      setError(null);

      try {
        if (type === "language") {
          return await exportLanguagePack(id);
        } else {
          return await exportExperiencePack(id);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "导出包失败";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /**
   * 删除包
   */
  const deletePack = useCallback(
    async (type: PackType, id: string) => {
      setLoading(true);
      setError(null);

      try {
        if (type === "language") {
          await deleteLanguagePack(id);
        } else {
          await deleteExperiencePack(id);
        }
        await refresh();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除包失败";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [refresh]
  );

  /**
   * 获取单个包
   */
  const getPack = useCallback(
    async (type: PackType, id: string): Promise<PackRecord | null> => {
      try {
        if (type === "language") {
          return await getLanguagePack(id);
        } else {
          return await getExperiencePack(id);
        }
      } catch {
        return null;
      }
    },
    []
  );

  return {
    languagePacks,
    experiencePacks,
    loading,
    error,
    refresh,
    importPack,
    exportPack,
    deletePack,
    getPack,
  };
}
