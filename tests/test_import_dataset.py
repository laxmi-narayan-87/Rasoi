import csv
import json
import tempfile
import unittest
from pathlib import Path

from app.recipes import all_recipes, get_recipe, search_recipes
from import_dataset import import_dataset, parse_row


class RecipeDatasetImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.csv_path = self.root / "recipes.csv"
        self.db_path = self.root / "recipes.sqlite3"
        all_recipes.cache_clear()

    def tearDown(self):
        all_recipes.cache_clear()
        self.temp_dir.cleanup()

    def write_csv(self, rows):
        fieldnames = list(rows[0].keys())
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_parse_json_arrays_from_extended_recipe_datasets(self):
        recipe = parse_row({
            "title": "Aloo Tomato Curry",
            "ingredients": '["potato", "tomato", "onion"]',
            "directions": '["Chop vegetables", "Cook until soft"]',
            "prep_time": "10 minutes",
            "cook_time": "20 minutes",
            "cuisine": "Indian",
            "course": "Main Course",
            "diet": "vegetarian",
        })

        self.assertIsNotNone(recipe)
        self.assertEqual(json.loads(recipe["ingredient_list"]), ["potato", "tomato", "onion"])
        self.assertEqual(recipe["instructions"], "1. Chop vegetables\n2. Cook until soft")
        self.assertEqual(recipe["total_time"], "30")
        self.assertEqual(recipe["diet"], "vegetarian")

    def test_imports_extended_dataset_column_names(self):
        self.write_csv([{
            "recipe_title": "Aloo Tomato Curry",
            "ingredients_canonical": '["potato", "tomato", "onion"]',
            "directions_text": '["Chop vegetables", "Cook until soft"]',
            "est_prep_time_min": "10",
            "est_cook_time_min": "15",
            "est_total_time_min": "25",
            "dietary_profile": "vegetarian",
            "cuisine_list": "North Indian",
            "course_list": "Dinner",
            "source_url": "https://example.test/aloo-tomato",
        }])

        result = import_dataset(self.csv_path, db_path=self.db_path)
        recipes = all_recipes(self.db_path)

        self.assertEqual(result, {"processed": 1, "skipped": 0})
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["name"], "Aloo Tomato Curry")
        self.assertEqual(recipes[0]["prep_time"], "10")
        self.assertEqual(recipes[0]["cook_time"], "15")
        self.assertEqual(recipes[0]["total_time"], "25")
        self.assertEqual(recipes[0]["cuisine"], "North Indian")
        self.assertEqual(recipes[0]["course"], "Dinner")
        self.assertEqual(recipes[0]["instructions"], "1. Chop vegetables\n2. Cook until soft")

    def test_import_is_idempotent_and_recipes_are_searchable(self):
        self.write_csv([{
            "title": "Aloo Tomato Curry",
            "ingredients": '["potato", "tomato", "onion"]',
            "directions": '["Chop vegetables", "Cook until soft"]',
            "prep_time": "10",
            "cook_time": "20",
            "cuisine": "Indian",
            "course": "Main Course",
            "diet": "vegetarian",
            "url": "https://example.test/aloo-tomato",
        }])

        first = import_dataset(self.csv_path, db_path=self.db_path)
        second = import_dataset(self.csv_path, db_path=self.db_path)
        recipes = all_recipes(self.db_path)
        result = search_recipes(["aloo", "tomato"], db_path=self.db_path)

        self.assertEqual(first, {"processed": 1, "skipped": 0})
        self.assertEqual(second, {"processed": 1, "skipped": 0})
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["name"], "Aloo Tomato Curry")
        self.assertEqual(result["total"], 1)
        self.assertEqual(get_recipe(recipes[0]["id"], self.db_path)["name"], "Aloo Tomato Curry")

    def test_same_title_without_url_keeps_different_ingredient_variants(self):
        self.write_csv([
            {
                "title": "Vegetable Curry",
                "ingredients": '["potato", "tomato"]',
                "directions": '["Cook"]',
            },
            {
                "title": "Vegetable Curry",
                "ingredients": '["cauliflower", "peas"]',
                "directions": '["Steam"]',
            },
        ])

        result = import_dataset(self.csv_path, db_path=self.db_path)
        self.assertEqual(result, {"processed": 2, "skipped": 0})
        self.assertEqual(len(all_recipes(self.db_path)), 2)


if __name__ == "__main__":
    unittest.main()
