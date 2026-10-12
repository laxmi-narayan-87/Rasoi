#!/usr/bin/env python3
import argparse
from pathlib import Path
from app.recipes import CSV_PATH, DB_PATH, import_csv

parser = argparse.ArgumentParser(description="Import Indian recipe CSV into local SQLite")
parser.add_argument("--csv", type=Path, default=CSV_PATH)
parser.add_argument("--db", type=Path, default=DB_PATH)
args = parser.parse_args()
try:
    count = import_csv(args.csv, args.db)
except Exception as exc:
    raise SystemExit(f"Import failed: {exc}")
print(f"Imported {count:,} recipes into {args.db}")
