#!/bin/bash
# Jenkins Build Failure Comprehensive Diagnostic Script
# Run on SERVER: bash deployment/jenkins/diagnose-jenkins.sh

set -e

CONTAINER_NAME="${1:-lb-jenkins}"
JOB_NAME="${2:-LB-Automotive-Dashboard-Pipeline}"
WORKSPACE_PATH="/var/jenkins_home/workspace/$JOB_NAME"

echo "========================================================================"
echo "🔍 JENKINS BUILD FAILURE COMPREHENSIVE DIAGNOSTIC"
echo "========================================================================"
echo "Timestamp: $(date)"
echo "Container: $CONTAINER_NAME"
echo "Job: $JOB_NAME"
echo "Expected Workspace: $WORKSPACE_PATH"
echo ""

# Phase 1: Environment Verification
echo "========================================================================"
echo "📋 PHASE 1: ENVIRONMENT VERIFICATION"
echo "========================================================================"

echo "🐳 Container State:"
echo "----------------------------------------"
if docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -q "$CONTAINER_NAME"; then
    echo "✅ Container $CONTAINER_NAME is running"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep "$CONTAINER_NAME"
else
    echo "❌ Container $CONTAINER_NAME is NOT running"
    docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep "$CONTAINER_NAME" || echo "Container not found"
    exit 1
fi

echo ""
echo "📊 Container Resources:"
echo "----------------------------------------"
docker stats "$CONTAINER_NAME" --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "🔧 Container Configuration:"
echo "----------------------------------------"
echo "User running Jenkins:"
docker exec "$CONTAINER_NAME" id jenkins 2>/dev/null || echo "❌ Jenkins user not found"
echo "Process tree:"
docker exec "$CONTAINER_NAME" ps aux | grep -E "(java|jenkins)" | head -5

echo ""
echo "💾 Volume Mounts:"
echo "----------------------------------------"
docker inspect "$CONTAINER_NAME" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Type}}){{"\n"}}{{end}}'

# Phase 2: Git Repository State
echo ""
echo "========================================================================"
echo "📁 PHASE 2: GIT REPOSITORY STATE ANALYSIS"
echo "========================================================================"

echo "🔍 Workspace Directory Structure:"
echo "----------------------------------------"
if docker exec "$CONTAINER_NAME" test -d "/var/jenkins_home/workspace"; then
    echo "✅ Workspace directory exists"
    echo "Available workspaces:"
    docker exec "$CONTAINER_NAME" ls -la /var/jenkins_home/workspace/ | grep -E "^d" | awk '{print $9, $3, $4, $6, $7, $8}' | column -t
else
    echo "❌ Workspace directory missing"
fi

echo ""
echo "🎯 Target Workspace Analysis:"
echo "----------------------------------------"
if docker exec "$CONTAINER_NAME" test -d "$WORKSPACE_PATH"; then
    echo "✅ Target workspace exists: $WORKSPACE_PATH"
    echo "Contents:"
    docker exec "$CONTAINER_NAME" ls -la "$WORKSPACE_PATH" | head -15
    
    echo ""
    echo "Ownership and permissions:"
    docker exec "$CONTAINER_NAME" ls -ld "$WORKSPACE_PATH"
    
    if docker exec "$CONTAINER_NAME" test -d "$WORKSPACE_PATH/.git"; then
        echo "✅ .git directory exists"
        echo ".git directory info:"
        docker exec "$CONTAINER_NAME" ls -la "$WORKSPACE_PATH/.git" | head -10
        
        echo ""
        echo "Git repository status:"
        docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git status 2>&1" || echo "❌ Git status failed"
        
        echo ""
        echo "Git remote configuration:"
        docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git remote -v 2>&1" || echo "❌ Git remote failed"
        
        echo ""
        echo "Git branch information:"
        docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git branch -a 2>&1" || echo "❌ Git branch failed"
        
        echo ""
        echo "Recent commits:"
        docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git log --oneline -5 2>&1" || echo "❌ Git log failed"
        
    else
        echo "❌ .git directory missing"
    fi
else
    echo "❌ Target workspace does not exist: $WORKSPACE_PATH"
fi

# Phase 3: Jenkins Configuration Audit
echo ""
echo "========================================================================"
echo "⚙️ PHASE 3: JENKINS CONFIGURATION AUDIT"
echo "========================================================================"

echo "🌐 Jenkins Service Status:"
echo "----------------------------------------"
echo "Checking Jenkins web interface..."
if docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/login 2>/dev/null | grep -qE "(200|403)"; then
    echo "✅ Jenkins web interface responding"
else
    echo "❌ Jenkins web interface not responding"
fi

echo ""
echo "📋 Jenkins System Information:"
echo "----------------------------------------"
echo "Java version:"
docker exec "$CONTAINER_NAME" java -version 2>&1 | head -3

echo ""
echo "Jenkins version:"
docker exec "$CONTAINER_NAME" find /usr/share/jenkins -name "jenkins.war" -exec ls -l {} \; 2>/dev/null || echo "Jenkins version not found"

echo ""
echo "🔐 SSH Configuration:"
echo "----------------------------------------"
echo "SSH directory structure:"
docker exec "$CONTAINER_NAME" ls -la /var/jenkins_home/.ssh/ 2>/dev/null || echo "❌ SSH directory missing"

if docker exec "$CONTAINER_NAME" test -f "/var/jenkins_home/.ssh/known_hosts"; then
    echo "✅ known_hosts exists"
    echo "Known hosts content:"
    docker exec "$CONTAINER_NAME" cat /var/jenkins_home/.ssh/known_hosts | head -5
    
    echo ""
    echo "GitHub in known_hosts:"
    if docker exec "$CONTAINER_NAME" grep -q "github.com" /var/jenkins_home/.ssh/known_hosts; then
        echo "✅ GitHub found in known_hosts"
    else
        echo "❌ GitHub NOT found in known_hosts"
    fi
else
    echo "❌ known_hosts missing"
fi

echo ""
echo "SSH key files:"
docker exec "$CONTAINER_NAME" ls -la /var/jenkins_home/.ssh/id_* 2>/dev/null || echo "❌ SSH key files missing"

echo ""
echo "🔑 SSH Connectivity Test:"
echo "----------------------------------------"
echo "Testing SSH to GitHub:"
docker exec -u jenkins "$CONTAINER_NAME" ssh -T -o StrictHostKeyChecking=no git@github.com 2>&1 | head -3 || echo "❌ SSH to GitHub failed"

# Phase 4: Process Flow Analysis
echo ""
echo "========================================================================"
echo "🔄 PHASE 4: PROCESS FLOW ANALYSIS"
echo "========================================================================"

echo "📜 Recent Jenkins Logs:"
echo "----------------------------------------"
echo "Last 30 lines of Jenkins logs:"
docker logs "$CONTAINER_NAME" --tail 30

echo ""
echo "🔍 Jenkins Job Configuration Files:"
echo "----------------------------------------"
echo "Looking for job configuration..."
JOB_CONFIG_PATH="/var/jenkins_home/jobs/$JOB_NAME/config.xml"
if docker exec "$CONTAINER_NAME" test -f "$JOB_CONFIG_PATH"; then
    echo "✅ Job configuration found: $JOB_CONFIG_PATH"
    echo "SCM configuration excerpt:"
    docker exec "$CONTAINER_NAME" grep -A 10 -B 2 "<scm" "$JOB_CONFIG_PATH" 2>/dev/null || echo "SCM config not found"
else
    echo "❌ Job configuration not found: $JOB_CONFIG_PATH"
    echo "Available jobs:"
    docker exec "$CONTAINER_NAME" ls -la /var/jenkins_home/jobs/ 2>/dev/null || echo "No jobs directory"
fi

echo ""
echo "🧪 Manual Git Operations Test:"
echo "----------------------------------------"
echo "Testing git config command (the failing command):"
if docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git config remote.origin.url 2>&1"; then
    echo "✅ git config command works"
else
    echo "❌ git config command fails (THIS IS THE ISSUE)"
fi

echo ""
echo "Testing git clone to temporary location:"
TEMP_CLONE_PATH="/tmp/test-clone-$$"
echo "Cloning to: $TEMP_CLONE_PATH"
if docker exec -u jenkins "$CONTAINER_NAME" sh -c "git clone git@github.com:GameBox-Inc/lb-automotive-webapp.git $TEMP_CLONE_PATH 2>&1"; then
    echo "✅ Git clone works to temporary location"
    echo "Cleaning up temp clone..."
    docker exec "$CONTAINER_NAME" rm -rf "$TEMP_CLONE_PATH"
else
    echo "❌ Git clone fails even to temporary location"
fi

# Summary and Recommendations
echo ""
echo "========================================================================"
echo "📊 DIAGNOSTIC SUMMARY & RECOMMENDATIONS"
echo "========================================================================"

echo "🎯 Key Findings:"
echo "----------------------------------------"

# Check each critical component
ISSUES_FOUND=0

echo -n "1. Container running: "
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo -n "2. Workspace exists: "
if docker exec "$CONTAINER_NAME" test -d "$WORKSPACE_PATH"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo -n "3. .git directory: "
if docker exec "$CONTAINER_NAME" test -d "$WORKSPACE_PATH/.git"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo -n "4. Git repo valid: "
if docker exec -u jenkins "$CONTAINER_NAME" sh -c "cd $WORKSPACE_PATH && git status >/dev/null 2>&1"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo -n "5. SSH to GitHub: "
if docker exec -u jenkins "$CONTAINER_NAME" ssh -T -o StrictHostKeyChecking=no git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo -n "6. Jenkins web UI: "
if docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/login 2>/dev/null | grep -qE "(200|403)"; then
    echo "✅ OK"
else
    echo "❌ ISSUE"
    ((ISSUES_FOUND++))
fi

echo ""
echo "🚨 Total Issues Found: $ISSUES_FOUND"

echo ""
echo "🛠️ Recommended Fix Priority:"
echo "----------------------------------------"

if [ $ISSUES_FOUND -eq 0 ]; then
    echo "✅ All components appear healthy. Issue may be intermittent or configuration-related."
    echo "   → Check Jenkins job configuration for 'Clean workspace' settings"
    echo "   → Review recent Jenkins logs for timing issues"
else
    echo "❌ Issues detected. Recommended fix order:"
    
    if ! docker exec "$CONTAINER_NAME" test -d "$WORKSPACE_PATH/.git"; then
        echo "   1. 🎯 CRITICAL: Fix workspace .git directory"
        echo "      → Run: bash deployment/jenkins/setup-workspace.sh"
    fi
    
    if ! docker exec -u jenkins "$CONTAINER_NAME" ssh -T -o StrictHostKeyChecking=no git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo "   2. 🔑 HIGH: Fix SSH authentication to GitHub"
        echo "      → Add GitHub to known_hosts"
        echo "      → Verify SSH keys and GitHub deploy key"
    fi
    
    if ! docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/login 2>/dev/null | grep -qE "(200|403)"; then
        echo "   3. ⚙️ MEDIUM: Fix Jenkins service"
        echo "      → Restart Jenkins container"
        echo "      → Check logs for startup issues"
    fi
fi

echo ""
echo "📋 Next Steps:"
echo "----------------------------------------"
echo "1. Review the diagnostic output above"
echo "2. Address issues in priority order"
echo "3. Re-run this diagnostic after each fix"
echo "4. Test Jenkins build once all issues resolved"

echo ""
echo "========================================================================"
echo "✅ DIAGNOSTIC COMPLETE - $(date)"
echo "========================================================================"