# AIPL 项目模块解耦重构方案

## 一、重构目标

将高度耦合的单体结构重构为分层架构，实现：

1. **接口隔离**：上层模块只依赖抽象接口
2. **依赖注入**：运行时注入具体实现
3. **可测试性**：支持 Mock 替换，便于单元测试
4. **可扩展性**：新增功能无需修改现有代码

---

## 二、新目录结构

```
aipl/
├── app.py                    # 应用启动器（组合根）
├── interfaces/               # 接口定义层
│   ├── __init__.py
│   └── protocols.py          # Protocol 接口定义
├── services/                 # 服务实现层
│   ├── __init__.py
│   ├── verifier_service.py   # IVerifier 实现
│   ├── controller_service.py # 控制器服务
│   ├── profile_service.py    # IProfileService 实现
│   ├── code_graph_service.py # ICodeGraphService 实现
│   └── ...
├── infra/                    # 基础设施层
│   ├── __init__.py
│   ├── container.py          # 依赖注入容器
│   ├── io_utils.py           # 公共 IO 工具
│   └── config.py             # 配置管理
└── tests/                    # 测试目录
    ├── test_verifier.py
    └── test_controller.py
```

---

## 三、核心变更

### 3.1 接口定义（interfaces/protocols.py）

使用 Python 的 `Protocol` 实现鸭子类型的静态检查：

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IVerifier(Protocol):
    def verify(self, ctx: TaskContext) -> VerifyResult:
        ...
    
    def register_check(self, check_type: str, handler: callable) -> None:
        ...

@runtime_checkable  
class IProfileService(Protocol):
    def ensure_profile(self, workspace: Path) -> dict:
        ...
    
    def compute_fingerprint(self, workspace: Path) -> str:
        ...
```

### 3.2 依赖注入容器（infra/container.py）

```python
class Container:
    def register(self, interface: type, implementation: type, lifetime: Lifetime):
        """注册服务"""
        ...
    
    def resolve(self, interface: type) -> object:
        """解析服务（自动注入依赖）"""
        ...
```

### 3.3 服务实现

服务类通过构造函数接收依赖：

```python
class TaskController:
    def __init__(
        self,
        config: AppConfig,
        verifier: IVerifier,           # 注入
        profile_service: IProfileService,  # 注入
        task_selector: ITaskSelector,      # 注入
        ...
    ):
        self._verifier = verifier
        self._profile_service = profile_service
        ...
```

### 3.4 组合根（app.py）

所有服务注册集中在一处：

```python
def _create_production_container(config: AppConfig) -> Container:
    container = Container()
    container.register(AppConfig, config, Lifetime.SINGLETON)
    container.register(IVerifier, Verifier, Lifetime.SINGLETON)
    container.register(IProfileService, ProfileService, Lifetime.SINGLETON)
    # ... 其他服务
    return container
```

---

## 四、迁移步骤

### 第一阶段：基础设施（1-2 天）

| 步骤 | 操作 | 产出 |
|------|------|------|
| 1 | 创建 `infra/io_utils.py` | 统一 JSON IO 操作 |
| 2 | 创建 `infra/container.py` | 依赖注入容器 |
| 3 | 修改现有代码使用新 IO 工具 | 消除重复代码 |

### 第二阶段：接口抽象（2-3 天）

| 步骤 | 操作 | 产出 |
|------|------|------|
| 4 | 定义 `interfaces/protocols.py` | 所有核心接口 |
| 5 | 定义数据类型 (dataclass/TypedDict) | 类型安全 |
| 6 | 为现有模块添加类型注解 | 渐进式类型化 |

### 第三阶段：服务重构（3-5 天）

| 步骤 | 操作 | 产出 |
|------|------|------|
| 7 | 重构 `verifier.py` → `services/verifier_service.py` | 实现 IVerifier |
| 8 | 重构 `profile.py` → `services/profile_service.py` | 实现 IProfileService |
| 9 | 重构 `code_graph.py` → `services/code_graph_service.py` | 实现 ICodeGraphService |
| 10 | 重构 `controller.py` → `services/controller_service.py` | 使用依赖注入 |

### 第四阶段：集成测试（2 天）

| 步骤 | 操作 | 产出 |
|------|------|------|
| 11 | 创建测试用 Mock 服务 | 可测试性 |
| 12 | 编写单元测试 | 测试覆盖 |
| 13 | 集成测试 | 端到端验证 |

---

## 五、关键代码对比

### 5.1 原代码（高耦合）

```python
# controller.py - 直接导入具体实现
from verifier import verify_task
from profile import ensure_profile, propose_soft

def main():
    # 直接调用具体函数
    profile = ensure_profile(root, workspace)
    passed, reasons = verify_task(run_dir, task_id, workspace)
```

### 5.2 新代码（低耦合）

```python
# services/controller_service.py - 依赖抽象接口
class TaskController:
    def __init__(
        self,
        verifier: IVerifier,          # 接口
        profile_service: IProfileService,  # 接口
    ):
        self._verifier = verifier
        self._profile_service = profile_service
    
    def run(self, ...):
        # 通过接口调用
        profile = self._profile_service.ensure_profile(workspace)
        result = self._verifier.verify(task_ctx)
```

---

## 六、测试示例

```python
# tests/test_controller.py
import pytest
from unittest.mock import Mock, MagicMock
from interfaces.protocols import IVerifier, IProfileService, VerifyResult
from services.controller_service import TaskController

class TestTaskController:
    
    def test_run_with_passing_task(self, tmp_path):
        # 创建 Mock
        mock_verifier = Mock(spec=IVerifier)
        mock_verifier.verify.return_value = VerifyResult(passed=True)
        
        mock_profile = Mock(spec=IProfileService)
        mock_profile.ensure_profile.return_value = {
            "workspace_id": "test",
            "fingerprint": "abc123",
            "effective_hard": {}
        }
        
        # 注入 Mock
        controller = TaskController(
            config=AppConfig(root_path=tmp_path),
            verifier=mock_verifier,
            profile_service=mock_profile,
            task_selector=Mock(),
            curriculum=Mock(),
            workspace_detector=Mock(),
        )
        
        # 测试
        result = controller.run(plan_id="test-plan")
        
        assert result["passed"] == True
        mock_verifier.verify.assert_called_once()
```

---

## 七、收益总结

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| **耦合度** | 高（直接依赖具体实现） | 低（依赖抽象接口） |
| **可测试性** | 难（需要真实文件系统/数据库） | 易（Mock 注入） |
| **可扩展性** | 难（修改需改动多处） | 易（实现新接口即可） |
| **代码复用** | 低（重复代码多） | 高（公共模块提取） |
| **类型安全** | 弱（dict 到处传） | 强（TypedDict/dataclass） |

---

## 八、后续建议

1. **渐进式迁移**：不要一次性重构，按模块逐步替换
2. **保持兼容**：原接口可暂时保留为 wrapper
3. **文档先行**：先明确接口契约再实现
4. **测试驱动**：每个新服务都配套单元测试

---

## 九、参考资料

- [Python Protocol 官方文档](https://docs.python.org/3/library/typing.html#typing.Protocol)
- [依赖注入模式](https://martinfowler.com/articles/injection.html)
- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID)
