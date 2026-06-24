import sys
from pathlib import Path

import yaml

from ._operations import get_operation_paths, needs_processing
from ._types import MediaDescriptor


async def cleanup() -> None:
    data = yaml.safe_load(sys.stdin)
    files: list[MediaDescriptor] = data["files"]

    for file_data in files:
        if not needs_processing(file_data):
            continue

        paths = get_operation_paths(Path(file_data["path"]))
        if not paths.backup.exists():
            continue
        if not paths.final.is_file():
            raise RuntimeError(f"final file not found: {paths.final}")

        paths.backup.unlink()
        print(f"removed {paths.backup}")
