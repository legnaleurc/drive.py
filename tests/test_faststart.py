import asyncio
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from app.faststart._main import _parse_args, main
from app.faststart._scanner import _walk, scan
from app.faststart._scripter import script


def _file(path: str, *, compliant: bool = False) -> dict:
    return {
        "path": path,
        "drop_title": False,
        "meta": {
            "video_codec": "AVC" if compliant else "VP9",
            "is_mp4": compliant,
            "is_faststart": compliant,
            "title": None,
            "audios": [],
            "subtitles": [],
        },
    }


def _manifest(*files: dict) -> dict:
    return {"root": "/media", "files": list(files)}


def _run_script(data: dict) -> str:
    stdin = io.StringIO(yaml.safe_dump(data))
    stdout = io.StringIO()
    with patch.object(sys, "stdin", stdin), redirect_stdout(stdout):
        asyncio.run(script())
    return stdout.getvalue()


def _run_main(args: list[str], data: dict) -> tuple[int, str, str]:
    stdin = io.StringIO(yaml.safe_dump(data))
    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(sys, "stdin", stdin),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        try:
            result = asyncio.run(main(args))
        except SystemExit as error:
            result = int(error.code)
    return result, stdout.getvalue(), stderr.getvalue()


def _run_generated_script(
    data: dict, *, path: Path | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if path is not None:
        env["PATH"] = f"{path}:{env['PATH']}"
    return subprocess.run(
        ["sh"],
        input=_run_script(data),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _write_fake_ffmpeg(directory: Path) -> Path:
    executable = directory / "ffmpeg"
    executable.write_text(
        "#!/bin/sh\n"
        "for output do :; done\n"
        'printf \'%s\' "${FFMPEG_OUTPUT:-transcoded}" > "$output"\n'
        'test "${FFMPEG_FAIL:-0}" != 1\n'
    )
    executable.chmod(0o755)
    return executable


class TestScript(unittest.TestCase):
    def test_non_mp4_uses_shared_transcode_function(self):
        output = _run_script(_manifest(_file("/media/movie.mkv")))

        self.assertIn("transcode() {\n", output)
        self.assertIn(
            "transcode /media/movie.mkv /media/movie.tmp.mp4 "
            "/media/movie.old.mkv /media/movie.mp4 -map 0:v:0 -c:v libx264 "
            "-crf 18 -preset veryslow\n",
            output,
        )
        self.assertEqual(output.count("ffmpeg -nostdin"), 1)

    def test_mp4_transcode_does_not_reject_source_as_final_collision(self):
        output = _run_script(_manifest(_file("/media/movie.mp4")))

        self.assertIn(
            "transcode /media/movie.mp4 /media/movie.tmp.mp4 "
            "/media/movie.old.mp4 /media/movie.mp4 ",
            output,
        )

    def test_compliant_video_emits_only_fail_fast_setting(self):
        output = _run_script(_manifest(_file("/media/movie.mp4", compliant=True)))

        self.assertEqual(output, "set -e\n")

    def test_generated_commands_quote_paths(self):
        output = _run_script(_manifest(_file("/media/my movie.mkv")))

        self.assertIn(
            "transcode '/media/my movie.mkv' '/media/my movie.tmp.mp4' "
            "'/media/my movie.old.mkv' '/media/my movie.mp4' ",
            output,
        )

    def test_rerun_skips_completed_non_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mkv"
            backup = Path(directory) / "movie.old.mkv"
            final = Path(directory) / "movie.mp4"
            backup.touch()
            final.touch()

            result = _run_generated_script(_manifest(_file(str(source))))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(backup.exists())
            self.assertTrue(final.exists())

    def test_rerun_finishes_interrupted_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mkv"
            temporary = Path(directory) / "movie.tmp.mp4"
            backup = Path(directory) / "movie.old.mkv"
            final = Path(directory) / "movie.mp4"
            temporary.write_text("transcoded")
            backup.touch()

            result = _run_generated_script(_manifest(_file(str(source))))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(temporary.exists())
            self.assertEqual(final.read_text(), "transcoded")

    def test_failed_ffmpeg_output_is_retranscoded_on_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "movie.mkv"
            temporary = root / "movie.tmp.mp4"
            backup = root / "movie.old.mkv"
            final = root / "movie.mp4"
            source.touch()
            _write_fake_ffmpeg(root)
            data = _manifest(_file(str(source)))

            with patch.dict(
                os.environ, {"FFMPEG_FAIL": "1", "FFMPEG_OUTPUT": "broken"}
            ):
                failed = _run_generated_script(data, path=root)

            self.assertNotEqual(failed.returncode, 0)
            self.assertTrue(source.exists())
            self.assertTrue(temporary.exists())
            self.assertEqual(temporary.read_text(), "broken")

            with patch.dict(os.environ, {"FFMPEG_FAIL": "0", "FFMPEG_OUTPUT": "valid"}):
                resumed = _run_generated_script(data, path=root)

            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertFalse(temporary.exists())
            self.assertTrue(backup.exists())
            self.assertEqual(final.read_text(), "valid")

    def test_rerun_rejects_inconsistent_non_mp4_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "movie.mkv"
            backup = root / "movie.old.mkv"
            final = root / "movie.mp4"
            source.touch()
            backup.touch()
            final.touch()

            result = _run_generated_script(_manifest(_file(str(source))))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("inconsistent transcode state", result.stderr)


class TestScan(unittest.TestCase):
    def test_scan_drops_non_null_titles_by_default(self):
        cases = [(None, False), ("Movie Title", True), ("", True)]

        for title, expected in cases:
            with self.subTest(title=title):
                path = Path("/media/movie.mkv")
                meta = _file(str(path))["meta"]
                meta["title"] = title
                stdout = io.StringIO()

                with (
                    patch("app.faststart._scanner._walk", return_value=iter([path])),
                    patch("app.faststart._scanner._transform", return_value=meta),
                    redirect_stdout(stdout),
                ):
                    asyncio.run(scan(Path("/media")))

                data = yaml.safe_load(stdout.getvalue())
                self.assertEqual(data["files"][0]["drop_title"], expected)

    def test_walk_ignores_generated_backup_and_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "movie.mkv"
            backup = root / "movie.old.mkv"
            temporary = root / "movie.tmp.mp4"
            video.touch()
            backup.touch()
            temporary.touch()

            with patch(
                "app.faststart._scanner._is_video", return_value=True
            ) as is_video:
                files = list(_walk(root))

            self.assertEqual(files, [video])
            is_video.assert_called_once_with(video)


class TestCleanup(unittest.TestCase):
    def test_cleanup_removes_backup_when_final_mp4_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mkv"
            backup = Path(directory) / "movie.old.mkv"
            final = Path(directory) / "movie.mp4"
            backup.touch()
            final.touch()

            result, stdout, stderr = _run_main(
                ["cleanup"], _manifest(_file(str(source)))
            )

            self.assertEqual(result, 0)
            self.assertFalse(backup.exists())
            self.assertEqual(stdout, f"removed {backup}\n")
            self.assertEqual(stderr, "")

    def test_cleanup_skips_missing_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mkv"
            final = Path(directory) / "movie.mp4"
            final.touch()

            result, stdout, stderr = _run_main(
                ["cleanup"], _manifest(_file(str(source)))
            )

            self.assertEqual((result, stdout, stderr), (0, "", ""))

    def test_cleanup_preserves_backup_when_final_mp4_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mkv"
            backup = Path(directory) / "movie.old.mkv"
            backup.touch()

            result, stdout, stderr = _run_main(
                ["cleanup"], _manifest(_file(str(source)))
            )

            self.assertEqual(result, 1)
            self.assertTrue(backup.exists())
            self.assertEqual(stdout, "")
            self.assertIn(f"final file not found: {source.with_suffix('.mp4')}", stderr)

    def test_cleanup_ignores_manifest_entries_that_needed_no_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movie.mp4"
            backup = Path(directory) / "movie.old.mp4"
            source.touch()
            backup.touch()

            result, stdout, stderr = _run_main(
                ["cleanup"], _manifest(_file(str(source), compliant=True))
            )

            self.assertEqual((result, stdout, stderr), (0, "", ""))
            self.assertTrue(backup.exists())


class TestArguments(unittest.TestCase):
    def test_script_no_longer_accepts_output_directory(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            _parse_args(["script", "--output", "/output"])
