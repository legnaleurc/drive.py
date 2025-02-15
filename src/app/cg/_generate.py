import sys
from pathlib import PurePath

import yaml
from wcpan.drive.core.exceptions import DriveError
from wcpan.drive.core.types import Drive, Node

from ..lib import create_default_drive
from ._types import AnalyzedData


async def generate(*, comic_path: PurePath, original_path: PurePath) -> None:
    async with create_default_drive() as drive:
        comic = await drive.get_node_by_path(comic_path)
        original = await drive.get_node_by_path(original_path)

        data_list: list[AnalyzedData] = yaml.safe_load(stream=sys.stdin)
        for data in data_list:
            try:
                await _move(
                    data,
                    drive=drive,
                    comic=comic,
                    comic_path=comic_path,
                    original=original,
                    original_path=original_path,
                )
            except DriveError as e:
                print(e, file=sys.stderr)


async def _move(
    data: AnalyzedData,
    /,
    *,
    drive: Drive,
    comic_path: PurePath,
    original_path: PurePath,
    comic: Node,
    original: Node,
):
    node = await drive.get_node_by_id(data["id"])
    match data["type"]:
        case "comic":
            print(f"move: {node.name} -> {comic_path}")
            await drive.move(node, new_parent=comic)
        case "original":
            print(f"move: {node.name} -> {original_path}")
            await drive.move(node, new_parent=original)
