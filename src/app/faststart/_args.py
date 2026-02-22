from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class KeywordArguments:
    data_path: Path
    root_path_list: list[PurePath]
    remux_only: bool
    transcode_only: bool
    cache_only: bool
    jobs: int
    tmp_path: Path | None
    source: Literal["drive", "local"]
    sink: Literal["drive", "local"]
    output_path: Path | None


def parse_args(args: list[str]) -> KeywordArguments:
    parser = ArgumentParser("app")

    parser.add_argument("--data-path", required=True, type=str)
    parser.add_argument("--tmp-path", type=str)
    parser.add_argument("--jobs", "-j", default=1)
    parser.add_argument("--source", choices=["drive", "local"], default="drive")
    parser.add_argument("--sink", choices=["drive", "local"], default="drive")
    parser.add_argument("--output", type=str)

    mutex_group = parser.add_mutually_exclusive_group()
    mutex_group.add_argument("--remux-only", action="store_true", default=False)
    mutex_group.add_argument("--transcode-only", action="store_true", default=False)
    mutex_group.add_argument("--cache-only", action="store_true", default=False)

    parser.add_argument("root_path", type=str, nargs="+")

    kwargs = parser.parse_args(args)

    if kwargs.sink == "local" and not kwargs.output:
        parser.error("--output is required when --sink=local")

    if kwargs.source == "local":
        root_path_list: list[PurePath] = [
            Path(_).expanduser().resolve() for _ in kwargs.root_path
        ]
    else:
        root_path_list = [PurePath(_) for _ in kwargs.root_path]

    return KeywordArguments(
        data_path=Path(kwargs.data_path).expanduser().resolve(),
        root_path_list=root_path_list,
        remux_only=kwargs.remux_only,
        transcode_only=kwargs.transcode_only,
        cache_only=kwargs.cache_only,
        jobs=kwargs.jobs,
        tmp_path=None if not kwargs.tmp_path else Path(kwargs.tmp_path),
        source=kwargs.source,
        sink=kwargs.sink,
        output_path=(
            None if not kwargs.output else Path(kwargs.output).expanduser().resolve()
        ),
    )
