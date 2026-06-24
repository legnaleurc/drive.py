import os
import stat
import sys
from pathlib import Path
from typing import Any, cast

import yaml

from ._types import Candidate, FileSnapshot, Manifest


def apply() -> int:
    manifest = _validate_manifest(yaml.safe_load(sys.stdin))
    failed = False

    for group in manifest["groups"]:
        selected = [
            candidate for candidate in group["candidates"] if candidate["remove"]
        ]
        if not selected:
            continue

        keeper_problems = [
            _snapshot_problem(keeper, expected_suffix=".zip")
            for keeper in group["keep"]
        ]
        if all(problem is not None for problem in keeper_problems):
            print(
                f"{group['creator']}: no unchanged ZIP keeper remains",
                file=sys.stderr,
            )
            failed = True
            continue

        for candidate in selected:
            path = Path(candidate["path"])
            problem = _snapshot_problem(candidate, expected_suffix=".7z")
            if problem is not None:
                print(f"{path}: {problem}", file=sys.stderr)
                failed = True
                continue
            try:
                path.unlink()
            except OSError as error:
                print(f"{path}: {error}", file=sys.stderr)
                failed = True
                continue
            print(f"remove: {path}")

    return int(failed)


def _validate_manifest(value: Any) -> Manifest:
    if not isinstance(value, dict):
        raise ValueError("manifest must be a mapping")
    if type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("unsupported manifest version")
    groups = value.get("groups")
    if not isinstance(groups, list):
        raise ValueError("manifest groups must be a list")

    selected_paths: set[str] = set()
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"group {group_index} must be a mapping")
        if group.get("match") not in {"exact", "fuzzy"}:
            raise ValueError(f"group {group_index} has invalid match type")
        if not isinstance(group.get("creator"), str):
            raise ValueError(f"group {group_index} has invalid creator")
        keepers = group.get("keep")
        candidates = group.get("candidates")
        if not isinstance(keepers, list) or not keepers:
            raise ValueError(f"group {group_index} must have a keeper")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError(f"group {group_index} must have candidates")

        for keeper_index, keeper in enumerate(keepers):
            _validate_snapshot(
                keeper,
                location=f"group {group_index} keeper {keeper_index}",
                expected_suffix=".zip",
            )
        for candidate_index, candidate in enumerate(candidates):
            location = f"group {group_index} candidate {candidate_index}"
            _validate_snapshot(
                candidate,
                location=location,
                expected_suffix=".7z",
            )
            if not isinstance(candidate.get("similarity"), (int, float)) or isinstance(
                candidate.get("similarity"), bool
            ):
                raise ValueError(f"{location} has invalid similarity")
            similarity = candidate["similarity"]
            if not 0 <= similarity <= 1:
                raise ValueError(f"{location} has invalid similarity")
            if not isinstance(candidate.get("remove"), bool):
                raise ValueError(f"{location} has invalid remove flag")
            if candidate["remove"]:
                path = candidate["path"]
                normalized_path = os.path.normpath(path)
                if normalized_path in selected_paths:
                    raise ValueError(f"duplicate selected path: {path}")
                selected_paths.add(normalized_path)

    return cast(Manifest, value)


def _validate_snapshot(value: Any, *, location: str, expected_suffix: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping")
    for field in ("path", "name", "title"):
        if not isinstance(value.get(field), str):
            raise ValueError(f"{location} has invalid {field}")
    for field in ("size", "mtime_ns"):
        field_value = value.get(field)
        if type(field_value) is not int or field_value < 0:
            raise ValueError(f"{location} has invalid {field}")

    path = Path(value["path"])
    if not path.is_absolute():
        raise ValueError(f"{location} path must be absolute")
    if path.name != value["name"]:
        raise ValueError(f"{location} path and name differ")
    if path.suffix.lower() != expected_suffix:
        raise ValueError(f"{location} has invalid archive type")


def _snapshot_problem(
    snapshot: FileSnapshot | Candidate, *, expected_suffix: str
) -> str | None:
    path = Path(snapshot["path"])
    try:
        file_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        return str(error)
    if not stat.S_ISREG(file_stat.st_mode):
        return "path is not a non-symlink regular file"
    if path.suffix.lower() != expected_suffix:
        return "archive type changed since analysis"
    if (
        file_stat.st_size != snapshot["size"]
        or file_stat.st_mtime_ns != snapshot["mtime_ns"]
    ):
        return "file changed since analysis"
    return None
