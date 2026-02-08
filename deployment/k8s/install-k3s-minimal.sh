#!/bin/bash
# Install K3s with storage optimization for 10GB environments
# Run on server: bash deployment/k8s/install-k3s-minimal.sh

set -e

echo "=========================================="
echo "Installing K3s with Storage Optimization"
echo "=========================================="

# Check available disk space
AVAILABLE=$(df / | awk 'NR==2 {print $4}')
echo "Available disk space: $(($AVAILABLE / 1024 / 1024))GB"

if [ $AVAILABLE -lt 2097152 ]; then
    echo "WARNING: Less than 2GB free. K3s installation may fail."
    echo "Please free up space first."
    exit 1
fi

# Install K3s with minimal components
# Disable: Traefik (we have our own), local-storage (use hostPath), servicelb, metrics-server
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --disable traefik \
  --disable servicelb \
  --disable local-storage \
  --disable metrics-server \
  --write-kubeconfig-mode 644 \
  --kubelet-arg 'image-gc-high-threshold=70' \
  --kubelet-arg 'image-gc-low-threshold=60' \
  --kubelet-arg 'eviction-hard=memory.available<200Mi,nodefs.available<1Gi' \
  --kubelet-arg 'eviction-soft=memory.available<300Mi,nodefs.available<2Gi' \
  --kubelet-arg 'eviction-soft-grace-period=memory.available=1m,nodefs.available=1m'" sh -s -

# Wait for K3s to be ready
echo "Waiting for K3s to start..."
sleep 10

# Set up kubectl for current user
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
export KUBECONFIG=~/.kube/config

# Verify installation
echo "=========================================="
echo "K3s Installation Complete"
echo "=========================================="
kubectl version --short
kubectl get nodes

echo ""
echo "✅ K3s installed with storage optimization:"
echo "   - Disabled: Traefik, ServiceLB, Local-Storage, Metrics-Server"
echo "   - Image GC: Triggers at 70% disk usage"
echo "   - Eviction: Triggers at <1GB free"
echo ""
echo "Next steps:"
echo "1. kubectl get nodes (verify node is Ready)"
echo "2. Install ArgoCD"
