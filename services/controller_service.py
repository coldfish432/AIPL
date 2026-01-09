import argparse
from pathlib import Path

from services.code_graph_service import CodeGraphService
from services.profile_service import ProfileService
from services.verifier import VerifierService
from services.controller import TaskController


def create_default_controller(root: Path) -> TaskController:
    return TaskController(root, ProfileService(), VerifierService(root), CodeGraphService(cache_root=root))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("--plan-id", dest="plan_id", help="plan id filter")
    parser.add_argument("--workspace", dest="workspace", help="workspace path")
    parser.add_argument("--max-rounds", dest="max_rounds", type=int, default=3, help="max retry rounds")
    parser.add_argument("--mode", dest="mode", default="autopilot", choices=["autopilot", "manual"], help="run mode")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    controller = create_default_controller(root)
    controller.run(args)


if __name__ == "__main__":
    main()
