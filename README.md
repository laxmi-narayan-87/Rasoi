# Rasoi — Indian Recipe Finder

A small Indian recipe finder. Users enter ingredients, get matching dishes, and open a dish to see its full ingredients and cooking instructions. Ingredient matching is deterministic and the local development database is SQLite.

## Architecture

- One FastAPI application serves the frontend and JSON API.
- SQLite stores the local recipe catalog.
- A process-local cache loads the catalog for subsequent search, filter, discovery, and detail requests.
- Ingredient matching and ranking are deterministic; popularity does not affect ranking.
- Each request uses only the ingredients and filters submitted in that request.

## Local setup

1. Obtain an Indian recipe CSV from a source you are authorized to use.
2. Place it at `data/IndianFoodDataset.csv`, or set `RASOI_DATASET_PATH` to its path.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start the app: `uvicorn app.main:app --reload`.

On local startup, Rasoi creates the SQLite schema and imports/updates records from the CSV if it exists. The importer supports common Indian recipe dataset columns such as `RecipeName`, `TranslatedRecipeName`, `Ingredients`, `TranslatedIngredients`, `Instructions`, `TranslatedInstructions`, `PrepTimeInMins`, `CookTimeInMins`, `TotalTimeInMins`, `Servings`, `Cuisine`, `Course`, `Diet`, and `URL`.

You can also run the importer manually:

```bash
python import_dataset.py
# Or point to a different CSV:
# Windows PowerShell:
$env:RASOI_DATASET_PATH = "D:\\path\\to\\recipes.csv"
python import_dataset.py
```

The importer can be run repeatedly; matching recipe name/source URL records are updated instead of duplicated. It reports processed and skipped rows. The source CSV is not included in this repository; check its license and source permissions before using or redistributing it.

Open `http://127.0.0.1:8000`; API docs are at `/docs`.

## Vercel deployment note

**The current SQLite storage is for local development and is not production-ready on Vercel.** Vercel Functions run in an ephemeral serverless environment: a SQLite file written by one invocation or instance is not a reliable persistent database, and importing a large CSV during every cold start is slow and can exceed function limits.

Before deploying the working recipe search to Vercel, migrate the catalog to a persistent hosted database (for example, PostgreSQL on Supabase or Neon), import the CSV once as a deployment/data setup step, and configure database connection settings as Vercel environment variables. Do not put database credentials in source control. The current code intentionally does not attempt a SQLite import when it detects Vercel, but the external-database adapter and schema migration are still required for the deployed app to serve recipes.

## API

- `POST /api/recipes/search` — search by ingredients, diet, cuisine, course and maximum time.
- `GET /api/recipes?q=rice&limit=20&offset=0` — browse/filter catalog with pagination.
- `GET /api/recipes/random` — choose a random matching recipe.
- `GET /api/recipes/{id}` — retrieve recipe ingredients and instructions.
- `GET /api/filters` — list available filter values.
- `GET /api/health` — report application and dataset status.

Example search JSON: `{"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}`.

## Data and limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic text parsing. Diet classification is heuristic and cannot guarantee allergy safety or dietary compliance. A `can_make_now` result means all parsed listed ingredients matched the submitted input; optional items and pantry staples can make that estimate imperfect. Review complete instructions before cooking.

## Tests

Run `python -m unittest discover -s tests -v` after the test suite is added.
