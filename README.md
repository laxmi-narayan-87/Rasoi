# Rasoi — Indian Recipe Finder

A small local-first Indian recipe finder. Users enter ingredients, get matching dishes, and open a dish to see its full ingredients and cooking instructions. No external recipe API, AI inference, accounts, favorites, saved searches, or search-history storage.

## Architecture

- One FastAPI application serves the frontend and JSON API.
- SQLite stores the imported recipe catalog.
- A process-local cache loads the catalog once and serves subsequent search, filter, discovery, and detail requests from memory.
- Ingredient matching and ranking are deterministic; popularity does not affect ranking.
- Each request uses only the ingredients and filters submitted in that request.

This is a deliberately small design for a small user base, not a claim of high-concurrency load testing. Restart the app after changing the database externally.

## Setup

Obtain the Indian Food Recipes CSV from a source you are authorized to use and place it at data/IndianFoodDataset.csv. Install dependencies, run python import_dataset.py, then start the app with uvicorn app.main:app --reload.

Open http://127.0.0.1:8000; API docs are at /docs. If the CSV is not present, the API starts but recipe endpoints report that the dataset is not loaded.

## API

- POST /api/recipes/search — search by ingredients, diet, cuisine, course and maximum time.
- GET /api/recipes?q=rice&limit=20&offset=0 — browse/filter catalog with pagination.
- GET /api/recipes/random — choose a random matching recipe.
- GET /api/recipes/{id} — retrieve recipe ingredients and instructions.
- GET /api/filters — list available filter values.
- GET /api/health — report application and dataset status.

Example search JSON: {"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}.

## Data and limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic text parsing. Diet classification is heuristic and cannot guarantee allergy safety or dietary compliance. A can_make_now result means all parsed listed ingredients matched the submitted input; optional items and pantry staples can make that estimate imperfect. Review complete instructions before cooking. Check the dataset's license and underlying source permissions before redistribution or commercial use.

## Tests

Run python -m unittest discover -s tests -v.
