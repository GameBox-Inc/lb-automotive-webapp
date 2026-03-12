# Vault Architecture: Why the Loop Happens and How to Improve

**Purpose:** Explain why the Unseal Vault → Main Vault → Backend chain keeps failing, which architectural weaknesses cause it, and how to make future deployments stable.

**Last Updated:** March 2026

---

## 1. Why We Keep Falling Into the Loop

The same failures repeat because **one break in a long, fragile chain** takes down the whole stack and recovery is manual and error-prone.

### The chain

```
Unseal Vault (re-init / rekey / sealed)
    → transit key or token changes or is unavailable
        → Main Vault cannot auto-unseal (403 invalid token, or 400 cipher failed)
            → Vault Agent cannot inject secrets into backend
                → Backend stuck Init:0/1
                    → Frontend 502
```

### What keeps breaking

| Failure | Trigger | Why it recurs |
|--------|---------|----------------|
| **403 invalid token** | Token in ConfigMap wrong, or Unseal Vault re-init revokes it | Token lives in two places (Jenkins + ConfigMap). Re-bootstrap creates a new token; if Jenkins or patch isn’t updated, next restart uses the old token. |
| **400 cipher: message authentication failed** | Unseal Vault re-initialized (or transit key recreated) | Main Vault’s storage was encrypted with the *old* transit key. New key with same name can’t decrypt it. No key versioning; re-init of Unseal Vault is a breaking change for Main Vault. |
| **Backend Init:0/1** | Main Vault sealed or crashlooping | Backend has no fallback; it blocks until Vault Agent succeeds. Any Vault outage = app outage. |
| **502 after “fix”** | Main Vault re-initialized to recover from cipher error | All app secrets are lost. If secrets aren’t re-seeded, Vault Agent fails on read (403 or missing path). |

So: **we’re not fixing a single bug; we’re operating a multi-step, stateful system with no single source of truth and no automated recovery.**

---

## 2. Architectural Weaknesses

### 2.1 Fragile seal chain (three hops)

- **Unseal Vault** is manually unsealed (Shamir). If it restarts, it’s sealed until Jenkins or an operator unseals it.
- **Main Vault** depends on Unseal Vault’s transit key and a **token** that must be patched into a ConfigMap (Vault 1.21 doesn’t support `token_file` in the seal block). That token can go out of sync with Jenkins or with the actual token in Unseal Vault.
- **Backend** depends on Main Vault being unsealed and having the right policies and secrets. No retry/backoff or alternative secret source.

Any re-init, rekey, or mis-patch in the first two steps breaks the third.

### 2.2 No single source of truth

- **Transit token:** Jenkins credential vs ConfigMap vs `main_vault_unseal_token.txt`. Any one can be stale.
- **Unseal keys:** Offline store vs Jenkins credentials. After rekey, both must be updated.
- **App secrets:** Only in Main Vault. After Main Vault re-init, they’re gone; re-seed is manual (or from memory/docs). No automated “re-seed from here” path.

### 2.3 Re-initialization is destructive and undocumented as such

- **Unseal Vault re-init** (e.g. after PVC wipe or “start fresh”): Creates a new transit key (same name `autounseal`). Main Vault’s ciphertext is tied to the old key → **400 cipher**. Recovery = Main Vault re-init + full re-seed.
- **Main Vault re-init:** All app secrets deleted. Recovery = re-create every secret and role; no backup/restore or GitOps re-seed in the current design.

So “re-initialize to fix something” in one place often forces a cascade of re-inits and re-seeds.

### 2.4 Deployment and pipeline split

- **Jenkins** applies gamebox-security, unseals Unseal Vault, patches Main Vault token, deploys lb-automotive.
- **GitHub Actions** (if used) may apply different manifests (e.g. lb-automotive with different secret strategy) or restart deployments without ensuring Vault is ready.
- Two pipelines + manual steps = inconsistent state (e.g. backend restarted before Vault is unsealed, or token never patched after Helm upgrade).

### 2.5 No automated recovery or ordering guarantees

- No operator or Job that: “If Unseal Vault is sealed, unseal it”; “If Main Vault is sealed, wait and retry”; “If Main Vault was re-initialized, re-seed secrets from X.”
- No formal “deployment order” enforced in-cluster (e.g. backend only starts after Vault is unsealed and secrets exist). Backend just blocks in Init until Vault works.

### 2.6 Resource pressure (2GB)

- Evictions or OOM can restart Unseal Vault or Main Vault. Restart = Unseal Vault sealed again; if nobody unseals it (e.g. Jenkins not run), the chain stays broken. So the system is sensitive to restarts and timing.

---

## 3. How to Improve for Stable Future Deployments

### 3.1 Short-term: Harden the current design (no big architecture change)

| Action | Purpose |
|--------|--------|
| **Single pipeline owner** | Use only Jenkins (or only one pipeline) to deploy gamebox-security and lb-automotive. Disable or narrow GitHub Actions so it doesn’t apply Vault/backend or restart backend without Vault being ready. |
| **Document “never re-init Unseal Vault”** | Add to runbooks: re-initializing Unseal Vault breaks Main Vault (cipher error) and forces full Main Vault re-init + re-seed. If Unseal Vault must be reset, document the full procedure: Unseal Vault re-init → Main Vault PVC wipe + re-init → re-seed all secrets → update Jenkins token/keys. |
| **Canonical re-seed script** | One script (e.g. `scripts/seed-vault-secrets.sh`) that reads from env or a secure store and creates `secret/lb-automotive/*` and policies/roles. Run it after every Main Vault re-init so re-seed is repeatable. |
| **Alerts** | Alert when Unseal Vault or Main Vault is sealed, or when backend pods are Init > 5 min. So you notice breakage quickly instead of discovering it via 502. |

These reduce the chance of accidental re-init and make recovery consistent.

### 3.2 Medium-term: Single source of truth and ordering

| Action | Purpose |
|--------|--------|
| **Transit token from one place** | E.g. store the transit token only in a K8s Secret; have a small init container or Job (running with high privileges) that patches the vault-config ConfigMap from that Secret after Helm install. So “current token” is the Secret; Jenkins only needs to update that Secret when you rotate. |
| **Automated Unseal Vault unseal** | A CronJob or operator that, if Unseal Vault is sealed, unseals it using keys from a K8s Secret (or from a secure store). Reduces dependence on “run Jenkins after every restart.” |
| **Backend init checks Vault** | Backend init container that waits for Vault unsealed and (optionally) for secret paths to exist, with backoff. Doesn’t fix Vault, but avoids silent stuck Init and makes ordering explicit. |

### 3.3 Long-term: Simplify or move off the dual-Vault chain

Choose one direction; both reduce the “chain length” and failure modes.

**Option A – Single Vault + Shamir (simpler chain)**

- One Vault (current Main Vault) with **Shamir seal** only. No Unseal Vault, no transit seal.
- Jenkins (or a secure Job) unseals it after deploy/restart using keys from Jenkins credentials.
- Pros: No transit token, no cipher mismatch, no “Unseal Vault re-init breaks Main Vault.”  
- Cons: Unseal required after every Vault restart; keys must be stored and used by automation.

**Option B – App secrets out of Vault (simplest for this app)**

- Store app secrets (SECRET_KEY, Twilio, Anthropic, DB URL) in **K8s Secrets** (or External Secrets from a single source). Backend reads from env/files mounted from those Secrets; **remove Vault Agent** from the backend deployment.
- Keep Vault only if you need it for other workloads or audit. For lb-automotive alone, this removes the entire Unseal Vault → Main Vault → Vault Agent chain and eliminates 502s caused by that chain.
- Pros: No seal chain for app; fewer moving parts; restarts don’t break app.  
- Cons: No Vault audit for these secrets; rotation is via K8s/External Secrets, not Vault.

**Option C – Keep dual-Vault but add backup/restore**

- Back up Main Vault’s secret engine data (e.g. `vault read -format=json` or snapshot) to a secure store. After Main Vault re-init, restore from backup instead of manual re-seed.
- Reduces impact of Main Vault re-init but doesn’t remove the fragility of the seal chain itself.

---

## 4. Recommended path (summary)

1. **Immediate:** Single pipeline owner; “never re-init Unseal Vault” in runbooks; canonical re-seed script; alerts for sealed Vaults and backend Init.
2. **Next:** Transit token from one place (e.g. Secret → patch ConfigMap); optional automated Unseal Vault unseal; backend init that waits for Vault.
3. **Later:** Either simplify to one Vault + Shamir, or move lb-automotive secrets to K8s/External Secrets and drop Vault from the app path, so deployments stay stable without depending on the full seal chain.

---

## 5. Implemented pieces (recommended path)

| Item | Location | Notes |
|------|----------|--------|
| **Single pipeline** | `.github/workflows/k8s-deploy.yaml` | Deploy runs only on `workflow_dispatch`; Jenkins is the automatic deploy. |
| **Canonical re-seed** | `deployment/scripts/seed-vault-secrets.sh` | Run after Main Vault re-init; set env vars and execute. |
| **Vault health check** | `deployment/k8s/gamebox-security/vault-health-cronjob.yaml` | CronJob every 5 min; fails if Vault sealed or no backend Running. |
| **Transit token from Secret** | `deployment/k8s/gamebox-security/vault/patch-transit-token-job.yaml` | Job reads `vault-transit-token` Secret and patches `vault-config` ConfigMap. |
| **Automated Unseal Vault unseal** | `deployment/k8s/vault-unseal-automation/unseal-cronjob.yaml` | Optional; create Secret `vault-unseal-keys` with key1/key2/key3. |
| **Backend wait for Vault** | `deployment/k8s/backend.yaml` | Init container `wait-for-vault` waits for Main Vault unsealed before Vault Agent. |

**Operational policy:** Do **not** re-initialize Unseal Vault unless you are prepared to re-initialize Main Vault and re-seed all app secrets. See [Unseal Vault Key Management](../runbooks/unseal-vault-key-management.md) procedure C.

---

## 6. Related docs

- [Vault Transit Token Management](../howto/vault-transit-token-management.md)
- [Common Failures §7, §8](../incidents/common-failures.md)
- [Unseal Vault Key Management](../runbooks/unseal-vault-key-management.md)
