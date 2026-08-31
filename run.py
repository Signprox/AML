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
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host. Defaults to 127.0.0.1 in development and 0.0.0.0 otherwise.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port.",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (recommended for UAT and production).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes when reload is disabled.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    os.environ["APP_ENV"] = args.environment
    reload = not args.no_reload and args.environment == "development"
    host = args.host or ("127.0.0.1" if args.environment == "development" else "0.0.0.0")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=args.port,
        reload=reload,
        workers=args.workers if not reload else 1,
    )


if __name__ == "__main__":
    main()
