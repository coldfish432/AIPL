from app import create_container
from pathlib import Path

from services.controller_service import TaskController
from services.profile_service import ProfileService
from interfaces.protocols import IVerifier
from services.verifier import VerifierService
from services.code_graph_service import CodeGraphService


REPO_ROOT = Path(__file__).resolve().parents[1]


# test容器resolves任务控制器
def test_container_resolves_task_controller():
    container = create_container(REPO_ROOT)
    controller = container.resolve(TaskController)
    assert isinstance(controller, TaskController)
    assert isinstance(controller._profile_service, ProfileService)
    assert isinstance(controller._verifier, VerifierService)
    assert isinstance(controller._code_graph_service, CodeGraphService)


# test容器singletonsarereused
def test_container_singletons_are_reused():
    container = create_container(REPO_ROOT)
    controller_a = container.resolve(TaskController)
    controller_b = container.resolve(TaskController)
    assert controller_a is controller_b
    assert controller_a._verifier is container.resolve(IVerifier)
