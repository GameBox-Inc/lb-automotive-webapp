# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated:** January 24, 2026
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
- **Frontend:** React 18 + TypeScript + Vite + TailwindCSS
- **Backend:** FastAPI (Python 3.11+) with SQLite database
- **Cache/Queue:** Redis
- **Reverse Proxy:** Traefik
- **Deployment:** Docker Compose on Hetzner server (178.156.223.196)
- **Domain:** kozytherocket.space
- **CI/CD:** GitHub Actions with self-hosted runner

### Tech Stack Details

**Backend:**
- FastAPI with Pydantic V2 models
- SQLite (WAL mode) - **Migration to PostgreSQL planned**
- JWT authentication (python-jose)
- Redis for caching, rate limiting, and session management
- Alembic for database migrations
- Twilio integration for IVR
- LLM integration: Ollama (local) and Anthropic Claude (cloud)
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
- Docker & Docker Compose
- Kubernetes manifests (in `deployment/k8s/`) - prepared, not yet deployed
- Traefik v2.10 reverse proxy (load balancing & routing)
- Cloudflare Tunnel (optional, for zero-exposed-ports access)
- WireGuard VPN (for secure server access)
- GitHub Actions with self-hosted runner for CI/CD
- GitHub Container Registry (GHCR) for Docker images

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
- SQLite with WAL mode (Write-Ahead Logging) at `python-backend/database.py:178`
- Connection management via `get_db_connection()` utility
- Parameterized queries only (NEVER use string concatenation for SQL)
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
    # CORRECT: Use ? placeholders
    cursor.execute(
        "SELECT * FROM table WHERE id = ?",
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
DATABASE_URL=sqlite:///./lb_automotive.db
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

### CI/CD Pipeline
- **Status:** ✅ Configured with self-hosted runner
- **File:** `.github/workflows/gamebox-engine.yaml`
- **Process:**
  1. Tests (backend + frontend)
  2. Build & push Docker images to GHCR
  3. Deploy on self-hosted runner (server)
  4. Run migrations
  5. Rebuild & restart containers
- **Runner:** Self-hosted on server at `/opt/actions-runner`

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
- **Directory:** `/opt/lb-automotive-dashboard`
- **Method:** Docker Compose
- **Domain:** kozytherocket.space
- **Access:** Cloudflare Tunnel or WireGuard VPN

### Deployment Process
1. Push to `release/v0.1` branch
2. GitHub Actions runs tests
3. Builds Docker images
4. Self-hosted runner deploys:
   - Pulls latest code
   - Runs migrations
   - Rebuilds containers
   - Restarts services

### Manual Deployment
```bash
cd /opt/lb-automotive-dashboard
git fetch origin
git reset --hard origin/release/v0.1
docker compose -f deployment/docker/docker-compose.yml up -d --build --force-recreate
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
1. **Database Migration** - SQLite → PostgreSQL (required for production scale)
2. **Connection Pooling** - Full implementation needed
3. **JWT Storage** - Move from localStorage to httpOnly cookies
4. **CSRF Protection** - Implement CSRF tokens
5. **Database Backups** - Automated backup system

### Medium Priority
- Kubernetes production deployment (manifests exist, not deployed)
- TLS/HTTPS certificate automation (currently self-signed)
- Enhanced monitoring and observability
- Multi-business architecture (see `ARCHITECTURE_GAP_ANALYSIS.md`)

### Known Bugs
- `getCases()` and `createCase()` methods missing from API client (StaffDashboard needs them)

---

## Important Files Reference

### Configuration
- `docker-compose.yml` - Local development
- `deployment/docker/docker-compose.yml` - Production deployment
- `.github/workflows/gamebox-engine.yaml` - CI/CD pipeline
- `python-backend/.env.example` - Environment variable template

### Documentation
- `API_REFERENCE.md` - API endpoint documentation
- `SECURITY_IMPROVEMENTS_SUMMARY.md` - Security changes log
- `ARCHITECTURE_GAP_ANALYSIS.md` - Current vs. future architecture
- `python-backend/README.md` - Backend-specific docs

### Scripts
- `deployment/scripts/generate_vpn_client.sh` - WireGuard client generation
- `deployment/scripts/setup_ollama.sh` - LLM service setup
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
ssh lb-admin@178.156.223.196
```

### WireGuard VPN
- Generate client config: `deployment/scripts/generate_vpn_client.sh <username>`
- Server endpoint: `178.156.223.196:51820`
- Subnet: `10.100.0.0/24`

### Cloudflare Tunnel
- Optional secure access method
- See: `CLOUDFLARE_TUNNEL_SETUP.md`

---

## Future Architecture Vision

See `ARCHITECTURE_GAP_ANALYSIS.md` for detailed comparison.

**Current:** Single-instance, Docker Compose, SQLite  
**Target:** Multi-business, Kubernetes clusters, PostgreSQL, high availability

**Migration Path:**
1. Phase 1: PostgreSQL migration + production K8s
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

## Notes for Claude

When working on this project:

1. **Always check existing patterns** - The codebase has established conventions for API routes, models, and frontend components.

2. **Security first** - Always validate input, use parameterized queries, check authentication/authorization.

3. **Database changes** - If modifying schema, consider migration scripts or Alembic migrations.

4. **Environment variables** - Remember `SECRET_KEY` and `ALLOWED_ORIGINS` are required (no defaults).

5. **Testing** - Test changes locally before pushing. The CI/CD pipeline will deploy automatically.

6. **Documentation** - Update relevant docs when making significant changes.

7. **24/7 Booking** - Business hours are per-day. IVR accepts calls 24/7. Appointments can be scheduled for future days even if currently closed.

8. **Repository name** - The GitHub repo is `lb-automotive-webapp` (not `lb-automotive-dashboard`).

---

**Last Updated:** January 24, 2026  
**Maintainer:** GameBox-Inc
