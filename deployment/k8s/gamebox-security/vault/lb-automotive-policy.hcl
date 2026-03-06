# path "secret/data/lb-automotive/*" {
#   capabilities = ["read", "list"]
# }
#
# LB Automotive Backend Policy
# ─────────────────────────────────────────────────────────────────────────────
# Grants read-only access to all secrets under the lb-automotive path.
# The pod can read app, twilio, and anthropic secrets but cannot write,
# delete, or access secrets belonging to any other application or namespace.
#
# Path structure:
#   secret/lb-automotive/app        — core application secrets
#   secret/lb-automotive/twilio     — Twilio credentials
#   secret/lb-automotive/anthropic  — LLM (Anthropic) credentials
# ─────────────────────────────────────────────────────────────────────────────

path "secret/data/lb-automotive/*" {
  capabilities = ["read", "list"]
}

# Allow the agent to renew its own token
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow the agent to look up its own token
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
