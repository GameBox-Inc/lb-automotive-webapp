#!/usr/bin/env bash
# Get a GitHub App installation access token (for GHCR docker login).
# Usage: ./github_app_token.sh <APP_ID> <INSTALLATION_ID> <path-to-.pem>
# Output: the token (or nothing on failure).
# Use in Jenkins: withCredentials([file(credentialsId: 'github-app-key', variable: 'KEY')]) { ... }
set -e

APP_ID="${1:?Usage: $0 <APP_ID> <INSTALLATION_ID> <path-to-.pem>}"
INSTALLATION_ID="${2:?Usage: $0 <APP_ID> <INSTALLATION_ID> <path-to-.pem>}"
PEM_PATH="${3:?Usage: $0 <APP_ID> <INSTALLATION_ID> <path-to-.pem>}"

base64url() { base64 | tr -d '\n' | tr '+/' '-_' | tr -d '='; }

NOW=$(date +%s)
IAT=$NOW
EXP=$((NOW + 600))
HEADER='{"alg":"RS256","typ":"JWT"}'
PAYLOAD="{\"iat\":$IAT,\"exp\":$EXP,\"iss\":\"$APP_ID\"}"

B64_HEADER=$(echo -n "$HEADER" | base64url)
B64_PAYLOAD=$(echo -n "$PAYLOAD" | base64url)
MESSAGE="${B64_HEADER}.${B64_PAYLOAD}"

SIG_B64=$(echo -n "$MESSAGE" | openssl dgst -sha256 -sign "$PEM_PATH" | base64url)
JWT="${MESSAGE}.${SIG_B64}"

RESP=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens")

HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

# GitHub may return 200 or 201 for installation token
if [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "200" ]; then
  echo "GitHub API returned $HTTP_CODE. Body (first 400 chars):" >&2
  echo "$BODY" | head -c 400 >&2
  echo "" >&2
  exit 1
fi

# Extract token: GitHub returns {"token":"ghs_...","expires_at":"..."}
TOKEN=""
if command -v jq >/dev/null 2>&1; then
  TOKEN=$(echo "$BODY" | jq -r '.token // empty')
fi
if [ -z "$TOKEN" ]; then
  # Fallback without jq: single-line JSON, match "token":"<value>"
  TOKEN=$(printf '%s' "$BODY" | tr -d '\n\r' | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
fi

if [ -z "$TOKEN" ]; then
  echo "No token in response (HTTP $HTTP_CODE). Check App ID, Installation ID, and .pem. Body (first 400 chars):" >&2
  echo "$BODY" | head -c 400 >&2
  echo "" >&2
  exit 1
fi
echo "$TOKEN"
