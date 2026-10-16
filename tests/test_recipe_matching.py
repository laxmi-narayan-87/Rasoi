"""Regression tests for recipe duration parsing."""
import unittest

from app.recipes import duration


class RecipeDurationTests(unittest.TestCase):
    def test_parses_plain_minutes(self):
        self.assertEqual(duration("45"), 45)

    def test_parses_fractional_hours(self):
        self.assertEqual(duration("1.5 hours"), 90)

    def test_parses_compound_hours_and_minutes(self):
        self.assertEqual(duration("1 hr 30 min"), 90)

    def test_rejects_unrecognized_duration_text(self):
        self.assertIsNone(duration("about an hour"))


if __name__ == "__main__":
    unittest.main()
