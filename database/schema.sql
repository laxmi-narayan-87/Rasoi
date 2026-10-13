-- Run once in the hosted PostgreSQL SQL editor if you prefer manual setup.
-- The Python importer also creates the recipes table automatically.
CREATE TABLE IF NOT EXISTS recipes (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    ingredients_raw TEXT,
    ingredient_list TEXT,
    ingredient_keys TEXT,
    instructions TEXT,
    prep_time TEXT,
    cook_time TEXT,
    total_time TEXT,
    servings TEXT,
    cuisine TEXT,
    course TEXT,
    diet TEXT,
    source_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_recipe_name ON recipes(name);
CREATE INDEX IF NOT EXISTS idx_recipe_cuisine ON recipes(cuisine);
CREATE INDEX IF NOT EXISTS idx_recipe_course ON recipes(course);
CREATE INDEX IF NOT EXISTS idx_recipe_diet ON recipes(diet);
