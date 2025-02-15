import sys
from pathlib import PurePath

import yaml
from wcpan.drive.core.exceptions import DriveError
from wcpan.drive.core.types import Drive, Node

from ..lib import create_default_drive
from ._types import AnalyzedData


async def apply(*, comic_path: PurePath, original_path: PurePath) -> None:
    async with create_default_drive() as drive:
        comic = await drive.get_node_by_path(comic_path)
        original = await drive.get_node_by_path(original_path)

        data_list: list[AnalyzedData] = yaml.safe_load(stream=sys.stdin)
        for data in data_list:
            try:
                node = await drive.get_node_by_id(data["id"])
                match data["type"]:
                    case "comic":
                        await _move(node, comic, drive=drive, dst_path=comic_path)
                    case "original":
                        await _move(node, original, drive=drive, dst_path=original_path)
            except DriveError as e:
                print(e, file=sys.stderr)


async def _move(src: Node, dst: Node, /, *, drive: Drive, dst_path: PurePath) -> None:
    print(f"move: {src.name} -> {dst_path}")
    await drive.move(src, new_parent=dst)
