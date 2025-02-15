import re
import sys
from pathlib import PurePath

import yaml

from ..lib import create_default_drive
from ._types import AnalyzedData, DataType


async def analyze(root_path: PurePath) -> None:
    async with create_default_drive() as drive:
        root = await drive.get_node_by_path(root_path)
        children = await drive.get_children(root)

        for child in children:
            if child.is_trashed:
                continue

            rv = _parse_name(child.name)
            if not rv:
                continue

            rv = _analyze_name(*rv)
            if not rv:
                continue

            data: AnalyzedData = {
                "id": child.id,
                "name": child.name,
                "type": rv,
            }

            yaml.dump(
                [data],
                default_flow_style=False,
                encoding="utf-8",
                stream=sys.stdout,
                allow_unicode=True,
            )


async def debug(name: str) -> None:
    rv = _parse_name(name)
    if not rv:
        return

    rv = _analyze_name(*rv)
    if not rv:
        return

    print(rv)


def _parse_name(name: str) -> tuple[str, list[str]] | None:
    rv = re.search(r"^\(([^\)]+)\)", name)
    if rv is None:
        return

    publisher = rv.group(1)

    rv = re.findall(r"\(([^\)]+)\)", name)

    return publisher, rv[1:]


def _analyze_name(publisher: str, tags: list[str]) -> DataType | None:
    if publisher == "成年コミック":
        return "comic"

    if not tags:
        return None

    parody = tags[-1]
    if parody == "オリジナル":
        return "original"

    return None
