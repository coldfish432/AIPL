/**
 * 统一 API 类型定义
 */

// ============================================================
// 基础状态类型
// ============================================================

export type ExecutionStatus =
  | "queued"
  | "starting"
  | "running"
  | "retrying"
  | "completed"
  | "failed"
  | "canceled"
  | "discarded";

export type ReviewStatus =
  | "none"
  | "pending"
  | "approved"
  | "applied"
  | "rejected"
  | "reworking";

export interface UnifiedStatus {
  execution: ExecutionStatus;
  review: ReviewStatus | null;
}

// ============================================================
// Plan 相关类型
// ============================================================

export interface PlanTask {
  id?: string;
  step_id?: string;
  task_id?: string;
  title?: string;
  name?: string;
  description?: string;
  status?: string;
  dependencies?: string[];
  capabilities?: string[];
}

export interface PlanSummary {
  id?: string;
  plan_id?: string;
  planId?: string;
  tasks_count?: number;
  tasksCount?: number;
  updated_at?: string | number;
  updatedAt?: string | number;
  ts?: string | number;
  input_task?: string;
  inputTask?: string;
  task?: string;
  workspace_path?: string;
  workspacePath?: string;
}

export interface PlanInfo {
  plan_id?: string;
  planId?: string;
  input_task?: string;
  inputTask?: string;
  raw_plan?: { tasks?: PlanTask[] };
  task_chain_text?: string;
}

export interface PlanDetailResponse {
  plan?: PlanInfo;
  snapshot?: { tasks?: PlanTask[] };
  task_chain_text?: string;
}

export interface CreatePlanResponse {
  plan_id?: string;
  planId?: string;
}

// ============================================================
// Run 相关类型
// ============================================================

export interface RunSummary {
  id?: string;
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  state?: string;
  updated_at?: string | number;
  updatedAt?: string | number;
  ts?: string | number;
  task?: string;
  input_task?: string;
  progress?: number;
  mode?: string;
  changed_files_count?: number;
  patchset_path?: string;
  workspace_main_root?: string;
  workspace_stage_root?: string;
  workspaceMainRoot?: string;
  workspaceStageRoot?: string;
}

export interface RunInfo {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  state?: string;
  task?: string;
  input_task?: string;
  updated_at?: string | number;
  updatedAt?: string | number;
  ts?: string | number;
  mode?: string;
  patchset_path?: string;
  changed_files_count?: number;
  workspace_main_root?: string;
  workspace_stage_root?: string;
}

export interface RunDetailResponse {
  run?: RunInfo;
}

export interface CreateRunResponse {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
}

export interface RetryOptions {
  fromStep?: string;
  resetAll?: boolean;
}

// ============================================================
// Event 相关类型
// ============================================================

export interface RunEvent {
  event_id?: number;
  ts?: number | string;
  time?: number | string;
  timestamp?: number | string;
  created_at?: number | string;
  type?: string;
  event?: string;
  name?: string;
  kind?: string;
  message?: string;
  detail?: string;
  summary?: string;
  task_title?: string;
  taskTitle?: string;
  title?: string;
  status?: string;
  level?: string;
  severity?: string;
  progress?: number;
  step?: string;
  step_id?: string;
  stepId?: string;
  step_total?: number;
  total_steps?: number;
  steps_total?: number;
  steps_done?: number;
  done_steps?: number;
  stepTotal?: number;
  stepsDone?: number;
  doneSteps?: number;
  round?: number | string;
  data?: unknown;
  payload?: unknown;
}

export interface RunEventsResponse {
  run_id?: string;
  cursor?: number;
  next_cursor?: number;
  cursor_type?: string;
  total?: number;
  events?: RunEvent[];
}

// ============================================================
// Artifact 相关类型
// ============================================================

export interface ArtifactItem {
  path: string;
  size: number;
  sha256: string;
  updated_at: number;
}

export interface ArtifactsResponse {
  plan_id?: string;
  run_id?: string;
  artifacts_root?: string;
  items?: ArtifactItem[];
  runs?: Array<{ run_id: string; run_dir: string }>;
}

// ============================================================
// Assistant 相关类型
// ============================================================

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface AssistantChatResponse {
  reply?: string;
  message?: string;
  [key: string]: unknown;
}

export interface AssistantPlanResponse {
  plan_id?: string;
  planId?: string;
  tasks_count?: number;
  [key: string]: unknown;
}

export interface AssistantConfirmResponse {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  [key: string]: unknown;
}

// ============================================================
// Workspace 相关类型
// ============================================================

export interface WorkspaceCheck {
  type?: string;
  cmd?: string;
  timeout?: number;
}

export interface WorkspaceCapabilities {
  project_type?: string;
  detected?: string[];
  commands?: Array<{ cmd?: string; kind?: string; timeout?: number }>;
}

export interface WorkspaceInfo {
  project_type?: string;
  allow_write?: string[];
  deny_write?: string[];
  checks?: WorkspaceCheck[];
  capabilities?: WorkspaceCapabilities;
}

// ============================================================
// Profile 相关类型
// ============================================================

export type ProfileData = Record<string, unknown>;

export interface ProfilePolicy {
  allow_write?: string[];
  deny_write?: string[];
  allowed_commands?: string[];
  command_timeout?: number;
  max_concurrency?: number;
}

// ============================================================
// Pack 相关类型
// ============================================================

export type PackRecord = Record<string, unknown>;
export type MemoryRecord = Record<string, unknown>;

export interface PackImportPayload {
  pack: PackRecord;
}

export interface PackExportPayload {
  name?: string;
  description?: string;
  includeRules?: boolean;
  includeChecks?: boolean;
  includeLessons?: boolean;
  includePatterns?: boolean;
}

// ============================================================
// Rule & Check 相关类型
// ============================================================

export interface WorkspaceRule {
  id: string;
  content: string;
  scope?: string;
  category?: string;
}

export interface WorkspaceCustomCheck {
  id: string;
  check: Record<string, unknown>;
  scope?: string;
}
