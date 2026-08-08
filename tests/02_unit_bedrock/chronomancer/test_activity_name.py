"""
Unit test for get_activity_display_name helper.
Run with: uv run python -m unittest TEST/unit/chronomancer/test_activity_name.py
"""

import os
import sys
import unittest

sys.path.append(os.getcwd())

from src.bot.chronomancer_ranking import get_activity_display_name


class TestActivityName(unittest.TestCase):
    def test_display_names(self):
        # Test lowercase display names
        self.assertEqual(get_activity_display_name("study"), "mental clarity")
        self.assertEqual(get_activity_display_name("travel"), "travel")
        self.assertEqual(get_activity_display_name("job_interview"), "career")
        self.assertEqual(get_activity_display_name("love"), "love")
        self.assertEqual(get_activity_display_name("speculation"), "speculation")

        # Test titlecase display names
        self.assertEqual(get_activity_display_name("study", title=True), "Mental Clarity")
        self.assertEqual(get_activity_display_name("travel", title=True), "Travel")
        self.assertEqual(get_activity_display_name("job_interview", title=True), "Career")
        self.assertEqual(get_activity_display_name("love", title=True), "Love")
        self.assertEqual(get_activity_display_name("speculation", title=True), "Speculation")


if __name__ == "__main__":
    unittest.main()
