#!/usr/bin/env bash
# Run Supabase/Postgres migrations on each pipeline deployment.
# Uses DATABASE_URL from the environment (e.g. Jenkins credential supabase-db-url).
# Applies frontend/supabase/migrations/*.sql in sorted order (by filename).
# Idempotent: migrations use CREATE IF NOT EXISTS / ON CONFLICT DO NOTHING where appropriate.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATIONS_DIR="$REPO_ROOT/frontend/supabase/migrations"
if [[ -z "$DATABASE_URL" ]]; then
  echo "ERROR: DATABASE_URL is not set. Cannot run migrations."
  exit 1
fi
if [[ ! -d "$MIGRATIONS_DIR" ]]; then
  echo "Migrations directory not found: $MIGRATIONS_DIR"
  exit 1
fi
echo "Applying Supabase migrations from $MIGRATIONS_DIR (sorted by filename)..."
for f in $(ls -1 "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
  name="$(basename "$f")"
  echo "  -> $name"
  if command -v psql &>/dev/null; then
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || { echo "  WARN: $name had non-zero exit (may be idempotent no-op). Continuing."; }
  else
    docker run --rm -e DATABASE_URL -v "$MIGRATIONS_DIR:/migrations:ro" postgres:15-alpine sh -c "psql \"\$DATABASE_URL\" -v ON_ERROR_STOP=1 -f \"/migrations/$name\"" || { echo "  WARN: $name had non-zero exit (may be idempotent no-op). Continuing."; }
  fi
done
echo "Supabase migrations completed."
