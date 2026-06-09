import asyncio
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from app.lfs._scripter import script


class TestScript(unittest.TestCase):
    def test_video_that_needs_no_processing_is_moved(self):
        data = {
            "root": "/input",
            "files": [
                {
                    "path": "/input/movie.mp4",
                    "drop_title": False,
                    "meta": {
                        "video_codec": "AVC",
                        "is_mp4": True,
                        "is_faststart": True,
                        "title": None,
                        "audios": [
                            {
                                "index": 0,
                                "is_aac": True,
                                "enabled": True,
                                "tags": None,
                            }
                        ],
                        "subtitles": [],
                    },
                }
            ],
        }
        stdin = io.StringIO(yaml.safe_dump(data))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), redirect_stdout(stdout):
            asyncio.run(script(output_dir=Path("/output")))

        self.assertEqual(
            stdout.getvalue(),
            "mkdir -p /output\nmv /input/movie.mp4 /output/movie.mp4\n",
        )
