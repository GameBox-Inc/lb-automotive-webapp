# Environment Variables

**Last Updated:** March 2026  
**Source:** Vault (production) or `.env` (local)

---

## Required (No Defaults)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing secret (e.g. `openssl rand -hex 32`) |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (e.g. `http://localhost:5173,https://kozytherocket.space`) |
| `DATABASE_URL` | PostgreSQL/Supabase connection string (production only) |

---

## Twilio

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (HMAC validation) |
| `TWILIO_PHONE_NUMBER` | Twilio phone number |
| `TWILIO_WEBHOOK_BASE_URL` | Base URL for webhook (e.g. `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`) |
| `TWILIO_SKIP_VALIDATION` | **Dev only:** `true` to skip HMAC validation. Never use in production. |

---

## Database

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL primary (required) |
| `DATABASE_READ_URL` | Optional read replica |

---

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis URL (cache, rate limit, sessions) |

---

## LLM (Anthropic)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `ANTHROPIC_MODEL` | Model (e.g. `claude-3-5-sonnet-20241022`) |

---

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` \| `production` |
| `CAPTCHA_REQUIRED` | `true` | Require captcha on login |
| `RATE_LIMIT_PER_MINUTE` | `120` | Rate limit per IP |
| `CSP_POLICY` | `strict` | Content Security Policy |

---

## Vault Paths (Production)

| Secret Path | Variables |
|-------------|-----------|
| `secret/data/lb-automotive/app` | SECRET_KEY, ALLOWED_ORIGINS, REDIS_URL, CSP_POLICY, etc. |
| `secret/data/lb-automotive/twilio` | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_WEBHOOK_BASE_URL |
| `secret/data/lb-automotive/anthropic` | ANTHROPIC_API_KEY, ANTHROPIC_MODEL |
| `gamebox/data/clients/lb-autorepair/database` | url (DATABASE_URL), read_url (optional) |

---

## Local Development

Copy `python-backend/.env.example` to `.env` and fill in values. For local dev without Twilio:

```bash
TWILIO_SKIP_VALIDATION=true
DATABASE_URL=postgresql://localhost:5432/lb_automotive  # or use Supabase
```

---

## Related

- [CLAUDE.md](../../CLAUDE.md) — Environment Variables section
- [configure-vault-supabase.sh](../../deployment/scripts/configure-vault-supabase.sh)
