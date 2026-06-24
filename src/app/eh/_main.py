import asyncio
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import yaml

from ._analyze import analyze
from ._args import parse_args
from ._crawl import crawl


async def _main(args: list[str]) -> int:
    path = _require_directory(parse_args(args))

    analyzed = ((entry, analyze(entry.name)) for entry in path.iterdir())
    sorted_ = sorted(
        ((entry, data) for entry, data in analyzed if data),
        key=lambda pair: -1 * pair[1].item_id,
    )
    crawled = ((entry, await crawl(data)) for entry, data in sorted_)
    async for entry, data in crawled:
        if not data:
            continue
        yaml.dump(
            [
                {
                    "name": entry.name,
                    "nyaa": [asdict(_) for _ in data],
                }
            ],
            stream=sys.stdout,
            default_flow_style=False,
            allow_unicode=True,
            encoding="utf-8",
        )
        await asyncio.sleep(1)

    return 0


def _require_directory(path: Path) -> Path:
    path = path.expanduser().resolve(strict=True)
    if not path.is_dir():
        raise NotADirectoryError(path)
    return path


def run_as_module() -> NoReturn:
    sys.exit(asyncio.run(_main(sys.argv[1:])))
