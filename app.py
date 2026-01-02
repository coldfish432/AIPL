from __future__ import annotations

from pathlib import Path

from infra.container import Container, Lifetime
from interfaces.protocols import ICodeGraphService, IProfileService, IVerifier
from services.code_graph_service import CodeGraphService
from services.controller_service import TaskController
from services.profile_service import ProfileService
from services.verifier import VerifierService


# 创建容器
def create_container(root: Path) -> Container:
    container = Container()
    container.register(Path, root)
    container.register(IProfileService, ProfileService, Lifetime.SINGLETON)
    container.register(IVerifier, VerifierService, Lifetime.SINGLETON)
    container.register(ICodeGraphService, CodeGraphService, Lifetime.SINGLETON)
    container.register(TaskController, TaskController, Lifetime.SINGLETON)
    return container
