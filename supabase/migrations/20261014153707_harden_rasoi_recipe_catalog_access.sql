-- Rasoi serves recipes through its FastAPI backend using a trusted,
-- server-side DATABASE_URL. Supabase client roles do not need direct table access.
-- Keep raw source rows and catalog backups unavailable to anon/authenticated roles.

REVOKE ALL PRIVILEGES ON TABLE public.recipes FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA private FROM anon, authenticated;
REVOKE USAGE, CREATE ON SCHEMA private FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA private FROM anon, authenticated;

ALTER TABLE public.recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE private.rasoi_source_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE private.recipes_catalog_backup_20261014 ENABLE ROW LEVEL SECURITY;
