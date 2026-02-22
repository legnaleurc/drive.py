#! /usr/bin/env python3

from contextlib import AsyncExitStack
from logging import getLogger
from logging.config import dictConfig
from pathlib import Path
from tempfile import TemporaryDirectory

from wcpan.drive.cli.lib import create_executor
from wcpan.logging import ConfigBuilder
from wcpan.queue import AioQueue

from app.lib import create_default_drive

from ._args import KeywordArguments, parse_args
from ._backend import (
    DriveSink,
    DriveSource,
    LocalSink,
    LocalSource,
    SinkBackend,
    SourceBackend,
)
from ._cache import initialize_cache
from ._processor import create_processor
from ._types import FileItem


_L = getLogger(__name__)


async def main(args: list[str]):
    kwargs = parse_args(args)

    kwargs.data_path.mkdir(exist_ok=True, parents=True)

    dsn = kwargs.data_path / "_migrated.sqlite"
    initialize_cache(dsn)
    dictConfig(
        ConfigBuilder(path=kwargs.data_path / "migrate.log")
        .add("wcpan")
        .add("app", level="D")
        .to_dict()
    )

    async with AsyncExitStack() as stack:
        pool = stack.enter_context(create_executor())
        work_folder = Path(stack.enter_context(TemporaryDirectory(dir=kwargs.tmp_path)))
        queue = stack.enter_context(AioQueue[None].fifo())

        drive = None
        if kwargs.source == "drive" or kwargs.sink == "drive":
            drive = await stack.enter_async_context(create_default_drive())
            async for change in drive.sync():
                _L.debug(change)

        source = _create_source(kwargs, drive)
        sink = _create_sink(kwargs, drive, pool)

        async for file_ in source.walk(kwargs.root_path_list):
            await queue.push(
                item_work(
                    file_,
                    source=source,
                    sink=sink,
                    work_folder=work_folder,
                    dsn=dsn,
                    remux_only=kwargs.remux_only,
                    transcode_only=kwargs.transcode_only,
                    cache_only=kwargs.cache_only,
                )
            )

        await queue.consume(kwargs.jobs)

    return 0


def _create_source(kwargs: KeywordArguments, drive) -> SourceBackend:
    if kwargs.source == "drive":
        assert drive is not None
        return DriveSource(drive)
    return LocalSource()


def _create_sink(kwargs: KeywordArguments, drive, pool) -> SinkBackend:
    if kwargs.sink == "drive":
        assert drive is not None
        same_location = kwargs.source == "drive"
        return DriveSink(drive, pool, same_location=same_location)
    assert kwargs.output_path is not None
    return LocalSink(kwargs.output_path)


async def item_work(
    item: FileItem,
    *,
    source: SourceBackend,
    sink: SinkBackend,
    work_folder: Path,
    dsn: Path,
    remux_only: bool,
    transcode_only: bool,
    cache_only: bool,
):
    processor = create_processor(
        work_folder=work_folder, dsn=dsn, source=source, sink=sink, item=item
    )
    if not processor:
        return

    _L.info(f"begin {item.name}")
    did_work = await processor(
        remux_only=remux_only,
        transcode_only=transcode_only,
        cache_only=cache_only,
    )
    _L.info(f"did_work={did_work}, end {item.name}")
