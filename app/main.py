from pathlib import Path
import logging
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .recipes import (
    all_recipes, database_backend, get_recipe, init_db, list_recipes,
    random_recipe, search_recipes,
)

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DATASET_PATH = Path(os.getenv("RASOI_DATASET_PATH", str(ROOT / "data" / "IndianFoodDataset.csv")))
Diet = Literal["any", "vegetarian", "non-vegetarian", "egg", "unknown"]

DATABASE_UNAVAILABLE_MESSAGE = (
    "Recipe database is unavailable. Verify that the Production DATABASE_URL "
    "contains a valid Supabase PostgreSQL connection URI and that the database is reachable."
)

app = FastAPI(
    title="Rasoi — Indian Recipe Finder API",
    version="1.1.0",
    description="Recipe catalog and ingredient matcher backed by local SQLite or hosted PostgreSQL.",
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


class SearchRequest(BaseModel):
    ingredients: list[str] = Field(min_length=1, max_length=100)
    diet: Diet = "any"
    cuisine: str = "any"
    course: str = "any"
    max_time: int | None = Field(default=None, ge=1, le=1440)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@app.on_event("startup")
def startup():
    # The schema and catalog are provisioned separately in hosted PostgreSQL.
    # Avoid running DDL or opening database connections during Vercel cold starts:
    # a transient database failure should not prevent the function from booting.
    if os.getenv("VERCEL") == "1":
        return

    init_db()

    # Automatic CSV import is intentionally local-only. Import to hosted
    # PostgreSQL explicitly with the importer and DATABASE_URL set in the shell,
    # so deploys and cold starts never reimport the dataset.
    if not os.getenv("DATABASE_URL") and DATASET_PATH.is_file():
        from import_dataset import import_dataset
        import_dataset(DATASET_PATH)
        all_recipes.cache_clear()


def load_catalog():
    """Load recipes or turn database errors into an actionable HTTP 503."""
    try:
        return all_recipes()
    except Exception as exc:
        logger.exception("Unable to load Rasoi recipe catalog")
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE) from exc


def require_data():
    if not load_catalog():
        raise HTTPException(
            503,
            "Recipe database is empty. Import the catalog into hosted PostgreSQL "
            "and verify the Production DATABASE_URL.",
        )


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/health")
def health():
    try:
        recipes = all_recipes()
    except Exception:
        logger.exception("Rasoi health check could not read the recipe catalog")
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "dataset_loaded": False,
                "recipe_count": 0,
                "database": database_backend(),
                "message": DATABASE_UNAVAILABLE_MESSAGE,
            },
        )

    return {
        "status": "ok",
        "dataset_loaded": bool(recipes),
        "recipe_count": len(recipes),
        "database": database_backend(),
    }


@app.get("/api/filters")
def filters():
    recipes = load_catalog()
    return {
        "diet": ["any", "vegetarian", "non-vegetarian", "egg", "unknown"],
        "cuisines": sorted({r["cuisine"] for r in recipes if r["cuisine"] != "Not specified"}),
        "courses": sorted({r["course"] for r in recipes if r["course"] != "Not specified"}),
        "max_time_options": [15, 30, 45, 60, 90],
    }


@app.post("/api/recipes/search")
def search(request: SearchRequest):
    if not any(item.strip() for item in request.ingredients):
        raise HTTPException(422, "Enter at least one ingredient.")
    require_data()
    return search_recipes(
        request.ingredients, request.diet, request.cuisine, request.course,
        request.limit, request.offset, max_time=request.max_time,
    )


@app.get("/api/recipes")
def catalog(
    q: str = Query("", max_length=100),
    diet: Diet = "any",
    cuisine: str = Query("any", max_length=100),
    course: str = Query("any", max_length=100),
    max_time: int | None = Query(None, ge=1, le=1440),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    require_data()
    return list_recipes(q.strip(), diet, cuisine, course, max_time, limit, offset)


@app.get("/api/recipes/random")
def discover(
    diet: Diet = "any",
    cuisine: str = Query("any", max_length=100),
    course: str = Query("any", max_length=100),
    max_time: int | None = Query(None, ge=1, le=1440),
):
    require_data()
    item = random_recipe(diet, cuisine, course, max_time)
    if item is None:
        raise HTTPException(404, "No recipes match these filters.")
    return item


@app.get("/api/recipes/{recipe_id}")
def detail(recipe_id: int):
    require_data()
    item = get_recipe(recipe_id)
    if item is None:
        raise HTTPException(404, "Recipe not found.")
    return item
