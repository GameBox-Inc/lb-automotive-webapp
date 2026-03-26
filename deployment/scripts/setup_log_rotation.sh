#!/bin/bash
# Setup log rotation and compression for containerized environment
# Prevents logs from filling up 40GB disk

set -e

echo "=== Setting up Log Rotation for 40GB Server ==="
echo ""

# Create logrotate config for container logs
echo "1. Creating logrotate configuration..."
sudo tee /etc/logrotate.d/k3s-containers > /dev/null <<'EOF'
/var/log/containers/*.log {
    daily
    rotate 7
    maxsize 50M
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        # Notify containers to reopen log files
        /usr/bin/killall -USR1 containerd || true
    endscript
}
EOF
echo "✓ Container log rotation configured"
echo ""

# Create logrotate config for k3s logs
echo "2. Configuring K3s log rotation..."
sudo tee /etc/logrotate.d/k3s > /dev/null <<'EOF'
/var/log/k3s.log {
    daily
    rotate 5
    maxsize 100M
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        /bin/systemctl reload k3s >/dev/null 2>&1 || true
    endscript
}
EOF
echo "✓ K3s log rotation configured"
echo ""

# Configure journald to limit log storage
echo "3. Limiting journald log storage..."
sudo mkdir -p /etc/systemd/journald.conf.d/
sudo tee /etc/systemd/journald.conf.d/size-limit.conf > /dev/null <<'EOF'
[Journal]
# Limit journal size to 500MB max
SystemMaxUse=500M
SystemKeepFree=1G
MaxRetentionSec=7day
MaxFileSec=1day
EOF
sudo systemctl restart systemd-journald
echo "✓ Journald limits configured (500MB max)"
echo ""

# Clean up old container logs immediately
echo "4. Cleaning up existing large logs..."
sudo find /var/log/containers/ -name "*.log" -size +50M -exec truncate -s 0 {} \;
sudo find /var/log/pods/ -name "*.log" -size +50M -exec truncate -s 0 {} \;
echo "✓ Large logs truncated"
echo ""

# Create cleanup cron job for disk space
echo "5. Creating daily disk cleanup cron job..."
sudo tee /etc/cron.daily/disk-cleanup > /dev/null <<'EOF'
#!/bin/bash
# Daily disk space cleanup

# Clean up old container logs
find /var/log/containers/ -name "*.log.*" -mtime +7 -delete
find /var/log/pods/ -name "*.log.*" -mtime +7 -delete

# Clean up old compressed logs
find /var/log/ -name "*.gz" -mtime +14 -delete

# Build cache is NOT removed by docker system prune; it can grow to many GB and
# keeps DiskPressure/taints recurring (see docs/runbooks/disk-pressure-docker-cleanup.md).
docker builder prune -f --filter "until=168h" 2>/dev/null || true

# Clean up Docker/containerd unused data
docker system prune -af --filter "until=168h" 2>/dev/null || true

# Clean up k3s cached images
k3s crictl rmi --prune 2>/dev/null || true

# Jenkins DinD: inner Docker holds pipeline build cache; host prune does not touch it.
docker exec jenkins-docker docker builder prune -f --filter "until=168h" 2>/dev/null || true
docker exec jenkins-docker docker image prune -a -f --filter "until=168h" 2>/dev/null || true

# Log disk usage
echo "$(date): Disk usage after cleanup" >> /var/log/disk-cleanup.log
df -h / >> /var/log/disk-cleanup.log
EOF
sudo chmod +x /etc/cron.daily/disk-cleanup
echo "✓ Daily cleanup cron job created"
echo ""

echo "=== Log Rotation Setup Complete! ==="
echo ""
echo "Logs will now:"
echo "  - Rotate daily if > 50MB"
echo "  - Keep 7 days of rotated logs (compressed)"
echo "  - Compress old logs"
echo "  - Clean up logs older than 14 days"
echo "  - Limit journald to 500MB max"
echo ""
echo "To manually run cleanup: sudo /etc/cron.daily/disk-cleanup"
echo "To check disk usage: df -h"
