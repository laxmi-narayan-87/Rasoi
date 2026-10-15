"""Regression tests for deterministic ingredient matching."""

import csv
import tempfile
import unittest
from pathlib import Path

from app.recipes import all_recipes, search_recipes
from import_dataset import import_dataset


class RecipeMatchingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.csv_path = root / "recipes.csv"
        self.db_path = root / "recipes.sqlite3"
        rows = [
            {
                "title": "Potato Tomato Curry",
                "ingredients": '["potato", "tomato", "onion"]',
                "directions": '["Chop vegetables", "Cook until soft"]',
                "prep_time": "10",
                "cook_time": "20",
                "total_time": "30",
                "cuisine": "North Indian",
                "course": "Main Course",
                "diet": "vegetarian",
            },
            {
                "title": "Olive Oil Pasta",
                "ingredients": '["pasta", "olive oil", "garlic"]',
                "directions": '["Boil pasta", "Toss with oil"]',
                "total_time": "15",
                "cuisine": "Italian",
                "course": "Main Course",
                "diet": "vegetarian",
            },
        ]
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        import_dataset(self.csv_path, db_path=self.db_path)
        all_recipes.cache_clear()

    def tearDown(self):
        all_recipes.cache_clear()
        self.temp_dir.cleanup()

    def test_hindi_aliases_and_case_whitespace_normalize(self):
        result = search_recipes(
            [" ALOO ", "tamatar"], db_path=self.db_path
        )

        self.assertEqual(result["total"], 1)
        match = result["items"][0]
        self.assertEqual(match["name"], "Potato Tomato Curry")
        self.assertEqual(match["matched_ingredients"], ["potato", "tomato"])
        self.assertEqual(match["input_match_percent"], 100)

    def test_missing_ingredients_are_reported_without_claiming_ready_to_cook(self):
        result = search_recipes(["aloo", "tomato"], db_path=self.db_path)
        match = result["items"][0]

        self.assertEqual(match["missing_ingredients"], ["onion"])
        self.assertFalse(match["can_make_now"])
        self.assertEqual(match["match_percent"], 67)

    def test_short_ingredient_does_not_match_as_a_substring(self):
        result = search_recipes(["oil"], db_path=self.db_path)

        self.assertEqual(result["total"], 0)

    def test_blank_ingredients_return_no_matches(self):
        result = search_recipes(["", "   "], db_path=self.db_path)

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_time_filter_excludes_unknown_or_longer_recipes(self):
        result = search_recipes(
            ["garlic"], db_path=self.db_path, max_time=15
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["name"], "Olive Oil Pasta")


if __name__ == "__main__":
    unittest.main()
