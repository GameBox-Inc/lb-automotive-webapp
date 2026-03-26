#!/bin/bash
# Daily disk space cleanup (installed as /etc/cron.daily/disk-cleanup on rocket-1).
# Keep in sync with deployment/scripts/setup_log_rotation.sh heredoc.

# Clean up old container logs
find /var/log/containers/ -name "*.log.*" -mtime +7 -delete
find /var/log/pods/ -name "*.log.*" -mtime +7 -delete

# Clean up old compressed logs
find /var/log/ -name "*.gz" -mtime +14 -delete

# Build cache is NOT removed by docker system prune
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
