import csv
import os
import sys
from pathlib import Path

from app.recipes import connect, database_backend
from import_dataset import normalize_header, parse_row

BATCH_SIZE = 500

FIELDS = (
    "name", "ingredients_raw", "ingredient_list", "ingredient_keys",
    "instructions", "prep_time", "cook_time", "total_time", "servings",
    "cuisine", "course", "diet", "source_url",
)


def recipe_key(name, source_url, ingredient_list):
    if source_url:
        return ("url", name, source_url)
    return ("ingredients", name, ingredient_list or "")


def batch_key(recipe):
    return recipe_key(
        recipe["name"],
        recipe.get("source_url") or "",
        recipe.get("ingredient_list") or "",
    )


def insert_batch(batch):
    if not batch:
        return

    row_placeholder = "(" + ", ".join(["?"] * len(FIELDS)) + ")"
    sql = (
        f"INSERT INTO recipes ({', '.join(FIELDS)}) VALUES "
        + ", ".join([row_placeholder] * len(batch))
    )
    values = [recipe[field] for recipe in batch for field in FIELDS]

    # Each batch commits separately when this context closes.
    with connect() as db:
        db.execute(sql, values)


def main():
    if database_backend() != "postgresql":
        raise RuntimeError(
            "STOP: PostgreSQL is not selected. No import was started."
        )

    csv_path = Path(
        sys.argv[1] if len(sys.argv) > 1
        else os.environ.get("RASOI_DATASET_PATH", "")
    ).expanduser()

    if not csv_path.is_file():
        raise FileNotFoundError(f"Recipe CSV not found: {csv_path}")

    # Read existing keys once, so rerunning can skip committed recipes.
    with connect() as db:
        rows = db.execute("""
            SELECT name,
                   COALESCE(source_url, '') AS source_url,
                   COALESCE(ingredient_list, '') AS ingredient_list
            FROM recipes
        """).fetchall()

    seen = {
        recipe_key(
            row["name"],
            row["source_url"],
            row["ingredient_list"],
        )
        for row in rows
    }

    print(f"Backend: {database_backend()}", flush=True)
    print(f"Existing recipes: {len(seen)}", flush=True)

    batch = []
    inserted = skipped = duplicates = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        headers = {normalize_header(h) for h in reader.fieldnames}

        if not headers.intersection({
            "recipetitle", "recipename", "translatedrecipename", "name", "title"
        }):
            raise ValueError("Recipe-name column not recognized.")

        if not headers.intersection({
            "translatedingredients", "ingredients", "ingredientlist",
            "ingredientslist", "ingredientscanonical",
            "ingredientsraw", "ingredienttext"
        }):
            raise ValueError("Ingredients column not recognized.")

        for row in reader:
            recipe = parse_row(row)

            if recipe is None:
                skipped += 1
                continue

            key = batch_key(recipe)

            if key in seen:
                duplicates += 1
                continue

            seen.add(key)
            batch.append(recipe)

            if len(batch) >= BATCH_SIZE:
                insert_batch(batch)
                inserted += len(batch)
                print(f"Committed {inserted} new recipes", flush=True)
                batch.clear()

    if batch:
        insert_batch(batch)
        inserted += len(batch)
        print(f"Committed {inserted} new recipes", flush=True)

    with connect() as db:
        total = db.execute(
            "SELECT COUNT(*) AS n FROM recipes"
        ).fetchone()["n"]

    print(f"New recipes inserted: {inserted}")
    print(f"Invalid/skipped rows: {skipped}")
    print(f"Existing or duplicate recipes skipped: {duplicates}")
    print(f"Total recipes now in Supabase: {total}", flush=True)


if __name__ == "__main__":
    main()
