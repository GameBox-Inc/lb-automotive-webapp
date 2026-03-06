#!/bin/bash
set -e

DEPLOY_USER="lb-admin"

# 1. Create User if not exists
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    echo "$DEPLOY_USER created."
fi

# 2. Setup SSH
mkdir -p "/home/$DEPLOY_USER/.ssh"
# Copy root's authorized keys
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi
chown -R "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
chmod 700 "/home/$DEPLOY_USER/.ssh"
if [ -f "/home/$DEPLOY_USER/.ssh/authorized_keys" ]; then
    chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi

# 3. Add to Sudoers
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$DEPLOY_USER"

# 4. Install Docker (Root req)
if ! command -v docker &> /dev/null; then
    echo 'Installing Docker...'
    curl -fsSL https://get.docker.com | sh
fi

# 5. Add user to Docker group
usermod -aG docker "$DEPLOY_USER"

# 6. Create App Dir & Ownership
REMOTE_DIR="/opt/lb-automotive-dashboard"
mkdir -p "$REMOTE_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$REMOTE_DIR"
