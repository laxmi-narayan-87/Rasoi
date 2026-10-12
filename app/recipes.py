"""Local SQLite recipe catalog and deterministic ingredient matching."""
from __future__ import annotations
import csv, json, random, re, sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "recipes.db"
CSV_PATH = ROOT / "data" / "IndianFoodDataset.csv"
ALIASES = {"aloo":"potato", "alu":"potato", "batata":"potato", "pyaz":"onion", "pyaaz":"onion", "tamatar":"tomato", "jeera":"cumin", "jira":"cumin", "haldi":"turmeric", "dhania":"coriander", "adrak":"ginger", "lahsun":"garlic", "dahi":"yogurt", "curd":"yogurt", "chawal":"rice", "matar":"peas", "gobi":"cauliflower", "baingan":"eggplant", "anda":"egg", "mirch":"chilli"}


def text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key(value):
    value = text(value).lower().strip(" .;:-()[]{}")
    value = re.sub(r"^\d+(?:[./]\d+)?\s*(?:g|kg|ml|l|cups?|tbsp|tsp)?\s*", "", value)
    value = re.sub(r"\b(finely chopped|roughly chopped|chopped|sliced|grated|crushed|fresh|dried|optional|for garnish|large|medium|small)\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return ALIASES.get(value, value)


def split_ingredients(value):
    parts = re.split(r"[,;\n•]+", text(value))
    result = []
    for part in parts:
        part = re.sub(r"^\d+[.)]\s*|^[-*.)\s]+", "", text(part))
        part = re.sub(r"\b(to taste|as required|as needed)\b", "", part, flags=re.I).strip(" .;:-")
        part = re.sub(r"^\d+(?:\s*/\s*\d+|\.\d+)?\s*(?:cups?|tbsp|tsp|tablespoons?|teaspoons?|grams?|g|kg|ml|litres?|liters?)\s+", "", part, flags=re.I)
        if part and part.lower() not in {"optional", "divided", "for garnish"}:
            result.append(part)
    return result


def row_value(row, *names):
    lower = {str(k).lower(): v for k, v in row.items()}
    return next((text(lower.get(n.lower())) for n in names if text(lower.get(n.lower()))), "")


def duration(value):
    value = text(value).lower()
    if value.isdigit():
        return int(value)
    hours = re.search(r"(\d+)\s*(?:hours?|hrs?|hr)\b", value)
    minutes = re.search(r"(\d+)\s*(?:minutes?|mins?|min)\b", value)
    return int(hours.group(1))*60 + int(minutes.group(1) if minutes else 0) if hours or minutes else None


def normalize_row(row, recipe_id):
    name = row_value(row, "TranslatedRecipeName", "RecipeName", "recipe_name", "name")
    raw = row_value(row, "TranslatedIngredients", "Ingredients", "ingredients")
    if not name or not raw:
        return None
    ingredients = split_ingredients(raw)
    diet_source = row_value(row, "Diet", "diet").lower()
    terms = " ".join(key(x) for x in ingredients)
    nonveg = ("chicken", "fish", "prawn", "shrimp", "mutton", "beef", "pork", "meat")
    if any(re.search(rf"\b{x}\b", terms) for x in nonveg) or "non-vegetarian" in diet_source:
        diet = "non-vegetarian"
    elif re.search(r"\begg\b", terms) or "egg" in diet_source:
        diet = "egg"
    elif "vegetarian" in diet_source or diet_source == "veg":
        diet = "vegetarian"
    else:
        diet = "unknown"
    return {
        "id": recipe_id, "name": name, "ingredients_raw": raw,
        "ingredient_list": ingredients,
        "ingredient_keys": sorted(set(filter(None, map(key, ingredients)))),
        "instructions": row_value(row, "TranslatedInstructions", "Instructions", "instructions", "method"),
        "prep_time": row_value(row, "Prep", "PrepTime", "PrepTimeInMins", "prep_time"),
        "cook_time": row_value(row, "Cook", "CookTime", "CookTimeInMins", "cook_time"),
        "total_time": row_value(row, "Total", "TotalTime", "TotalTimeInMins", "total_time"),
        "servings": row_value(row, "Servings", "servings"),
        "cuisine": row_value(row, "Cuisine", "cuisine") or "Not specified",
        "course": row_value(row, "Course", "course") or "Not specified",
        "diet": diet, "source_url": row_value(row, "URL", "RecipeURL", "url", "SourceURL"),
    }


@contextmanager
def connect(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=DB_PATH):
    with connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY, name TEXT, ingredients_raw TEXT, ingredient_list TEXT,
            ingredient_keys TEXT, instructions TEXT, prep_time TEXT, cook_time TEXT,
            total_time TEXT, servings TEXT, cuisine TEXT, course TEXT, diet TEXT, source_url TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_recipe_name ON recipes(name)")


def import_csv(csv_path=CSV_PATH, db_path=DB_PATH):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    init_db(db_path)
    rows = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for recipe_id, raw in enumerate(csv.DictReader(f), 1):
            recipe = normalize_row(raw, recipe_id)
            if recipe:
                rows.append((
                    recipe["id"], recipe["name"], recipe["ingredients_raw"],
                    json.dumps(recipe["ingredient_list"], ensure_ascii=False),
                    json.dumps(recipe["ingredient_keys"], ensure_ascii=False),
                    recipe["instructions"], recipe["prep_time"], recipe["cook_time"],
                    recipe["total_time"], recipe["servings"], recipe["cuisine"],
                    recipe["course"], recipe["diet"], recipe["source_url"],
                ))
    with connect(db_path) as db:
        db.execute("DELETE FROM recipes")
        db.executemany("INSERT INTO recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    all_recipes.cache_clear()
    return len(rows)


@lru_cache(maxsize=4)
def all_recipes(db_path=DB_PATH):
    db_path = Path(db_path)
    if not db_path.exists():
        return []
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


def _filtered(query="", diet="any", cuisine="any", course="any", max_time=None, db_path=DB_PATH):
    result = []
    for recipe in all_recipes(Path(db_path)):
        if diet != "any" and recipe["diet"] != diet:
            continue
        if cuisine != "any" and cuisine.casefold() not in recipe["cuisine"].casefold():
            continue
        if course != "any" and course.casefold() not in recipe["course"].casefold():
            continue
        minutes = duration(recipe["total_time"])
        if max_time is not None and (minutes is None or minutes > max_time):
            continue
        searchable = " ".join([recipe["name"], recipe["cuisine"], recipe["course"], *recipe["ingredient_list"]])
        if query and query.casefold() not in searchable.casefold():
            continue
        result.append(recipe)
    return result


def summary(recipe):
    return {field: recipe.get(field) for field in (
        "id", "name", "cuisine", "course", "diet", "prep_time", "cook_time", "total_time", "servings"
    )} | {"ingredient_preview": recipe["ingredient_list"][:5]}


def list_recipes(query="", diet="any", cuisine="any", course="any", max_time=None, limit=20, offset=0, db_path=DB_PATH):
    items = sorted(_filtered(query, diet, cuisine, course, max_time, db_path), key=lambda r: r["name"].casefold())
    return {"total": len(items), "items": [summary(r) for r in items[offset:offset + limit]]}


def random_recipe(diet="any", cuisine="any", course="any", max_time=None, db_path=DB_PATH):
    items = _filtered(diet=diet, cuisine=cuisine, course=course, max_time=max_time, db_path=db_path)
    return summary(random.choice(items)) if items else None


def get_recipe(recipe_id, db_path=DB_PATH):
    return next((r for r in all_recipes(Path(db_path)) if r["id"] == recipe_id), None)


def search_recipes(ingredients, diet="any", cuisine="any", course="any", limit=50, offset=0, db_path=DB_PATH, max_time=None):
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
