import csv
import sys
from pathlib import Path

from app.recipes import connect, database_backend
from import_dataset import parse_row

EXPECTED_ROWS = 62126
BATCH_SIZE = 500
STAGING = "private.rasoi_recipe_catalog_staging"
BACKUP = "recipes_catalog_backup_20261014"

FIELDS = (
    "name", "ingredients_raw", "ingredient_list", "ingredient_keys",
    "instructions", "prep_time", "cook_time", "total_time", "servings",
    "cuisine", "course", "diet", "source_url",
)

def save_batch(batch):
    if not batch:
        return

    columns = ("id",) + FIELDS
    row_placeholder = "(" + ", ".join(["?"] * len(columns)) + ")"
    placeholders = ", ".join([row_placeholder] * len(batch))
    updates = ", ".join(
        f"{field} = EXCLUDED.{field}" for field in FIELDS
    )

    sql = f"""
        INSERT INTO {STAGING} ({", ".join(columns)})
        VALUES {placeholders}
        ON CONFLICT (id) DO UPDATE SET {updates}
    """

    values = []
    for source_id, recipe in batch:
        values.extend([source_id] + [recipe[field] for field in FIELDS])

    with connect() as db:
        db.execute(sql, values)

def main():
    if database_backend() != "postgresql":
        raise RuntimeError("PostgreSQL is not selected.")

    csv_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else
        __import__("os").environ["RASOI_DATASET_PATH"]
    )

    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS private.rasoi_recipe_catalog_staging (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                ingredients_raw TEXT,
                ingredient_list TEXT,
                ingredient_keys TEXT,
                instructions TEXT,
                prep_time TEXT,
                cook_time TEXT,
                total_time TEXT,
                servings TEXT,
                cuisine TEXT,
                course TEXT,
                diet TEXT,
                source_url TEXT
            )
        """)

    total = parsed = skipped = 0
    batch = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        for source_id, row in enumerate(reader, start=1):
            total += 1
            recipe = parse_row(row)

            if recipe is None:
                skipped += 1
                continue

            batch.append((source_id, recipe))
            parsed += 1

            if len(batch) >= BATCH_SIZE:
                save_batch(batch)
                print(f"Staged {parsed} source rows", flush=True)
                batch.clear()

    if batch:
        save_batch(batch)
        batch.clear()

    if total != EXPECTED_ROWS or parsed != EXPECTED_ROWS or skipped != 0:
        raise RuntimeError(
            f"Source validation failed: total={total}, "
            f"parsed={parsed}, skipped={skipped}. Catalog was not switched."
        )

    with connect() as db:
        db.execute(
            f"DELETE FROM {STAGING} WHERE id > ?",
            (total,),
        )
        staged = db.execute(
            f"SELECT COUNT(*) AS n FROM {STAGING}"
        ).fetchone()["n"]

    print(f"Verified staging rows: {staged}", flush=True)

    if staged != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS} staged rows, found {staged}. "
            "The existing catalog remains active."
        )

    # Atomically preserve the old catalog and activate the complete one.
    with connect() as db:
        backup_exists = db.execute(
            "SELECT to_regclass(?) AS relation",
            (f"private.{BACKUP}",),
        ).fetchone()["relation"]

        if backup_exists is not None:
            raise RuntimeError(
                f"Backup private.{BACKUP} already exists. "
                "Stop and inspect the database before retrying."
            )

        private_recipes_exists = db.execute(
            "SELECT to_regclass('private.recipes') AS relation"
        ).fetchone()["relation"]

        if private_recipes_exists is not None:
            raise RuntimeError(
                "private.recipes already exists. "
                "Stop and inspect the database before switching."
            )

        db.execute("ALTER TABLE public.recipes SET SCHEMA private")
        db.execute(
            f"ALTER TABLE private.recipes RENAME TO {BACKUP}"
        )
        db.execute(
            "ALTER TABLE private.rasoi_recipe_catalog_staging SET SCHEMA public"
        )
        db.execute(
            "ALTER TABLE public.rasoi_recipe_catalog_staging RENAME TO recipes"
        )
        db.execute(
            "CREATE INDEX idx_recipe_name ON public.recipes(name)"
        )
        db.execute("""
            SELECT setval(
                pg_get_serial_sequence('public.recipes', 'id'),
                (SELECT COALESCE(MAX(id), 1) FROM public.recipes),
                true
            )
        """)

        final_count = db.execute(
            "SELECT COUNT(*) AS n FROM public.recipes"
        ).fetchone()["n"]

        if final_count != EXPECTED_ROWS:
            raise RuntimeError(
                f"Final count {final_count} is incorrect; "
                "the table switch will be rolled back."
            )

    print("\nCATALOG UPDATE SUCCESSFUL")
    print("Active public.recipes rows:", final_count)
    print(f"Previous catalog preserved as private.{BACKUP}")

if __name__ == "__main__":
    main()
