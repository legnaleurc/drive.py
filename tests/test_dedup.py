import copy
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from app.dedup import _main as dedup_main
from app.dedup._analyze import build_manifest
from app.dedup._apply import apply
from app.dedup._matching import levenshtein_similarity, parse_archive_name


def _apply_manifest(manifest: object) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(yaml.safe_dump(manifest, allow_unicode=True))),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = apply()
    return result, stdout.getvalue(), stderr.getvalue()


def _run_main(args: list[str], stdin: str = "") -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(stdin)),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = dedup_main.main(args)
    return result, stdout.getvalue(), stderr.getvalue()


class TestParseArchiveName(unittest.TestCase):
    def test_parses_supported_metadata_without_changing_the_title(self):
        first = parse_archive_name(
            "[Sample Circle (Artist)] Clockwork Garden [DL版] [1234567].7z"
        )
        second = parse_archive_name(
            "(架空即売会42) [Sample Circle (Artist)] "
            "Clockwork Garden (オリジナル) [DL版].zip"
        )
        different = parse_archive_name(
            "(Fiction Expo 7) [Sample Circle (Artist)] "
            "AClockwork Garden (オリジナル) [DL版].zip"
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertIsNotNone(different)
        assert first is not None
        assert second is not None
        assert different is not None
        self.assertEqual(first.creator, second.creator)
        self.assertEqual(first.title, "Clockwork Garden")
        self.assertEqual(second.title, first.title)
        self.assertEqual(different.title, "AClockwork Garden")
        self.assertNotEqual(different.title, first.title)
        self.assertEqual(first.archive_type, "7z")
        self.assertEqual(second.archive_type, "zip")

    def test_preserves_unrecognized_trailing_parenthetical_as_title_text(self):
        parsed = parse_archive_name(
            "(Imaginary Market 12) [Sample Circle] Clockwork Garden (Anthology).zip"
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.title, "Clockwork Garden (Anthology)")


class TestLevenshteinSimilarity(unittest.TestCase):
    def test_reports_normalized_similarity(self):
        self.assertEqual(levenshtein_similarity("same", "same"), 1.0)
        self.assertAlmostEqual(levenshtein_similarity("abc", "xbc"), 2 / 3)
        self.assertEqual(levenshtein_similarity("", "abc"), 0.0)


class TestBuildManifest(unittest.TestCase):
    def test_groups_exact_cross_format_duplicates_and_excludes_different_title(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seven_zip = root / (
                "[Sample Circle (Artist)] Clockwork Garden [DL版] [1234567].7z"
            )
            matching_zip = root / (
                "(架空即売会42) [Sample Circle (Artist)] "
                "Clockwork Garden (オリジナル) [DL版].zip"
            )
            different_zip = root / (
                "(Fiction Expo 7) [Sample Circle (Artist)] "
                "AClockwork Garden (オリジナル) [DL版].zip"
            )
            seven_zip.write_text("seven")
            matching_zip.write_text("zip")
            different_zip.write_text("different")

            manifest = build_manifest(root)

            self.assertEqual(manifest["version"], 1)
            self.assertEqual(len(manifest["groups"]), 1)
            group = manifest["groups"][0]
            self.assertEqual(group["match"], "exact")
            self.assertEqual(group["creator"], "Sample Circle (Artist)")
            self.assertEqual(
                [item["path"] for item in group["keep"]], [str(matching_zip)]
            )
            self.assertEqual(
                [item["path"] for item in group["candidates"]],
                [str(seven_zip)],
            )
            self.assertEqual(group["candidates"][0]["similarity"], 1.0)
            self.assertIs(group["candidates"][0]["remove"], True)

    def test_emits_best_fuzzy_match_for_manual_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seven_zip = root / "[Circle] Clockwork Garden [1].7z"
            close_zip = root / "[Circle] AClockwork Garden.zip"
            distant_zip = root / "[Circle] Distant Shore.zip"
            seven_zip.write_text("seven")
            close_zip.write_text("close")
            distant_zip.write_text("distant")

            manifest = build_manifest(root)

            self.assertEqual(len(manifest["groups"]), 1)
            group = manifest["groups"][0]
            self.assertEqual(group["match"], "fuzzy")
            self.assertEqual(group["keep"][0]["path"], str(close_zip))
            candidate = group["candidates"][0]
            self.assertEqual(candidate["path"], str(seven_zip))
            self.assertGreaterEqual(candidate["similarity"], 0.9)
            self.assertIs(candidate["remove"], False)

    def test_ignores_nested_symlink_and_unsupported_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Title.zip"
            target = root / "target.7z"
            nested = root / "nested"
            keeper.write_text("keeper")
            target.write_text("target")
            (root / "[Circle] Title.7z").symlink_to(target)
            (root / "[Circle] Title.rar").write_text("rar")
            nested.mkdir()
            (nested / "[Circle] Title.7z").write_text("nested")

            manifest = build_manifest(root)

            self.assertEqual(manifest, {"version": 1, "groups": []})


class TestApply(unittest.TestCase):
    def test_removes_selected_unchanged_7z_and_keeps_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Title.zip"
            duplicate = root / "[Circle] Title [1].7z"
            keeper.write_text("keeper")
            duplicate.write_text("duplicate")
            manifest = build_manifest(root)

            result, stdout, stderr = _apply_manifest(manifest)

            self.assertEqual(result, 0)
            self.assertEqual(stdout, f"remove: {duplicate}\n")
            self.assertEqual(stderr, "")
            self.assertTrue(keeper.exists())
            self.assertFalse(duplicate.exists())

    def test_does_not_remove_disabled_fuzzy_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Black Title.zip"
            candidate = root / "[Circle] Black Titles.7z"
            keeper.write_text("keeper")
            candidate.write_text("candidate")
            manifest = build_manifest(root)
            self.assertEqual(manifest["groups"][0]["match"], "fuzzy")

            result, stdout, stderr = _apply_manifest(manifest)

            self.assertEqual(result, 0)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertTrue(keeper.exists())
            self.assertTrue(candidate.exists())

    def test_reports_stale_candidate_and_continues_with_later_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale_keeper = root / "[A] One.zip"
            stale = root / "[A] One.7z"
            valid_keeper = root / "[B] Two.zip"
            valid = root / "[B] Two.7z"
            for path in (stale_keeper, stale, valid_keeper, valid):
                path.write_text(path.name)
            manifest = build_manifest(root)
            stale.write_text("changed after analysis")

            result, stdout, stderr = _apply_manifest(manifest)

            self.assertEqual(result, 1)
            self.assertIn(str(stale), stderr)
            self.assertIn("changed since analysis", stderr)
            self.assertEqual(stdout, f"remove: {valid}\n")
            self.assertTrue(stale.exists())
            self.assertFalse(valid.exists())

    def test_skips_group_when_no_unchanged_keeper_remains(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Title.zip"
            duplicate = root / "[Circle] Title.7z"
            keeper.write_text("keeper")
            duplicate.write_text("duplicate")
            manifest = build_manifest(root)
            keeper.unlink()

            result, stdout, stderr = _apply_manifest(manifest)

            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertIn("no unchanged ZIP keeper remains", stderr)
            self.assertTrue(duplicate.exists())

    def test_rejects_duplicate_selected_paths_before_removing_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Title.zip"
            duplicate = root / "[Circle] Title.7z"
            keeper.write_text("keeper")
            duplicate.write_text("duplicate")
            manifest = build_manifest(root)
            manifest["groups"].append(manifest["groups"][0].copy())

            with self.assertRaisesRegex(ValueError, "duplicate selected path"):
                _apply_manifest(manifest)

            self.assertTrue(duplicate.exists())

    def test_rejects_lexically_equivalent_duplicate_selected_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keeper = root / "[Circle] Title.zip"
            duplicate = root / "[Circle] Title.7z"
            keeper.write_text("keeper")
            duplicate.write_text("duplicate")
            manifest = build_manifest(root)
            repeated_group = copy.deepcopy(manifest["groups"][0])
            repeated_group["candidates"][0]["path"] = str(
                root / "unused" / ".." / duplicate.name
            )
            manifest["groups"].append(repeated_group)

            with self.assertRaisesRegex(ValueError, "duplicate selected path"):
                _apply_manifest(manifest)

            self.assertTrue(duplicate.exists())


class TestMain(unittest.TestCase):
    def test_analyze_emits_an_empty_versioned_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            result, stdout, stderr = _run_main(["analyze", directory])

            self.assertEqual(result, 0)
            self.assertEqual(yaml.safe_load(stdout), {"version": 1, "groups": []})
            self.assertEqual(stderr, "")

    def test_apply_reports_malformed_manifest_as_command_error(self):
        result, stdout, stderr = _run_main(["apply"], "not: a valid manifest\n")

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("unsupported manifest version", stderr)

    def test_apply_rejects_boolean_manifest_version(self):
        result, stdout, stderr = _run_main(
            ["apply"], yaml.safe_dump({"version": True, "groups": []})
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("unsupported manifest version", stderr)


if __name__ == "__main__":
    unittest.main()
