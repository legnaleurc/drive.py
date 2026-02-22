from dataclasses import dataclass
from hashlib import sha256
from mimetypes import guess_type
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class FileItem(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def mime_type(self) -> str: ...

    @property
    def size(self) -> int: ...


@dataclass(frozen=True)
class LocalFileItem:
    path: Path

    @property
    def id(self) -> str:
        return sha256(str(self.path).encode()).hexdigest()

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def mime_type(self) -> str:
        type_, _ = guess_type(self.path)
        return type_ or "application/octet-stream"

    @property
    def size(self) -> int:
        return self.path.stat().st_size
