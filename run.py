import argparse
import os
from collections.abc import Sequence

import uvicorn


SUPPORTED_ENVIRONMENTS = ("development", "uat", "production")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the AML API using an environment-specific configuration.",
    )
    parser.add_argument(
        "environment",
        choices=SUPPORTED_ENVIRONMENTS,
        help="Configuration environment to load.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    os.environ["APP_ENV"] = args.environment
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
