#!/usr/bin/env bash
# tail-app-logs.sh — Tail backend logs via SSH
# Usage: ./scripts/tail-app-logs.sh [lines]
# Set DEPLOY_HOST or uses lb-admin@178.156.223.196

HOST="${DEPLOY_HOST:-lb-admin@178.156.223.196}"
LINES="${1:-100}"

ssh -o StrictHostKeyChecking=no "$HOST" \
  "sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --tail=$LINES -f"
