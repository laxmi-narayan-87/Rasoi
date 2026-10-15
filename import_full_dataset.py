"""Preserve the raw source CSV in a private PostgreSQL table.

Run explicitly with DATABASE_URL and RASOI_DATASET_PATH configured. This tool
is separate from the web runtime and never runs during Vercel startup.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from psycopg.types.json import Jsonb

from app.recipes import connect, database_backend

BATCH_SIZE = 500
EXPECTED_ROWS = 62126


def save_batch(batch):
    if not batch:
        return
    placeholders = ", ".join(["(?, ?, ?)"] * len(batch))
    values = [value for row in batch for value in row]
    sql = f"""
        INSERT INTO private.rasoi_source_rows
            (source_row_id, recipe_title, row_data)
        VALUES {placeholders}
        ON CONFLICT (source_row_id) DO UPDATE SET
            recipe_title = EXCLUDED.recipe_title,
            row_data = EXCLUDED.row_data
    """
    with connect() as db:
        db.execute(sql, values)


def main():
    if database_backend() != "postgresql":
        raise RuntimeError("PostgreSQL is not selected; refusing to import.")

    csv_path = Path(os.environ["RASOI_DATASET_PATH"]).expanduser()
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    with connect() as db:
        db.execute("CREATE SCHEMA IF NOT EXISTS private")
        db.execute("""
            CREATE TABLE IF NOT EXISTS private.rasoi_source_rows (
                source_row_id BIGINT PRIMARY KEY,
                recipe_title TEXT,
                row_data JSONB NOT NULL
            )
        """)

    processed = 0
    batch = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "recipe_title" not in reader.fieldnames:
            raise ValueError("Expected recipe_title column was not found.")

        for row_id, row in enumerate(reader, start=1):
            batch.append((row_id, row.get("recipe_title") or "", Jsonb(row)))
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

    print(f"Source rows processed: {processed}")
    print(f"Total source records preserved: {count}")
    if count != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} source records, found {count}.")


if __name__ == "__main__":
    main()
