import unittest

from app.jav import _actress_name_variants, _make_name, _split_keep_tail


class TestActressNameVariants(unittest.TestCase):
    def test_single_name(self):
        self.assertEqual(_actress_name_variants("Alice"), ["Alice"])

    def test_alternate_name(self):
        self.assertEqual(_actress_name_variants("Alice（Emily）"), ["Alice", "Emily"])

    def test_leading_parens(self):
        self.assertEqual(_actress_name_variants("（Alice）"), ["Alice"])

    def test_multiple_variants(self):
        self.assertEqual(
            _actress_name_variants("Alice（Emily）（Sara）"), ["Alice", "Emily", "Sara"]
        )


class TestSplitKeepTail(unittest.TestCase):
    def test_all_actresses_at_end(self):
        head, keep_tail, found = _split_keep_tail("Video 3 Bob Alice", ["Alice", "Bob"])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3 Bob Alice")
        self.assertEqual(found, {0, 1})

    def test_actresses_reversed_order(self):
        head, keep_tail, found = _split_keep_tail("Video 3 Alice Bob", ["Alice", "Bob"])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3 Alice Bob")
        self.assertEqual(found, {0, 1})

    def test_alternate_name_in_title(self):
        # actress listed as "Alice（Emily）" but title has "Emily"
        head, keep_tail, found = _split_keep_tail(
            "Video 3 Emily Bob", ["Alice（Emily）", "Bob"]
        )
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3 Emily Bob")
        self.assertEqual(found, {0, 1})

    def test_canonical_name_in_title(self):
        # actress listed as "Alice（Emily）" and title has "Alice"
        head, keep_tail, found = _split_keep_tail(
            "Video 3 Alice Bob", ["Alice（Emily）", "Bob"]
        )
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3 Alice Bob")
        self.assertEqual(found, {0, 1})

    def test_only_one_actress_at_end(self):
        head, keep_tail, found = _split_keep_tail("Video 3 Alice", ["Alice", "Bob"])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3 Alice")
        self.assertEqual(found, {0})

    def test_no_actress_at_end(self):
        head, keep_tail, found = _split_keep_tail("Video 3", ["Alice", "Bob"])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3")
        self.assertEqual(found, set())

    def test_actress_in_middle_not_stripped(self):
        # actress appears in the middle — should not be detected in tail
        head, keep_tail, found = _split_keep_tail("Alice Video 3", ["Alice", "Bob"])
        self.assertEqual(head, "Alice Video")
        self.assertEqual(keep_tail, "3")
        self.assertEqual(found, set())

    def test_no_series_number(self):
        head, keep_tail, found = _split_keep_tail("Video Bob Alice", ["Alice", "Bob"])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "Bob Alice")
        self.assertEqual(found, {0, 1})

    def test_empty_actresses(self):
        head, keep_tail, found = _split_keep_tail("Video 3", [])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "3")
        self.assertEqual(found, set())

    def test_empty_actresses_no_series(self):
        head, keep_tail, found = _split_keep_tail("Video", [])
        self.assertEqual(head, "Video")
        self.assertEqual(keep_tail, "")
        self.assertEqual(found, set())


class TestMakeName(unittest.TestCase):
    def test_title_already_has_all_actresses(self):
        # No duplication — title is kept intact
        result = _make_name("ID", "Video 3 Bob Alice", ["Alice", "Bob"])
        self.assertEqual(result, "ID Video 3 Bob Alice")

    def test_alternate_name_already_in_title(self):
        result = _make_name("ID", "Video 3 Emily Bob", ["Alice（Emily）", "Bob"])
        self.assertEqual(result, "ID Video 3 Emily Bob")

    def test_title_missing_all_actresses(self):
        result = _make_name("ID", "Video 3", ["Alice", "Bob"])
        self.assertEqual(result, "ID Video 3 Alice Bob")

    def test_title_missing_one_actress(self):
        result = _make_name("ID", "Video 3 Alice", ["Alice", "Bob"])
        self.assertEqual(result, "ID Video 3 Alice Bob")

    def test_actress_at_start_not_appended(self):
        # Alice is at the start — do not append her again
        result = _make_name("ID", "Alice Video 3", ["Alice", "Bob"])
        self.assertEqual(result, "ID Alice Video 3 Bob")

    def test_actress_in_middle_not_appended(self):
        # Alice appears in the middle — do not append her again
        result = _make_name("ID", "Video Alice Story 3", ["Alice", "Bob"])
        self.assertEqual(result, "ID Video Alice Story 3 Bob")

    def test_actress_alternate_name_in_middle_not_appended(self):
        # Alternate name "Emily" is in the middle — do not append "Alice（Emily）"
        result = _make_name("ID", "Video Emily Story 3", ["Alice（Emily）", "Bob"])
        self.assertEqual(result, "ID Video Emily Story 3 Bob")

    def test_empty_actresses(self):
        result = _make_name("ID", "Video 3", [])
        self.assertEqual(result, "ID Video 3")

    def test_truncation_preserves_series_and_actresses(self):
        # "ID " (3) + 253 + " 3 Alice Bob" (12) = 268 > 255 → must truncate
        long_title = "A" * 253 + " 3 Alice Bob"
        result = _make_name("ID", long_title, ["Alice", "Bob"])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("3 Alice Bob"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncation_empty_actresses_preserves_series(self):
        # "ID " (3) + 253 + " 5" (2) = 258 > 255 → must truncate
        long_title = "A" * 253 + " 5"
        result = _make_name("ID", long_title, [])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("5"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_no_truncation_when_fits(self):
        result = _make_name("ID", "Short Title 3", ["Alice"])
        self.assertNotIn("\u2026", result)
        self.assertEqual(result, "ID Short Title 3 Alice")

    def test_truncation_actresses_already_at_end_no_duplication(self):
        # title already ends with actress names; truncation must not re-append them
        # "ID " (3) + 245 + " Alice Bob" (10) = 258 > 255 → must truncate
        long_title = "A" * 245 + " Alice Bob"
        result = _make_name("ID", long_title, ["Alice", "Bob"])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("Alice Bob"))
        self.assertNotIn("Alice Bob Alice Bob", result)
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncation_alternate_name_at_end_no_duplication(self):
        # title ends with the alternate name variant; actress listed as "Alice（Emily）"
        # "ID " (3) + 245 + " Emily Bob" (10) = 258 > 255 → must truncate
        long_title = "A" * 245 + " Emily Bob"
        result = _make_name("ID", long_title, ["Alice（Emily）", "Bob"])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("Emily Bob"))
        self.assertNotIn("Emily Bob Alice", result)
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncation_missing_actresses_appended_and_preserved(self):
        # actresses not in title → appended; truncation must keep series + appended names
        # "ID " (3) + 248 + " 3" (2) + " Alice Bob" (10) = 263 > 255 → must truncate
        long_title = "A" * 248 + " 3"
        result = _make_name("ID", long_title, ["Alice", "Bob"])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("3 Alice Bob"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncation_no_series_number_actresses_at_end(self):
        # no series number; actresses at end form the entire keep window
        # "ID " (3) + 248 + " Alice" (6) = 257 > 255 → must truncate
        long_title = "A" * 248 + " Alice"
        result = _make_name("ID", long_title, ["Alice"])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("Alice"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncation_multibyte_exceeds_byte_limit(self):
        # "あ" is 3 bytes; "ID " (3) + 84*"あ" (252) + " 5" (2) = 257 bytes > 255
        long_title = "あ" * 84 + " 5"
        result = _make_name("ID", long_title, [])
        self.assertIn("\u2026", result)
        self.assertTrue(result.endswith("5"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)


if __name__ == "__main__":
    unittest.main()
