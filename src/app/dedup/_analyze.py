import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from ._matching import ParsedArchiveName, levenshtein_similarity, parse_archive_name
from ._types import Candidate, FileSnapshot, Group, Manifest


_FUZZY_THRESHOLD = 0.9


@dataclass(frozen=True, kw_only=True)
class _Archive:
    path: Path
    parsed: ParsedArchiveName


def analyze(root_path: Path) -> None:
    yaml.safe_dump(
        build_manifest(root_path),
        stream=sys.stdout,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def build_manifest(root_path: Path) -> Manifest:
    root = root_path.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)

    archives = _scan(root)
    exact_groups, assigned_paths = _build_exact_groups(archives)
    fuzzy_groups = _build_fuzzy_groups(archives, assigned_paths)
    return {"version": 1, "groups": exact_groups + fuzzy_groups}


def _scan(root: Path) -> list[_Archive]:
    archives: list[_Archive] = []
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if entry.is_symlink() or not entry.is_file():
            continue
        parsed = parse_archive_name(entry.name)
        if parsed is not None:
            archives.append(_Archive(path=entry, parsed=parsed))
    return archives


def _build_exact_groups(
    archives: list[_Archive],
) -> tuple[list[Group], set[Path]]:
    grouped: dict[tuple[str, str], list[_Archive]] = {}
    for archive in archives:
        key = (archive.parsed.creator, archive.parsed.title)
        grouped.setdefault(key, []).append(archive)

    groups: list[Group] = []
    assigned_paths: set[Path] = set()
    for (creator, _title), members in sorted(grouped.items()):
        keepers = sorted(
            (member for member in members if member.parsed.archive_type == "zip"),
            key=lambda member: str(member.path),
        )
        duplicates = sorted(
            (member for member in members if member.parsed.archive_type == "7z"),
            key=lambda member: str(member.path),
        )
        if not keepers or not duplicates:
            continue
        groups.append(
            {
                "match": "exact",
                "creator": creator,
                "keep": [_snapshot(member) for member in keepers],
                "candidates": [
                    _candidate(member, similarity=1.0, remove=True)
                    for member in duplicates
                ],
            }
        )
        assigned_paths.update(member.path for member in keepers + duplicates)
    return groups, assigned_paths


def _build_fuzzy_groups(
    archives: list[_Archive], assigned_paths: set[Path]
) -> list[Group]:
    zips_by_creator: dict[str, list[_Archive]] = {}
    unmatched_7z: list[_Archive] = []
    for archive in archives:
        if archive.path in assigned_paths:
            continue
        if archive.parsed.archive_type == "zip":
            zips_by_creator.setdefault(archive.parsed.creator, []).append(archive)
        else:
            unmatched_7z.append(archive)

    groups: list[Group] = []
    for duplicate in sorted(unmatched_7z, key=lambda member: str(member.path)):
        possible = zips_by_creator.get(duplicate.parsed.creator, [])
        scored = sorted(
            (
                (
                    levenshtein_similarity(duplicate.parsed.title, keeper.parsed.title),
                    keeper,
                )
                for keeper in possible
            ),
            key=lambda pair: (-pair[0], str(pair[1].path)),
        )
        if not scored or scored[0][0] < _FUZZY_THRESHOLD:
            continue
        similarity, keeper = scored[0]
        groups.append(
            {
                "match": "fuzzy",
                "creator": duplicate.parsed.creator,
                "keep": [_snapshot(keeper)],
                "candidates": [
                    _candidate(
                        duplicate,
                        similarity=round(similarity, 4),
                        remove=False,
                    )
                ],
            }
        )
    return groups


def _snapshot(archive: _Archive) -> FileSnapshot:
    stat = archive.path.stat(follow_symlinks=False)
    return {
        "path": str(archive.path),
        "name": archive.path.name,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "title": archive.parsed.title,
    }


def _candidate(archive: _Archive, *, similarity: float, remove: bool) -> Candidate:
    return {
        **_snapshot(archive),
        "similarity": similarity,
        "remove": remove,
    }
