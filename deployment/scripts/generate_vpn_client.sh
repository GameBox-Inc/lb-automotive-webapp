#!/bin/bash
set -e

# WireGuard Client Generation Script
# Usage: ./generate_vpn_client.sh <username>

if [ -z "$1" ]; then
    echo "Usage: $0 <username>"
    exit 1
fi

USERNAME=$1
WG_CONF="/etc/wireguard/wg0.conf"
# Try to get public key from running interface first, then file
SERVER_PUBKEY=$(wg show wg0 public-key 2>/dev/null || cat /etc/wireguard/publickey 2>/dev/null)
SERVER_ENDPOINT="178.156.223.196:51820" # Replace with actual public IP if different
ALLOWED_IPS="0.0.0.0/0, ::/0" # Full tunnel by default

if [ -z "$SERVER_PUBKEY" ]; then
    echo "Error: Could not determine server public key. Ensure WireGuard is running or /etc/wireguard/publickey exists."
    exit 1
fi

if [ ! -f "$WG_CONF" ]; then
    echo "Error: WireGuard configuration file not found at $WG_CONF"
    exit 1
fi

# Check for required tools
if ! command -v wg &> /dev/null; then
    echo "Error: wireguard-tools not installed"
    exit 1
fi

# 1. Generate Keys
CLIENT_PRIVKEY=$(wg genkey)
CLIENT_PUBKEY=$(echo "$CLIENT_PRIVKEY" | wg pubkey)
CLIENT_PSK=$(wg genpsk)

# 2. Find Available IP
# Assumes 10.100.0.0/24 subnet. 
# Scanning wg0.conf for used IPs.
# Start from .2 (server is .1)
for i in {2..254}; do
    IP="10.100.0.$i"
    if ! grep -q "$IP" "$WG_CONF"; then
        CLIENT_IP="$IP"
        break
    fi
done

if [ -z "$CLIENT_IP" ]; then
    echo "Error: No available IPs in 10.100.0.0/24 subnet"
    exit 1
fi

echo "Assigning IP: $CLIENT_IP to user: $USERNAME"

# 3. Add Peer to Server Config
echo "" >> "$WG_CONF"
echo "# Client: $USERNAME" >> "$WG_CONF"
echo "[Peer]" >> "$WG_CONF"
echo "PublicKey = $CLIENT_PUBKEY" >> "$WG_CONF"
echo "PresharedKey = $CLIENT_PSK" >> "$WG_CONF"
echo "AllowedIPs = $CLIENT_IP/32" >> "$WG_CONF"
echo "" >> "$WG_CONF"

# 4. Reload WireGuard
# Use wg syncconf to apply changes without dropping connections if possible,
# but usually 'wg addconf' is safer for appending.
# We'll use systemctl for simplicity if available, or wg-quick.
if systemctl is-active --quiet wg-quick@wg0; then
    # Hot reload (add peer only)
    wg set wg0 peer "$CLIENT_PUBKEY" preshared-key <(echo "$CLIENT_PSK") allowed-ips "$CLIENT_IP/32"
    # Also save Config? Using wg-quick strip overrides comments.
    # We manually edited the file, so we probably just want to sync it or let the temp change ride until restart?
    # wg-quick down/up is disruptive.
    # 'wg set' applies immediately but doesn't persist unless we use `wg-quick save` which overwrites comments.
    # Since we manually appended to wg0.conf, the persistence is handled. 
    # 'wg set' applies it to runtime.
    echo "Runtime configuration updated."
else
    echo "Warning: WireGuard service doesn't seem active. Configuration file updated anyway."
fi

# 5. Generate Client Config
CLIENT_CONF="${USERNAME}.conf"
cat > "$CLIENT_CONF" <<EOF
[Interface]
PrivateKey = $CLIENT_PRIVKEY
Address = $CLIENT_IP/32
DNS = 1.1.1.1

[Peer]
PublicKey = $SERVER_PUBKEY
PresharedKey = $CLIENT_PSK
Endpoint = $SERVER_ENDPOINT
AllowedIPs = $ALLOWED_IPS
PersistentKeepalive = 25
EOF

echo "✅ Client configuration generated: $CLIENT_CONF"

# 6. Show QR Code
if command -v qrencode &> /dev/null; then
    echo "Scan this QR code with the WireGuard App:"
    qrencode -t ansiutf8 < "$CLIENT_CONF"
else
    echo "Install 'qrencode' to generate QR codes automatically."
fi
