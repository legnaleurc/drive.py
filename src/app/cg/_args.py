from argparse import ArgumentParser
from collections.abc import Awaitable, Callable
from pathlib import PurePath
from typing import Literal

from ._analyze import analyze, debug
from ._apply import apply


type Action = Callable[[], Awaitable[None]]


def parse_args(args: list[str]) -> Action:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a given path")
    analyze_parser.add_argument("path", help="Path to analyze")

    apply_parser = subparsers.add_parser(
        "apply", help="Apply sheet to stdout from stdin"
    )
    apply_parser.add_argument("--comic", required=True, help="Path to comic")
    apply_parser.add_argument("--original", required=True, help="Path to original")

    debug_parser = subparsers.add_parser("debug", help="Debug name")
    debug_parser.add_argument("name", help="File name")

    kwargs = parser.parse_args(args)
    command: Literal["analyze", "apply", "debug"] = kwargs.command
    match command:
        case "analyze":
            return lambda: analyze(PurePath(kwargs.path))
        case "apply":
            return lambda: apply(
                comic_path=PurePath(kwargs.comic),
                original_path=PurePath(kwargs.original),
            )
        case "debug":
            return lambda: debug(kwargs.name)
