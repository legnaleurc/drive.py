import sys

import yaml
from wcpan.drive.core.exceptions import DriveError

from ..lib import create_default_drive
from ._types import ManifestEntry


async def apply() -> None:
    entries: list[ManifestEntry] = yaml.safe_load(sys.stdin)

    async with create_default_drive() as drive:
        for entry in entries:
            try:
                node = await drive.get_node_by_id(entry["id"])
                await drive.move(node, new_parent=None, new_name=entry["new_name"])
                print(f"rename: {entry['name']} → {entry['new_name']}")
            except DriveError as e:
                print(e, file=sys.stderr)
