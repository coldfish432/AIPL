from app import create_container
from services.controller_service import TaskController
from services.profile_service import ProfileService
from services.verifier_service import Verifier
from services.code_graph_service import CodeGraphService


def test_container_resolves_task_controller():
    container = create_container()
    controller = container.resolve(TaskController)
    assert isinstance(controller, TaskController)
    assert isinstance(controller._profile_service, ProfileService)
    assert isinstance(controller._verifier, Verifier)
    assert isinstance(controller._code_graph_service, CodeGraphService)
