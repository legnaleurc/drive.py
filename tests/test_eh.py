import asyncio
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml

from app.eh._main import _main
from app.eh._types import CrawledData


class TestMain(unittest.TestCase):
    def test_scans_immediate_entries_in_descending_item_id_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            newest = root / "[Author] Newest [20].7z"
            oldest = root / "[Author] Oldest [10].7z"
            nested_root = root / "nested"
            newest.write_text("")
            oldest.write_text("")
            nested_root.mkdir()
            (nested_root / "[Author] Nested [30].7z").write_text("")
            (root / "unmatched.txt").write_text("")

            drive = AsyncMock()
            drive.get_children.return_value = []
            drive_context = AsyncMock()
            drive_context.__aenter__.return_value = drive
            crawled = CrawledData(title="result", url="https://example.com/result")
            stdout = io.StringIO()

            with (
                patch(
                    "app.eh._main.create_default_drive",
                    return_value=drive_context,
                    create=True,
                ),
                patch("app.eh._main.crawl", AsyncMock(return_value=[crawled])) as crawl,
                patch("app.eh._main.asyncio.sleep", AsyncMock()) as sleep,
                redirect_stdout(stdout),
            ):
                result = asyncio.run(_main([str(root)]))

            self.assertEqual(result, 0)
            self.assertEqual(
                yaml.safe_load(stdout.getvalue()),
                [
                    {
                        "name": newest.name,
                        "nyaa": [
                            {
                                "title": crawled.title,
                                "url": crawled.url,
                            }
                        ],
                    },
                    {
                        "name": oldest.name,
                        "nyaa": [
                            {
                                "title": crawled.title,
                                "url": crawled.url,
                            }
                        ],
                    },
                ],
            )
            self.assertEqual(
                [call.args[0].title for call in crawl.await_args_list],
                ["Newest", "Oldest"],
            )
            self.assertEqual(sleep.await_count, 2)

    def test_expands_user_path_and_omits_empty_crawl_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "library"
            root.mkdir()
            archive = root / "[Author] Title [10].7z"
            archive.write_text("")
            stdout = io.StringIO()

            with (
                patch.dict(os.environ, {"HOME": directory}),
                patch("app.eh._main.crawl", AsyncMock(return_value=[])) as crawl,
                patch("app.eh._main.asyncio.sleep", AsyncMock()) as sleep,
                redirect_stdout(stdout),
            ):
                try:
                    result = asyncio.run(_main(["~/library"]))
                except OSError as error:
                    self.fail(f"user path was not expanded: {error}")

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "")
            crawl.assert_awaited_once()
            sleep.assert_not_awaited()

    def test_rejects_missing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"

            with self.assertRaises(FileNotFoundError):
                asyncio.run(_main([str(missing)]))

    def test_rejects_non_directory_path(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "archive.7z"
            file_path.write_text("")

            with self.assertRaises(NotADirectoryError):
                asyncio.run(_main([str(file_path)]))


if __name__ == "__main__":
    unittest.main()
