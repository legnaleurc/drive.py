from typing import Literal, TypedDict


class FileSnapshot(TypedDict):
    path: str
    name: str
    size: int
    mtime_ns: int
    title: str


class Candidate(FileSnapshot):
    similarity: float
    remove: bool


class Group(TypedDict):
    match: Literal["exact", "fuzzy"]
    creator: str
    keep: list[FileSnapshot]
    candidates: list[Candidate]


class Manifest(TypedDict):
    version: Literal[1]
    groups: list[Group]
