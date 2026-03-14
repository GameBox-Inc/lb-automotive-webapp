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

if [ "$HTTP_CODE" != "201" ]; then
  echo "GitHub API returned $HTTP_CODE: $BODY" >&2
  exit 1
fi

if command -v jq >/dev/null 2>&1; then
  TOKEN=$(echo "$BODY" | jq -r '.token')
else
  TOKEN=$(echo "$BODY" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
fi

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "No token in response" >&2
  exit 1
fi
echo "$TOKEN"
