#!/usr/bin/env bash
set -euo pipefail

echo "▶ Local Docker cleanup (Jenkins agent)..."
# Remove stopped containers, dangling images, and unused networks on the Jenkins node
docker system prune -f || true

echo "▶ Remote Docker + containerd cleanup on ${DEPLOY_HOST:-<unset>}..."
ssh -o StrictHostKeyChecking=no "${DEPLOY_USER}@${DEPLOY_HOST}" bash << 'EOF'
set -euo pipefail

echo "▶ Pruning old Docker images (not used in last 7 days)..."
sudo docker system prune -a -f --filter "until=168h" || true

echo "▶ Pruning unused containerd images (K3s)..."
sudo k3s crictl rmi --prune || true

echo "▶ Cleaning up completed/failed pods..."
sudo k3s kubectl delete pods --all-namespaces \
  --field-selector=status.phase==Succeeded --ignore-not-found || true
sudo k3s kubectl delete pods --all-namespaces \
  --field-selector=status.phase==Failed --ignore-not-found || true

echo "✅ Remote cleanup done."
EOF

