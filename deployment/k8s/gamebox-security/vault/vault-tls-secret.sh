#!/bin/bash
# =============================================================================
# vault-tls-secret.sh — Generate Vault TLS certificates and create K8s secrets
# Run once on the server before deploying Vault via Helm.
# =============================================================================
set -euo pipefail

NAMESPACE="gamebox-security"
VAULT_SERVICE="vault"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "================================================"
echo " Vault TLS Certificate Bootstrap"
echo " Namespace: $NAMESPACE"
echo "================================================"

# ─── 1. Generate Self-Signed CA ───────────────────────────────────────────────
echo ""
echo "▶ Generating CA key and certificate..."
openssl genrsa -out "$TMPDIR/ca.key" 4096

openssl req -x509 -new -nodes \
  -key "$TMPDIR/ca.key" \
  -sha256 \
  -days 3650 \
  -out "$TMPDIR/ca.crt" \
  -subj "/O=GameBox Inc/CN=GameBox Vault CA"

# ─── 2. Generate Vault Server Certificate ─────────────────────────────────────
echo "▶ Generating Vault server certificate..."
openssl genrsa -out "$TMPDIR/vault.key" 4096

# SAN must include all the DNS names Vault will be reachable by
cat > "$TMPDIR/vault-csr.conf" <<EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
O = GameBox Inc
CN = vault.${NAMESPACE}.svc

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = vault
DNS.2 = vault.${NAMESPACE}
DNS.3 = vault.${NAMESPACE}.svc
DNS.4 = vault.${NAMESPACE}.svc.cluster.local
DNS.5 = vault-active.${NAMESPACE}.svc.cluster.local
IP.1 = 127.0.0.1
EOF

openssl req -new \
  -key "$TMPDIR/vault.key" \
  -out "$TMPDIR/vault.csr" \
  -config "$TMPDIR/vault-csr.conf"

openssl x509 -req \
  -in "$TMPDIR/vault.csr" \
  -CA "$TMPDIR/ca.crt" \
  -CAkey "$TMPDIR/ca.key" \
  -CAcreateserial \
  -out "$TMPDIR/vault.crt" \
  -days 3650 \
  -sha256 \
  -extfile "$TMPDIR/vault-csr.conf" \
  -extensions v3_req

# ─── 3. Create gamebox-security namespace if missing ──────────────────────────
kubectl apply -f "$(dirname "$0")/../namespace.yaml"

# ─── 4. Create K8s TLS Secrets ───────────────────────────────────────────────
echo "▶ Creating vault-server-tls secret..."
kubectl create secret generic vault-server-tls \
  --namespace="$NAMESPACE" \
  --from-file=vault.key="$TMPDIR/vault.key" \
  --from-file=vault.crt="$TMPDIR/vault.crt" \
  --from-file=ca.crt="$TMPDIR/ca.crt" \
  --dry-run=client -o yaml | kubectl apply -f -

# The CA bundle is needed by the agent injector mutating webhook to trust Vault
echo "▶ Creating vault-ca secret (for injector webhook trust)..."
kubectl create secret generic vault-ca \
  --namespace="$NAMESPACE" \
  --from-file=ca.crt="$TMPDIR/ca.crt" \
  --dry-run=client -o yaml | kubectl apply -f -

# Store CA cert in a well-known ConfigMap so other namespaces can mount it
echo "▶ Creating vault-ca-bundle ConfigMap..."
kubectl create configmap vault-ca-bundle \
  --namespace="$NAMESPACE" \
  --from-file=ca.crt="$TMPDIR/ca.crt" \
  --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "✅ Vault TLS secrets created:"
echo "   - vault-server-tls  (vault.key, vault.crt, ca.crt)"
echo "   - vault-ca          (ca.crt)"
echo "   - vault-ca-bundle   (ConfigMap)"
echo ""
echo "Next: helm install vault using vault-helm-values.yaml"
