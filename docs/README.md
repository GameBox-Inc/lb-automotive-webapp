# LB Automotive Dashboard — Documentation Index

Quick reference to find architecture, runbooks, and setup docs.

## Root-level docs

- **CLAUDE.md** — Primary system overview, conventions, deployment, and conventions for AI/human contributors.
- **API_REFERENCE.md** — API endpoints and frontend client methods (when present at repo root).

## Architecture

- **docs/architecture/voice-flow.md** — Twilio IVR flow, decision tree, request path.
- **docs/architecture/vault-stability-and-improvements.md** — Vault stability and improvements.
- **docs/architecture/ivr-conversational-upgrade.md** — IVR conversational upgrade.
- **docs/COMBINED_IVR_AND_CALENDAR_REDESIGN.md** — IVR and calendar redesign.
- **docs/supabase-ivr-booking-schema-assessment.md** — Supabase/IVR booking schema.

## Runbooks (operational)

- **docs/runbooks/k8s-debugging.md** — Kubernetes debugging.
- **docs/runbooks/ingress-service-endpoints.md** — Ingress and service endpoints.
- **docs/runbooks/twilio-debugging.md** — Twilio/IVR debugging.
- **docs/runbooks/twilio-503.md** — Twilio 503 handling.
- **docs/runbooks/twiml-validation.md** — TwiML validation.
- **docs/runbooks/audio-playback.md** — Audio playback.
- **docs/runbooks/audio-playback-failure.md** — Audio playback failure.
- **docs/runbooks/vault-init-failures.md** — Vault init failures.
- **docs/runbooks/vault-unseal-order.md** — Vault unseal order.
- **docs/runbooks/unseal-vault-key-management.md** — Unseal key management.
- **docs/runbooks/twilio-k8s-traefik-review.md** — Twilio, K8s, Traefik review.

## Incidents and troubleshooting

- **docs/incidents/common-failures.md** — Common failure modes and fixes (502, CrashLoopBackOff, Vault, etc.).

## How-to and config

- **docs/howto/vault-transit-token-management.md** — Vault transit token and Jenkins credentials.
- **docs/howto/github-app-ghcr.md** — GitHub App and GHCR.
- **docs/config/env-vars.md** — Environment variables.

## Contracts and assessments

- **docs/contracts/twilio-webhooks.md** — Twilio webhook contracts.
- **docs/runbook-supabase-verify-and-apply.md** — Supabase verify and apply.
- **docs/SUPABASE_RLS_AND_USER_ROLES.md** — RLS and user roles.
- **docs/FRAMEWORK_FEATURES_TO_USE.md** — Framework features.
- **docs/UX_UI_IMPROVEMENTS_REPORT.md** — UX/UI improvements.
