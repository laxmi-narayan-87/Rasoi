import csv
import os
from pathlib import Path

from app.recipes import connect, database_backend
from psycopg.types.json import Jsonb

BATCH_SIZE = 500
CSV_PATH = Path(os.environ["RASOI_DATASET_PATH"])

if database_backend() != "postgresql":
    raise RuntimeError("PostgreSQL is not selected.")

if not CSV_PATH.is_file():
    raise FileNotFoundError(CSV_PATH)


def save_batch(batch):
    if not batch:
        return

    placeholders = []
    values = []

    for row_id, title, original_row in batch:
        placeholders.append("(?, ?, ?)")
        values.extend((row_id, title, Jsonb(original_row)))

    sql = f"""
        INSERT INTO private.rasoi_source_rows
            (source_row_id, recipe_title, row_data)
        VALUES {", ".join(placeholders)}
        ON CONFLICT (source_row_id) DO UPDATE SET
            recipe_title = EXCLUDED.recipe_title,
            row_data = EXCLUDED.row_data
    """

    with connect() as db:
        db.execute(sql, values)


with connect() as db:
    db.execute("CREATE SCHEMA IF NOT EXISTS private")
    db.execute("""
        CREATE TABLE IF NOT EXISTS private.rasoi_source_rows (
            source_row_id BIGINT PRIMARY KEY,
            recipe_title TEXT,
            row_data JSONB NOT NULL
        )
    """)

batch = []
processed = 0

with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
    reader = csv.DictReader(handle)

    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    if "recipe_title" not in reader.fieldnames:
        raise ValueError("Expected recipe_title column was not found.")

    for row_id, row in enumerate(reader, start=1):
        batch.append((
            row_id,
            row.get("recipe_title") or "",
            row,
        ))

        if len(batch) >= BATCH_SIZE:
            save_batch(batch)
            processed += len(batch)
            print(f"Processed {processed} source rows", flush=True)
            batch.clear()

if batch:
    save_batch(batch)
    processed += len(batch)

with connect() as db:
    count = db.execute(
        "SELECT COUNT(*) AS n FROM private.rasoi_source_rows"
    ).fetchone()["n"]

print("Source rows processed:", processed)
print("Total source records preserved:", count)

if count != 62126:
    raise RuntimeError(
        f"Expected 62126 source records, found {count}."
    )
