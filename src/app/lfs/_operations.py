from pathlib import Path
from typing import NamedTuple

from ._types import MediaDescriptor


VIDEO_CODEC_SET = {"AVC", "HEVC"}


class OperationPaths(NamedTuple):
    source: Path
    temporary: Path
    backup: Path
    final: Path


def needs_processing(file_data: MediaDescriptor) -> bool:
    meta = file_data["meta"]
    return not (
        meta["video_codec"] in VIDEO_CODEC_SET
        and meta["is_mp4"]
        and meta["is_faststart"]
        and all(audio["is_aac"] for audio in meta["audios"])
        and all(audio["enabled"] for audio in meta["audios"])
        and not any(subtitle["enabled"] for subtitle in meta["subtitles"])
        and not file_data["drop_title"]
    )


def get_operation_paths(source: Path) -> OperationPaths:
    return OperationPaths(
        source=source,
        temporary=source.with_name(f"{source.stem}.tmp.mp4"),
        backup=source.with_name(f"{source.stem}.old{source.suffix}"),
        final=source.with_suffix(".mp4"),
    )
