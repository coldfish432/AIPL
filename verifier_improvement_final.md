# Verifier 终版改进方案

> 整合本次会话所有讨论，涵盖：架构重构、核心逻辑修复、代码验证闭环、功能增强、安全改进

---

## 一、问题清单与优先级

| 优先级 | 类别 | 问题 | 位置 | 影响 |
|--------|------|------|------|------|
| 🔴 P0 | 架构 | 934行单文件难维护 | verifier_service.py | 可维护性差 |
| 🔴 P0 | 功能 | 无检查时自动失败 | 810-814行 | 正常任务被误判失败 |
| 🔴 P0 | 功能 | 执行检查双重绑定 | 879-881行 | 逻辑矛盾 |
| 🔴 P0 | 功能 | 代码修改后无强制验证 | - | 无法保证代码可运行 |
| 🟠 P1 | 监控 | 无检查耗时统计 | _run_checks | 无法定位性能问题 |
| 🟠 P1 | 安全 | shell=True 注入风险 | 175-184行 | 潜在安全漏洞 |
| 🟠 P1 | 稳定 | 命令输出无大小限制 | _run_command | 可能耗尽磁盘 |
| 🟠 P1 | 功能 | HTTP 不支持 Headers/Body | _handle_http_check | API 测试受限 |
| 🟡 P2 | 功能 | 只有通过/失败两态 | - | 缺少警告级别 |
| 🟡 P2 | 功能 | 不支持正则匹配 | - | 复杂内容检查不便 |
| 🟢 P3 | 功能 | Schema 验证不完整 | _validate_schema | 复杂 schema 不支持 |

---

## 二、架构重构：模块化拆分

### 2.1 目录结构

```
services/verifier/
├── __init__.py              # 模块导出
├── config.py                # 配置常量 (~180行)
├── types.py                 # 类型定义 (~150行)
├── utils.py                 # 工具函数 (~180行)
├── registry.py              # 检查注册器 (~60行)
├── runner.py                # 命令执行器 (~210行)
├── schema.py                # Schema 验证 (~330行)
├── context.py               # 任务上下文加载 (~210行)
├── error_collector.py       # 错误收集 (~280行)
├── checks/
│   ├── __init__.py          # 检查模块初始化
│   ├── base.py              # 基础检查函数 (~180行)
│   ├── file.py              # 文件检查 (~220行)
│   ├── command.py           # 命令检查 (~290行)
│   └── http.py              # HTTP 检查 (~230行)
└── service.py               # 主服务类 (~400行)
```

### 2.2 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| `config.py` | 所有配置常量，支持环境变量覆盖 | 无 |
| `types.py` | 类型定义：CheckResult, VerifyResult, ReworkRequest | 无 |
| `utils.py` | 通用工具：reason(), tail(), extract_key_error_lines() | 无 |
| `registry.py` | 检查处理器注册表，装饰器模式 | 无 |
| `runner.py` | 命令执行器，支持安全模式和 shell 模式 | config, utils |
| `schema.py` | JSON Schema 验证，支持 anyOf/oneOf/allOf | config, utils |
| `context.py` | 任务上下文加载：backlog, history, plan | utils |
| `error_collector.py` | 执行错误收集，修复指导生成 | config, types, utils |
| `checks/` | 各类检查处理器 | registry, utils, runner |
| `service.py` | 主服务类，编排验证流程 | 所有模块 |

---

## 三、核心逻辑修复

### 3.1 无检查时的行为（原810-814行）

**问题**：无检查项时直接返回失败，但很多任务本身就没有定义检查

**修复**：可配置行为

```python
# config.py
NO_CHECKS_BEHAVIOR = os.getenv("AIPL_NO_CHECKS_BEHAVIOR", "fail").lower()
# 可选值: fail / warn / pass

# service.py
if not effective_checks:
    if NO_CHECKS_BEHAVIOR == "fail":
        passed = False
        reasons = [reason("no_checks_defined", hint="未定义任何验证检查")]
    elif NO_CHECKS_BEHAVIOR == "warn":
        passed = True
        reasons = [reason("no_checks_warning", hint="未定义检查", severity="warning")]
    else:  # pass
        passed = True
        reasons = []
```

### 3.2 执行检查双重绑定（原879-881行）

**问题**：原逻辑 `if passed and not executed_any and has_execution_checks and not skipped_any` 存在矛盾

**修复**：重新设计验证执行要求函数

```python
def verify_execution_requirement(check_results, effective_checks, passed, reasons):
    """
    验证执行要求：代码修改后必须有命令执行且成功
    
    规则：
    1. 必须有执行类检查（command/http_check）
    2. 至少一个检查必须真正执行（executed=True）
    3. 执行的检查必须成功（ok=True）
    """
    if not REQUIRE_EXECUTION:
        return passed, reasons
    
    execution_checks = [c for c in effective_checks if c.get("type") in EXECUTION_CHECK_TYPES]
    execution_results = [c for c in check_results if c.get("type") in EXECUTION_CHECK_TYPES]
    
    # 规则1：必须有执行类检查
    if not execution_checks:
        if NO_CHECKS_BEHAVIOR == "fail":
            return False, reasons + [reason("no_execution_check_defined")]
        return passed, reasons
    
    # 统计执行情况
    executed_results = [c for c in execution_results if c.get("executed") is True]
    skipped_results = [c for c in execution_results if c.get("status") == "skipped"]
    
    # 规则2：必须有真正执行的检查
    if not executed_results:
        # 特殊处理：测试被禁用时可配置允许
        tests_disabled_count = sum(1 for r in skipped_results if r.get("skip_reason") == "tests_disabled")
        if ALLOW_SKIP_TESTS and tests_disabled_count == len(skipped_results):
            return passed, reasons + [reason("tests_skipped_allowed", severity="info")]
        
        return False, reasons + [reason("no_command_executed", skipped_commands=[...])]
    
    # 规则3：执行成功（已在 run_checks 中处理）
    return passed, reasons
```

---

## 四、代码验证闭环：修改代码后必须验证+失败重试

### 4.1 工作流程

```
LLM 生成代码 → 写入文件 → 运行验证命令(pytest/npm test)
                                    ↓
                         ┌─────────┴─────────┐
                         ↓                   ↓
                       成功 ✓              失败 ✗
                         │                   │
                         │          收集详细错误信息
                         │          (stdout/stderr/关键错误行)
                         │                   │
                         │          生成 rework_request.json
                         │          {
                         │            "error_summary": "SyntaxError at line 15",
                         │            "fix_guidance": "请修复语法错误...",
                         │            "remaining_attempts": 2
                         │          }
                         │                   │
                         │          下一轮 LLM 读取错误 → 修复代码
                         │                   │
                         │          最多重试 3 次
                         ↓                   ↓
                       完成               最终失败
```

### 4.2 错误收集器

```python
# error_collector.py

def collect_execution_errors(check_results: list[dict], log_dir: Path) -> ExecutionErrors:
    """收集命令执行的详细错误信息"""
    errors = ExecutionErrors()
    
    for result in check_results:
        if result.get("type") not in EXECUTION_CHECK_TYPES:
            continue
        if result.get("ok") is True:
            continue
        
        errors.has_errors = True
        idx = result.get("index", 0)
        
        # 读取完整输出日志
        stdout = (log_dir / f"cmd-{idx}.stdout.txt").read_text(errors="replace")
        stderr = (log_dir / f"cmd-{idx}.stderr.txt").read_text(errors="replace")
        
        # 提取关键错误行
        key_errors = extract_key_error_lines(stderr + "\n" + stdout)
        
        errors.failed_commands.append(ExecutionError(
            cmd=result.get("cmd"),
            exit_code=result.get("exit_code"),
            status=result.get("status"),
            stdout=stdout[-3000:],
            stderr=stderr[-3000:],
            key_errors=key_errors,
        ))
    
    # 生成错误摘要
    errors.error_summary = _build_error_summary(errors.failed_commands)
    
    return errors


def extract_key_error_lines(output: str, max_lines: int = 30) -> str:
    """提取关键错误行"""
    keywords = [
        "error:", "Error:", "ERROR:",
        "failed", "Failed", "FAILED",
        "Traceback", "SyntaxError", "TypeError", "ValueError",
        "AssertionError", "ImportError", "ModuleNotFoundError",
        "cannot find", "not found", "undefined",
    ]
    
    lines = output.split("\n")
    key_lines = []
    
    for line in lines:
        if any(kw in line for kw in keywords):
            key_lines.append(line)
    
    return "\n".join(key_lines[:max_lines])


def generate_fix_guidance(reasons: list[dict], errors: ExecutionErrors) -> str:
    """生成修复指导"""
    guidance = []
    
    if errors.has_errors:
        guidance.append("## 代码执行失败")
        guidance.append("")
        guidance.append("请分析以下错误信息并修复代码：")
        guidance.append("")
        guidance.append("```")
        guidance.append(errors.error_summary[:2000])
        guidance.append("```")
        guidance.append("")
        guidance.append("### 修复建议")
        guidance.append("1. 检查语法错误")
        guidance.append("2. 确保变量/函数名正确")
        guidance.append("3. 验证导入的模块存在")
        guidance.append("4. 检查函数参数类型和数量")
    
    return "\n".join(guidance)
```

### 4.3 ReworkRequest 数据结构

```python
@dataclass
class ReworkRequest:
    round: int
    remaining_attempts: int
    why_failed: list[dict]
    execution_errors: ExecutionErrors
    error_summary: str
    fix_guidance: str
    prev_stdout: str
    code_modified: bool
    produced_files: list[str]
    workspace: str
    suspected_related_files: list[str]
    
    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "remaining_attempts": self.remaining_attempts,
            "why_failed": self.why_failed,
            "error_summary": self.error_summary,
            "fix_guidance": self.fix_guidance,
            "execution_errors": {...},
            "next_round_should_do": "根据错误信息修复代码，确保能够正常运行。",
            ...
        }
```

### 4.4 在 controller_service.py 中使用

```python
# controller_service.py 约 508-548 行

if passed:
    break

# 失败且还有重试机会
if round_id < max_rounds - 1:
    rework = verifier.collect_errors_for_retry(
        run_dir=run_dir,
        round_id=round_id,
        max_rounds=max_rounds,
        reasons=reasons,
        produced_files=shape.get("produced", []),
        workspace_path=workspace_path,
        prev_stdout=stdout_txt,
        suspected_related_files=suspected_related_files,
    )
    write_json(round_dir / "rework_request.json", rework.to_dict())
```

---

## 五、功能增强

### 5.1 检查耗时统计

```python
def run_checks(effective_checks, run_dir, workspace, retry_context):
    total_start = time.time()
    check_results = []
    
    for idx, check in enumerate(effective_checks):
        check_start = time.time()
        
        # 执行检查...
        ok, reason, info = handler(check, ...)
        
        duration_ms = int((time.time() - check_start) * 1000)
        
        record = {
            "index": idx,
            "type": check.get("type"),
            "ok": ok,
            "duration_ms": duration_ms,  # 新增
            ...
        }
        check_results.append(record)
    
    total_duration_ms = int((time.time() - total_start) * 1000)
    return passed, reasons, check_results, total_duration_ms
```

### 5.2 命令输出大小限制

```python
# config.py
MAX_OUTPUT_BYTES = _env_int("AIPL_MAX_OUTPUT_BYTES", 10 * 1024 * 1024)  # 10MB

# runner.py
def _truncate(self, text: str) -> str:
    if len(text) <= MAX_OUTPUT_BYTES:
        return text
    half = MAX_OUTPUT_BYTES // 2
    return text[:half] + "\n...[truncated]...\n" + text[-half:]
```

### 5.3 安全的命令执行

```python
# runner.py
class SubprocessRunner(CommandRunner):
    def __init__(self, allow_shell: bool = False):
        self.allow_shell = allow_shell
    
    def run(self, cmd: str, cwd: Path, timeout: int) -> dict:
        if self.allow_shell:
            return self._run_shell(cmd, cwd, timeout)
        return self._run_safe(cmd, cwd, timeout)
    
    def _run_safe(self, cmd: str, cwd: Path, timeout: int) -> dict:
        """安全模式：不使用 shell"""
        try:
            cmd_parts = shlex.split(cmd)
        except ValueError as e:
            return {"executed": False, "stderr": f"Invalid command: {e}"}
        
        result = subprocess.run(
            cmd_parts,
            cwd=cwd,
            shell=False,  # 安全
            timeout=timeout,
            capture_output=True,
            ...
        )
        return {...}
```

### 5.4 HTTP 检查增强

```python
@register_check("http_check")
def handle_http_check(check, run_dir, workspace, log_dir, idx):
    url = check.get("url")
    method = check.get("method", "GET")
    headers = check.get("headers", {})  # 新增：自定义请求头
    body = check.get("body")  # 新增：请求体
    retry = check.get("retry", 3)  # 新增：重试次数
    
    # 构建请求
    req = Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    
    # 请求体处理
    data = None
    if body:
        if isinstance(body, dict):
            data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        else:
            data = str(body).encode()
    
    # 带重试的请求
    status, resp_body, error = http_request_with_retry(req, data, timeout, retry)
    ...

# 使用示例
{
    "type": "http_check",
    "url": "http://localhost:8080/api/health",
    "method": "POST",
    "headers": {"Authorization": "Bearer token123"},
    "body": {"action": "check"},
    "expected_status": 200,
    "json_contains": {"status": "ok"},
    "retry": 3
}
```

### 5.5 三态检查结果（警告）

```python
# 配置软失败
{
    "type": "file_contains",
    "path": "README.md",
    "needle": "## Installation",
    "soft": true  # 失败只产生警告，不影响整体结果
}

# 处理逻辑
is_soft = check.get("soft", False)
if not ok and reason:
    if is_soft:
        reason["severity"] = "warning"
        # 不影响 passed
    else:
        reasons.append(reason)
        passed = False
```

### 5.6 正则匹配文件内容

```python
@register_check("file_matches")
def handle_file_matches(check, run_dir, workspace, log_dir, idx):
    path = check.get("path")
    pattern = check.get("pattern")
    flags = 0
    if check.get("ignore_case"):
        flags |= re.IGNORECASE
    if check.get("multiline"):
        flags |= re.MULTILINE
    
    text = target.read_text()
    match = re.search(pattern, text, flags)
    
    if not match:
        return False, reason("pattern_not_found", pattern=pattern), info
    
    return True, None, {"match": match.group(0)[:200]}

# 使用示例
{
    "type": "file_matches",
    "path": "src/version.py",
    "pattern": "VERSION\\s*=\\s*['\"]\\d+\\.\\d+\\.\\d+['\"]",
    "ignore_case": true
}
```

### 5.7 Schema 验证增强

```python
def validate_schema(data, schema, path=""):
    # 支持 anyOf
    any_of = schema.get("anyOf")
    if any_of:
        for sub in any_of:
            if validate_schema(data, sub, path)[0]:
                return True, None
        return False, f"{path}: no schema matched"
    
    # 支持 oneOf
    one_of = schema.get("oneOf")
    if one_of:
        matches = sum(1 for s in one_of if validate_schema(data, s, path)[0])
        if matches != 1:
            return False, f"{path}: exactly one should match"
        return True, None
    
    # 支持 allOf
    all_of = schema.get("allOf")
    if all_of:
        for sub in all_of:
            ok, err = validate_schema(data, sub, path)
            if not ok:
                return False, err
        return True, None
    
    # 原有逻辑...
```

---

## 六、配置参数汇总

```bash
# ===== 验证执行策略 =====
AIPL_REQUIRE_EXECUTION=true           # 代码修改后必须执行验证
AIPL_ALLOW_SKIP_TESTS=false           # 是否允许跳过测试
AIPL_NO_CHECKS_BEHAVIOR=fail          # 无检查时行为: fail/warn/pass
AIPL_MAX_RETRY_ROUNDS=3               # 最大重试次数

# ===== 命令执行 =====
AIPL_ALLOW_SHELL_COMMANDS=true        # 是否允许 shell 模式（向后兼容）
AIPL_COMMAND_TIMEOUT=300              # 默认命令超时(秒)
AIPL_BUILD_TIMEOUT=900                # 构建超时
AIPL_TEST_TIMEOUT=600                 # 测试超时
AIPL_MAX_OUTPUT_BYTES=10485760        # 输出最大字节数(10MB)

# ===== 命令白名单 =====
AIPL_ALLOWED_COMMANDS=python,python3,pytest,npm,node,npx,mvn,gradle,go,cargo

# ===== HTTP 检查 =====
AIPL_HTTP_TIMEOUT=30                  # HTTP 默认超时
AIPL_HTTP_RETRIES=3                   # HTTP 重试次数
AIPL_HTTP_SOFT_FAIL=false             # HTTP 失败是否软处理

# ===== 风险评估 =====
AIPL_HIGH_RISK_THRESHOLD=7            # 高风险阈值
AIPL_HIGH_RISK_LABELS=high,critical   # 高风险标签

# ===== 测试控制 =====
AIPL_DISABLE_TESTS=false              # 禁用测试
AIPL_ALLOW_TESTS=false                # 强制允许测试
```

---

## 七、API 使用示例

### 7.1 基本使用

```python
from services.verifier import VerifierService

# 创建实例
verifier = VerifierService(root_path)

# 验证任务
passed, reasons = verifier.verify_task(
    run_dir=run_dir,
    task_id="task-001",
    workspace_path=workspace
)

if passed:
    print("验证通过")
else:
    print("验证失败:", reasons)
```

### 7.2 收集错误用于重试

```python
if not passed:
    rework = verifier.collect_errors_for_retry(
        run_dir=run_dir,
        round_id=0,
        max_rounds=3,
        reasons=reasons,
        produced_files=["src/main.py"],
        workspace_path=str(workspace),
        prev_stdout="...",
    )
    
    # 保存供下一轮 LLM 读取
    with open(round_dir / "rework_request.json", "w") as f:
        json.dump(rework.to_dict(), f, ensure_ascii=False, indent=2)
```

### 7.3 自定义检查处理器

```python
from services.verifier import register_check

@register_check("my_custom_check")
def handle_my_check(check, run_dir, workspace, log_dir, idx):
    # 实现自定义检查逻辑
    target = check.get("target")
    
    # 执行检查
    ok = some_validation(target)
    
    if not ok:
        return False, {"type": "custom_check_failed", "target": target}, {"executed": True}
    
    return True, None, {"executed": True, "target": target}
```

---

## 八、迁移指南

### 8.1 API 变化

```python
# 旧 API
from services.verifier_service import verify_task
passed, reasons = verify_task(root, run_dir, task_id, workspace)

# 新 API
from services.verifier import VerifierService
verifier = VerifierService(root)
passed, reasons = verifier.verify_task(run_dir, task_id, workspace)
```

### 8.2 向后兼容层

如需保持旧 API，创建 `services/verifier_service.py`：

```python
"""向后兼容层"""
from .verifier import VerifierService, set_command_runner

_service = None

def verify_task(root, run_dir, task_id, workspace_path=None):
    global _service
    if _service is None or _service.root != root:
        _service = VerifierService(root)
    return _service.verify_task(run_dir, task_id, workspace_path)
```

### 8.3 迁移步骤

1. 备份原文件：`cp services/verifier_service.py services/verifier_service.py.bak`
2. 创建新目录：`mkdir -p services/verifier/checks`
3. 复制新模块文件
4. 全局搜索替换导入语句
5. 更新调用方式为面向对象
6. 测试验证
7. 删除旧文件（可选）

---

## 九、检查类型速查

| 类型 | 说明 | 关键参数 |
|------|------|----------|
| `file_exists` | 文件存在检查 | `path` |
| `file_contains` | 文件内容包含 | `path`, `needle` |
| `file_matches` | 文件内容正则匹配 | `path`, `pattern`, `flags` |
| `file_check` | 综合文件检查 | `path`, `min_size`, `max_size`, `contains`, `not_contains` |
| `json_schema` | JSON Schema 验证 | `path`, `schema` 或 `schema_path` |
| `command` | 命令执行 | `cmd`, `timeout`, `expect_exit_code`, `cwd` |
| `command_contains` | 命令输出包含 | `cmd`, `needle`, `search_in` |
| `http_check` | HTTP 请求检查 | `url`, `method`, `headers`, `body`, `expected_status`, `json_contains` |

---

## 十、总结

本方案通过以下改进全面提升 verifier 的质量：

1. **架构重构**：934行单文件拆分为13个模块，职责清晰，易于维护和测试
2. **核心修复**：解决无检查行为、执行检查双重绑定等逻辑问题
3. **验证闭环**：代码修改后必须验证，失败自动收集错误反馈 LLM 重试
4. **功能增强**：耗时统计、输出限制、HTTP 增强、正则匹配、三态结果
5. **安全改进**：可配置的安全命令执行模式
6. **可配置性**：所有行为均可通过环境变量配置

文件总行数：约 3000 行（含完整注释和文档字符串），相比原 934 行增加了大量功能。
