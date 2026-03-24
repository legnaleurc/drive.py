import sys
from pathlib import Path
from shutil import rmtree

import yaml


async def cleanup() -> None:
    manifest = yaml.safe_load(sys.stdin)
    for entry in manifest:
        folder = Path(entry["path"])
        archive_path = folder.parent / f"{folder.name}.7z"
        assert archive_path.is_file(), f"archive not found: {archive_path}"
        rmtree(folder)
        print(f"removed {folder}")
