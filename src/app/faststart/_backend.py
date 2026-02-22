import asyncio
import shutil
from collections.abc import AsyncIterator
from concurrent.futures import Executor
from logging import getLogger
from mimetypes import guess_type
from pathlib import Path, PurePath
from typing import Protocol

from wcpan.drive.cli.lib import get_file_hash
from wcpan.drive.core.lib import download_file_to_local, upload_file_from_local
from wcpan.drive.core.types import Drive, MediaInfo, Node

from app.lib import get_daily_usage

from ._types import FileItem, LocalFileItem


_L = getLogger(__name__)


class SourceBackend(Protocol):
    def walk(self, roots: list[PurePath]) -> AsyncIterator[FileItem]: ...

    async def fetch(self, item: FileItem, dest_dir: Path) -> Path: ...


class SinkBackend(Protocol):
    async def store(
        self, local_path: Path, origin: FileItem, media_info: MediaInfo
    ) -> FileItem: ...

    def quota_used(self) -> int: ...


class DriveSource:
    def __init__(self, drive: Drive):
        self._drive = drive

    async def walk(self, roots: list[PurePath]) -> AsyncIterator[FileItem]:
        for root_path in roots:
            root_node = await self._drive.get_node_by_path(root_path)
            if not root_node:
                continue
            async for _root, _folders, files in self._drive.walk(root_node):
                for file_ in files:
                    yield file_

    async def fetch(self, item: FileItem, dest_dir: Path) -> Path:
        assert isinstance(item, Node)
        _L.info(f"downloading {item.name}")
        downloaded_path = await download_file_to_local(self._drive, item, dest_dir)
        _L.info(f"downloaded {item.name}")
        return downloaded_path


class LocalSource:
    async def walk(self, roots: list[PurePath]) -> AsyncIterator[FileItem]:
        for root_path in roots:
            p = Path(str(root_path))
            if not p.exists():
                continue
            if p.is_file():
                yield LocalFileItem(p)
                continue
            for file_path in sorted(p.rglob("*")):
                if file_path.is_file():
                    yield LocalFileItem(file_path)

    async def fetch(self, item: FileItem, dest_dir: Path) -> Path:
        assert isinstance(item, LocalFileItem)
        dest = dest_dir / item.name
        shutil.copy2(item.path, dest)
        return dest


class DriveSink:
    def __init__(self, drive: Drive, pool: Executor, *, same_location: bool):
        self._drive = drive
        self._pool = pool
        self._same_location = same_location

    async def store(
        self, local_path: Path, origin: FileItem, media_info: MediaInfo
    ) -> FileItem:
        assert isinstance(origin, Node)
        if self._same_location:
            return await self._store_same_location(local_path, origin, media_info)
        return await self._store_different_location(local_path, origin, media_info)

    def quota_used(self) -> int:
        return get_daily_usage(self._drive)

    async def _store_same_location(
        self, local_path: Path, origin: Node, media_info: MediaInfo
    ) -> Node:
        await self._rename_remote(origin)
        try:
            new_node = await self._upload(local_path, origin, media_info)
            await self._verify(local_path, new_node)
            await self._delete_remote(origin)
            return new_node
        except Exception:
            _L.exception("upload error")
            await self._restore_remote(origin)
            raise

    async def _store_different_location(
        self, local_path: Path, origin: Node, media_info: MediaInfo
    ) -> Node:
        new_node = await self._upload(local_path, origin, media_info)
        await self._verify(local_path, new_node)
        return origin

    async def _upload(
        self, local_path: Path, origin: Node, media_info: MediaInfo
    ) -> Node:
        _L.info(f"uploading {local_path}")
        assert origin.parent_id
        parent_node = await self._drive.get_node_by_id(origin.parent_id)
        type_, _ = guess_type(local_path)
        node = await upload_file_from_local(
            self._drive, local_path, parent_node, mime_type=type_, media_info=media_info
        )
        _L.info(f"uploaded {node.id}")
        return node

    async def _verify(self, local_path: Path, uploaded_node: Node):
        _L.info(f"verifying {local_path}")
        local_hash = await get_file_hash(local_path, pool=self._pool, drive=self._drive)
        if local_hash != uploaded_node.hash:
            _L.info(f"removing {uploaded_node.name}")
            await self._drive.move(uploaded_node, trashed=True)
            _L.info(f"removed {uploaded_node.name}")
            raise Exception("hash mismatch")
        _L.info(f"verified {uploaded_node.hash}")

    async def _rename_remote(self, origin: Node):
        await self._drive.move(origin, new_name=f"__{origin.name}")
        _L.debug("confirming rename")
        while True:
            await _wait_for_sync(self._drive)
            new_node = await self._drive.get_node_by_id(origin.id)
            if new_node.name != origin.name:
                break
            await asyncio.sleep(1)
        _L.debug("rename confirmed")

    async def _restore_remote(self, origin: Node):
        await self._drive.move(origin, new_name=origin.name)
        _L.debug("confirming restore")
        while True:
            await _wait_for_sync(self._drive)
            new_node = await self._drive.get_node_by_id(origin.id)
            if new_node.name == origin.name:
                break
            await asyncio.sleep(1)
        _L.debug("restore confirmed")

    async def _delete_remote(self, origin: Node):
        _L.info(f"removing {origin.name}")
        await self._drive.move(origin, trashed=True)
        await _wait_for_sync(self._drive)
        _L.info(f"removed {origin.name}")


class LocalSink:
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    async def store(
        self, local_path: Path, origin: FileItem, media_info: MediaInfo
    ) -> FileItem:
        self._output_dir.mkdir(exist_ok=True, parents=True)
        dest = self._output_dir / local_path.name
        _L.info(f"copying {local_path} -> {dest}")
        shutil.copy2(local_path, dest)
        _L.info(f"copied to {dest}")
        return origin

    def quota_used(self) -> int:
        return 0


async def _wait_for_sync(drive: Drive):
    async for change in drive.sync():
        _L.debug(change)
