import re

from ._types import AnalyzedData


def analyze(name: str) -> AnalyzedData | None:
    rv = re.match(r"^\[([^\]]+)\](.+)\[(\d+)\]\.7z$", name)
    if not rv:
        return None

    author = rv.group(1)
    title = rv.group(2).replace("[DL版]", "").strip()
    title = re.sub(r"\([^()]+\)$", "", title).strip()

    return AnalyzedData(
        author=author,
        title=title,
    )
