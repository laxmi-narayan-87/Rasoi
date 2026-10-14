"""Import a locally downloaded recipe CSV into Rasoi's active database.

By default this imports into local SQLite. Set DATABASE_URL in the environment
to import into hosted PostgreSQL instead. Importing into cloud PostgreSQL is a
manual, controlled operation; the Vercel app never downloads or imports the CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

from app.recipes import (
    all_recipes, connect, database_backend, init_db, key, split_ingredients,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "data" / "IndianFoodDataset.csv"
CSV_PATH = Path(os.getenv("RASOI_DATASET_PATH", str(DEFAULT_CSV))).expanduser()


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def parse_list(value: str) -> list[str] | None:
    """Parse JSON-list-like cells from recipe datasets, if present."""
    value = (value or "").strip()
    if not value.startswith("["):
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, list):
        return None
    return [str(item).strip() for item in parsed if item is not None and str(item).strip()]


def parse_row(row: dict[str, str]) -> dict | None:
    normalized = {normalize_header(k): (v or "").strip() for k, v in row.items()}

    def first(*names: str, default: str = "") -> str:
        for name in names:
            value = normalized.get(normalize_header(name), "")
            if value:
                return value
        return default

    def as_minutes(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if value.isdigit():
            return value
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*(minutes?|mins?|min|hours?|hrs?|hr)\s*", value, re.I
        )
        if not match:
            return value
        number = float(match.group(1))
        if match.group(2).lower().startswith(("hour", "hr")):
            number *= 60
        return str(int(number)) if number.is_integer() else str(number)

    name = first(
<<<<<<< Updated upstream
        "TranslatedRecipeName", "RecipeName", "Recipe Name", "recipe_name", "name", "title"
    )
    raw_ingredients = first(
        "TranslatedIngredients", "Ingredients", "ingredient_list", "ingredients", "ingredients_list"
=======
        "recipe_title", "TranslatedRecipeName", "RecipeName", "Recipe Name", "recipe_name", "name", "title"
    )
    raw_ingredients = first(
        "ingredients_canonical", "ingredients_raw", "ingredient_text", "TranslatedIngredients", "Ingredients", "ingredient_list", "ingredients", "ingredients_list"
>>>>>>> Stashed changes
    )
    if not name or not raw_ingredients:
        return None

    parsed_ingredients = parse_list(raw_ingredients)
    if parsed_ingredients is not None:
        ingredients = []
        for value in parsed_ingredients:
            ingredients.extend(split_ingredients(value))
    else:
        ingredients = split_ingredients(raw_ingredients)
    if not ingredients:
        return None

<<<<<<< Updated upstream
    prep = as_minutes(first("PrepTimeInMins", "Prep Time", "prep_time", "preparation_time"))
    cook = as_minutes(first("CookTimeInMins", "Cook Time", "cook_time"))
=======
    prep = as_minutes(first("est_prep_time_min", "PrepTimeInMins", "Prep Time", "prep_time", "preparation_time"))
    cook = as_minutes(first("est_cook_time_min", "CookTimeInMins", "Cook Time", "cook_time"))
>>>>>>> Stashed changes
    total = as_minutes(first("TotalTimeInMins", "Total Time", "total_time"))
    if not total and prep.isdigit() and cook.isdigit():
        total = str(int(prep) + int(cook))

<<<<<<< Updated upstream
    diet_raw = first("Diet", "diet", "diet_type").lower()
=======
    diet_raw = first("dietary_profile", "Diet", "diet", "diet_type").lower()
>>>>>>> Stashed changes
    if "vegetarian" in diet_raw and "non" not in diet_raw and "vegan" not in diet_raw:
        diet = "vegetarian"
    elif any(term in diet_raw for term in ("non-vegetarian", "non vegetarian", "nonvegetarian")):
        diet = "non-vegetarian"
    elif "egg" in diet_raw:
        diet = "egg"
    else:
        diet = "unknown"

    raw_instructions = first(
<<<<<<< Updated upstream
        "TranslatedInstructions", "Instructions", "instruction", "method", "steps", "directions"
=======
        "directions_text", "directions_raw", "TranslatedInstructions", "Instructions", "instruction", "method", "steps", "directions"
>>>>>>> Stashed changes
    )
    parsed_instructions = parse_list(raw_instructions)
    if parsed_instructions is not None:
        instructions = "\n".join(
            f"{index}. {step}" for index, step in enumerate(parsed_instructions, start=1)
        )
    else:
        instructions = raw_instructions or "No instructions available in the source dataset."

    return {
        "name": name,
        "ingredients_raw": raw_ingredients,
        "ingredient_list": json.dumps(ingredients, ensure_ascii=False),
        "ingredient_keys": json.dumps([key(item) for item in ingredients], ensure_ascii=False),
        "instructions": instructions,
        "prep_time": prep,
        "cook_time": cook,
        "total_time": total,
        "servings": first("Servings", "servings", "yield"),
<<<<<<< Updated upstream
        "cuisine": first("Cuisine", "cuisine", "cuisine_type", default="Not specified"),
        "course": first("Course", "course", "meal_type", "category", default="Not specified"),
=======
        "cuisine": first("cuisine_list", "Cuisine", "cuisine", "cuisine_type", default="Not specified"),
        "course": first("course_list", "Course", "course", "meal_type", "category", default="Not specified"),
>>>>>>> Stashed changes
        "diet": diet,
        "source_url": first("URL", "SourceURL", "source_url", "url", "recipe_url", "link", "Recipe URL"),
    }


def import_dataset(
    csv_path: Path = CSV_PATH,
    replace: bool = False,
    db_path: Path | None = None,
) -> dict[str, int]:
    """Import CSV rows. Pass db_path to force a specific local SQLite file (useful for tests)."""
    csv_path = Path(csv_path).expanduser()
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Recipe CSV not found: {csv_path}\n"
            "Run python download_dataset.py or set RASOI_DATASET_PATH to the CSV path."
        )

    init_db(db_path)
    processed = skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        normalized_headers = {normalize_header(name) for name in reader.fieldnames}
<<<<<<< Updated upstream
        if not normalized_headers.intersection({"translatedrecipename", "recipename", "name", "title"}):
=======
        if not normalized_headers.intersection({"recipetitle", "translatedrecipename", "recipename", "name", "title"}):
>>>>>>> Stashed changes
            raise ValueError(
                "Could not identify a recipe-name column. Inspect the CSV headers and "
                "extend parse_row() with the dataset's actual column names."
            )
        if not normalized_headers.intersection({
<<<<<<< Updated upstream
            "translatedingredients", "ingredients", "ingredientlist", "ingredientslist"
=======
            "translatedingredients", "ingredients", "ingredientlist", "ingredientslist", "ingredientscanonical", "ingredientsraw", "ingredienttext"
>>>>>>> Stashed changes
        }):
            raise ValueError(
                "Could not identify an ingredients column. Inspect the CSV headers and "
                "extend parse_row() with the dataset's actual column names."
            )

        with connect(db_path) as db:
            if replace:
                db.execute("DELETE FROM recipes")
            for row in reader:
                recipe = parse_row(row)
                if recipe is None:
                    skipped += 1
                    continue

                if recipe["source_url"]:
                    existing = db.execute(
                        "SELECT id FROM recipes WHERE name = ? AND COALESCE(source_url, '') = ? LIMIT 1",
                        (recipe["name"], recipe["source_url"]),
                    ).fetchone()
                else:
                    # Avoid collapsing distinct recipes that share a title but have no URL.
                    existing = db.execute(
                        "SELECT id FROM recipes WHERE name = ? AND COALESCE(source_url, '') = '' "
                        "AND ingredient_list = ? LIMIT 1",
                        (recipe["name"], recipe["ingredient_list"]),
                    ).fetchone()

                fields = (
                    "ingredients_raw", "ingredient_list", "ingredient_keys", "instructions",
                    "prep_time", "cook_time", "total_time", "servings", "cuisine", "course", "diet",
                )
                if existing:
                    db.execute(
                        "UPDATE recipes SET " + ", ".join(f"{field}=?" for field in fields) + " WHERE id=?",
                        tuple(recipe[field] for field in fields) + (existing["id"],),
                    )
                else:
                    insert_fields = (
                        "name", "ingredients_raw", "ingredient_list", "ingredient_keys", "instructions",
                        "prep_time", "cook_time", "total_time", "servings", "cuisine", "course", "diet", "source_url",
                    )
                    db.execute(
                        f"INSERT INTO recipes ({', '.join(insert_fields)}) VALUES ({', '.join('?' for _ in insert_fields)})",
                        tuple(recipe[field] for field in insert_fields),
                    )
                processed += 1

    all_recipes.cache_clear()
    return {"processed": processed, "skipped": skipped}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Import recipe CSV into local SQLite or DATABASE_URL PostgreSQL."
    )
    parser.add_argument("csv_path", nargs="?", type=Path, default=CSV_PATH, help="CSV file path")
    parser.add_argument(
        "--replace", action="store_true",
        help="delete existing recipes before import (use carefully with a production database)",
    )
    args = parser.parse_args(argv)
    try:
        result = import_dataset(args.csv_path, replace=args.replace)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Dataset import failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Dataset import complete into {database_backend()}. "
        f"Processed/updated: {result['processed']}; skipped: {result['skipped']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
