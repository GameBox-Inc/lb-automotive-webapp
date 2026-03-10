#!/usr/bin/env bash
# tail-traefik-logs.sh — Tail Traefik (ingress) logs via SSH
# Usage: ./scripts/tail-traefik-logs.sh [lines]
# Set DEPLOY_HOST or uses lb-admin@178.156.223.196

HOST="${DEPLOY_HOST:-lb-admin@178.156.223.196}"
LINES="${1:-100}"

ssh -o StrictHostKeyChecking=no "$HOST" \
  "sudo k3s kubectl logs -n gamebox-security -l app.kubernetes.io/name=traefik --tail=$LINES -f"
