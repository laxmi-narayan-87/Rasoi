import csv
import tempfile
import unittest
from pathlib import Path
from app.recipes import all_recipes, import_csv, key, search_recipes, list_recipes, random_recipe, get_recipe, split_ingredients


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv = self.root / "recipes.csv"
        self.db = self.root / "recipes.db"
        rows = [
            {"RecipeName":"Potato Tomato Curry","Ingredients":"2 cups potato, 1 tomato, cumin, onion","Instructions":"Cook everything.\nServe hot.","PrepTimeInMins":"10","CookTimeInMins":"20","TotalTimeInMins":"30","Cuisine":"North Indian","Course":"Main Course","Diet":"Vegetarian","Servings":"2"},
            {"RecipeName":"Eggplant Fry","Ingredients":"eggplant, oil, salt","Instructions":"Fry it.","TotalTimeInMins":"15","Cuisine":"Indian","Course":"Snack","Diet":"Vegetarian"},
        ]
        with self.csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        import_csv(self.csv, self.db)
        all_recipes.cache_clear()

    def tearDown(self):
        all_recipes.cache_clear()
        self.tmp.cleanup()

    def test_hindi_alias_and_ingredient_split(self):
        self.assertEqual(key("aloo"), "potato")
        self.assertIn("potato", split_ingredients("2 cups potato, 1 tomato"))

    def test_search_ranks_and_reports_missing(self):
        data = search_recipes(["aloo", "tomato"], db_path=self.db)
        self.assertEqual(data["items"][0]["name"], "Potato Tomato Curry")
        self.assertIn("cumin", data["items"][0]["missing_ingredients"])

    def test_eggplant_is_not_egg(self):
        self.assertEqual(get_recipe(2, self.db)["diet"], "vegetarian")

    def test_catalog_filters_and_paginates(self):
        data = list_recipes(diet="vegetarian", max_time=20, limit=1, db_path=self.db)
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["items"]), 1)

    def test_random_and_detail_use_local_data(self):
        self.assertIsNotNone(random_recipe(db_path=self.db))
        self.assertIn("instructions", get_recipe(1, self.db))

    def test_time_aliases_imported(self):
        self.assertEqual(get_recipe(1, self.db)["total_time"], "30")

    def test_missing_dataset_errors(self):
        with self.assertRaises(FileNotFoundError):
            import_csv(self.root / "missing.csv", self.db)


if __name__ == "__main__":
    unittest.main()
