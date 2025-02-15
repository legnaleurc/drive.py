import asyncio
import sys
from typing import NoReturn

from ._args import parse_args


async def _main(args: list[str]) -> int:
    action = parse_args(args)
    try:
        await action()
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def run_as_module() -> NoReturn:
    sys.exit(asyncio.run(_main(sys.argv[1:])))
