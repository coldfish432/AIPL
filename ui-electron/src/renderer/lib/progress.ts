import { RunEvent, RunSummary } from "../apiClient";
import { formatEventType } from "./events";

function clampProgress(value: number) {
  if (Number.isNaN(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function coerceNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function extractTotalSteps(evt: RunEvent): number | null {
  return (
    coerceNumber(evt.step_total) ??
    coerceNumber(evt.total_steps) ??
    coerceNumber(evt.steps_total) ??
    coerceNumber(evt.stepTotal) ??
    null
  );
}

function extractDoneSteps(evt: RunEvent): number | null {
  return (
    coerceNumber(evt.done_steps) ??
    coerceNumber(evt.steps_done) ??
    coerceNumber(evt.stepsDone) ??
    coerceNumber(evt.doneSteps) ??
    null
  );
}

export function computeProgress(events: RunEvent[]): number {
  let progress = 0;
  let totalSteps: number | null = null;
  let derivedDoneSteps = 0;

  for (const evt of events) {
    const evtTotal = extractTotalSteps(evt);
    if (evtTotal !== null) totalSteps = evtTotal;
    const type = formatEventType(evt).toLowerCase();
    if (type === "step_done") {
      derivedDoneSteps += 1;
    }
  }

  for (const evt of events) {
    if (typeof evt.progress === "number") {
      progress = Math.max(progress, clampProgress(evt.progress));
      continue;
    }

    if (totalSteps !== null) {
      const doneSteps = extractDoneSteps(evt) ?? derivedDoneSteps;
      if (doneSteps !== null && totalSteps > 0) {
        const computed = clampProgress((doneSteps / totalSteps) * 100);
        progress = Math.max(progress, computed);
        continue;
      }
    }

    const type = formatEventType(evt).toLowerCase();
    const mapping: Record<string, number> = {
      run_start: 1,
      run_init: 1,
      step_start: 35,
      step_done: 75,
      awaiting_review: 90,
      apply_start: 95,
      apply_done: 98,
      run_done: 100,
      discard_done: 100
    };
    if (mapping[type] !== undefined) {
      progress = Math.max(progress, mapping[type]);
    }
  }

  return clampProgress(progress);
}

export function selectProgressFromRun(record: RunSummary | Record<string, unknown>): number | null {
  const progress = (record as { progress?: unknown }).progress;
  if (typeof progress === "number") return clampProgress(progress);
  const status = String((record as { status?: unknown; state?: unknown }).status || (record as { state?: unknown }).state || "").toLowerCase();
  if (status === "done") return 100;
  if (status === "failed" || status === "canceled" || status === "discarded") return 100;
  if (status === "awaiting_review") return 90;
  return null;
}
