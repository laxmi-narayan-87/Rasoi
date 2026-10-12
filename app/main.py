from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .recipes import all_recipes, get_recipe, init_db, list_recipes, random_recipe, search_recipes

BASE = Path(__file__).resolve().parent
Diet = Literal["any", "vegetarian", "non-vegetarian", "egg", "unknown"]
app = FastAPI(
    title="Rasoi — Indian Recipe Finder API",
    version="1.0.0",
    description="Local recipe catalog and ingredient matcher. No external recipe API or user-history storage.",
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
    init_db()


def require_data():
    if not all_recipes():
        raise HTTPException(503, "Recipe database is empty. The local SQLite database must contain recipe records.")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/health")
def health():
    recipes = all_recipes()
    return {"status": "ok", "dataset_loaded": bool(recipes), "recipe_count": len(recipes)}


@app.get("/api/filters")
def filters():
    recipes = all_recipes()
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
