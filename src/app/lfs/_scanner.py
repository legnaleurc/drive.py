import sys
from collections.abc import Iterator
from pathlib import Path

import magic
import yaml
from pymediainfo import MediaInfo, Track

from ._types import AudioStream, MediaContainer, MediaDescriptor, SubtitleStream


async def scan(root_path: Path) -> None:
    files: list[MediaDescriptor] = []
    for file_path in _walk(root_path):
        meta = _transform(file_path)
        files.append({"path": str(file_path), "drop_title": False, "meta": meta})

    data: dict[str, object] = {"root": str(root_path), "files": files}
    yaml.safe_dump(
        data,
        sys.stdout,
        encoding="utf-8",
        allow_unicode=True,
        default_flow_style=False,
    )


def _walk(root_path: Path) -> Iterator[Path]:
    for root, _, files in root_path.walk():
        for file_ in files:
            file_path = root / file_

            if not _is_video(file_path):
                continue

            yield file_path


def _is_video(file_path: Path) -> bool:
    mime_type = magic.from_file(file_path, mime=True)  # type: ignore
    return mime_type.startswith("video/")


def _get_tags(track: Track) -> dict[str, object] | None:
    language = getattr(track, "language", None)
    if language is None:
        return None
    return {"language": language}


def _transform(file_path: Path) -> MediaContainer:
    media_info = MediaInfo.parse(
        file_path,
        mediainfo_options={"File_TestContinuousFileNames": "0"},
        output=None,
    )

    general = media_info.general_tracks[0]
    is_mp4 = general.format == "MPEG-4"
    is_faststart = general.isstreamable == "Yes"
    title = getattr(general, "title", None)

    video_codec = media_info.video_tracks[0].format if media_info.video_tracks else ""

    audios: list[AudioStream] = [
        {
            "index": i,
            "is_aac": t.format == "AAC",
            "enabled": True,
            "tags": _get_tags(t),
        }
        for i, t in enumerate(media_info.audio_tracks)
    ]
    subtitles: list[SubtitleStream] = [
        {
            "index": i,
            "enabled": False,
            "tags": _get_tags(t),
        }
        for i, t in enumerate(media_info.text_tracks)
    ]

    return {
        "video_codec": video_codec,
        "is_mp4": is_mp4,
        "is_faststart": is_faststart,
        "title": title,
        "audios": audios,
        "subtitles": subtitles,
    }
