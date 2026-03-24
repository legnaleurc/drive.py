import asyncio
import sys
from pathlib import Path

import magic
import yaml


_CONCURRENCY = 8
_sem = asyncio.Semaphore(_CONCURRENCY)


async def _detect_mime(path: Path) -> str:
    async with _sem:
        return await asyncio.to_thread(magic.from_file, str(path), mime=True)  # type: ignore


def _write_entry(entry: dict) -> None:
    item_yaml = yaml.safe_dump(entry, allow_unicode=True, default_flow_style=False)
    lines = item_yaml.splitlines()
    sys.stdout.write("- " + lines[0] + "\n")
    for line in lines[1:]:
        sys.stdout.write("  " + line + "\n")
    sys.stdout.flush()


async def scan(paths: list[Path]) -> None:
    for root_path in paths:
        for folder, subdirs, files in root_path.walk():
            mime_types = await asyncio.gather(
                *[_detect_mime(folder / f) for f in files]
            )
            type_counts: dict[str, int] = {}
            for mime in mime_types:
                type_counts[mime] = type_counts.get(mime, 0) + 1
            _write_entry(
                {"path": str(folder), "types": type_counts, "folders": len(subdirs)}
            )
