import { STORAGE_KEYS } from "../config/settings";

const MAX_HISTORY = 5;

export function loadWorkspaceHistory(): string[] {
  const raw = localStorage.getItem(STORAGE_KEYS.workspaceHistoryKey);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((item) => typeof item === "string" && item.trim()).slice(0, MAX_HISTORY);
    }
  } catch {
    // ignore
  }
  return [];
}

export function addWorkspaceToHistory(path: string): void {
  if (!path) return;
  const normalized = path.trim();
  if (!normalized) return;
  const current = loadWorkspaceHistory().filter((item) => item !== normalized);
  current.unshift(normalized);
  const next = current.slice(0, MAX_HISTORY);
  localStorage.setItem(STORAGE_KEYS.workspaceHistoryKey, JSON.stringify(next));
}
