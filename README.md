# Rasoi — Indian Recipe Finder

Rasoi is a FastAPI-powered recipe finder. Users enter ingredients, browse dishes, filter by cuisine/diet/course/cooking time, and view cooking instructions. Ingredient matching is deterministic.

## Architecture

- **Local development:** SQLite stores the recipe catalog in `data/Recipe Database.db`.
- **Production on Vercel:** the API connects to persistent PostgreSQL through the server-only `DATABASE_URL` (for example, a Supabase PostgreSQL connection string).
- The recipe CSV is downloaded and processed locally. Vercel does not download Kaggle data or import it during application startup.
- Recipe matching currently loads the catalog into a process-local cache; profile cold-start time and memory use with the full dataset before scaling.

## 1. Download the dataset locally

Install the app dependencies and optional Kaggle downloader:

```powershell
python -m pip install -r requirements.txt
python -m pip install kagglehub
python download_dataset.py
```

The downloader defaults to `wafaaelhusseini/extended-recipes-dataset-64k-dishes`. It finds the downloaded CSV and copies the selected file to `data/IndianFoodDataset.csv`. If multiple CSVs exist, choose one explicitly:

```powershell
python download_dataset.py --csv-name "the-file-name.csv"
```

If Kaggle requires authentication, follow KaggleHub's instructions. Check the dataset license and usage terms before redistribution or commercial use. The CSV and local database are excluded from Git.

## 2. Import locally and run

```powershell
python import_dataset.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`; API docs are at `/docs`.

The importer supports common headers such as `title`, `RecipeName`, `TranslatedRecipeName`, `ingredients`, `TranslatedIngredients`, `directions`, `instructions`, `Prep Time`, `Cook Time`, `Total Time`, `Cuisine`, `Course`, `Diet`, and `URL`. JSON-array ingredient and instruction cells are supported. If the dataset uses different headers, inspect its first row and extend `parse_row()` in `import_dataset.py`.

Imports are repeatable. Rows with a source URL are matched by recipe name and URL; rows without a URL are matched by recipe name and ingredient list. Use `--replace` only when you intentionally want to clear the selected database before importing.

## 3. Configure hosted PostgreSQL for Vercel

A local SQLite database cannot serve Vercel requests because its filesystem is not shared persistent storage. Use hosted PostgreSQL, for example a dedicated Supabase project for Rasoi.

1. Provision the PostgreSQL database/schema.
2. Set `DATABASE_URL` locally to run the one-time cloud import.
3. Run `python import_dataset.py` against the local CSV; the import runs on your computer and writes rows to hosted PostgreSQL.
4. Add the same private `DATABASE_URL` to Vercel Project Settings → Environment Variables for Production, then redeploy.

Example (replace placeholders with the real private connection URI; do not commit it):

```powershell
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require"
python import_dataset.py
Remove-Item Env:DATABASE_URL
```

For providers that require TLS, preserve the provider's required SSL parameters. The importer creates the `recipes` table and name index if needed; alternatively, run `database/schema.sql` in the hosted PostgreSQL SQL editor first. Keep real database credentials out of GitHub. For local SQLite, leave `DATABASE_URL` unset.

## 4. Deploy and smoke-test

The current repository routes the FastAPI application through its configured Vercel deployment setup. Check the deployed URL after any deployment and verify:

- `/api/health` — database backend and catalog status.
- `/api/recipes` — browse/search catalog.
- `/api/recipes/random` — random recipe.
- `/api/recipes/{id}` — recipe details.
- `POST /api/recipes/search` — ingredient matching.

The application deliberately avoids falling back to ephemeral SQLite on Vercel if `DATABASE_URL` is missing. It does not import the dataset during Vercel startup or cold starts.

## Dependencies and database access controls

`requirements.txt` declares direct application dependencies; pip resolves their transitive dependencies. GitHub Actions installs dependencies, compiles Python sources, runs regression tests, and audits the dependency set with `pip-audit`.

The FastAPI backend accesses PostgreSQL through server-side `DATABASE_URL`; the browser does not need direct Supabase Data API access to recipe tables. The catalog, retained backup, and private source rows have row-level security enabled and direct access revoked from `anon` and `authenticated`. Keep `supabase/migrations/20261014153707_harden_rasoi_recipe_catalog_access.sql` in sync with any schema or permission changes.

## API

- `POST /api/recipes/search` — search by ingredients, diet, cuisine, course, and maximum cooking time.
- `GET /api/recipes?q=rice&limit=20&offset=0` — browse/filter catalog with pagination.
- `GET /api/recipes/random` — choose a random matching recipe.
- `GET /api/recipes/{id}` — retrieve recipe ingredients and instructions.
- `GET /api/filters` — list available filter values.
- `GET /api/health` — report catalog status, recipe count, and backend type.

Example request:

```json
{"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and do not require a Kaggle download or cloud credentials. A live PostgreSQL/Vercel smoke test still requires the configured production environment.

## Data limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic text parsing. Diet classification is based on source labels and cannot guarantee allergy safety or dietary compliance. `can_make_now` means all parsed listed ingredients matched the submitted input; optional items and pantry staples can make that estimate imperfect. Review complete instructions before cooking.
