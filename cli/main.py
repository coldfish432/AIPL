import os
from pathlib import Path

from cli.parsers import create_parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if getattr(args, "db_path", None):
        os.environ["AIPL_DB_PATH"] = args.db_path

    root = Path(args.root).resolve()
    args.func(args, root)


if __name__ == "__main__":
    main()
