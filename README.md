# Rasoi — Indian Recipe Finder

Rasoi is a FastAPI recipe finder. Enter ingredients, browse recipes, filter by diet/cuisine/course/time, and open cooking instructions.

## Architecture

- Local development uses SQLite in `data/Recipe Database.db`.
- Production on Vercel uses persistent PostgreSQL via the server-side `DATABASE_URL` (for example, Supabase).
- Dataset downloading/import is an explicit local/admin workflow; it does not run in Vercel startup.
- Recipe matching loads a process-local cache. Profile cold starts and memory with the full catalog before scaling.

## Local setup

```powershell
python -m pip install -r requirements.txt
python -m pip install kagglehub
python download_dataset.py
python import_dataset.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`; API docs are at `/docs`.

The downloader defaults to `wafaaelhusseini/extended-recipes-dataset-64k-dishes`. If multiple CSV files are found, select one explicitly with `python download_dataset.py --csv-name "file.csv"`. Check the dataset license and usage terms before redistribution/commercial use.

The importer supports common headers, JSON-array ingredients/instructions, and repeatable upserts. Rows with a source URL are matched by name and URL; rows without a URL are matched by name and ingredient list. Use `--replace` only when you intentionally want to clear the selected database.

## Production PostgreSQL and Vercel

1. Provision the PostgreSQL schema and load the catalog from your local CSV using the manual importer.
2. Configure the same private `DATABASE_URL` in Vercel Project Settings for Production.
3. Redeploy, then verify `/api/health`, `/api/recipes`, `/api/recipes/random`, `/api/recipes/{id}`, and `POST /api/recipes/search`.

A local SQLite file is not shared with Vercel. The application deliberately refuses to fall back to ephemeral SQLite on Vercel when `DATABASE_URL` is missing. Never commit a real database URI or credentials.

## Dependencies and security

`requirements.txt` lists the direct application dependencies; pip resolves their transitive dependencies. GitHub Actions installs these packages, compiles Python sources, runs regression tests, and audits the resolved environment with `pip-audit`.

The FastAPI backend accesses PostgreSQL through the server-only `DATABASE_URL`; the browser does not require direct Supabase Data API access. Recipe catalog and private source/backup tables have RLS enabled and direct access revoked from `anon` and `authenticated`. Keep the SQL migration in sync with schema/permission changes.

## API

- `POST /api/recipes/search`: ingredient matching, diet/cuisine/course/time filters.
- `GET /api/recipes?q=rice&limit=20&offset=0`: browse/filter recipes.
- `GET /api/recipes/random`: choose a random match.
- `GET /api/recipes/{id}`: recipe detail.
- `GET /api/filters`: available filter values.
- `GET /api/health`: dataset status and backend type.

Example request:

```json
{"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and need no Kaggle download or cloud credentials. A live PostgreSQL/Vercel smoke test still needs the configured production environment.

## Data limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic parsing. Diet classification relies on source labels and cannot guarantee allergy safety or dietary compliance. `can_make_now` means all parsed listed ingredients matched; optional items and pantry staples may make that estimate imperfect.
