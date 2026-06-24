import re
import unicodedata
from dataclasses import dataclass
from typing import Literal


type ArchiveType = Literal["zip", "7z"]


@dataclass(frozen=True, kw_only=True)
class ParsedArchiveName:
    creator: str
    title: str
    archive_type: ArchiveType


_LEADING_METADATA = re.compile(r"^\([^)]*\)\s*(?=\[)")
_CREATOR_PREFIX = re.compile(r"^\[([^]]+)]\s*(.+)$")
_TRAILING_METADATA = re.compile(r"\s*(?:\(オリジナル\)|\[DL版]|\[\d+])\s*$")


def parse_archive_name(name: str) -> ParsedArchiveName | None:
    lowered = name.lower()
    archive_type: ArchiveType
    if lowered.endswith(".zip"):
        archive_type = "zip"
        stem = name[:-4]
    elif lowered.endswith(".7z"):
        archive_type = "7z"
        stem = name[:-3]
    else:
        return None

    stem = _LEADING_METADATA.sub("", stem.strip())
    matched = _CREATOR_PREFIX.fullmatch(stem)
    if matched is None:
        return None

    creator = _normalize_text(matched.group(1))
    title = matched.group(2)
    while True:
        stripped = _TRAILING_METADATA.sub("", title)
        if stripped == title:
            break
        title = stripped
    title = _normalize_text(title)
    if not creator or not title:
        return None

    return ParsedArchiveName(
        creator=creator,
        title=title,
        archive_type=archive_type,
    )


def levenshtein_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left

    previous = list(range(len(left) + 1))
    for right_index, right_character in enumerate(right, start=1):
        current = [right_index]
        for left_index, left_character in enumerate(left, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[left_index] + 1,
                    previous[left_index - 1] + (left_character != right_character),
                )
            )
        previous = current

    distance = previous[-1]
    return 1 - distance / max(len(left), len(right))


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split())
