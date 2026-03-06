from argparse import ArgumentParser
from collections.abc import Awaitable, Callable
from pathlib import PurePath
from typing import Literal

from ._analyze import analyze
from ._apply import apply
from ._verify import verify


type Action = Callable[[], Awaitable[None]]


def parse_args(args: list[str]) -> Action:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser(
        "analyze", help="Scan remote path and emit rename manifest"
    )
    analyze_parser.add_argument("path", help="Remote path to scan")

    subparsers.add_parser(
        "verify", help="Validate new_name entries from manifest on stdin"
    )

    subparsers.add_parser("apply", help="Apply renames from manifest on stdin")

    kwargs = parser.parse_args(args)
    command: Literal["analyze", "verify", "apply"] = kwargs.command

    match command:
        case "analyze":
            return lambda: analyze(PurePath(kwargs.path))
        case "verify":
            return verify
        case "apply":
            return apply
        case _:
            parser.print_help()
            raise SystemExit(1)
