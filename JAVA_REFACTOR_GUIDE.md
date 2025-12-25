# Java Server 层 & UI 层解耦重构方案

## 一、当前问题诊断

### 1.1 Java Server 层问题

| 模块 | 问题 | 严重程度 |
|------|------|----------|
| `RunController` | 控制器包含数据库访问逻辑（listPlansFromDb/listRunsFromDb） | 高 |
| `RunController` | 直接使用 JDBC，未分离 Repository 层 | 高 |
| `RunController` | 单个控制器承担 Plan/Run/Job 三类 API | 中 |
| `EngineClient` | 命令构建逻辑重复，缺乏抽象 | 中 |
| `JobService` | 混合数据访问、业务逻辑、后台调度 | 高 |
| 全局 | 缺乏 Service 层，Controller 直接调用底层组件 | 高 |
| 全局 | 使用 JsonNode 作为 DTO，类型不安全 | 中 |
| 全局 | 异常处理不统一，throws Exception 泛滥 | 中 |

### 1.2 UI 层问题

| 模块 | 问题 | 严重程度 |
|------|------|----------|
| `backend.ts` | 硬编码端口号 18088 | 低 |
| `main.ts` | 配置分散，缺乏统一配置管理 | 低 |
| 全局 | 缺乏 API 客户端抽象层 | 中 |

---

## 二、目标架构

### 2.1 Java Server 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    Controller Layer                      │
│  PlanController / RunController / JobController          │
│  (仅负责 HTTP 请求/响应处理)                              │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    Service Layer                         │
│  PlanService / RunService / JobService                   │
│  (业务逻辑编排)                                          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   Repository Layer                       │
│  PlanRepository / RunRepository / JobRepository          │
│  (数据访问抽象)                                          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                 Infrastructure Layer                     │
│  EngineClient / DatabaseConfig / ExceptionHandler        │
│  (底层基础设施)                                          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 新目录结构

```
com.aipl.platform/
├── PlatformApplication.java
├── api/                          # Controller 层
│   ├── controller/
│   │   ├── PlanController.java
│   │   ├── RunController.java
│   │   ├── JobController.java
│   │   └── ProfileController.java
│   ├── dto/                      # 数据传输对象
│   │   ├── request/
│   │   │   ├── PlanRequest.java
│   │   │   ├── RunRequest.java
│   │   │   └── JobRequest.java
│   │   └── response/
│   │       ├── ApiResponse.java
│   │       ├── PlanDTO.java
│   │       ├── RunDTO.java
│   │       └── JobDTO.java
│   └── exception/
│       ├── GlobalExceptionHandler.java
│       └── BusinessException.java
├── service/                      # Service 层
│   ├── PlanService.java
│   ├── RunService.java
│   ├── JobService.java
│   └── ProfileService.java
├── repository/                   # Repository 层
│   ├── PlanRepository.java
│   ├── RunRepository.java
│   └── JobRepository.java
├── domain/                       # 领域模型
│   ├── Plan.java
│   ├── Run.java
│   └── Job.java
├── engine/                       # 引擎集成
│   ├── EngineClient.java
│   ├── EngineCommand.java
│   └── EngineCommandBuilder.java
├── config/                       # 配置
│   ├── AppConfig.java
│   ├── DatabaseConfig.java
│   └── SecurityConfig.java
└── infra/                        # 基础设施
    ├── scheduling/
    │   └── JobScheduler.java
    └── util/
        └── JsonUtils.java
```

---

## 三、核心重构代码

所有代码已生成在对应目录中，以下是关键变更说明。

### 3.1 领域模型定义

**新增文件**: `domain/Run.java`, `domain/Job.java`

- 使用 Builder 模式创建对象
- 状态枚举内置状态判断方法
- 与数据库表解耦

```java
// 使用示例
Job job = Job.builder()
    .jobId("job_abc123")
    .task("Fix bug in module X")
    .workspace("/path/to/workspace")
    .build();

job.markRunning();  // 状态转换
job.getStatus().isTerminal();  // 状态判断
```

### 3.2 Repository 层

**新增文件**: `repository/JobRepository.java`, `repository/RunRepository.java`

- 仅负责 CRUD 操作
- 返回领域对象而非 JsonNode
- 使用 DataSource 注入，支持连接池

```java
@Repository
public class JobRepository {
    private final DataSource dataSource;
    
    public Optional<Job> findById(String jobId) { ... }
    public List<Job> findByStatus(JobStatus status) { ... }
    public void updateStatus(String jobId, JobStatus status) { ... }
}
```

### 3.3 Service 层

**新增文件**: `service/JobService.java`

- 业务逻辑编排
- 不直接访问数据库
- 不处理 HTTP 相关逻辑

```java
@Service
public class JobService {
    private final JobRepository jobRepository;
    private final EngineClient engineClient;
    
    public Job enqueue(String task, String planId, String workspace) {
        // 业务逻辑
    }
}
```

### 3.4 调度器分离

**新增文件**: `infra/scheduling/JobScheduler.java`

- 从 JobService 中分离后台调度逻辑
- 独立的线程池管理
- 优雅关闭支持

### 3.5 Controller 瘦身

**修改文件**: `api/controller/JobController.java`

原 RunController 拆分为：
- `PlanController.java` - Plan 相关 API
- `RunController.java` - Run 相关 API  
- `JobController.java` - Job 相关 API

每个 Controller 仅负责：
- HTTP 请求/响应处理
- 参数校验
- DTO 转换

### 3.6 EngineClient 重构

使用 Builder 模式消除重复代码：

```java
// 旧代码（重复）
public JsonNode plan(String task, String planId, String workspace) {
    List<String> cmd = new ArrayList<>();
    cmd.add("python");
    cmd.add("engine_cli.py");
    cmd.add("plan");
    cmd.add("--task");
    cmd.add(task);
    if (planId != null && !planId.isBlank()) {
        cmd.add("--plan-id");
        cmd.add(planId);
    }
    // ...
}

// 新代码（Builder）
public JsonNode plan(String task, String planId, String workspace) {
    return command("plan")
        .arg("--task", task)
        .argIfPresent("--plan-id", planId)
        .argIfPresent("--workspace", workspace)
        .execute();
}
```

---

## 四、UI 层重构

### 4.1 配置集中管理

**新增文件**: `ui-electron/src/main/config.ts`

- 所有配置项集中定义
- 支持环境变量覆盖
- 类型安全

### 4.2 服务器管理模块化

**新增文件**: `ui-electron/src/main/server.ts`

- 状态机管理服务器生命周期
- 与配置解耦
- 可测试

### 4.3 API 客户端抽象

**新增文件**: `ui-electron/src/main/api-client.ts`

- 统一的 API 调用接口
- 类型定义
- 可在渲染进程复用

---

## 五、依赖关系对比

### 5.1 重构前

```
RunController
├── EngineClient (直接依赖)
├── RunStore (直接依赖)
├── EnginePaths (直接依赖)
├── JobService (直接依赖，且 JobService 包含调度逻辑)
├── JDBC Connection (直接创建)
└── ObjectMapper (直接创建)
```

### 5.2 重构后

```
JobController
└── JobService (接口依赖)
    ├── JobRepository (接口依赖)
    └── EngineClient (接口依赖)

JobScheduler (独立组件)
└── JobService (接口依赖)
```

---

## 六、迁移步骤

### Phase 1: 基础设施（1-2 天）

1. 创建 `domain/` 目录和领域模型
2. 创建 `repository/` 目录和数据访问层
3. 配置 DataSource Bean

### Phase 2: Service 层（2-3 天）

4. 创建 `service/` 目录
5. 迁移业务逻辑到 Service 层
6. 创建 `JobScheduler`

### Phase 3: Controller 重构（1-2 天）

7. 拆分 `RunController`
8. 创建 DTO 类
9. 添加全局异常处理

### Phase 4: EngineClient 重构（1 天）

10. 实现 CommandBuilder
11. 统一异常处理

### Phase 5: UI 层重构（1 天）

12. 创建配置模块
13. 重构服务器管理
14. 创建 API 客户端

---

## 七、测试策略

### 7.1 单元测试

```java
@ExtendWith(MockitoExtension.class)
class JobServiceTest {
    @Mock
    private JobRepository jobRepository;
    
    @Mock
    private EngineClient engineClient;
    
    @InjectMocks
    private JobService jobService;
    
    @Test
    void shouldEnqueueJob() {
        // Given
        when(jobRepository.generateJobId()).thenReturn("job_123");
        
        // When
        Job job = jobService.enqueue("task", null, "/workspace");
        
        // Then
        assertThat(job.getJobId()).isEqualTo("job_123");
        verify(jobRepository).save(any(Job.class));
    }
}
```

### 7.2 集成测试

```java
@SpringBootTest
@AutoConfigureMockMvc
class JobControllerIntegrationTest {
    @Autowired
    private MockMvc mockMvc;
    
    @Test
    void shouldCreateJob() throws Exception {
        mockMvc.perform(post("/api/jobs")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"task\":\"test task\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.ok").value(true));
    }
}
```

---

## 八、收益总结

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| Controller 职责 | 混合 HTTP/业务/数据访问 | 仅 HTTP 处理 |
| 数据访问 | JDBC 散落各处 | 集中在 Repository |
| 业务逻辑 | 与调度混合 | 独立 Service 层 |
| 后台任务 | 内嵌在 Service | 独立 Scheduler |
| 代码重复 | EngineClient 方法重复 | Builder 模式消除 |
| 异常处理 | throws Exception 泛滥 | 统一全局处理 |
| 类型安全 | JsonNode 传递 | DTO + 领域模型 |
| 可测试性 | 难以 Mock | 依赖注入，易于测试 |
