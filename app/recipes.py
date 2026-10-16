"""Recipe catalog and deterministic ingredient matching.

Use SQLite for local development by default. Set DATABASE_URL to use a hosted
PostgreSQL database (for example Supabase) in production or during a one-time
cloud import. The public API remains database-agnostic.
"""
from __future__ import annotations

import json
import os
import random
import re
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "Recipe Database.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

ALIASES = {
    "aloo": "potato", "alu": "potato", "batata": "potato",
    "pyaz": "onion", "pyaaz": "onion", "tamatar": "tomato",
    "jeera": "cumin", "jira": "cumin", "haldi": "turmeric",
    "dhania": "coriander", "adrak": "ginger", "lahsun": "garlic",
    "dahi": "yogurt", "curd": "yogurt", "chawal": "rice",
    "matar": "peas", "gobi": "cauliflower", "baingan": "eggplant",
    "anda": "egg", "mirch": "chilli",
}


def text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key(value):
    value = text(value).lower().strip(" .;:-()[]{}")
    value = re.sub(r"^\d+(?:[./]\d+)?\s*(?:g|kg|ml|l|cups?|tbsp|tsp)?\s*", "", value)
    value = re.sub(
        r"\b(finely chopped|roughly chopped|chopped|sliced|grated|crushed|fresh|dried|optional|for garnish|large|medium|small)\b",
        " ", value,
    )
    value = re.sub(r"\s+", " ", value).strip()
    return ALIASES.get(value, value)


def split_ingredients(value):
    parts = re.split(r"[,;\n•]+", text(value))
    result = []
    for part in parts:
        part = re.sub(r"^\d+[.)]\s*|^[-*.)\s]+", "", text(part))
        part = re.sub(r"\b(to taste|as required|as needed)\b", "", part, flags=re.I).strip(" .;:-")
        part = re.sub(
            r"^\d+(?:\s*/\s*\d+|\.\d+)?\s*(?:cups?|tbsp|tsp|tablespoons?|teaspoons?|grams?|g|kg|ml|litres?|liters?)\s+",
            "", part, flags=re.I,
        )
        if part and part.lower() not in {"optional", "divided", "for garnish"}:
            result.append(part)
    return result


def duration(value):
    """Convert common cooking-time strings to minutes; return None if unknown."""
    value = text(value).lower()
    if value.isdigit():
        return int(value)

    # Support compound and fractional values such as "1 hr 30 min" and "1.5 hours".
    matches = list(re.finditer(
        r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|hr|minutes?|mins?|min)\b",
        value,
    ))
    if not matches:
        return None

    remainder = value
    total = 0.0
    for match in reversed(matches):
        amount = float(match.group(1))
        unit = match.group(2)
        total += amount * (60 if unit.startswith(("hour", "hr")) else 1)
        remainder = remainder[:match.start()] + remainder[match.end():]

    # Reject partially parsed values instead of silently returning a misleading duration.
    if re.sub(r"[\s,and]+", "", remainder):
        return None
    return int(total) if total.is_integer() else round(total)

def database_backend():
    """Return the active backend without exposing connection details."""
    return "postgresql" if DATABASE_URL else ("unconfigured" if os.getenv("VERCEL") == "1" else "sqlite")


class _PostgresConnection:
    """Small adapter so existing parameterized SQL can use SQLite-style '?' markers."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        return self._connection.execute(sql.replace("?", "%s"), params)


@contextmanager
def connect(db_path=None):
    """Open the configured database, or an explicit SQLite path for tests/tools.

    Passing db_path always selects SQLite. With no path, DATABASE_URL selects
    PostgreSQL; otherwise the local SQLite file is used.
    """
    if db_path is not None or not DATABASE_URL:
        # Never silently fall back to ephemeral SQLite on Vercel. Explicit db_path
        # remains available for tests and local import tools.
        if db_path is None and os.getenv("VERCEL") == "1":
            raise RuntimeError(
                "DATABASE_URL is required on Vercel. Configure the Production "
                "environment with a valid Supabase PostgreSQL connection URI."
            )
        target = Path(db_path) if db_path is not None else DB_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg is not installed. Install project requirements."
        ) from exc

    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    try:
        yield _PostgresConnection(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None):
    """Create the recipe table and index in the selected database."""
    with connect(db_path) as db:
        if db_path is not None or not DATABASE_URL:
            db.execute("""CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY, name TEXT, ingredients_raw TEXT, ingredient_list TEXT,
                ingredient_keys TEXT, instructions TEXT, prep_time TEXT, cook_time TEXT,
                total_time TEXT, servings TEXT, cuisine TEXT, course TEXT, diet TEXT, source_url TEXT
            )""")
        else:
            db.execute("""CREATE TABLE IF NOT EXISTS recipes (
                id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, ingredients_raw TEXT,
                ingredient_list TEXT, ingredient_keys TEXT, instructions TEXT,
                prep_time TEXT, cook_time TEXT, total_time TEXT, servings TEXT,
                cuisine TEXT, course TEXT, diet TEXT, source_url TEXT
            )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_recipe_name ON recipes(name)")


@lru_cache(maxsize=4)
def all_recipes(db_path=None):
    """Load and cache the catalog for a database target."""
    if db_path is not None:
        db_path = Path(db_path)
    with connect(db_path) as db:
        rows = db.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    recipes = []
    for row in rows:
        recipe = dict(row)
        recipe["ingredient_list"] = json.loads(recipe.pop("ingredient_list") or "[]")
        recipe["ingredient_keys"] = json.loads(recipe.pop("ingredient_keys") or "[]")
        recipe.pop("ingredients_raw", None)
        recipes.append(recipe)
    return recipes


def _matches(wanted, available):
    return wanted == available or (
        len(wanted) >= 4 and (
            re.search(rf"\b{re.escape(wanted)}\b", available)
            or re.search(rf"\b{re.escape(available)}\b", wanted)
        )
    )


def _filtered(query="", diet="any", cuisine="any", course="any", max_time=None, db_path=None):
    result = []
    for recipe in all_recipes(db_path):
        if diet != "any" and recipe["diet"] != diet:
            continue
        if cuisine != "any" and cuisine.casefold() not in recipe["cuisine"].casefold():
            continue
        if course != "any" and course.casefold() not in recipe["course"].casefold():
            continue
        minutes = duration(recipe["total_time"])
        if max_time is not None and (minutes is None or minutes > max_time):
            continue
        searchable = " ".join([
            recipe["name"], recipe["cuisine"], recipe["course"], *recipe["ingredient_list"]
        ])
        if query and query.casefold() not in searchable.casefold():
            continue
        result.append(recipe)
    return result


def summary(recipe):
    return {field: recipe.get(field) for field in (
        "id", "name", "cuisine", "course", "diet", "prep_time", "cook_time", "total_time", "servings"
    )} | {"ingredient_preview": recipe["ingredient_list"][:5]}


def list_recipes(query="", diet="any", cuisine="any", course="any", max_time=None, limit=20, offset=0, db_path=None):
    items = sorted(_filtered(query, diet, cuisine, course, max_time, db_path), key=lambda r: r["name"].casefold())
    return {"total": len(items), "items": [summary(r) for r in items[offset:offset + limit]]}


def random_recipe(diet="any", cuisine="any", course="any", max_time=None, db_path=None):
    items = _filtered(diet=diet, cuisine=cuisine, course=course, max_time=max_time, db_path=db_path)
    return summary(random.choice(items)) if items else None


def get_recipe(recipe_id, db_path=None):
    return next((r for r in all_recipes(db_path) if r["id"] == recipe_id), None)


def search_recipes(ingredients, diet="any", cuisine="any", course="any", limit=50, offset=0, db_path=None, max_time=None):
    requested = sorted(set(filter(None, (key(x) for x in ingredients))))
    if not requested:
        return {"total": 0, "items": []}
    found = []
    for recipe in _filtered(diet=diet, cuisine=cuisine, course=course, max_time=max_time, db_path=db_path):
        keys = list(dict.fromkeys(filter(None, (key(x) for x in recipe["ingredient_list"]))))
        matched = [wanted for wanted in requested if any(_matches(wanted, available) for available in keys)]
        if not matched:
            continue
        missing = [
            display for display in recipe["ingredient_list"]
            if key(display) and not any(_matches(wanted, key(display)) for wanted in requested)
        ]
        coverage = len({available for available in keys if any(_matches(w, available) for w in requested)}) / max(1, len(keys))
        found.append({
            **summary(recipe),
            "matched_ingredients": matched,
            "unmatched_user_ingredients": [w for w in requested if w not in matched],
            "missing_ingredients": list(dict.fromkeys(missing)),
            "matched_count": len(matched), "requested_count": len(requested),
            "match_percent": round(100 * coverage),
            "input_match_percent": round(100 * len(matched) / len(requested)),
            "can_make_now": not missing, "score": round(100 * coverage, 1),
        })
    found.sort(key=lambda r: (-int(r["can_make_now"]), -r["match_percent"], -r["input_match_percent"], r["name"].casefold()))
    return {
        "total": len(found), "items": found[offset:offset + limit],
        "message": "Match percentage reflects listed ingredients supplied. Check full instructions for pantry staples and optional ingredients.",
    }

