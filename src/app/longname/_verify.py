import sys

import yaml

from ._rules import is_valid_name, suggest_name
from ._types import ManifestEntry


async def verify() -> None:
    entries: list[ManifestEntry] = yaml.safe_load(sys.stdin)
    output: list[ManifestEntry] = []

    for entry in entries:
        name = entry["name"]
        if is_valid_name(name):
            new_name = name
        else:
            new_name = suggest_name(name)
        output.append({"id": entry["id"], "name": name, "new_name": new_name})

    yaml.dump(
        output,
        default_flow_style=False,
        encoding=None,
        stream=sys.stdout,
        allow_unicode=True,
    )
