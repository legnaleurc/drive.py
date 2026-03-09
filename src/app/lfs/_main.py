import sys
from argparse import ArgumentParser
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from ._scanner import scan
from ._scripter import script


async def main(args: list[str]) -> int:
    action = _parse_args(args)
    try:
        await action()
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def _parse_args(args: list[str]) -> Callable[[], Awaitable[None]]:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    scan_parser = subparsers.add_parser("scan", help="Scan a given path")
    scan_parser.add_argument("path", help="Path to scan")

    script_parser = subparsers.add_parser(
        "script", help="Generate script to stdout from stdin"
    )
    script_parser.add_argument("--output", help="Output root directory")

    kwargs = parser.parse_args(args)
    command: Literal["scan", "script"] = kwargs.command
    match command:
        case "scan":
            path: str = kwargs.path
            return lambda: scan(Path(path))
        case "script":
            return lambda: script(
                output_dir=Path(kwargs.output) if kwargs.output else None
            )
