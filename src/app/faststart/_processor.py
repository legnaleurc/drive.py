import asyncio
import shutil
import subprocess
from contextlib import contextmanager
from logging import getLogger
from os.path import splitext
from pathlib import Path

from wcpan.drive.cli.lib import get_video_info

from ._backend import SinkBackend, SourceBackend
from ._cache import has_cache, is_migrated, need_transcode, set_cache, unset_cache
from ._types import FileItem


VIDEO_CODEC_SET = {"AVC", "HEVC"}
H264_PRESET = "veryslow"
H264_CRF = "18"
MP4_FLAGS = "+faststart"

DAILY_UPLOAD_QUOTA = 500 * 1024 * 1024 * 1024


_L = getLogger(__name__)


class VideoProcessor(object):
    def __init__(
        self,
        *,
        work_folder: Path,
        dsn: Path,
        source: SourceBackend,
        sink: SinkBackend,
        item: FileItem,
    ):
        self.work_folder = work_folder
        self.dsn = dsn
        self._source = source
        self._sink = sink
        self._item = item
        # implies mp4
        self.is_faststart = False
        self.is_h264 = False
        self.is_aac = False

    async def prepare_codec_info(self) -> None:
        raise NotImplementedError()

    @property
    def transcoded_file_name(self) -> str:
        raise NotImplementedError()

    @property
    def codec_command(self) -> list[str]:
        # codec options
        if self.is_h264:
            vc = ["-c:v", "copy"]
        else:
            vc = ["-c:v", "libx264", "-crf", H264_CRF, "-preset", H264_PRESET]
        if self.is_aac:
            ac = ["-c:a", "copy"]
        else:
            ac = []
        # muxer options
        fast_start = ["-movflags", MP4_FLAGS]
        # keeps subtitles if possible
        all_streams = ["-map", "0"]
        # increase frame queue to fix corrupted frames
        frame_queue = ["-max_muxing_queue_size", "1024"]
        return fast_start + ac + vc + all_streams + frame_queue

    @property
    def output_folder(self) -> Path:
        folder = self.work_folder / self._item.id
        return folder

    @property
    def raw_file_path(self) -> Path:
        return self.output_folder / f"__{self._item.name}"

    @property
    def transcoded_file_path(self) -> Path:
        return self.output_folder / self.transcoded_file_name

    def update_codec_from_media_info(self):
        from pymediainfo import MediaInfo

        media_info = MediaInfo.parse(
            self.raw_file_path,
            mediainfo_options={"File_TestContinuousFileNames": "0"},
            output=None,
        )

        self.is_faststart = all(
            track.isstreamable == "Yes" for track in media_info.general_tracks
        )
        self.is_aac = all(track.format == "AAC" for track in media_info.audio_tracks)
        self.is_h264 = all(
            track.format in VIDEO_CODEC_SET for track in media_info.video_tracks
        )

    @property
    def is_skippable(self) -> bool:
        return self.is_faststart and self.is_native_codec

    @property
    def is_native_codec(self) -> bool:
        return self.is_h264 and self.is_aac

    async def __call__(
        self,
        *,
        remux_only: bool,
        transcode_only: bool,
        cache_only: bool,
    ):
        if is_migrated(self.dsn, self._item):
            _L.info("(cache) already migrated, skip")
            return False

        if (
            transcode_only
            and has_cache(self.dsn, self._item)
            and not need_transcode(self.dsn, self._item)
        ):
            _L.info("no need transcode, skip")
            return False

        if (
            remux_only
            and has_cache(self.dsn, self._item)
            and need_transcode(self.dsn, self._item)
        ):
            _L.info("need transcode, skip")
            return False

        if cache_only and has_cache(self.dsn, self._item):
            _L.info("already cached, skip")
            return False

        if (
            not cache_only
            and (self._sink.quota_used() + self._item.size) >= DAILY_UPLOAD_QUOTA
        ):
            _L.info("not enough quota, skip")
            return False

        with self._local_context():
            try:
                await self._download()
            except Exception:
                _L.exception("download failed")
                return True

            try:
                await self.prepare_codec_info()
            except Exception:
                _L.exception("ffmpeg failed")
                return True
            if self.is_skippable:
                _L.info("nothing to do, skip")
                set_cache(self.dsn, self._item, True, True)
                return True

            set_cache(self.dsn, self._item, self.is_faststart, self.is_native_codec)

            if remux_only and not self.is_native_codec:
                _L.info("need transcode, skip")
                return True

            if transcode_only and self.is_native_codec:
                _L.info("no need transcode, skip")
                return True

            if cache_only:
                _L.info("cached, skip")
                return True

            self._dump_info()
            transcode_command = self._get_transcode_command()
            _L.info(" ".join(transcode_command))

            exit_code = await _shell_call(transcode_command, self.output_folder)
            if exit_code != 0:
                _L.error("ffmpeg failed")
                return True
            media_info = get_video_info(self.transcoded_file_path)
            _L.info(media_info)

            result_item = await self._sink.store(
                self.transcoded_file_path, self._item, media_info
            )
            if result_item.id != self._item.id:
                unset_cache(self.dsn, self._item)
            set_cache(self.dsn, result_item, True, True)
            return True

    def _get_transcode_command(self):
        main_cmd = ["ffmpeg", "-nostdin", "-y"]
        input_cmd = ["-i", str(self.raw_file_path)]
        codec_cmd = self.codec_command
        output_path = self.transcoded_file_path
        cmd = main_cmd + input_cmd + codec_cmd + [str(output_path)]
        return cmd

    async def _download(self):
        _L.info(f"fetching {self._item.name}")
        output_folder = self.output_folder
        fetched_path = await self._source.fetch(self._item, output_folder)
        output_path = self.raw_file_path
        fetched_path.rename(output_path)
        _L.info(f"fetched {self._item.name}")

    def _dump_info(self):
        _L.info(f"item id: {self._item.id}")
        _L.info(f"item name: {self._item.name}")
        _L.info(f"is faststart: {self.is_faststart}")
        _L.info(f"is h264: {self.is_h264}")
        _L.info(f"is aac: {self.is_aac}")

    @contextmanager
    def _local_context(self):
        output_folder = self.output_folder
        output_folder.mkdir(exist_ok=True)
        try:
            yield
        finally:
            shutil.rmtree(output_folder)
            _L.info(f"deleted {output_folder}")


class MP4Processor(VideoProcessor):
    def __init__(
        self,
        *,
        work_folder: Path,
        dsn: Path,
        source: SourceBackend,
        sink: SinkBackend,
        item: FileItem,
    ):
        super().__init__(
            work_folder=work_folder,
            dsn=dsn,
            source=source,
            sink=sink,
            item=item,
        )

    async def prepare_codec_info(self):
        self.update_codec_from_media_info()

    @property
    def transcoded_file_name(self):
        return self._item.name


class MaybeH264Processor(VideoProcessor):
    def __init__(
        self,
        *,
        work_folder: Path,
        dsn: Path,
        source: SourceBackend,
        sink: SinkBackend,
        item: FileItem,
    ):
        super().__init__(
            work_folder=work_folder,
            dsn=dsn,
            source=source,
            sink=sink,
            item=item,
        )

    async def prepare_codec_info(self):
        self.update_codec_from_media_info()
        self.is_faststart = False

    @property
    def transcoded_file_name(self):
        name, _ext = splitext(self._item.name)
        return name + ".mp4"


class MKVProcessor(VideoProcessor):
    def __init__(
        self,
        *,
        work_folder: Path,
        dsn: Path,
        source: SourceBackend,
        sink: SinkBackend,
        item: FileItem,
    ):
        super().__init__(
            work_folder=work_folder,
            dsn=dsn,
            source=source,
            sink=sink,
            item=item,
        )

    async def prepare_codec_info(self):
        self.update_codec_from_media_info()
        self.is_faststart = False

    @property
    def transcoded_file_name(self):
        name, _ext = splitext(self._item.name)
        return name + ".mp4"


class NeverH264Processor(VideoProcessor):
    def __init__(
        self,
        *,
        work_folder: Path,
        dsn: Path,
        source: SourceBackend,
        sink: SinkBackend,
        item: FileItem,
    ):
        super().__init__(
            work_folder=work_folder,
            dsn=dsn,
            source=source,
            sink=sink,
            item=item,
        )

    async def prepare_codec_info(self):
        self.update_codec_from_media_info()
        self.is_faststart = False

    @property
    def transcoded_file_name(self):
        name, _ext = splitext(self._item.name)
        return name + ".mp4"


async def _shell_call(cmd_list: list[str], folder: Path):
    with open(folder / "shell.log", "ab") as out:
        p = await asyncio.create_subprocess_exec(
            *cmd_list, stdout=out, stderr=subprocess.STDOUT
        )
        return await p.wait()


_PROCESSOR_TABLE: dict[str, type[VideoProcessor]] = {
    "video/mp4": MP4Processor,
    "video/x-matroska": MKVProcessor,
    "video/x-msvideo": MaybeH264Processor,
    "video/x-ms-wmv": NeverH264Processor,
    "video/quicktime": MaybeH264Processor,
    "video/mpeg": MaybeH264Processor,
}


def create_processor(
    *,
    work_folder: Path,
    dsn: Path,
    source: SourceBackend,
    sink: SinkBackend,
    item: FileItem,
) -> VideoProcessor | None:
    if item.mime_type in _PROCESSOR_TABLE:
        constructor = _PROCESSOR_TABLE[item.mime_type]
        return constructor(
            work_folder=work_folder,
            dsn=dsn,
            source=source,
            sink=sink,
            item=item,
        )
    return None
