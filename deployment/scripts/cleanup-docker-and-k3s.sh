#!/usr/bin/env bash
# Do not use set -e; ensure we never fail the pipeline when run from Jenkins post { always { } }
set -uo pipefail

echo "▶ Local Docker cleanup (Jenkins agent)..."
docker system prune -f || true

if [[ -z "${DEPLOY_HOST:-}" || -z "${DEPLOY_USER:-}" ]]; then
  echo "▶ Skipping remote cleanup (DEPLOY_HOST or DEPLOY_USER unset)."
  exit 0
fi

echo "▶ Remote Docker + containerd cleanup on ${DEPLOY_HOST}..."
ssh -o StrictHostKeyChecking=no "${DEPLOY_USER}@${DEPLOY_HOST}" bash << 'EOF'
set +e
echo "▶ Pruning old Docker images (not used in last 7 days)..."
sudo docker system prune -a -f --filter "until=168h" || true
echo "▶ Pruning unused containerd images (K3s)..."
sudo k3s crictl rmi --prune || true
echo "▶ Cleaning up completed/failed pods..."
sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase==Succeeded --ignore-not-found 2>/dev/null || true
sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase==Failed --ignore-not-found 2>/dev/null || true
echo "✅ Remote cleanup done."
EOF

exit 0

