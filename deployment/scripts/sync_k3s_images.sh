#!/bin/bash
set -e

echo "🔄 Syncing Docker Images to K3s..."

# Tag images to match K8s manifests
echo "🏷️  Tagging images..."
docker tag docker-frontend:latest lb-automotive-frontend:latest
docker tag docker-backend:latest lb-automotive-backend:latest

# Export and Import Frontend
echo "📦 Processing Frontend..."
docker save lb-automotive-frontend:latest -o /tmp/frontend.tar
k3s ctr images import /tmp/frontend.tar
rm /tmp/frontend.tar

# Export and Import Backend
echo "📦 Processing Backend..."
docker save lb-automotive-backend:latest -o /tmp/backend.tar
k3s ctr images import /tmp/backend.tar
rm /tmp/backend.tar

echo "✅ Images imported into K3s!"
k3s ctr images list | grep lb-automotive
