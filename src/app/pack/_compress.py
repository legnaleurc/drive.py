import sys
from asyncio import create_subprocess_exec
from asyncio.subprocess import DEVNULL
from pathlib import Path
from shutil import copyfile, copytree, move
from tempfile import TemporaryDirectory

import yaml


async def compress() -> None:
    manifest = yaml.safe_load(sys.stdin)
    for entry in manifest:
        folder = Path(entry["path"])
        await _compress_one(folder)


async def _compress_one(folder: Path) -> None:
    with TemporaryDirectory(dir="/var/tmp") as tmp:
        work_dir = Path(tmp)

        # Deep copy — copyfile copies content only, no permissions
        local_copy = work_dir / folder.name
        copytree(folder, local_copy, copy_function=copyfile)

        # Normalize permissions on local copy
        local_copy.chmod(0o755)
        for root, dirs, files in local_copy.walk():
            for d in dirs:
                (root / d).chmod(0o755)
            for f in files:
                (root / f).chmod(0o644)

        # Archive from local copy
        archive_path = work_dir / f"{folder.name}.7z"
        cmd = ["7z", "a", "-y", str(archive_path), "*"]
        p = await create_subprocess_exec(*cmd, cwd=local_copy, stdin=DEVNULL)
        rv = await p.wait()
        assert rv == 0

        # Move archive to final destination (beside original folder)
        final_path = folder.parent / f"{folder.name}.7z"
        move(archive_path, final_path)
