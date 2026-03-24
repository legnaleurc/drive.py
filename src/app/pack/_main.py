import sys
from argparse import ArgumentParser
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from ._cleanup import cleanup
from ._compress import compress
from ._scan import scan


async def main(args: list[str]) -> int:
    action = _parse_args(args)
    try:
        await action()
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def _parse_args(args: list[str]) -> Callable[[], Awaitable[None]]:
    parser = ArgumentParser("pack")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    scan_parser = subparsers.add_parser(
        "scan", help="Scan paths and output YAML manifest"
    )
    scan_parser.add_argument("paths", nargs="+", help="Paths to scan")

    subparsers.add_parser("compress", help="Compress folders from stdin YAML manifest")

    subparsers.add_parser(
        "cleanup", help="Remove source folders from stdin YAML manifest"
    )

    kwargs = parser.parse_args(args)
    command: Literal["scan", "compress", "cleanup"] = kwargs.command
    match command:
        case "scan":
            paths = [Path(p) for p in kwargs.paths]
            return lambda: scan(paths)
        case "compress":
            return lambda: compress()
        case "cleanup":
            return lambda: cleanup()
