import sys
from pathlib import PurePath

import yaml

from ..lib import create_default_drive
from ._rules import is_valid_name, suggest_name
from ._types import ManifestEntry


async def analyze(path: PurePath) -> None:
    async with create_default_drive() as drive:
        root = await drive.get_node_by_path(path)
        entries: list[ManifestEntry] = []

        async for _parent, dirs, files in drive.walk(root):
            for node in dirs + files:
                if node.is_trashed:
                    continue
                if is_valid_name(node.name):
                    continue
                entries.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "new_name": suggest_name(node.name),
                    }
                )

        if entries:
            yaml.dump(
                entries,
                default_flow_style=False,
                encoding=None,
                stream=sys.stdout,
                allow_unicode=True,
            )
