import shlex
import sys
from pathlib import Path

import yaml

from ._types import AudioStream, MediaDescriptor, SubtitleStream


H264_PRESET = "veryslow"
H264_CRF = "18"
MP4_FLAGS = "+faststart"
VIDEO_CODEC_SET = {"AVC", "HEVC"}


async def generate(output_dir: Path | None = None) -> None:
    data = yaml.safe_load(sys.stdin)
    root = data["root"]
    files: list[MediaDescriptor] = data["files"]

    for file_data in files:
        src = file_data["path"]
        drop_title = file_data["drop_title"]
        meta = file_data["meta"]
        copy = (
            meta["video_codec"] in VIDEO_CODEC_SET
            and meta["is_mp4"]
            and meta["is_faststart"]
            and all(a["is_aac"] for a in meta["audios"])
            and all(a["enabled"] for a in meta["audios"])
            and not any(s["enabled"] for s in meta["subtitles"])
            and not drop_title
        )

        if output_dir is not None:
            dst = output_dir / Path(src).relative_to(root)
            dst = dst.with_suffix(".mp4")
        else:
            dst = Path(src).with_suffix(".mp4")

        mkdir_cmd = f"mkdir -p {shlex.quote(str(dst.parent))}"

        if copy:
            print(mkdir_cmd)
            print(shlex.join(["cp", src, str(dst)]))
        else:
            print(mkdir_cmd)
            cmd = _build_ffmpeg_cmd(src, str(dst), meta, drop_title)
            print(shlex.join(cmd))


def _build_ffmpeg_cmd(src: str, dst: str, meta: dict, drop_title: bool) -> list[str]:
    video_codec = meta["video_codec"]
    audios: list[AudioStream] = meta["audios"]
    subtitles: list[SubtitleStream] = meta["subtitles"]

    main_cmd = ["ffmpeg", "-nostdin", "-y"]
    src_cmd = ["-i", src]
    video_cmd = _get_video_cmd(video_codec)
    audio_cmd = _get_audio_cmd(audios)
    subtitle_cmd = _get_subtitle_cmd(subtitles)
    title_cmd = _get_title_cmd(drop_title)
    dst_cmd = ["-movflags", MP4_FLAGS, dst]

    return (
        main_cmd + src_cmd + video_cmd + audio_cmd + subtitle_cmd + title_cmd + dst_cmd
    )


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
