const DEBOUNCE_MS = 300;
const timers: Map<string, number> = new Map();

export function saveDebounced<T>(key: string, value: T): void {
  const existing = timers.get(key);
  if (existing) window.clearTimeout(existing);

  const timer = window.setTimeout(() => {
    localStorage.setItem(key, JSON.stringify(value));
    timers.delete(key);
  }, DEBOUNCE_MS);

  timers.set(key, timer);
}

export function saveJson<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}

export function loadJson<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function removeItem(key: string): void {
  localStorage.removeItem(key);
}
