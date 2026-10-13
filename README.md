# Rasoi — Indian Recipe Finder

A small Indian recipe finder. Users enter ingredients, get matching dishes, and open a dish to see its ingredients and cooking instructions. Ingredient matching is deterministic; SQLite is used for local development.

## Architecture

- One FastAPI application serves the frontend and JSON API.
- SQLite stores the local recipe catalog.
- A process-local cache loads the catalog for subsequent search, filter, discovery, and detail requests.
- Ingredient matching and ranking are deterministic; popularity does not affect ranking.

## Local setup

1. Obtain a recipe CSV from a source you are authorized to use.
2. Place it at `data/IndianFoodDataset.csv`, or set `RASOI_DATASET_PATH` to its location.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Start the app: `uvicorn app.main:app --reload`.

On local startup, Rasoi initializes the SQLite schema and imports/updates rows from the CSV if the file exists. To run the importer manually, use `python import_dataset.py`. The importer accepts common headers including `TranslatedRecipeName`, `RecipeName`, `TranslatedIngredients`, `Ingredients`, `TranslatedInstructions`, `Instructions`, `PrepTimeInMins`, `CookTimeInMins`, `TotalTimeInMins`, `Servings`, `Cuisine`, `Course`, `Diet`, and `URL`. Re-running the importer updates matching recipe name/source URL rows instead of blindly duplicating them.

The CSV is not included in this repository. Check its license and source permissions before use or redistribution. Open `http://127.0.0.1:8000`; API docs are at `/docs`.

## Vercel deployment

**The current SQLite implementation is for local development and is not a complete Vercel production setup.** Vercel Functions use an ephemeral filesystem, so a local SQLite file cannot be relied on for persistent shared data. The application also intentionally skips CSV import when it detects Vercel. Before production deployment, connect the API to a persistent hosted PostgreSQL database (such as Supabase or Neon), import the dataset once into that database, and configure connection details as Vercel environment variables. Do not commit database credentials to GitHub.

## API

- `POST /api/recipes/search` — search by ingredients, diet, cuisine, course and maximum time.
- `GET /api/recipes?q=rice&limit=20&offset=0` — browse/filter catalog with pagination.
- `GET /api/recipes/random` — choose a random matching recipe.
- `GET /api/recipes/{id}` — retrieve recipe ingredients and instructions.
- `GET /api/filters` — list available filter values.
- `GET /api/health` — report dataset status.

Example search JSON: `{"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}`.

## Data limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic text parsing. Diet classification is heuristic and cannot guarantee allergy safety or dietary compliance. A `can_make_now` result means all parsed listed ingredients matched the submitted input; optional items and pantry staples can make that estimate imperfect. Review complete instructions before cooking.

## Tests

Run `python -m unittest discover -s tests -v` after the test suite is added.
