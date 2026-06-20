import shlex
import sys
from pathlib import Path

import yaml

from ._operations import VIDEO_CODEC_SET, get_operation_paths, needs_processing
from ._types import AudioStream, MediaDescriptor, SubtitleStream


H264_PRESET = "veryslow"
H264_CRF = "18"
MP4_FLAGS = "+faststart"

TRANSCODE_FUNCTION_TEMPLATE = """\
transcode() {
    src=$1
    tmp=$2
    old=$3
    final=$4
    shift 4

    if [ -e "$old" ] && [ -e "$final" ]; then
        if { [ "$src" = "$final" ] || [ ! -e "$src" ]; } && [ ! -e "$tmp" ]; then
            return 0
        fi
        echo "inconsistent transcode state: $src" >&2
        return 1
    fi

    if [ -e "$old" ] && [ -e "$tmp" ]; then
        if [ ! -e "$src" ] && [ ! -e "$final" ]; then
            mv -- "$tmp" "$final"
            return 0
        fi
        echo "inconsistent transcode state: $src" >&2
        return 1
    fi

    if [ -e "$old" ] || { [ "$src" != "$final" ] && [ -e "$final" ]; }; then
        echo "inconsistent transcode state: $src" >&2
        return 1
    fi

    if [ ! -e "$src" ]; then
        echo "inconsistent transcode state: $src" >&2
        return 1
    fi

    ffmpeg -nostdin -y -i "$src" "$@" -movflags @MP4_FLAGS@ "$tmp"
    mv -- "$src" "$old"
    mv -- "$tmp" "$final"
}
"""


async def script() -> None:
    data = yaml.safe_load(sys.stdin)
    files: list[MediaDescriptor] = data["files"]
    files = [file_data for file_data in files if needs_processing(file_data)]

    print("set -e")
    if not files:
        return

    print()
    print(
        TRANSCODE_FUNCTION_TEMPLATE.replace(
            "@MP4_FLAGS@", shlex.quote(MP4_FLAGS)
        )
    )
    for file_data in files:
        paths = get_operation_paths(Path(file_data["path"]))
        cmd = [
            "transcode",
            str(paths.source),
            str(paths.temporary),
            str(paths.backup),
            str(paths.final),
            *_build_ffmpeg_options(file_data["meta"], file_data["drop_title"]),
        ]
        print(shlex.join(cmd))


def _build_ffmpeg_options(meta: dict, drop_title: bool) -> list[str]:
    video_codec = meta["video_codec"]
    audios: list[AudioStream] = meta["audios"]
    subtitles: list[SubtitleStream] = meta["subtitles"]

    video_cmd = _get_video_cmd(video_codec)
    audio_cmd = _get_audio_cmd(audios)
    subtitle_cmd = _get_subtitle_cmd(subtitles)
    title_cmd = _get_title_cmd(drop_title)

    return video_cmd + audio_cmd + subtitle_cmd + title_cmd


def _get_video_cmd(video_codec: str) -> list[str]:
    mapping = ["-map", "0:v:0"]
    if video_codec in VIDEO_CODEC_SET:
        return mapping + ["-c:v", "copy"]
    else:
        return mapping + ["-c:v", "libx264", "-crf", H264_CRF, "-preset", H264_PRESET]


def _get_audio_cmd(audios: list[AudioStream]) -> list[str]:
    rv: list[str] = []
    for audio in audios:
        if not audio["enabled"]:
            continue
        index = audio["index"]
        is_aac = audio["is_aac"]
        mapping = ["-map", f"0:a:{index}"]
        if is_aac:
            rv += mapping + ["-c:a", "copy"]
        else:
            rv += mapping
    return rv


def _get_subtitle_cmd(subtitles: list[SubtitleStream]) -> list[str]:
    rv: list[str] = []
    for subtitle in subtitles:
        if not subtitle["enabled"]:
            continue
        index = subtitle["index"]
        rv += ["-map", f"0:s:{index}"]
    return rv


def _get_title_cmd(drop_title: bool) -> list[str]:
    if drop_title:
        return ["-metadata", "title="]
    return []
