#!/bin/bash
# Remove Ollama and ArgoCD to free up ~2GB RAM for 2GB server
# Run this script on the server to immediately free memory

set -e

echo "=== Removing Memory-Intensive Services for 2GB Server ==="
echo ""

# Remove Ollama (uses 1-2GB RAM)
echo "1. Removing Ollama deployment..."
kubectl delete deployment ollama -n lb-automotive --ignore-not-found=true
kubectl delete service ollama -n lb-automotive --ignore-not-found=true
kubectl delete pvc ollama-data-pvc -n lb-automotive --ignore-not-found=true
echo "✓ Ollama removed"
echo ""

# Remove ArgoCD if installed (uses 500MB-1GB RAM)
echo "2. Checking for ArgoCD..."
if kubectl get namespace argocd &>/dev/null; then
    echo "   ArgoCD found. Removing..."
    kubectl delete namespace argocd --timeout=60s
    echo "✓ ArgoCD removed"
else
    echo "   ArgoCD not installed"
fi
echo ""

# Clean up completed pods
echo "3. Cleaning up completed/failed pods..."
kubectl delete pods -n lb-automotive --field-selector=status.phase==Succeeded --ignore-not-found=true
kubectl delete pods -n lb-automotive --field-selector=status.phase==Failed --ignore-not-found=true
echo "✓ Cleanup complete"
echo ""

echo "=== Memory freed! ==="
echo "Note: Backend will now use Anthropic Claude API only."
echo "Ensure ANTHROPIC_API_KEY is set in secrets."
echo ""
echo "To verify memory usage:"
echo "  kubectl top nodes"
echo "  kubectl top pods -n lb-automotive"
