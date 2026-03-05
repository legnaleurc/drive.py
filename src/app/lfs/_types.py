from typing import TypedDict


class SubtitleStream(TypedDict):
    index: int
    enabled: bool
    tags: dict | None


class AudioStream(TypedDict):
    index: int
    is_aac: bool
    enabled: bool
    tags: dict | None


class MediaContainer(TypedDict):
    video_codec: str
    is_mp4: bool
    is_faststart: bool
    title: str | None
    audios: list[AudioStream]
    subtitles: list[SubtitleStream]


class MediaDescriptor(TypedDict):
    path: str
    drop_title: bool
    meta: MediaContainer
