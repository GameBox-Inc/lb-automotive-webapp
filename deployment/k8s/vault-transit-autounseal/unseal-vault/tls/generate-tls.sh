#!/bin/bash
# =============================================================================
# generate-tls.sh — Generate self-signed CA + TLS certs for Unseal Vault
#
# Run this ONCE on your workstation or the server before deploying.
# Output: ca.crt, vault.crt, vault.key → create K8s secret from these.
#
# Usage:
#   UNSEAL_VAULT_DNS=unseal-vault.vault-unseal.svc.cluster.local \
#   UNSEAL_VAULT_IP=10.42.0.1 \
#   bash generate-tls.sh
# =============================================================================
set -euo pipefail

UNSEAL_VAULT_DNS="${UNSEAL_VAULT_DNS:-unseal-vault.vault-unseal.svc.cluster.local}"
UNSEAL_VAULT_IP="${UNSEAL_VAULT_IP:-127.0.0.1}"
OUT_DIR="${OUT_DIR:-./certs}"
CA_DAYS=3650
CERT_DAYS=730

mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

echo "==> Generating CA key and certificate..."
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days $CA_DAYS -key ca.key -out ca.crt \
  -subj "/CN=Vault Unseal CA/O=GameBox/C=US"

echo "==> Generating Vault server key..."
openssl genrsa -out vault.key 2048

echo "==> Creating CSR with SANs..."
cat > vault.ext <<EOF
[req]
req_extensions = v3_req
distinguished_name = dn
[dn]
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = ${UNSEAL_VAULT_DNS}
DNS.2 = unseal-vault
DNS.3 = unseal-vault.vault-unseal
DNS.4 = unseal-vault.vault-unseal.svc
DNS.5 = localhost
IP.1  = ${UNSEAL_VAULT_IP}
IP.2  = 127.0.0.1
EOF

openssl req -new -key vault.key -out vault.csr \
  -subj "/CN=${UNSEAL_VAULT_DNS}/O=GameBox/C=US" \
  -config vault.ext

echo "==> Signing server cert with CA..."
openssl x509 -req -days $CERT_DAYS \
  -in vault.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out vault.crt \
  -extensions v3_req \
  -extfile vault.ext

echo "==> Verifying cert chain..."
openssl verify -CAfile ca.crt vault.crt

echo ""
echo "==> Create K8s TLS secret (run on server):"
echo "kubectl create secret generic unseal-vault-tls \\"
echo "  --from-file=ca.crt=${OUT_DIR}/ca.crt \\"
echo "  --from-file=vault.crt=${OUT_DIR}/vault.crt \\"
echo "  --from-file=vault.key=${OUT_DIR}/vault.key \\"
echo "  --namespace=vault-unseal"
echo ""
echo "==> Also create the CA secret for Main Vault to verify TLS:"
echo "kubectl create secret generic unseal-vault-ca \\"
echo "  --from-file=ca.crt=${OUT_DIR}/ca.crt \\"
echo "  --namespace=gamebox-security"

# Clean up sensitive files
rm -f vault.csr vault.ext ca.key ca.srl
chmod 600 vault.key
echo ""
echo "==> Done. Store ca.crt, vault.crt, vault.key securely. DO NOT COMMIT TO GIT."
