import asyncio
import sys
from dataclasses import asdict
from typing import NoReturn

import yaml

from app.lib import create_default_drive

from ._analyze import analyze
from ._args import parse_args
from ._crawl import crawl


async def _main(args: list[str]) -> int:
    path = parse_args(args)

    async with create_default_drive() as drive:
        parent = await drive.get_node_by_path(path)
        children = await drive.get_children(parent)

        analyzed = ((_, analyze(_.name)) for _ in children if not _.is_trashed)
        crawled = ((_, await crawl(data)) for _, data in analyzed if data is not None)
        async for node, data in crawled:
            if not data:
                continue
            yaml.dump(
                [
                    {
                        "name": node.name,
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


def run_as_module() -> NoReturn:
    sys.exit(asyncio.run(_main(sys.argv[1:])))
