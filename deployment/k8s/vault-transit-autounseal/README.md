# Vault Transit Auto-Unseal

**Architecture**: Two Vault CE instances, fully self-hosted, no cloud KMS.

```
┌─────────────────────────────────────────────────────────────┐
│ K3s Cluster                                                  │
│                                                              │
│  ┌──────────────────┐        seal "transit"                 │
│  │ vault-unseal ns  │◄──────────────────────────────────┐   │
│  │                  │   encrypt/decrypt autounseal key   │   │
│  │  Unseal Vault    │                                    │   │
│  │  - Transit eng.  │                                    │   │
│  │  - Raft storage  │                                    │   │
│  └──────────────────┘                                    │   │
│                                                           │   │
│  ┌──────────────────────────────────────────────────┐    │   │
│  │ gamebox-security ns                              │    │   │
│  │                                                  │    │   │
│  │  Main Vault  ─────────────────────────────────────────┘   │
│  │  - HA + Raft storage                             │        │
│  │  - Auto-unseals via transit                      │        │
│  │  - Agent Injector                                │        │
│  └──────────────────────────────────────────────────┘        │
│                                                              │
│  ┌──────────────────────────────────────────────────┐        │
│  │ lb-automotive ns                                 │        │
│  │  - backend (secrets injected by Vault sidecar)   │        │
│  └──────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Why This Is Secure

| Property | How it's achieved |
|----------|------------------|
| Secrets never in Git | K8s Secrets used for tokens only; keys stay offline |
| Least privilege | Transit token only has encrypt/decrypt on one key |
| TLS everywhere | Self-signed CA; verified server TLS between Vaults |
| Audit trail | Both Vaults log to stdout → captured by K8s |
| No cloud dependency | Fully self-hosted Vault CE |
| Auto-unseal | Main Vault unseals itself via Unseal Vault transit key |

## Threat Model

- **Unseal Vault** compromise: attacker gets transit token → can unseal Main Vault, but NOT read app secrets (transit is math, not storage)
- **Main Vault** compromise: attacker needs both Vault + its mTLS path
- **etcd compromise**: K8s Secret holding transit token exposed → rotate token immediately
- **Unseal Vault down**: Main Vault stays sealed until restored (use `breakglass_unseal.md`)

## File Structure

```
vault-transit-autounseal/
├── README.md                      ← This file
├── unseal-vault/
│   ├── namespace.yaml             ← vault-unseal namespace
│   ├── vault-helm-values.yaml     ← Unseal Vault Helm values
│   ├── networkpolicy.yaml         ← Restrict ingress to gamebox-security only
│   └── tls/
│       ├── generate-tls.sh        ← Generate CA + server certs
│       └── README.md
├── main-vault/
│   ├── vault-helm-values-ha.yaml  ← Main Vault HA+Raft+transit seal
│   └── secret-unseal-token.yaml.template
├── bootstrap/
│   ├── bootstrap_unseal_vault.sh  ← One-time Unseal Vault setup
│   └── bootstrap_main_vault.sh    ← One-time Main Vault setup
└── ops/
    ├── verify.sh                  ← Full validation suite
    ├── rotate_transit_key.md      ← Key rotation procedure
    └── breakglass_unseal.md       ← Emergency recovery
```

## Bootstrap Order

> [!IMPORTANT]
> Unseal Vault MUST be up and healthy before Main Vault starts. Main Vault's seal config points to Unseal Vault — if it can't reach it on startup, it won't unseal.

```
1. Generate TLS certs      → tls/generate-tls.sh
2. Create K8s secrets      → kubectl create secret ...
3. Deploy Unseal Vault     → helm install (unseal-vault namespace)
4. Bootstrap Unseal Vault  → bootstrap/bootstrap_unseal_vault.sh
5. Create transit token secret → kubectl create secret vault-transit-token
6. Deploy Main Vault       → helm upgrade (gamebox-security namespace)
7. Bootstrap Main Vault    → bootstrap/bootstrap_main_vault.sh
8. Verify                  → ops/verify.sh
```

## Step-by-Step Deployment

### 1. Generate TLS certs

```bash
cd deployment/k8s/vault-transit-autounseal/unseal-vault/tls
bash generate-tls.sh
```

### 2. Create K8s secrets

```bash
# Unseal Vault TLS
kubectl create secret generic unseal-vault-tls \
  --from-file=ca.crt=certs/ca.crt \
  --from-file=vault.crt=certs/vault.crt \
  --from-file=vault.key=certs/vault.key \
  --namespace=vault-unseal

# Share CA with Main Vault namespace
kubectl create secret generic unseal-vault-ca \
  --from-file=ca.crt=certs/ca.crt \
  --namespace=gamebox-security
```

### 3. Deploy Unseal Vault

```bash
kubectl apply -f deployment/k8s/vault-transit-autounseal/unseal-vault/namespace.yaml
kubectl apply -f deployment/k8s/vault-transit-autounseal/unseal-vault/networkpolicy.yaml

helm install unseal-vault hashicorp/vault \
  --namespace vault-unseal \
  --values deployment/k8s/vault-transit-autounseal/unseal-vault/vault-helm-values.yaml
```

### 4. Bootstrap Unseal Vault

```bash
cd deployment/k8s/vault-transit-autounseal/bootstrap
bash bootstrap_unseal_vault.sh
# → saves main_vault_unseal_token.txt
```

### 5. Create transit token secret for Main Vault

```bash
kubectl create secret generic vault-transit-token \
  --from-literal=token=$(cat main_vault_unseal_token.txt) \
  --namespace=gamebox-security
```

### 6. Upgrade Main Vault with transit seal

```bash
helm upgrade vault hashicorp/vault \
  --namespace gamebox-security \
  --values deployment/k8s/vault-transit-autounseal/main-vault/vault-helm-values-transit-seal.yaml
```

> [!IMPORTANT]
> The `vault-helm-values-transit-seal.yaml` file contains a `token = "PLACEHOLDER_TRANSIT_TOKEN"` placeholder.
> You **must** patch the ConfigMap with the real token before the pod starts, or Vault will make
> unauthenticated requests to Unseal Vault and receive a 403.
> The `bootstrap_main_vault.sh` script handles this automatically.

### 7. Bootstrap Main Vault

```bash
bash bootstrap_main_vault.sh
# → saves main_vault_init.json (recovery keys — store offline!)
```

### 8. Verify

```bash
bash ../ops/verify.sh
```

## Backup / Restore

### Raft snapshots (run weekly via cron or Jenkins)

```bash
# Unseal Vault snapshot
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault login <ROOT_TOKEN>
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator raft snapshot save /tmp/unseal-snap.snap
kubectl cp vault-unseal/vault-0:/tmp/unseal-snap.snap ./unseal-vault-$(date +%Y%m%d).snap

# Main Vault snapshot
kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault login <ROOT_TOKEN>
kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator raft snapshot save /tmp/main-snap.snap
kubectl cp gamebox-security/vault-0:/tmp/main-snap.snap ./main-vault-$(date +%Y%m%d).snap
```

## Hardening Checklist

- [ ] Root tokens stored offline (not in K8s, not in Git)
- [ ] Unseal Vault init keys stored in physical safe or offline password manager
- [ ] Audit logging enabled on both Vaults
- [ ] Transit token has TTL + periodic renewal
- [ ] NetworkPolicy restricts Unseal Vault ingress to Main Vault only
- [ ] TLS verified (no `tls_skip_verify = true` in production)
- [ ] etcd encryption enabled on K3s for K8s Secrets at rest
- [ ] Raft snapshots automated weekly

## Known Issues / Gotchas

### `token_file` is silently ignored in Vault 1.21.2

The `seal "transit"` HCL stanza does **not** support a `token_file` parameter in Vault 1.21.x.
If you set `token_file = "/path/to/token"` it is silently ignored and Vault makes unauthenticated
requests to Unseal Vault, resulting in a `403 permission denied` on startup.

**Root cause found during initial deployment (2026-03-05).**

**Fix**: Use `token = "<actual_token>"` directly in the HCL `seal "transit"` stanza.
The Helm values file uses a `PLACEHOLDER_TRANSIT_TOKEN` sentinel; the bootstrap script or
`fix_seal.sh` patches the ConfigMap with the real token at deploy time.

## Key Rotation

See `ops/rotate_transit_key.md`

## Emergency Recovery

See `ops/breakglass_unseal.md`
