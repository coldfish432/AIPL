from __future__ import annotations

from infra.container import Container, Lifetime
from interfaces.protocols import ICodeGraphService, IProfileService, IVerifier
from services.code_graph_service import CodeGraphService
from services.controller_service import TaskController
from services.profile_service import ProfileService
from services.verifier_service import Verifier


def create_container() -> Container:
    container = Container()
    container.register(IProfileService, ProfileService, Lifetime.SINGLETON)
    container.register(IVerifier, Verifier, Lifetime.SINGLETON)
    container.register(ICodeGraphService, CodeGraphService, Lifetime.SINGLETON)
    container.register(TaskController, TaskController, Lifetime.SINGLETON)
    return container
