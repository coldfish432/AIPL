import { RunEvent } from "../apiClient";

export type StreamState = "connecting" | "connected" | "disconnected";

type EventPayload = Record<string, unknown>;

export function formatTimestamp(value: unknown) {
  if (!value) return "";
  if (typeof value === "number") {
    const dt = new Date(value);
    return Number.isNaN(dt.getTime()) ? "" : dt.toLocaleString();
  }
  if (typeof value === "string") {
    const dt = new Date(value);
    return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString();
  }
  return "";
}

export function formatEventType(evt: RunEvent) {
  return evt.type || evt.event || evt.name || evt.kind || "event";
}

/**
 * 事件类型到 [前缀] 的映射
 */
const EVENT_TYPE_LABELS: Record<string, string> = {
  // 运行生命周期
  run_init: "初始化",
  run_start: "开始",
  run_done: "完成",
  run_fail: "失败",
  run_failed: "失败",
  
  // 工作区
  workspace_stage_ready: "工作区",
  workspace_ready: "工作区",
  workspace_init: "工作区",
  
  // 步骤
  step_start: "步骤",
  step_done: "步骤",
  step_fail: "步骤",
  step_failed: "步骤",
  step_round_start: "轮次",
  step_round_done: "轮次",
  step_round_verified: "验证",
  
  // 子代理/Codex
  subagent_start: "代理",
  subagent_done: "代理",
  codex_start: "生成",
  codex_done: "生成",
  codex_timeout: "超时",
  codex_failed: "失败",
  
  // 文件操作
  file_read: "读取",
  file_write: "写入",
  file_create: "创建",
  file_delete: "删除",
  file_patch: "修补",
  
  // 命令执行
  command_start: "命令",
  command_done: "命令",
  cmd_start: "命令",
  cmd_done: "命令",
  
  // 搜索
  search_start: "搜索",
  search_done: "搜索",
  grep_start: "搜索",
  grep_done: "搜索",
  
  // 思考/规划
  thinking: "思考",
  planning: "规划",
  analyzing: "分析",
  
  // 验证
  verification_start: "验证",
  verification_done: "验证",
  check_start: "检查",
  check_done: "检查",
  
  // 补丁/审核
  patchset_ready: "补丁",
  awaiting_review: "审核",
  apply_start: "应用",
  apply_done: "应用",
  discard_done: "丢弃",
  
  // 返工
  rework_start: "返工",
  rework_done: "返工",
  
  // 状态
  status_transition: "状态",
  state_change: "状态",
  
  // 错误/警告
  error: "错误",
  warning: "警告",
  warn: "警告",
};

/**
 * 获取事件类型的显示标签 [xxx]
 */
export function getEventTypeLabel(evt: RunEvent): string {
  const type = formatEventType(evt).toLowerCase();
  return EVENT_TYPE_LABELS[type] || "事件";
}

/**
 * 生成人类可读的步骤摘要
 * 这是核心函数，覆盖模型运行中的每一步
 */
export function formatStepSummary(evt: RunEvent): string {
  const type = formatEventType(evt).toLowerCase();
  const data = (evt.data ?? evt.payload ?? {}) as Record<string, unknown>;
  
  // 优先使用事件自带的 summary
  if (typeof evt.summary === "string" && evt.summary.trim()) {
    return evt.summary;
  }
  
  // 根据事件类型生成摘要
  switch (type) {
    // ========== 运行生命周期 ==========
    case "run_init": {
      const workspace = (evt as Record<string, unknown>).workspace;
      if (workspace) {
        const wsPath = String(workspace);
        const shortPath = wsPath.length > 40 ? "..." + wsPath.slice(-37) : wsPath;
        return `初始化运行环境: ${shortPath}`;
      }
      return "初始化运行环境";
    }
    
    case "run_start":
      return "开始执行任务";
    
    case "run_done": {
      const passed = (evt as Record<string, unknown>).passed;
      const status = (evt as Record<string, unknown>).status || "";
      if (passed === true) return "执行成功完成";
      if (passed === false) return `执行结束: ${status || "失败"}`;
      return "执行完成";
    }
    
    case "run_fail":
    case "run_failed": {
      const reason = evt.message || evt.detail || "";
      return reason ? `执行失败: ${truncate(reason, 50)}` : "执行失败";
    }
    
    // ========== 工作区 ==========
    case "workspace_stage_ready": {
      const stageRoot = (evt as Record<string, unknown>).stage_root;
      if (stageRoot) {
        return `Stage 工作区就绪`;
      }
      return "工作区准备就绪";
    }
    
    case "workspace_ready":
    case "workspace_init":
      return "工作区初始化完成";
    
    // ========== 步骤执行 ==========
    case "step_start": {
      const stepId = getEventStepId(evt);
      const taskId = (evt as Record<string, unknown>).task_id;
      if (taskId) {
        return `开始步骤 ${stepId || ""}: ${truncate(String(taskId), 40)}`;
      }
      return `开始执行步骤 ${stepId || ""}`;
    }
    
    case "step_done": {
      const stepId = getEventStepId(evt);
      return `步骤 ${stepId || ""} 执行完成`;
    }
    
    case "step_fail":
    case "step_failed": {
      const stepId = getEventStepId(evt);
      return `步骤 ${stepId || ""} 执行失败`;
    }
    
    case "step_round_start": {
      const round = (evt as Record<string, unknown>).round;
      const mode = (evt as Record<string, unknown>).mode;
      const roundNum = typeof round === "number" ? round + 1 : 1;
      if (roundNum === 1) {
        return "首次尝试执行";
      }
      return `第 ${roundNum} 轮重试${mode === "good" ? "" : ` (${mode})`}`;
    }
    
    case "step_round_done": {
      const round = (evt as Record<string, unknown>).round;
      const roundNum = typeof round === "number" ? round + 1 : 1;
      return `第 ${roundNum} 轮执行完成`;
    }
    
    case "step_round_verified": {
      const passed = (evt as Record<string, unknown>).passed;
      const round = (evt as Record<string, unknown>).round;
      const roundNum = typeof round === "number" ? round + 1 : 1;
      if (passed === true) {
        return `第 ${roundNum} 轮验证通过`;
      }
      return `第 ${roundNum} 轮验证未通过，准备重试`;
    }
    
    // ========== 子代理/Codex ==========
    case "subagent_start": {
      const mode = (evt as Record<string, unknown>).mode;
      return mode === "good" ? "启动代码生成代理" : `启动代理 (${mode} 模式)`;
    }
    
    case "subagent_done": {
      const mode = (evt as Record<string, unknown>).mode;
      return "代理执行完成，已生成代码变更";
    }
    
    case "codex_start":
      return "正在调用 Codex 生成代码方案...";
    
    case "codex_done":
      return "Codex 响应完成，解析执行计划";
    
    case "codex_timeout":
      return "Codex 调用超时";
    
    case "codex_failed": {
      const reason = evt.message || evt.detail || "";
      return reason ? `Codex 调用失败: ${truncate(reason, 40)}` : "Codex 调用失败";
    }
    
    // ========== 文件操作 ==========
    case "file_read": {
      const path = data.path || data.file || "";
      const filename = getFilename(String(path));
      return `读取文件: ${filename}`;
    }
    
    case "file_write":
    case "file_create": {
      const path = data.path || data.file || "";
      const filename = getFilename(String(path));
      return `写入文件: ${filename}`;
    }
    
    case "file_delete": {
      const path = data.path || data.file || "";
      const filename = getFilename(String(path));
      return `删除文件: ${filename}`;
    }
    
    case "file_patch": {
      const path = data.path || data.file || "";
      const filename = getFilename(String(path));
      return `修补文件: ${filename}`;
    }
    
    // ========== 命令执行 ==========
    case "command_start":
    case "cmd_start": {
      const cmd = data.command || data.cmd || evt.message || "";
      const cmdStr = String(cmd);
      return `执行命令: ${describeCommand(cmdStr)}`;
    }
    
    case "command_done":
    case "cmd_done": {
      const success = data.success !== false && data.returncode === 0;
      const cmd = data.command || data.cmd || "";
      if (success) {
        return "命令执行成功";
      }
      const rc = data.returncode ?? data.return_code ?? "";
      return `命令执行失败 (退出码: ${rc})`;
    }
    
    // ========== 搜索 ==========
    case "search_start":
    case "grep_start": {
      const query = data.query || data.pattern || data.needle || "";
      const queryStr = String(query);
      return `搜索: "${truncate(queryStr, 30)}"`;
    }
    
    case "search_done":
    case "grep_done": {
      const count = data.count || data.matches || data.results;
      if (typeof count === "number") {
        return `搜索完成，找到 ${count} 处匹配`;
      }
      return "搜索完成";
    }
    
    // ========== 思考/规划 ==========
    case "thinking": {
      const thought = evt.message || evt.detail || "";
      return thought ? truncate(thought, 60) : "正在思考...";
    }
    
    case "planning": {
      const plan = evt.message || evt.detail || "";
      return plan ? `规划: ${truncate(plan, 50)}` : "正在规划执行方案...";
    }
    
    case "analyzing":
      return evt.message || "正在分析代码...";
    
    // ========== 验证 ==========
    case "verification_start":
    case "check_start": {
      const checkCount = data.check_count || data.checks;
      if (typeof checkCount === "number") {
        return `开始验证 (${checkCount} 项检查)`;
      }
      return "开始验证执行结果...";
    }
    
    case "verification_done":
    case "check_done": {
      const passed = data.passed;
      const failedCount = data.failed_count || data.failures;
      if (passed === true) {
        return "所有检查项验证通过";
      }
      if (typeof failedCount === "number") {
        return `验证完成，${failedCount} 项未通过`;
      }
      return passed === false ? "验证未通过" : "验证完成";
    }
    
    // ========== 补丁/审核 ==========
    case "patchset_ready": {
      const changedFiles = (evt as Record<string, unknown>).changed_files;
      const count = typeof changedFiles === "number" ? changedFiles : 0;
      return `补丁集生成完成 (${count} 个文件变更)`;
    }
    
    case "awaiting_review":
      return "等待人工审核确认";
    
    case "apply_start":
      return "正在应用代码变更到主工作区...";
    
    case "apply_done":
      return "代码变更已成功应用";
    
    case "discard_done":
      return "变更已丢弃";
    
    // ========== 返工 ==========
    case "rework_start": {
      const round = (evt as Record<string, unknown>).round;
      const roundNum = typeof round === "number" ? round + 1 : "";
      return `开始返工修复${roundNum ? ` (第 ${roundNum} 轮)` : ""}`;
    }
    
    case "rework_done": {
      const passed = (evt as Record<string, unknown>).passed;
      return passed ? "返工修复成功" : "返工修复未通过";
    }
    
    // ========== 状态变更 ==========
    case "status_transition":
    case "state_change": {
      const from = data.from || data.old_status || "";
      const to = data.to || data.new_status || data.status || "";
      if (from && to) {
        return `状态变更: ${from} → ${to}`;
      }
      return `状态更新: ${to || "unknown"}`;
    }
    
    // ========== 错误/警告 ==========
    case "error": {
      const msg = evt.message || evt.detail || "";
      return msg ? `错误: ${truncate(msg, 50)}` : "发生错误";
    }
    
    case "warning":
    case "warn": {
      const msg = evt.message || evt.detail || "";
      return msg ? `警告: ${truncate(msg, 50)}` : "警告";
    }
    
    // ========== 默认处理 ==========
    default:
      return formatEventMessage(evt);
  }
}

/**
 * 原始的消息格式化（作为 fallback）
 */
export function formatEventMessage(evt: RunEvent) {
  if (typeof evt.message === "string" && evt.message.trim()) return evt.message;
  if (typeof evt.detail === "string" && evt.detail.trim()) return evt.detail;
  if (typeof evt.summary === "string" && evt.summary.trim()) return evt.summary;
  const payload = evt.data ?? evt.payload;
  if (payload !== undefined) {
    return typeof payload === "string" ? payload : JSON.stringify(payload);
  }
  if (evt.status || typeof evt.progress === "number") {
    return JSON.stringify({ status: evt.status, progress: evt.progress });
  }
  return JSON.stringify(evt);
}

export function extractEvents(payload: unknown): RunEvent[] {
  if (!payload || typeof payload !== "object") return [];
  const record = payload as EventPayload;
  const data = record.data;
  if (data && typeof data === "object") {
    const events = (data as EventPayload).events;
    if (Array.isArray(events)) return events as RunEvent[];
  }
  if (Array.isArray(record.events)) return record.events as RunEvent[];
  return [];
}

export function getEventKey(evt: RunEvent): string {
  if (typeof evt.event_id === "number") return `event-${evt.event_id}`;
  const stepId = getEventStepId(evt) || "";
  const ts = evt.ts ?? evt.time ?? evt.timestamp ?? evt.created_at ?? "";
  const type = formatEventType(evt);
  const message = evt.message ?? evt.detail ?? evt.summary ?? "";
  const base = `${ts}|${type}|${stepId}|${message}`;
  let hash = 0;
  for (let i = 0; i < base.length; i += 1) {
    hash = (hash << 5) - hash + base.charCodeAt(i);
    hash |= 0;
  }
  return `h-${Math.abs(hash)}`;
}

export function getEventStepId(evt: RunEvent): string | null {
  const stepId = evt.step_id ?? evt.stepId ?? evt.step;
  if (typeof stepId === "string" && stepId.trim()) return stepId;
  if (typeof stepId === "number") return String(stepId);
  return null;
}

export function getEventLevel(evt: RunEvent): "error" | "warning" | null {
  const level = String(evt.level || evt.severity || "").toLowerCase();
  if (level === "error" || level === "fatal") return "error";
  if (level === "warn" || level === "warning") return "warning";
  const type = formatEventType(evt).toLowerCase();
  if (type === "run_fail" || type === "run_failed" || type === "codex_failed" || type === "codex_timeout") return "error";
  if (type === "step_fail" || type === "step_failed") return "error";
  return null;
}

// ========== 辅助函数 ==========

/**
 * 截断字符串
 */
function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen - 3) + "...";
}

/**
 * 获取文件名
 */
function getFilename(path: string): string {
  if (!path) return "";
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

/**
 * 描述命令（生成友好的命令描述）
 */
function describeCommand(cmd: string): string {
  if (!cmd) return "";
  
  const parts = cmd.trim().split(/\s+/);
  if (parts.length === 0) return cmd;
  
  const cmdName = parts[0];
  
  // 常见命令的友好描述
  const descriptions: Record<string, () => string> = {
    rg: () => {
      const pattern = parts.find((p, i) => i > 0 && !p.startsWith("-"));
      return pattern ? `rg 搜索 "${truncate(pattern, 20)}"` : "rg 搜索";
    },
    grep: () => {
      const pattern = parts.find((p, i) => i > 0 && !p.startsWith("-"));
      return pattern ? `grep 搜索 "${truncate(pattern, 20)}"` : "grep 搜索";
    },
    cat: () => {
      const file = parts[parts.length - 1];
      return file && !file.startsWith("-") ? `cat ${getFilename(file)}` : "cat";
    },
    head: () => {
      const file = parts[parts.length - 1];
      return file && !file.startsWith("-") ? `head ${getFilename(file)}` : "head";
    },
    tail: () => {
      const file = parts[parts.length - 1];
      return file && !file.startsWith("-") ? `tail ${getFilename(file)}` : "tail";
    },
    ls: () => "ls 列出目录",
    find: () => {
      const nameIdx = parts.indexOf("-name");
      if (nameIdx !== -1 && parts[nameIdx + 1]) {
        return `find 查找 "${parts[nameIdx + 1]}"`;
      }
      return "find 查找文件";
    },
    npm: () => {
      if (parts[1] === "install" || parts[1] === "i") return "npm install 安装依赖";
      if (parts[1] === "run") return `npm run ${parts[2] || ""}`;
      if (parts[1] === "test") return "npm test 运行测试";
      if (parts[1] === "build") return "npm build 构建";
      return `npm ${parts[1] || ""}`;
    },
    yarn: () => {
      if (parts[1] === "add") return "yarn add 安装依赖";
      if (parts[1] === "test") return "yarn test 运行测试";
      if (parts[1] === "build") return "yarn build 构建";
      return `yarn ${parts[1] || ""}`;
    },
    pip: () => {
      if (parts[1] === "install") return `pip install ${parts[2] || ""}`;
      return `pip ${parts[1] || ""}`;
    },
    python: () => {
      const script = parts.find((p, i) => i > 0 && p.endsWith(".py"));
      return script ? `python ${getFilename(script)}` : "python";
    },
    node: () => {
      const script = parts.find((p, i) => i > 0 && (p.endsWith(".js") || p.endsWith(".ts")));
      return script ? `node ${getFilename(script)}` : "node";
    },
    git: () => {
      const subCmd = parts[1] || "";
      const gitDescs: Record<string, string> = {
        status: "git status 检查状态",
        diff: "git diff 查看差异",
        log: "git log 查看日志",
        add: "git add 暂存变更",
        commit: "git commit 提交",
        push: "git push 推送",
        pull: "git pull 拉取",
        checkout: "git checkout 切换",
        branch: "git branch 分支",
      };
      return gitDescs[subCmd] || `git ${subCmd}`;
    },
    cd: () => parts[1] ? `cd ${truncate(parts[1], 30)}` : "cd",
    mkdir: () => parts[parts.length - 1] ? `mkdir ${getFilename(parts[parts.length - 1])}` : "mkdir",
    rm: () => "rm 删除",
    cp: () => "cp 复制",
    mv: () => "mv 移动",
    touch: () => parts[1] ? `touch ${getFilename(parts[1])}` : "touch",
    echo: () => "echo 输出",
    sed: () => "sed 替换",
    awk: () => "awk 处理",
    curl: () => "curl 请求",
    wget: () => "wget 下载",
  };
  
  if (descriptions[cmdName]) {
    return descriptions[cmdName]();
  }
  
  // 默认：截断显示
  return truncate(cmd, 40);
}
