from argparse import ArgumentParser
from collections.abc import Awaitable, Callable
from pathlib import PurePath
from typing import Literal

from ._analyze import analyze, debug
from ._generate import generate


type Action = Callable[[], Awaitable[None]]


def parse_args(args: list[str]) -> Action:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a given path")
    analyze_parser.add_argument("path", help="Path to analyze")

    generate_parser = subparsers.add_parser(
        "generate", help="Generate script to stdout from stdin"
    )
    generate_parser.add_argument("--comic", help="Path to comic", required=True)
    generate_parser.add_argument("--original", help="Path to original", required=True)

    debug_parser = subparsers.add_parser("debug", help="Debug name")
    debug_parser.add_argument("name", help="File name")

    kwargs = parser.parse_args(args)
    command: Literal["analyze", "generate", "debug"] = kwargs.command
    match command:
        case "analyze":
            return lambda: analyze(PurePath(kwargs.path))
        case "generate":
            return lambda: generate(
                comic_path=PurePath(kwargs.comic),
                original_path=PurePath(kwargs.original),
            )
        case "debug":
            return lambda: debug(kwargs.name)
