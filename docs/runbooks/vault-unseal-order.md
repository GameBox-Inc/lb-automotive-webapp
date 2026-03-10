# Vault Unseal Order and Pending Pods

**Last Updated:** March 2026  
**Related:** [Vault Init Failures](vault-init-failures.md) | [K8s Debugging](k8s-debugging.md)

---

## Important: vault-agent-injector Does NOT Unseal vault-0

The **vault-agent-injector** is a Kubernetes admission webhook that adds Vault Agent sidecars to pods (e.g. backend). It **consumes** Main Vault after it is unsealed — it does **not** unseal vault-0.

---

## Correct Unseal Flow

```
1. Unseal Vault (vault-unseal namespace)
   └── Must be Running and manually unsealed first
   └── Hosts transit engine; Main Vault uses it for auto-unseal

2. Main Vault (vault-0, gamebox-security)
   └── Auto-unseals via transit seal → contacts Unseal Vault
   └── No manual unseal needed if Unseal Vault is reachable

3. vault-agent-injector (gamebox-security)
   └── Connects to Main Vault to inject secrets into app pods
   └── Requires Main Vault to be unsealed
```

---

## When All Pods Are Pending

If `vault-0`, `vault-agent-injector`, and other gamebox-security pods show `Pending` with "pod does not have a host assigned", the scheduler cannot place them — usually due to **resource pressure** on the 2GB node.

### 1. Check if Unseal Vault is deployed and running

```bash
sudo k3s kubectl get pods -n vault-unseal
sudo k3s kubectl get pods -n gamebox-security
```

If `vault-unseal` namespace doesn't exist or Unseal Vault isn't deployed, Main Vault cannot auto-unseal. Deploy Unseal Vault first (see `deployment/k8s/vault-transit-autounseal/README.md`).

### 2. Ensure Unseal Vault is deployed before gamebox-security

Unseal Vault has lower resource requests (64Mi/256Mi) and should schedule first. Apply vault-unseal manifests **before** gamebox-security:

```bash
# If vault-unseal exists in the repo
sudo k3s kubectl apply -f ~/k8s-manifests/k8s/vault-transit-autounseal/unseal-vault/
# Then apply gamebox-security
```

### 3. Manually unseal Unseal Vault (if it restarts)

Unseal Vault uses **manual unseal** (Shamir). When its pod restarts, you must unseal it:

```bash
# Check status
sudo k3s kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault status

# Unseal with keys (typically 3 of 5)
sudo k3s kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <KEY1>
sudo k3s kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <KEY2>
sudo k3s kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <KEY3>
```

Store Unseal Vault root token and unseal keys securely (see your credentials document).

### 4. Reduce resource requests to fit the 2GB node

If pods remain Pending, reduce requests in:

- `deployment/k8s/gamebox-security/vault/vault-helm-values.yaml` — Main Vault (256Mi→128Mi)
- `deployment/k8s/gamebox-security/traefik/traefik-helm-values.yaml` — Traefik
- `deployment/k8s/gamebox-security/cloudflared.yaml` — Cloudflared
- Vault Agent Injector (64Mi/128Mi in vault-helm-values)

### 5. Reduce replicas

Set Traefik and cloudflared to 1 replica to free memory.

---

## Summary

| Component            | Unseals vault-0? | Role                                      |
|---------------------|------------------|-------------------------------------------|
| Unseal Vault         | No (vault-0 uses it) | Transit engine; Main Vault auto-unseals via it |
| Main Vault (vault-0) | Self (via transit)   | Auto-unseals when Unseal Vault is reachable    |
| vault-agent-injector| No               | Injects secrets into app pods; needs vault-0 unsealed |

**Order:** Unseal Vault (running + unsealed) → vault-0 (auto-unseals) → vault-agent-injector (can inject).
