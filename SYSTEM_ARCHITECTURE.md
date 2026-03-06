# LB Automotive - System Architecture & Product Tiers

This document serves as the high-level Architecture Decision Record (ADR) and business packaging model for the LB Automotive Dashboard and IVR platform.

## 1. Current System Architecture

The platform is designed as a cloud-native, highly secure, and automated application stack running on Kubernetes.

### Infrastructure & Orchestration
* **Kubernetes (K3s):** Lightweight Kubernetes distribution serving as the container orchestration layer.
* **Traefik v3 (Gateway API):** Ingress controller managing external traffic, TLS termination, and request routing to internal services.
* **Cloudflare Tunnel (`cloudflared`):** Provides a secure, outbound-only connection to the Cloudflare edge, hiding the origin server's IP and protecting against DDoS attacks.

### Security & Secrets Management
* **HashiCorp Vault (Transit Auto-Unseal Architecture):** 
  * Replaced static Kubernetes secrets with dynamic secret injection.
  * **Dual-Vault Setup:** An isolated "Unseal Vault" provides a transit engine key to automatically unseal the "Main Vault" on pod restart.
  * **Kubernetes Auth Method:** Pods authenticate to Vault using their native ServiceAccount JWT tokens (via TokenReview).
  * **Vault Agent Injector:** Sidecar containers inject secrets (Twilio, Anthropic, DB URLs) directly into the application environment at runtime (`/vault/secrets/*.env`) without exposing them to the Kubernetes API.

### Application Stack
* **Frontend (React + Vite):** Modern Single Page Application compiled to static assets and served via an Nginx container.
* **Backend (Python / FastAPI):** Asynchronous API handling business logic, user authentication, and third-party webhooks.
* **Database (SQLite -> Postgres path):** Currently utilizing file-based SQLite (with WAL enabled) on a PersistentVolume for relational data (Appointments, Users, Staff).
* **Caching & State (Redis):** Distributed in-memory store used for API rate-limiting, CAPTCHA verification state, and session management.

### AI & Communications
* **Twilio Programmable Voice:** Handles incoming calls and webhooks to the backend for the Interactive Voice Response (IVR) system.
* **Anthropic Claude (LLM):** Powers the conversational AI logic for the IVR, making intelligent routing and booking decisions.

### CI/CD
* **Jenkins:** Declarative pipeline triggered via GitHub push. Handles Python/Node testing, Docker image building, pushing to GitHub Container Registry (GHCR), and applying Kubernetes manifests directly to the server.

---

## 2. Three-Tier SaaS Packaging Model

Given the robust, microservices-driven architecture we have built, the platform can be packaged and sold to automotive shops (or other service businesses) in three distinct tiers. This allows you to monetize the advanced security and AI features as premium add-ons.

### Tier 1: "Digital Garage" (Basic/Starter)
**Target:** Small, independent mechanics who just need an online booking presence and basic management.
* **Features:**
  * Custom Branded Web Dashboard (React/FastAPI).
  * Online Appointment Booking & Calendar Management.
  * Staff Scheduling & Service Catalog management.
  * Standard DDoS Protection (Cloudflare standard).
* **Technical Implementation:**
  * Runs on a multi-tenant database schema or lightweight isolated SQLite instance.
  * Does **not** include the AI IVR system.
  * Standard JWT authentication without strict Captcha enforcement.

### Tier 2: "AutoPilot IVR" (Pro/Business)
**Target:** Growing auto repair shops with dedicated front-desk staff who are overwhelmed by phone calls.
* **Features:**
  * *Everything in Tier 1, plus:*
  * **AI-Powered Phone Receptionist (IVR):** 24/7 AI voice agent (Twilio + Anthropic) to answer FAQs, quote standard services, and route emergencies.
  * **Automated Appointment Sync:** AI agent directly books customer appointments into the dashboard.
  * **Call Analytics & Insights:** Real-time dashboards tracking AI agent call volume, intent resolution rates, and drop-off points.
  * **Enhanced Web Security:** Redis-backed rate limiting and active CAPTCHA validation to stop bot booking spam.
* **Technical Implementation:**
  * Connects the tenant's Twilio sub-account to the `verify-webhook` pipeline.
  * Leverages the Anthropic LLM API for dynamic conversation state tracking (`call_states` in DB).

### Tier 3: "Enterprise Fleet" (Advanced/Zero-Trust)
**Target:** Franchise dealerships or multi-location garage networks requiring strict data security, compliance, and custom workflows.
* **Features:**
  * *Everything in Tier 2, plus:*
  * **Military-Grade Data Protection:** All API keys, customer PII encryption keys, and credentials are dynamically managed and rotated.
  * **Zero-Trust Network Access:** The application is entirely hidden from the public internet using private tunnels.
  * **Custom AI Prompt Engineering:** Tailored AI voices, multi-language support, and specific dealership upselling scripts.
  * **Advanced Multi-Location Analytics:** Roll-up reporting across multiple franchises and advanced data exports for business intelligence.
  * **Dedicated Infrastructure:** Single-tenant K8s deployment guaranteeing resources.
* **Technical Implementation:**
  * Uses the **HashiCorp Vault Transit Auto-Unseal** architecture. Each Enterprise client gets their isolated Vault path/policy.
  * **Cloudflare Zero-Trust Tunnels (`cloudflared`)** route traffic securely without opening any inbound firewall ports.
  * Jenkins pipeline handles dedicated, isolated deployments for the enterprise tenant.

---

## Technical Debt / Next Steps for Scale
To comfortably host dozens or hundreds of tenants on Tier 2/3:
1. **Database Migration:** The current SQLite implementation (`PRAGMA journal_mode=WAL`) is excellent for single-tenant, but for a true multi-tenant SaaS, migrating the backend SQLAlchemy models to PostgreSQL is required.
2. **Vault Secret Operator (VSO):** Migrate from the `vault-agent-injector` sidecar to the Vault Secrets Operator to decouple Vault availability from Pod startup health.
