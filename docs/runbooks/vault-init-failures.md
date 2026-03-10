# Vault Init Failures Runbook

**Last Updated:** March 2026  
**Related:** [Vault Unseal Order](vault-unseal-order.md) | [K8s Debugging](k8s-debugging.md) | [Twilio 503](twilio-503.md)

---

## Symptoms

- Backend pods in `Init:0/2` or `CrashLoopBackOff`
- `vault-agent-init` container fails
- Backend never becomes Ready

---

## Checklist

1. **Vault is unsealed**
   ```bash
   sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- vault status
   ```
   If sealed: Main Vault auto-unseals via **Unseal Vault** (vault-unseal namespace). Ensure Unseal Vault is running and unsealed first. See [Vault Unseal Order](vault-unseal-order.md).

2. **Vault policy allows app secrets**
   - Path: `secret/data/lb-automotive/*` or `gamebox/data/clients/lb-autorepair/*`
   - Role: `lb-automotive-role` (or equivalent)
   - Check: `vault policy read <policy-name>`

3. **Init container logs**
   ```bash
   sudo k3s kubectl logs -n lb-automotive <pod-name> -c vault-agent-init
   ```
   Look for 403, permission denied, or TLS errors.

4. **Vault TLS / connectivity**
   - Backend must reach Vault (network policy, service DNS)
   - `VAULT_ADDR` env in backend deployment must be correct

5. **Kubernetes auth configured**
   - Vault Kubernetes auth must have `lb-automotive` namespace configured
   - Service account token must be valid

---

## Quick Commands

```bash
# Vault status
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- vault status

# Init container logs
sudo k3s kubectl logs -n lb-automotive -l app=backend -c vault-agent-init --tail=50

# Describe pod (init container status)
sudo k3s kubectl describe pod -n lb-automotive -l app=backend
```

---

## Jenkins Auto-Unseal

Jenkins pipeline auto-unseals Vault if sealed. Check Jenkins credentials for `vault-unseal-key-1`, `vault-unseal-key-2`, `vault-unseal-key-3`.
