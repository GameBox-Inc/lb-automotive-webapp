# How-To: Vault Transit Token Management

**Purpose:** Prevent and recover from Main Vault CrashLoopBackOff caused by "invalid token" / 403 when contacting Unseal Vault.

**Last Updated:** March 2026

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Credentials You Must Manage](#2-credentials-you-must-manage)
3. [Initial Setup (One-Time)](#3-initial-setup-one-time)
4. [Jenkins Pipeline — What It Does](#4-jenkins-pipeline--what-it-does)
5. [Direct Server Steps (When Needed)](#5-direct-server-steps-when-needed)
6. [Preventing Token Issues](#6-preventing-token-issues)
7. [Recovery Checklist](#7-recovery-checklist)
8. [Quick Reference](#8-quick-reference)

---

## 1. Architecture Overview

```
Unseal Vault (vault-unseal)     Main Vault (gamebox-security)     Backend (lb-automotive)
├── Unsealed manually          ├── Auto-unseals via transit      ├── Vault Agent injects secrets
├── Transit engine             ├── Uses "transit token" to       ├── Needs Main Vault unsealed
│   └── autounseal key         │   call Unseal Vault             └── API → 502 if backend down
└── Shamir seal (3 of 5)       └── Token in ConfigMap
```

**Main Vault** needs a **transit token** to authenticate to Unseal Vault and use its encrypt/decrypt API. That token is stored in:

1. Jenkins credential `vault-transit-token` (used by pipeline)
2. K8s ConfigMap `vault` in namespace `gamebox-security` (key `extraconfig-from-values.hcl`)

The Helm chart ships with `token = "PLACEHOLDER_TRANSIT_TOKEN"`. The Jenkins "Patch Vault Seal Token" stage replaces it with the real token. If the token is wrong, expired, or revoked, Main Vault crashes with 403.

---

## 2. Credentials You Must Manage

| Credential | Where Stored | Used By | When to Update |
|------------|--------------|---------|----------------|
| **Unseal Vault root token** | Offline (password manager, `unseal_init.json`) | You (manual recovery) | Never — keep forever |
| **Unseal Vault unseal keys** (3 of 5) | Offline + Jenkins credentials | Jenkins "Unseal Unseal Vault" stage | After rekey only |
| **Transit token** | Jenkins `vault-transit-token` + optionally `main_vault_unseal_token.txt` | Jenkins "Patch Vault Seal Token" stage | After bootstrap, rekey, or token rotation |

**Critical:** Jenkins and the ConfigMap must stay in sync. If you update the transit token on Unseal Vault, you must update Jenkins and re-patch the ConfigMap (or restart the pipeline).

---

## 3. Initial Setup (One-Time)

### 3.1 Bootstrap Unseal Vault

Run from a machine with `kubectl` access to the cluster:

```bash
cd deployment/k8s/vault-transit-autounseal/bootstrap
bash bootstrap_unseal_vault.sh
```

**Outputs:**
- `unseal_init.json` — root token + 5 unseal keys (0600, keep offline)
- `main_vault_unseal_token.txt` — transit token for Main Vault (0600)

### 3.2 Create K8s Secret (Optional)

```bash
kubectl create secret generic vault-transit-token \
  --from-literal=token=$(cat main_vault_unseal_token.txt) \
  --namespace=gamebox-security
```

This secret is used by the Helm chart for the file mount; the ConfigMap is what actually injects the token into the HCL (Vault 1.21.2 ignores `token_file`).

### 3.3 Add Jenkins Credentials

**Jenkins → Manage Jenkins → Credentials → Add credentials**

| ID | Type | Value |
|----|------|-------|
| `vault-unseal-key-1` | Secret text | First unseal key from `unseal_init.json` |
| `vault-unseal-key-2` | Secret text | Second unseal key |
| `vault-unseal-key-3` | Secret text | Third unseal key |
| `vault-transit-token` | Secret text | Contents of `main_vault_unseal_token.txt` |

### 3.4 Store Offline Backup

- **Unseal Vault root token** — from `unseal_init.json` → `root_token`
- **Unseal keys** — from `unseal_init.json` → `unseal_keys_b64[0..4]`
- **Transit token** — from `main_vault_unseal_token.txt` (copy; keep with Jenkins credential)

### 3.5 Pipeline Run

After a push to `main` / `master` / `release/*`, the pipeline will:

1. Unseal Unseal Vault (if sealed) using `vault-unseal-key-1/2/3`
2. Patch the ConfigMap with the transit token from `vault-transit-token`
3. Restart vault-0

---

## 4. Jenkins Pipeline — What It Does

### Stage: Unseal Unseal Vault

- **When:** Runs on main/master/release branches
- **Prerequisite:** Credentials `vault-unseal-key-1`, `vault-unseal-key-2`, `vault-unseal-key-3`
- **Action:** If Unseal Vault is sealed, sends 3 unseal keys via `kubectl exec`
- **If skipped:** Unseal Vault stays sealed → Main Vault cannot auto-unseal → backend 502

### Stage: Patch Vault Seal Token

- **When:** Runs on main/master/release branches
- **Prerequisite:** Credential `vault-transit-token`
- **Action:** If ConfigMap contains `PLACEHOLDER_TRANSIT_TOKEN`, replaces it with the real token and restarts vault-0
- **If token already patched:** Does not restart vault-0 (idempotent)
- **If token is wrong:** Main Vault will crashloop after restart; pipeline continues but app is broken

### Important Limitation

The Jenkins patch **only** runs when `PLACEHOLDER_TRANSIT_TOKEN` is found. If the ConfigMap already has a token (wrong or expired), Jenkins does **not** overwrite it. You must manually patch or reset the Helm release to get the placeholder back, then re-run the pipeline.

---

## 5. Direct Server Steps (When Needed)

### 5.1 Unseal Unseal Vault (Manual)

```bash
ssh lb-admin@178.156.223.196

# Check status
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault status

# If sealed, unseal with 3 keys
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY1>
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY2>
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY3>
```

### 5.2 Create New Transit Token

```bash
ROOT_TOKEN="hvs.xxxx"   # your Unseal Vault root token

NEW_TOKEN=$(sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$ROOT_TOKEN" vault token create \
  -policy=main-vault-autounseal \
  -display-name="main-vault-autounseal" \
  -ttl=8760h -period=8760h -orphan=true -renewable=true -format=json 2>/dev/null | \
  jq -r '.auth.client_token')

echo "New token: $NEW_TOKEN"
```

### 5.3 Patch ConfigMap and Restart Vault

```bash
# ConfigMap name (HashiCorp Helm chart creates vault-config)
CM="vault-config"

CURRENT=$(sudo k3s kubectl get configmap "$CM" -n gamebox-security \
  -o jsonpath='{.data.extraconfig-from-values\.hcl}' 2>/dev/null)
CONFIG_KEY="extraconfig-from-values.hcl"
[ -z "$CURRENT" ] && CURRENT=$(sudo k3s kubectl get configmap "$CM" -n gamebox-security \
  -o jsonpath='{.data.server-config\.hcl}' 2>/dev/null) && CONFIG_KEY="server-config.hcl"

NEW=$(echo "$CURRENT" | sed "s|token *= *\"[^\"]*\"|token = \"$NEW_TOKEN\"|")

sudo k3s kubectl patch configmap "$CM" -n gamebox-security --type merge \
  -p "$(echo "{\"data\":{\"$CONFIG_KEY\":$(echo "$NEW" | jq -Rs .)}}")"

sudo k3s kubectl delete pod vault-0 -n gamebox-security
sudo k3s kubectl wait pod vault-0 -n gamebox-security --for=condition=Ready --timeout=120s
```

### 5.4 Restart Backend

```bash
sudo k3s kubectl rollout restart deploy/backend -n lb-automotive
```

---

## 6. Preventing Token Issues

### Do

| Action | When |
|--------|------|
| **Update Jenkins** `vault-transit-token` | Immediately after creating a new transit token |
| **Re-run pipeline** after updating Jenkins | So the patch stage applies the new token |
| **Store backup** of transit token | Offline with unseal keys |
| **Keep Unseal Vault root token** | Forever; needed for recovery |

### Don't

| Action | Why |
|--------|-----|
| **Re-initialize Unseal Vault** without updating Jenkins | Old transit token becomes invalid |
| **Rekey Unseal Vault** without updating Jenkins unseal keys | Jenkins can't unseal |
| **Revoke the transit token** | Main Vault will fail startup |
| **Delete** `unseal_init.json` | You lose root token + unseal keys |

### When Token Becomes Invalid

- Unseal Vault was re-initialized (rekey or wipe)
- Transit token was revoked
- Token expired (policy uses 8760h TTL; renew before expiry)
- Jenkins credential was never set or has wrong value

---

## 7. Recovery Checklist

When you see `vault-0` CrashLoopBackOff with "invalid token" / 403:

1. **Unseal Unseal Vault** (if sealed) — §5.1
2. **Create new transit token** — §5.2 (need root token)
3. **Update Jenkins credential** `vault-transit-token`
4. **Patch ConfigMap** — §5.3 (or re-run pipeline if ConfigMap has PLACEHOLDER)
5. **Restart backend** — §5.4

**If you don't have the root token:** Unseal Vault must be re-bootstrapped (destructive). See [Unseal Vault Key Management](../runbooks/unseal-vault-key-management.md) § "If keys are lost".

---

## 8. Quick Reference

### Jenkins Credentials

| ID | Purpose |
|----|---------|
| `vault-unseal-key-1` | Unseal Vault key shares |
| `vault-unseal-key-2` | |
| `vault-unseal-key-3` | |
| `vault-transit-token` | Main Vault transit seal token |
| `lb-server-ssh` | SSH to deploy server |

### Server Commands

```bash
# Vault status
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- env VAULT_ADDR=http://127.0.0.1:8200 vault status
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- vault status

# Pod status
sudo k3s kubectl get pods -n vault-unseal
sudo k3s kubectl get pods -n gamebox-security
sudo k3s kubectl get pods -n lb-automotive

# Main Vault logs (when crashlooping)
sudo k3s kubectl logs -n gamebox-security vault-0 -c vault --tail=100
```

### Related Docs

- [Common Failures §7 — Transit Token 403](../incidents/common-failures.md#7-main-vault-crashloopbackoff--transit-token-403)
- [Unseal Vault Key Management](../runbooks/unseal-vault-key-management.md)
- [Vault Unseal Order](../runbooks/vault-unseal-order.md)
- [K8s Debugging](../runbooks/k8s-debugging.md)
