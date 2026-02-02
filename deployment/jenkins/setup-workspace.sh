#!/bin/bash
# Setup Jenkins pipeline workspace with a git clone (fixes "not in a git directory").
# Run on the SERVER where Jenkins runs: bash deployment/jenkins/setup-workspace.sh

set -e

JOB_NAME="${1:-LB-Automotive-Dashboard}"
WORKSPACE="/var/jenkins_home/workspace/$JOB_NAME"
REPO_URL="git@github.com:GameBox-Inc/lb-automotive-webapp.git"
CONTAINER="${2:-lb-jenkins}"

echo "=========================================="
echo "Jenkins workspace setup (debug)"
echo "=========================================="
echo "Job name:    $JOB_NAME"
echo "Workspace:   $WORKSPACE"
echo "Container:   $CONTAINER"
echo "Repo:        $REPO_URL"
echo ""

# Check container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: Container '$CONTAINER' is not running."
    docker ps -a --format 'table {{.Names}}\t{{.Status}}' | head -20
    exit 1
fi
echo "[OK] Container $CONTAINER is running."

# List existing workspaces (debug)
echo ""
echo "Existing workspace folders:"
docker exec "$CONTAINER" ls -la /var/jenkins_home/workspace/ 2>/dev/null || echo "(workspace dir missing or empty)"
echo ""

# Remove and recreate workspace
echo "Removing and recreating: $WORKSPACE"
docker exec "$CONTAINER" rm -rf "$WORKSPACE"
docker exec "$CONTAINER" mkdir -p "$WORKSPACE"
docker exec "$CONTAINER" chown -R jenkins:jenkins "$WORKSPACE"
echo "[OK] Directory created and owned by jenkins."

# Clone as jenkins user
echo ""
echo "Cloning repo into workspace (as jenkins user)..."
if ! docker exec -u jenkins "$CONTAINER" sh -c "cd $WORKSPACE && git clone $REPO_URL ."; then
    echo "ERROR: git clone failed."
    echo "Check: GitHub host key in known_hosts, SSH key in container, deploy key on GitHub."
    exit 1
fi
echo "[OK] Clone completed."

# Verify
echo ""
echo "Verification:"
docker exec "$CONTAINER" ls -la "$WORKSPACE" | head -15
echo ""
echo ".git contents:"
docker exec "$CONTAINER" ls -la "$WORKSPACE/.git" 2>/dev/null || { echo "ERROR: .git missing"; exit 1; }
echo ""
echo "git status (as jenkins):"
docker exec -u jenkins "$CONTAINER" sh -c "cd $WORKSPACE && git status"
echo ""
echo "=========================================="
echo "Done. In Jenkins UI: run Build Now."
echo "Workspace path (must match job): $WORKSPACE"
echo "=========================================="
