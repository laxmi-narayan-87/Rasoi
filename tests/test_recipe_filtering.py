"""Regression tests for SQL-backed recipe filters."""
import json
import tempfile
import unittest
from pathlib import Path

from app.recipes import connect, init_db, list_recipes


class RecipeFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "recipes.sqlite3"
        init_db(self.db_path)
        with connect(self.db_path) as db:
            for recipe_id, name, ingredients, cuisine, course, diet, total_time in [
                (1, "Aloo Tomato Curry", ["potato", "tomato", "onion"], "North Indian", "Main Course", "vegetarian", "30"),
                (2, "Tomato Pasta", ["tomato", "pasta"], "Italian", "Dinner", "vegetarian", "1 hr 30 min"),
                (3, "Egg Curry", ["egg", "onion"], "North Indian", "Main Course", "egg", "unknown"),
            ]:
                db.execute(
                    """INSERT INTO recipes
                    (id, name, ingredients_raw, ingredient_list, ingredient_keys,
                     instructions, prep_time, cook_time, total_time, servings,
                     cuisine, course, diet, source_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        recipe_id, name, ", ".join(ingredients), json.dumps(ingredients),
                        json.dumps(ingredients), "Cook", "10", "20", total_time,
                        "2", cuisine, course, diet, "",
                    ),
                )

    def tearDown(self):
        from app.recipes import all_recipes
        all_recipes.cache_clear()
        self.temp_dir.cleanup()

    def test_filters_by_diet_cuisine_and_course(self):
        result = list_recipes(
            diet="vegetarian", cuisine="indian", course="main", db_path=self.db_path
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["name"], "Aloo Tomato Curry")

    def test_query_matches_ingredient_and_escapes_like_wildcards(self):
        result = list_recipes(query="tomato", db_path=self.db_path)
        self.assertEqual(result["total"], 2)
        literal_wildcard = list_recipes(query="%", db_path=self.db_path)
        self.assertEqual(literal_wildcard["total"], 0)

    def test_time_filter_excludes_unknown_and_over_limit_recipes(self):
        result = list_recipes(max_time=45, db_path=self.db_path)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["name"], "Aloo Tomato Curry")


if __name__ == "__main__":
    unittest.main()
