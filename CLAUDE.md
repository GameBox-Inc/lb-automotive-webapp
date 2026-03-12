# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated:** March 5, 2026
**Repository:** `GameBox-Inc/lb-automotive-webapp`
**Branch:** `release/v0.1`

---

## Project Overview

**LB Automotive Dashboard** is a full-stack automotive shop management system designed for appointment scheduling, customer relationship management (CRM), staff tracking, and automated phone system (IVR) integration via Twilio.

### Core Features
- 📅 **Appointment Scheduling** - 24/7 booking with dynamic business hours per day
- 👥 **Customer Management** - CRM with history tracking and search
- 🛠️ **Service Catalog** - Manage services, pricing, and categories
- 👨‍🔧 **Staff Management** - Track mechanics and service advisors
- 📞 **Twilio IVR Integration** - Automated phone system for booking
- ⚙️ **Admin Settings** - Configurable business hours, IVR messages, and system settings
- 🔒 **Security Hardened** - 15+ security improvements implemented

---

## Architecture

### Current State (Production)
- **Server:** Hetzner 2GB RAM / 2 vCPU / 40GB SSD - **Optimized for low resources**
- **Frontend:** React 18 + TypeScript + Vite + TailwindCSS (128MB limit)
- **Backend:** FastAPI (Python 3.11+) with PostgreSQL/Supabase (384MB limit)
- **Cache/Queue:** Redis (64MB limit, LRU eviction)
- **Reverse Proxy:** Frontend Nginx → Backend (replaces K3s Ingress)
- **Ingress Routing:** Traefik v3 via Kubernetes Gateway API (Cloudflare Tunnel → Traefik → services)
- **Secrets Management:** K8s Secrets for lb-automotive backend (app-secrets, twilio-secrets, anthropic-secrets). No Vault dependency for the app.
- **Deployment:** Kubernetes (K3s) on Hetzner server (178.156.223.196)
- **Domain:** kozytherocket.space
- **CI/CD:** Jenkins (Dockerized, self-hosted) — replaced GitHub Actions
- **LLM:** Anthropic Claude API (Ollama removed due to memory constraints)
- **VPN:** WireGuard (10.100.0.0/24, app accessible at 10.100.0.1:30080)

### Tech Stack Details

**Backend:**
- FastAPI with Pydantic V2 models
- PostgreSQL/Supabase (psycopg2) with optional read replica
- JWT authentication (python-jose)
- Redis for caching (64MB limit for 2GB server), rate limiting, and session management
- Alembic for database migrations
- Twilio integration for IVR
- LLM integration: Anthropic Claude (cloud) - **Ollama removed for 2GB server**
- Prometheus-compatible metrics

**Frontend:**
- React 18 with TypeScript
- Vite 5.4 build tool
- TailwindCSS 3.4 for styling
- React Router v6 for navigation
- Recharts for analytics visualization
- React Hot Toast for notifications
- Custom API client (`src/lib/supabase.ts` - misleading name, it's a generic API wrapper)

**Infrastructure:**
- Docker & Docker Compose (for local development)
- K3s (lightweight Kubernetes) in production - **Optimized for 2GB RAM**
- Kubernetes manifests (in `deployment/k8s/`) with strict memory limits
- Cloudflare Tunnel (for zero-exposed-ports public access via Traefik)
- WireGuard VPN (for secure server access, subnet 10.100.0.0/24)
- Jenkins CI/CD (Dockerized, `Jenkinsfile` in repo root)
- GitHub Container Registry (GHCR) for Docker images
- Application secrets via K8s Secrets in `lb-automotive` (see `deployment/k8s/create-secrets.sh`). Vault may remain in `gamebox-security` for other workloads.
- Traefik v3 as Gateway API ingress controller
- Automated log rotation and compression (7-day retention)
- Monthly database archiving (K8s CronJob)

---

## Project Structure

```
lb-automotive-dashboard/
├── frontend/                    # React frontend application
│   ├── src/
│   │   ├── pages/              # Page components (Login, AdminIVR, etc.)
│   │   ├── components/         # Reusable UI components
│   │   ├── lib/                # Utilities (supabase.ts = API client)
│   │   └── types/              # TypeScript type definitions
│   └── package.json
│
├── python-backend/              # FastAPI backend
│   ├── main.py                 # Application entry point
│   ├── database.py             # DB initialization & utilities
│   ├── auth.py                 # JWT authentication
│   ├── security.py             # Security middleware & validators
│   ├── models.py               # Pydantic models
│   ├── routes/                 # API route handlers
│   │   ├── appointments.py
│   │   ├── auth_routes.py
│   │   ├── business_hours.py  # Per-day business hours (24/7 booking)
│   │   ├── customers.py
│   │   ├── services.py
│   │   ├── settings.py
│   │   ├── staff.py
│   │   └── twilio_webhook.py   # IVR webhook handler
│   ├── scheduler.py            # Appointment slot generation
│   └── requirements.txt
│
├── deployment/
│   ├── docker/                 # Docker Compose & Dockerfiles
│   ├── k8s/                    # Kubernetes manifests (future)
│   ├── scripts/                # Deployment & setup scripts
│   └── ansible/                # Ansible playbooks
│
├── .github/workflows/          # CI/CD pipelines
│   └── gamebox-engine.yaml     # Main CI/CD workflow
│
└── Documentation files:
    ├── API_REFERENCE.md
    ├── SECURITY_IMPROVEMENTS_SUMMARY.md
    ├── ARCHITECTURE_GAP_ANALYSIS.md
    └── [various setup guides]
```

---

## Key Conventions & Patterns

### Backend (FastAPI)

**Authentication:**
- JWT tokens stored in `Authorization: Bearer <token>` header
- Admin-only endpoints use `get_current_admin_user()` dependency
- Regular endpoints use `get_current_user()` dependency
- Tokens expire after 30 days

**API Structure:**
- All API routes prefixed with `/api`
- Routes organized in `routes/` directory
- Pydantic models in `models.py` for request/response validation
- Database access via `database.py` utilities

**Database:**
- PostgreSQL/Supabase via `python-backend/database.py` — `DATABASE_URL` required (PostgreSQL only)
- Optional `DATABASE_READ_URL` for read replica
- Connection management via `get_db_connection()` and `DatabaseContextManager`
- Parameterized queries only — use `%s` placeholders (NEVER use string concatenation for SQL)
- Foreign key relationships enforced
- Always close connections after use

**Security:**
- Input sanitization via `security.py::sanitize_input()`
- Rate limiting: 300 req/min per IP (configured in middleware)
- CORS: Explicit origins only (no wildcards)
- Security headers: CSP, HSTS, X-Frame-Options, X-XSS-Protection
- Password policy: 12+ chars, uppercase, lowercase, digit, special char
- Global exception handlers prevent stack trace leakage

### Frontend (React)

**API Client:**
- Centralized in `src/lib/supabase.ts` (despite name, it's a generic API client)
- All API calls go through this client
- JWT token stored in `localStorage` (TODO: migrate to httpOnly cookies)
- Automatic token refresh handling

**State Management:**
- React hooks for local state
- No global state management library (consider adding if needed)

**Styling:**
- TailwindCSS utility classes
- Responsive design patterns

**Type Safety:**
- TypeScript interfaces in `src/types/index.ts`
- API responses typed via interfaces

### Database Operations Pattern

**Always use parameterized queries:**
```python
from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
try:
    # CORRECT: Use %s placeholders (PostgreSQL)
    cursor.execute(
        "SELECT * FROM table WHERE id = %s",
        (record_id,)
    )
    result = cursor.fetchone()
    conn.commit()
finally:
    conn.close()
```

**NEVER concatenate SQL strings:**
```python
# WRONG - SQL injection vulnerability!
cursor.execute(f"SELECT * FROM table WHERE id = {record_id}")
```

### Environment Variables

**Required (No Defaults):**
- `SECRET_KEY` - JWT signing secret (generate with `openssl rand -hex 32`)
- `ALLOWED_ORIGINS` - Comma-separated CORS origins (e.g., `http://localhost:5173,https://kozytherocket.space`)

**Twilio IVR:**
```bash
TWILIO_ACCOUNT_SID=<account_sid>
TWILIO_AUTH_TOKEN=<auth_token>
TWILIO_PHONE_NUMBER=<phone_number>
```

**LLM Configuration:**
```bash
LLM_PROVIDER=ollama                          # or "anthropic"
ANTHROPIC_API_KEY=<api_key>                  # if using Anthropic
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022   # Claude model
OLLAMA_HOST=http://ollama:11434              # Ollama endpoint
OLLAMA_MODEL=smollm2:135m                    # Ollama model
```

**Optional:**
```bash
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql://user:pass@host:5432/dbname  # Required in production
DATABASE_READ_URL=postgresql://user:pass@replica:5432/dbname  # Optional read replica
CSP_POLICY=strict  # or "development"
```

---

## Important Features & Implementations

### 24/7 Booking System
- **Status:** ✅ Implemented
- **Files:**
  - `python-backend/database.py` - `business_hours` table
  - `python-backend/routes/business_hours.py` - Per-day hours API
  - `python-backend/scheduler.py` - Dynamic slot generation
  - `python-backend/routes/twilio_webhook.py` - No call blocking
  - `frontend/src/pages/AdminIVR.tsx` - Per-day hours UI
- **Key:** Business hours defined per day (Mon-Sun), IVR accepts calls 24/7, appointments scheduled for future days even if currently closed

### Security Improvements
- **Status:** ✅ 15+ improvements completed
- **See:** `SECURITY_IMPROVEMENTS_SUMMARY.md`
- **Key Changes:**
  - SECRET_KEY hardening (no defaults)
  - CORS whitelist only
  - Password policy enforcement
  - Input sanitization
  - Security headers
  - Rate limiting
  - Global exception handlers

### CI/CD Pipeline (Jenkins)
- **Status:** ✅ Production pipeline running
- **File:** `Jenkinsfile` (repo root)
- **Process:**
  1. Backend tests (`pytest`)
  2. Frontend lint + build
  3. Docker images built & pushed to GHCR
  4. K8s manifests synced to server via SCP
  5. `kubectl apply` for all manifests
  6. Ensure app-secrets exist (from Jenkins credentials secret-key, allowed-origins)
  7. `kubectl set image` to update deployments
  8. Rollout status verification
- **Jenkins:** Dockerized, accessible on server
- **Key credentials (in Jenkins):** `github-token`, `lb-server-ssh`, `secret-key`, `allowed-origins`

### Secrets Management (K8s Secrets)
- **Status:** Backend reads from K8s Secrets (no Vault dependency). Create via `deployment/k8s/create-secrets.sh` or Jenkins "Ensure App Secrets" stage.
- **Secrets:** `app-secrets` (SECRET_KEY, ALLOWED_ORIGINS, DATABASE_URL, REDIS_URL, LLM_PROVIDER, CSP_POLICY), `twilio-secrets`, `anthropic-secrets` (optional).
- **Jenkins:** Add secret-text credentials `secret-key` and `allowed-origins`; pipeline creates/updates `app-secrets`. For Twilio/Anthropic run `create-secrets.sh` on the server once.

### Routing Architecture
- **VPN users:** `10.100.0.1:30080` → frontend Nginx → `proxy_pass http://backend:8000` for `/api/*`
- **Public (Twilio):** Cloudflare Tunnel → Traefik → `lb-automotive-routes.yaml` → backend
- **Frontend Nginx config:** `deployment/docker/nginx.conf` (copied into Docker image at build)
- **⚠️ Ingress objects are deleted** by Jenkinsfile — all routing via Nginx + Traefik

---

## Database Schema

### Key Tables
- **users** - Authentication (username, hashed password, role)
- **customers** - CRM data (name, phone, email, history)
- **staff** - Mechanics and advisors
- **services** - Service catalog with pricing
- **appointments** - Customer appointments with status tracking
- **business_hours** - Per-day business hours (0=Monday, 6=Sunday)
- **settings** - System configuration (IVR messages, etc.)
- **call_states** - IVR call state management
- **ivr_logs** - IVR interaction logs

### Migrations
- Alembic configured in `python-backend/alembic/`
- Standalone migration script: `python-backend/migrate_business_hours.py`

---

## Deployment

### Current Production Setup
- **Server:** Hetzner (178.156.223.196)
- **User:** `lb-admin`
- **K8s manifests on server:** `~/k8s-manifests/k8s/`
- **Method:** Kubernetes (K3s) via Jenkins pipeline
- **Domain:** kozytherocket.space
- **Access:** Cloudflare Tunnel (public) or WireGuard VPN (internal)
- **SSH:** Port 22 (Ansible playbook for port 2222 exists but not yet applied)

### Deployment Process
1. Push to `release/v0.1` branch
2. Jenkins triggers automatically
3. Runs backend tests + frontend build
4. Builds & pushes Docker images to GHCR
5. SCPs K8s manifests to `~/k8s-manifests/` on server
6. `kubectl apply` for all namespaces + manifests
7. Ensures app-secrets exist (from Jenkins credentials)
8. `kubectl set image` to update backend + frontend deployments
9. Waits for rollout completion

### Manual Deployment
```bash
# SSH to server
ssh lb-admin@178.156.223.196

# Apply manifests
sudo k3s kubectl apply -f ~/k8s-manifests/k8s/redis.yaml \
  -f ~/k8s-manifests/k8s/backend.yaml \
  -f ~/k8s-manifests/k8s/frontend.yaml

# Update image
sudo k3s kubectl set image deployment/backend backend=ghcr.io/gamebox-inc/lb-automotive-backend:<TAG> -n lb-automotive
sudo k3s kubectl set image deployment/frontend frontend=ghcr.io/gamebox-inc/lb-automotive-frontend:<TAG> -n lb-automotive
```

---

## Development Guidelines

### Adding New Features

**Backend:**
1. Create Pydantic models in `models.py`
2. Add route handlers in `routes/`
3. Register router in `main.py`
4. Add database schema changes (if needed)
5. Write tests (if applicable)

**Frontend:**
1. Add TypeScript interfaces in `src/types/index.ts`
2. Add API methods in `src/lib/supabase.ts`
3. Create page/component in `src/pages/` or `src/components/`
4. Add routing if new page

### Security Checklist for New Features
Every new feature MUST follow these security practices:

- [ ] Input validation (Pydantic models)
- [ ] Input sanitization (`security.py::sanitize_input()`)
- [ ] Parameterized database queries (NEVER concatenate SQL strings)
- [ ] Authentication/authorization checks (`get_current_user()` or `get_current_admin_user()`)
- [ ] Rate limiting (applied globally at 300 req/min per IP)
- [ ] CORS configuration (explicit whitelist via `ALLOWED_ORIGINS`)
- [ ] Error handling (global exception handlers prevent stack traces)

**Common vulnerabilities to avoid:**
- SQL injection (use parameterized queries)
- XSS (sanitize inputs, CSP headers enabled)
- Command injection (validate/sanitize shell commands)
- Information leakage (exception handlers prevent stack traces)

### Code Style
- **Python:** Follow PEP 8, use type hints
- **TypeScript:** Use interfaces, avoid `any` types
- **Naming:** Descriptive names, consistent patterns

---

## Known Issues & TODOs

### High Priority
1. **Server Resources** - 2GB RAM is minimal; upgrade to 4GB+ recommended for production
2. **Connection Pooling** - Full implementation needed
4. **JWT Storage** - Move from localStorage to httpOnly cookies
5. **CSRF Protection** - Implement CSRF tokens

### Medium Priority
- TLS/HTTPS certificate automation (currently self-signed)
- Enhanced monitoring and observability
- Multi-business architecture (see `ARCHITECTURE_GAP_ANALYSIS.md`)
- Restore Ollama support (requires 8GB+ RAM server)

### Recently Completed
- ✅ PostgreSQL/Supabase migration (SQLite removed)
- ✅ Backend uses K8s Secrets (no Vault dependency)
- ✅ Kubernetes production deployment (K3s on 2GB server)
- ✅ Memory optimization for low-resource environment
- ✅ Automated log rotation and compression
- ✅ Disk space monitoring
- ✅ Ollama removed (uses Anthropic Claude API instead)

### Known Bugs
- `getCases()` and `createCase()` methods missing from API client (StaffDashboard needs them)

---

## Important Files Reference

### Configuration
- `docker-compose.yml` - Local development
- `deployment/docker/docker-compose.yml` - Docker Compose deployment (deprecated)
- `deployment/k8s/` - Kubernetes manifests (production)
- `.github/workflows/gamebox-engine.yaml` - CI/CD pipeline
- `python-backend/.env.example` - Environment variable template

### Documentation
- `DEPLOYMENT_2GB_SERVER.md` - **Complete 2GB server deployment guide**
- `QUICK_FIX_2GB_SERVER.md` - **Emergency OOM fix guide**
- `API_REFERENCE.md` - API endpoint documentation
- `SECURITY_IMPROVEMENTS_SUMMARY.md` - Security changes log
- `ARCHITECTURE_GAP_ANALYSIS.md` - Current vs. future architecture
- `python-backend/README.md` - Backend-specific docs
- `docs/howto/vault-transit-token-management.md` - **Vault transit token + Jenkins credential management**
- `docs/incidents/common-failures.md` - Common failure modes and fixes
- `docs/architecture/vault-stability-and-improvements.md` - **Why Vault chain fails repeatedly and how to improve**

### Scripts
- `deployment/scripts/configure-vault-supabase.sh` - **Store Supabase/PostgreSQL URL in Vault**
- `deployment/scripts/remove_memory_hogs.sh` - **Remove Ollama/ArgoCD to free RAM**
- `deployment/scripts/setup_log_rotation.sh` - **Setup automated log cleanup**
- `deployment/scripts/generate_vpn_client.sh` - WireGuard client generation
- `setup_git_on_server.sh` - Git repository initialization on server

---

## Testing

### Backend Tests
```bash
cd python-backend
pytest                      # Run all tests
pytest tests/test_auth.py   # Run specific test file
```

### Frontend Tests
```bash
cd frontend
npm run test               # Run Vitest tests
npm run test:ui            # Interactive test UI
npm run test:coverage      # Coverage report
```

### Manual Testing
- API: http://localhost:8000/docs (Swagger UI)
- Frontend: http://localhost:5173 (dev server)

---

## Common Development Tasks

### Add New API Endpoint

**1. Create Pydantic models** in `python-backend/models.py`:
```python
class NewFeatureRequest(BaseModel):
    field: str

class NewFeatureResponse(BaseModel):
    id: int
    field: str
```

**2. Create route** in `python-backend/routes/` (e.g., `new_feature.py`):
```python
from fastapi import APIRouter, Depends
from auth import get_current_user
from models import NewFeatureRequest, NewFeatureResponse
from security import sanitize_input

router = APIRouter()

@router.post("/api/new-feature")
async def create_feature(
    request: NewFeatureRequest,
    current_user: dict = Depends(get_current_user)
):
    # Input sanitization
    safe_field = sanitize_input(request.field)

    # Database operations (always use parameterized queries)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO table (field) VALUES (?)",
        (safe_field,)
    )
    conn.commit()
    conn.close()

    return {"id": cursor.lastrowid, "field": safe_field}
```

**3. Register router** in `python-backend/main.py`:
```python
from routes import new_feature
app.include_router(new_feature.router)
```

**4. Add frontend type** in `frontend/src/types/index.ts`:
```typescript
export interface NewFeature {
  id: number;
  field: string;
}
```

**5. Add API client method** in `frontend/src/lib/supabase.ts`:
```typescript
async createFeature(data: { field: string }): Promise<NewFeature> {
  return this.request('/new-feature', {
    method: 'POST',
    headers: this.getHeaders(),
    body: JSON.stringify(data)
  });
}
```

### Update Database Schema
1. Modify `database.py` initialization
2. Create Alembic migration: `alembic revision --autogenerate -m "description"`
3. Apply migration: `alembic upgrade head`
4. Or use standalone script for simple changes

### Deploy Changes
1. Commit and push to `release/v0.1`
2. GitHub Actions will automatically deploy
3. Monitor Actions tab for deployment status
4. Check server logs if issues: `docker logs lb-auto-backend`

---

## Server Access

### SSH Access
```bash
ssh lb-admin@178.156.223.196  # Port 22 (default)
# NOTE: Ansible playbook exists to change to port 2222 but not yet applied
```

### WireGuard VPN
- Generate client config: `deployment/scripts/generate_vpn_client.sh <username>`
- Server endpoint: `178.156.223.196:51820`
- Subnet: `10.100.0.0/24`
- App via VPN: `http://10.100.0.1:30080` (frontend), `:30800` (backend)

### Cloudflare Tunnel
- Deployed in `gamebox-security` namespace (2 replicas)
- Routes public traffic through Traefik
- Twilio webhook: `twilio.kozytherocket.space/lb-automotive/api/twilio/`

---

## Future Architecture Vision

See `ARCHITECTURE_GAP_ANALYSIS.md` for detailed comparison.

**Current:** Single-instance, K3s, PostgreSQL/Supabase
**Target:** Multi-business, Kubernetes clusters, high availability

**Migration Path:**
1. Phase 1: ✅ PostgreSQL migration + production K8s (done)
2. Phase 2: High availability (replicas, redundancy)
3. Phase 3: Multi-business architecture
4. Phase 4: Advanced features (service mesh, multi-region)

**Current Status:** ~60-70% away from target architecture (infrastructure gap, not code gap)

---

## Quick Reference

### Default Credentials
- Username: `admin`
- Password: `admin123`
- **⚠️ Change in production!**

### Key URLs
- Production: https://kozytherocket.space
- API Docs: http://localhost:8000/docs (dev)
- Frontend: http://localhost:5173 (dev)

### Development Commands

**Frontend:**
```bash
cd frontend
npm ci                    # Install dependencies
npm run dev              # Start dev server (localhost:5173)
npm run build            # Production build
npm run lint             # Run ESLint
npm run test             # Run Vitest tests
npm run test:ui          # Interactive test UI
npm run test:coverage    # Coverage report
```

**Backend:**
```bash
cd python-backend
pip install -r requirements.txt  # Install dependencies
python main.py                   # Start FastAPI (localhost:8000)
pytest                           # Run tests
bandit -r .                      # Security scan
```

**Docker (Local Development):**
```bash
# Root directory - uses docker-compose.yml
docker compose up -d --build              # Start all services
docker compose logs -f python-backend     # Follow backend logs
docker compose down                       # Stop all services
```

**Production Deployment:**
```bash
# On server at /opt/lb-automotive-dashboard
cd deployment/docker
docker compose up -d --build --force-recreate  # Deploy
docker compose ps                              # Check status
docker logs lb-auto-backend --tail 50          # View logs
docker exec lb-auto-backend python migrate_business_hours.py  # Run migrations
```

---

## Notes for AI Assistants

When working on this project:

1. **Always check existing patterns** - The codebase has established conventions for API routes, models, and frontend components.

2. **Security first** - Always validate input, use parameterized queries, check authentication/authorization.

3. **Database changes** - If modifying schema, consider migration scripts or Alembic migrations.

4. **Environment variables** - Remember `SECRET_KEY` and `ALLOWED_ORIGINS` are required (no defaults). Injected via Vault in production.

5. **Testing** - Test changes locally before pushing. Jenkins pipeline deploys automatically on push.

6. **Documentation** - **Always update `CLAUDE.md`** when making architecture or deployment changes.

7. **24/7 Booking** - Business hours are per-day. IVR accepts calls 24/7. Appointments can be scheduled for future days even if currently closed.

8. **Repository name** - The GitHub repo is `lb-automotive-webapp` (not `lb-automotive-dashboard`).

9. **Case sensitivity** - Use kebab-case for filenames. Windows is case-insensitive but Linux Docker builds are case-sensitive. This has caused build failures.

10. **`security_config.json`** - Required by `security.py` at startup. Contains SQL/XSS regex patterns. Must be in the Docker image or mounted via ConfigMap.

11. **App secrets** - Backend uses K8s Secrets (`app-secrets`, `twilio-secrets`, `anthropic-secrets`). Create via `deployment/k8s/create-secrets.sh` or Jenkins credentials `secret-key` and `allowed-origins`.

12. **Frontend Nginx proxy** - The production Nginx config is at `deployment/docker/nginx.conf`, NOT `frontend/nginx.conf`. It proxies `/api/*` to `http://backend:8000`.

13. **Ingress is deleted** - The Jenkinsfile removes legacy Ingress objects. All routing is via frontend Nginx (VPN) and Traefik HTTPRoutes (public/Cloudflare).

14. **SSH connection limits** - The server may drop SSH connections if too many are opened rapidly. Combine kubectl commands into single SSH sessions when possible.

15. **K3s NetworkPolicy + DNAT** — `ipBlock` rules with ClusterIPs (e.g. `10.43.0.1/32`) don't work because kube-proxy DNATs them to pod IPs before policy evaluation. Service port → container port mapping also breaks `port` rules. Avoid restrictive egress policies on Traefik and cloudflared.

16. **Traefik CRD middlewares + Gateway API** — Traefik v3.6 cannot resolve Middleware CRDs referenced via `ExtensionRef` in HTTPRoutes, even with `kubernetesCRD.enabled=true`. Use native Gateway API filters (`URLRewrite`, `RequestHeaderModifier`) instead.

17. **Twilio webhook path** — Twilio sends to `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`. The HTTPRoute uses `URLRewrite` `ReplacePrefixMatch` to strip `/lb-automotive` → backend sees `/api/twilio/webhook`.

18. **Stale HTTPRoutes** — Delete any manually-created HTTPRoutes not in `lb-automotive-routes.yaml`. Stale routes referencing broken middlewares cause Traefik 502 errors for ALL routes.

19. **Traefik Service port** — The Traefik K8s Service maps port **80** → container port **8000**. All internal references (cloudflared config, NetworkPolicies) must use port 80 for the Service, not 8000.

---

**Last Updated:** March 5, 2026  
**Maintainer:** GameBox-Inc
