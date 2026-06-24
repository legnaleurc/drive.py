from argparse import ArgumentParser
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from ._analyze import analyze
from ._apply import apply


type Action = Callable[[], int]


def parse_args(args: list[str]) -> Action:
    parser = ArgumentParser("dedup")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser(
        "analyze", help="Scan immediate archives and emit a YAML manifest"
    )
    analyze_parser.add_argument("path", help="Local directory to scan")

    subparsers.add_parser("apply", help="Remove selected files from a stdin manifest")

    kwargs = parser.parse_args(args)
    command: Literal["analyze", "apply"] | None = kwargs.command
    match command:
        case "analyze":
            return lambda: _analyze(Path(kwargs.path))
        case "apply":
            return apply
        case _:
            parser.print_help()
            raise SystemExit(1)


def _analyze(path: Path) -> int:
    analyze(path)
    return 0
