# Unseal Vault Key Management (Shamir) — Rotation + Recovery

**Last Updated:** March 2026  
**Scope:** `vault-unseal/unseal-vault-0` (Transit-only Vault) and its relationship to Main Vault `gamebox-security/vault-0`.

---

## Operational policy

**Do not re-initialize Unseal Vault** unless you are doing a full recovery and accept re-initializing Main Vault and re-seeding all app secrets. Re-init of Unseal Vault creates a new transit key; Main Vault’s data was encrypted with the old key and will fail with `cipher: message authentication failed`. See [Vault stability and improvements](../architecture/vault-stability-and-improvements.md).

---

## Why this exists

Main Vault uses **transit auto-unseal** and depends on **Unseal Vault** being **unsealed**.

Unseal Vault uses **Shamir seal** (manual unseal). If it restarts sealed and no automation unseals it, Main Vault will fail startup and crashloop.

---

## Ground rules (do not skip)

- **Treat Unseal Vault key shares as production root material.**
- Store shares **outside the cluster** (not in Kubernetes Secrets).
- Keep a written record of:
  - Unseal Vault **init date**
  - **share count / threshold**
  - **where each share is stored**
  - **who holds each share**
- **Important environment detail (this cluster):** Unseal Vault serves on **HTTP**.
  - Always use `VAULT_ADDR=http://127.0.0.1:8200` for `kubectl exec` commands targeting `unseal-vault-0`.

---

## Fast triage (when Main Vault is crashlooping)

### 1) Check Unseal Vault sealed state

```bash
kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault status
```

If `Sealed: true`, Unseal Vault must be unsealed before Main Vault can recover.

---

## Standard procedure A — Manual unseal (normal restart)

Unseal Vault requires **3 of 5** keys (or whatever threshold is configured).

```bash
kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY_1>

kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY_2>

kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <KEY_3>
```

Verify:

```bash
kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault status
```

Then restart Main Vault to recover:

```bash
kubectl delete pod -n gamebox-security vault-0
kubectl get pod -n gamebox-security vault-0 -w
```

---

## Standard procedure B — Rotate (rekey) Unseal Vault Shamir shares

Use this when you want new shares (compromise suspected, staff change, periodic rotation).

**Prerequisites**
- Unseal Vault is **unsealed**
- You have **Unseal Vault root token**
- You have access to run commands on the cluster admin machine

### Rekey workflow (interactive)

Run the ops script:

```bash
bash deployment/k8s/vault-transit-autounseal/ops/rekey-unseal-vault.sh
```

It will:
- confirm current seal state
- start `vault operator rekey -init`
- accept the required number of existing key shares
- output **new key shares** (store offline immediately)

### After rekey

- Update the “key share ledger” (who holds what)
- If Jenkins automation unseals Unseal Vault, update Jenkins credentials:
  - `vault-unseal-key-1`
  - `vault-unseal-key-2`
  - `vault-unseal-key-3`
- Validate end-to-end (see Validation section).

---

## Standard procedure C — If keys are lost (unseal impossible)

If you see this error when attempting unseal:

- `failed to decrypt keys from storage`
- `cipher: message authentication failed`

…then the keys you’re using do **not** match the current Unseal Vault storage. If the correct keys are unrecoverable, Unseal Vault cannot be unsealed.

**⚠️ Important:** Re-initializing Unseal Vault (below) creates a **new** transit key. Main Vault’s data was encrypted with the **old** key and will then fail with `cipher: message authentication failed` on decrypt. You must also [re-initialize Main Vault and re-seed app secrets](../incidents/common-failures.md#8-main-vault--transit-decrypt-400-cipher-message-authentication-failed). See [Vault stability and improvements](../architecture/vault-stability-and-improvements.md) for why this chain is fragile and how to avoid it.

### Recovery option (destructive to Unseal Vault only)

1) **Wipe Unseal Vault PVC** (data loss in Unseal Vault; Main Vault will need a new transit token):

```bash
kubectl delete pod -n vault-unseal unseal-vault-0
kubectl delete pvc -n vault-unseal data-unseal-vault-0
```

2) Re-bootstrap Unseal Vault using the repo bootstrap script (creates transit key + new token):

```bash
cd deployment/k8s/vault-transit-autounseal/bootstrap
bash bootstrap_unseal_vault.sh
```

3) Update downstream dependencies:
- Update Jenkins credential `vault-transit-token` to the newly generated transit token.
- Update Jenkins `vault-unseal-key-1/2/3` to the newly generated shares (if you use Jenkins to unseal).

4) Restart Main Vault:

```bash
kubectl delete pod -n gamebox-security vault-0
```

---

## Validation checklist (required)

### Validate Unseal Vault

```bash
kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault status
```

Expect: `Sealed: false`.

### Validate transit endpoint is reachable from Main Vault network

```bash
kubectl exec -n gamebox-security vault-0 -c vault -- \
  sh -lc 'wget -qO- http://unseal-vault.vault-unseal.svc.cluster.local:8200/v1/sys/health || true'
```

### Validate Main Vault recovers

```bash
kubectl get pod -n gamebox-security vault-0 -w
kubectl logs -n gamebox-security vault-0 -c vault --tail=120
```

---

## Operational “ledger” template

Record this in your password manager / secure offline store:

- Unseal Vault init date:
- Share count / threshold:
- Holder #1:
- Holder #2:
- Holder #3:
- Holder #4:
- Holder #5:
- Jenkins unseal credentials updated? (Y/N, date):
- Transit token rotated? (Y/N, date):

