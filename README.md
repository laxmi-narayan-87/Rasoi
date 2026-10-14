# Rasoi — Indian Recipe Finder

Rasoi is a FastAPI-powered recipe finder. Users enter ingredients, browse dishes, filter by cuisine/diet/course/cooking time, and view cooking instructions. Ingredient matching is deterministic.

## Architecture

- **Local development:** SQLite stores the recipe catalog in \`data/Recipe Database.db\`.
- **Production on Vercel:** the API connects to a persistent PostgreSQL database through \`DATABASE_URL\` (for example, a Supabase PostgreSQL connection string).
- The recipe CSV is downloaded and processed locally. Vercel does not download Kaggle data and does not import the CSV on application startup.
- The current matching implementation loads the catalog into a process-local cache. This is simple for the first release; profile cold-start time and memory use with the full 64K dataset before scaling further.

## 1. Download the Kaggle dataset locally

Install the app dependencies and the optional Kaggle downloader:

\`\`\`powershell
python -m pip install -r requirements.txt
python -m pip install kagglehub
python download_dataset.py
\`\`\`

The downloader uses this dataset by default:

\`wafaaelhusseini/extended-recipes-dataset-64k-dishes\`

It finds the downloaded CSV and copies the selected file to \`data/IndianFoodDataset.csv\`. If KaggleHub reports multiple CSV files, choose one explicitly:

\`\`\`powershell
python download_dataset.py --csv-name "the-file-name.csv"
\`\`\`

If Kaggle requires authentication, follow KaggleHub's authentication instructions. Check the dataset license and usage terms before redistribution or commercial use. The CSV and local database are intentionally excluded from Git.

## 2. Import locally into SQLite

\`\`\`powershell
python import_dataset.py
\`\`\`

Then start the app:

\`\`\`powershell
uvicorn app.main:app --reload
\`\`\`

Open \`http://127.0.0.1:8000\`; API docs are at \`http://127.0.0.1:8000/docs\`.

The importer understands common headers such as \`title\`, \`RecipeName\`, \`TranslatedRecipeName\`, \`ingredients\`, \`TranslatedIngredients\`, \`directions\`, \`instructions\`, \`Prep Time\`, \`Cook Time\`, \`Total Time\`, \`Cuisine\`, \`Course\`, \`Diet\`, and \`URL\`. JSON-array ingredient and instruction cells are supported. If the actual Kaggle CSV uses different headers, inspect its first row and extend \`parse_row()\` in \`import_dataset.py\`.

Imports are repeatable. Rows with a source URL are matched by recipe name and URL; rows without a URL are matched by recipe name and ingredient list. Use \`--replace\` only when you intentionally want to clear the target table before importing.

## 3. Configure hosted PostgreSQL for Vercel

A local SQLite database on your laptop cannot serve requests to Vercel. Vercel's filesystem is ephemeral and is not a shared persistent database. Use a hosted PostgreSQL database, for example a dedicated Supabase project for Rasoi.

1. Create a PostgreSQL database/project with your provider.
2. Copy its PostgreSQL connection URI. For Supabase, use the connection string recommended for your runtime/network and include \`sslmode=require\` when the provider's URI requires it.
3. Set \`DATABASE_URL\` in your local PowerShell session to perform the one-time cloud import.
4. Run the importer against the same local CSV. The mapping/cleaning runs on your laptop, but the rows are written directly to the hosted PostgreSQL database.
5. Add the same \`DATABASE_URL\` value to Vercel Project Settings → Environment Variables for the Production environment, then redeploy.

Example (replace the placeholder with your real private connection string):

\`\`\`powershell
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require"
python import_dataset.py
Remove-Item Env:DATABASE_URL
\`\`\`

The importer creates the \`recipes\` table and name index if they do not exist. Alternatively, run \`database/schema.sql\` in your hosted PostgreSQL SQL editor first. **Never commit the actual database URI or credentials to GitHub.** The \`.env\` file is ignored by Git.

For local SQLite development, leave \`DATABASE_URL\` unset. When \`DATABASE_URL\` is set, the importer and app use PostgreSQL. The CSV remains on your laptop; it does not need to be uploaded to GitHub or copied into the Vercel deployment.

## 4. Deploy on Vercel

The repository includes \`api/index.py\` and \`vercel.json\` to expose the FastAPI app through Vercel's Python runtime.

Before deploying:
- Add \`DATABASE_URL\` in Vercel's Environment Variables.
- Ensure the cloud import has completed successfully.
- Redeploy after changing environment variables.
- Check \`/api/health\`. It reports the active database backend and recipe count without exposing credentials.
- Test \`/api/recipes\`, \`/api/recipes/random\`, \`/api/recipes/{id}\`, and \`POST /api/recipes/search\`.

The application intentionally fails startup on Vercel if \`DATABASE_URL\` is missing rather than silently creating an empty SQLite database. It does not run the dataset importer during Vercel startup or cold starts.

## Dependency and database access controls

Runtime dependencies are pinned in `requirements.txt` using the versions resolved by the project's Python 3.12 CI environment. CI checks for unresolved merge-conflict markers, compiles the Python sources, runs importer regression tests, and audits the pinned dependency set with `pip-audit`.

Rasoi's FastAPI backend accesses PostgreSQL with the server-side `DATABASE_URL`. The browser application does not need direct Supabase Data API access to recipe tables. The catalog, retained backup, and private source rows have row-level security enabled, and the `anon` and `authenticated` client roles have been revoked direct table access. Do not add public read policies unless the app is intentionally redesigned to query Supabase directly and the exposure has been reviewed.

The production hardening SQL is tracked at `supabase/migrations/20261014153707_harden_rasoi_recipe_catalog_access.sql`. It must be kept in sync with any future schema or permission changes.

## API

- \`POST /api/recipes/search\` — search by ingredients, diet, cuisine, course, and maximum time.
- \`GET /api/recipes?q=rice&limit=20&offset=0\` — browse/filter catalog with pagination.
- \`GET /api/recipes/random\` — choose a random matching recipe.
- \`GET /api/recipes/{id}\` — retrieve recipe ingredients and instructions.
- \`GET /api/filters\` — list available filter values.
- \`GET /api/health\` — report dataset status, recipe count, and backend type.

Example search JSON:

\`\`\`json
{"ingredients":["aloo","tomato","jeera"],"diet":"vegetarian","limit":20}
\`\`\`

## Tests

Run the local importer regression tests:

\`\`\`powershell
python -m unittest discover -s tests -v
\`\`\`

These tests use temporary SQLite databases and do not require a Kaggle download or cloud credentials. A live PostgreSQL/Vercel smoke test still needs to be run after configuring the cloud database.

## Data limitations

Ingredient normalization uses a small Hindi/English alias list and heuristic text parsing. Diet classification is based on source labels and cannot guarantee allergy safety or dietary compliance. A \`can_make_now\` result means all parsed listed ingredients matched the submitted input; optional items and pantry staples can make that estimate imperfect. Review complete instructions before cooking.
