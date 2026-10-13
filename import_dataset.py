"""Import an Indian recipe CSV into Rasoi's SQLite database.

Local development:
    python import_dataset.py
    RASOI_DATASET_PATH=data/IndianFoodDataset.csv python import_dataset.py

The importer is idempotent by recipe name + source URL. It accepts common column
names from Indian recipe datasets. It does not download datasets automatically;
obtain the dataset from a source you are authorized to use.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

from app.recipes import connect, init_db, key, split_ingredients

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "data" / "IndianFoodDataset.csv"
CSV_PATH = Path(os.getenv("RASOI_DATASET_PATH", str(DEFAULT_CSV))).expanduser()


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


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
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(minutes?|mins?|min|hours?|hrs?|hr)\s*", value, re.I)
        if not match:
            return value
        number = float(match.group(1))
        if match.group(2).lower().startswith(("hour", "hr")):
            number *= 60
        return str(int(number)) if number.is_integer() else str(number)

    name = first("TranslatedRecipeName", "RecipeName", "recipe_name", "name")
    raw_ingredients = first("TranslatedIngredients", "Ingredients", "ingredient_list", "ingredients")
    if not name or not raw_ingredients:
        return None

    ingredients = split_ingredients(raw_ingredients)
    if not ingredients:
        return None

    prep = as_minutes(first("PrepTimeInMins", "prep_time", "preparation_time"))
    cook = as_minutes(first("CookTimeInMins", "cook_time"))
    total = as_minutes(first("TotalTimeInMins", "total_time"))
    if not total and prep.isdigit() and cook.isdigit():
        total = str(int(prep) + int(cook))

    diet_raw = first("Diet", "diet").lower()
    if "vegetarian" in diet_raw and "non" not in diet_raw and "vegan" not in diet_raw:
        diet = "vegetarian"
    elif any(term in diet_raw for term in ("non-vegetarian", "non vegetarian", "nonvegetarian")):
        diet = "non-vegetarian"
    elif "egg" in diet_raw:
        diet = "egg"
    else:
        diet = "unknown"

    return {
        "name": name,
        "ingredients_raw": raw_ingredients,
        "ingredient_list": json.dumps(ingredients, ensure_ascii=False),
        "ingredient_keys": json.dumps([key(item) for item in ingredients], ensure_ascii=False),
        "instructions": first("TranslatedInstructions", "Instructions", "instruction", "method", "steps")
            or "No instructions available in the source dataset.",
        "prep_time": prep,
        "cook_time": cook,
        "total_time": total,
        "servings": first("Servings", "servings"),
        "cuisine": first("Cuisine", "cuisine", default="Not specified"),
        "course": first("Course", "course", default="Not specified"),
        "diet": diet,
        "source_url": first("URL", "SourceURL", "source_url", "url"),
    }


def import_dataset(csv_path: Path = CSV_PATH, replace: bool = False) -> dict[str, int]:
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Recipe CSV not found: {csv_path}\n"
            "Place the authorized dataset at data/IndianFoodDataset.csv or set "
            "RASOI_DATASET_PATH to its path."
        )

    init_db()
    processed = skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        with connect() as db:
            if replace:
                db.execute("DELETE FROM recipes")
            for row in reader:
                recipe = parse_row(row)
                if recipe is None:
                    skipped += 1
                    continue

                existing = db.execute(
                    "SELECT id FROM recipes WHERE name = ? AND COALESCE(source_url, '') = ? LIMIT 1",
                    (recipe["name"], recipe["source_url"]),
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

    return {"processed": processed, "skipped": skipped}


def main() -> int:
    try:
        result = import_dataset()
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Dataset import failed: {exc}", file=sys.stderr)
        return 1
    from app.recipes import all_recipes
    all_recipes.cache_clear()
    print(f"Dataset import complete. Processed/updated: {result['processed']}; skipped: {result['skipped']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
