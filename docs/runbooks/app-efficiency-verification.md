# App efficiency hardening — verification

Use this after deploying **DB pooling**, **metric path normalization**, and **conditional `seed_data()`**.

## 1. Database connection pooling

- **Default:** `DB_POOL_ENABLED=true` (see [`python-backend/database.py`](../../python-backend/database.py)). Each checkout for `use_app_role=True` reapplies RLS session vars.
- **Tune:** `DB_POOL_MIN`, `DB_POOL_MAX` (env). For external poolers (PgBouncer), you can set `DB_POOL_ENABLED=false` and point `DATABASE_URL` at the pooler.
- **Check (Postgres):** active connections from app role should stay bounded under load vs one new connection per request.

```sql
-- On Postgres (adjust app user name)
SELECT count(*) FROM pg_stat_activity WHERE usename = current_user;
```

- **Load:** `npm run debug:webhook:stress` against a dev endpoint (with `TWILIO_SKIP_VALIDATION=true` only in non-prod). Watch for connection errors or timeouts.

## 2. Prometheus HTTP metrics cardinality

- **Before:** `http_requests_total` used raw `request.url.path`.
- **After:** labels use the route template when available, else UUID/numeric segments become `{id}` (see [`python-backend/observability/monitoring.py`](../../python-backend/observability/monitoring.py)).
- **Check:** scrape `/metrics` and confirm `endpoint` labels are stable templates (e.g. `/api/appointments/{id}`) not unbounded unique paths.

## 3. Startup / `seed_data()`

- **Production default:** `seed_data()` is **skipped** unless `RUN_SEED_ON_STARTUP=true` or `ENVIRONMENT` is `development` / `test` (see [`python-backend/main.py`](../../python-backend/main.py)).
- **Required:** Jenkins **Run Supabase Migrations** stage must keep schema and required rows (e.g. `business_hours`) in sync. Do not rely on per-pod seed in production.
- **One-off:** To force seed in a environment, set `RUN_SEED_ON_STARTUP=true` on the backend Deployment temporarily, then remove.

## 4. Redis (IVR)

- Manifest: [`deployment/k8s/redis.yaml`](../../deployment/k8s/redis.yaml) (`maxmemory`, LRU policy).
- Under stress, watch **evicted_keys** and IVR `step=processing` behavior. If results vanish before Twilio polls, increase Redis memory **and** container limit together.
- Backend: **`IVR_LLM_CONCURRENCY_LIMIT`** (default `4` in [`python-backend/utils/background_tasks.py`](../../python-backend/utils/background_tasks.py)) caps concurrent LLM work per process.

## 5. Rollout timing

- `kubectl rollout restart deployment/backend -n lb-automotive` and time until pods are **Ready**; skipping seed should shorten startup on cold replicas.

## 6. Automated tests

```bash
cd python-backend
pytest tests/test_metrics_endpoint_normalize.py tests/test_rls_session_vars.py
```

Full suite requires PostgreSQL reachable at `DATABASE_URL` (see `pytest.ini`).
