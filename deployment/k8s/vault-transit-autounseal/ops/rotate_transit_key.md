# Transit Key Rotation Procedure

Vault supports non-disruptive key rotation. The old key version remains available for decrypting existing ciphertext while all new encrypt operations use the latest version.

## When to Rotate

- **Scheduled**: Every 6–12 months
- **Incident response**: If the token is compromised
- **If audit logs show unexpected decrypt activity**

## Rotation Steps

```bash
# 1. Login to Unseal Vault with root token
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault login <UNSEAL_VAULT_ROOT_TOKEN>

# 2. Rotate the transit key (non-disruptive — old versions still decrypt)
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault write -f transit/keys/autounseal/rotate

# 3. Verify new key version
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault read transit/keys/autounseal \
  | grep -E "latest_version|min_decryption_version"

# 4. (Optional) After confirming Main Vault works, trim old key versions
# min_decryption_version prevents decryption with versions below this number
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault write transit/keys/autounseal/config \
  min_decryption_version=<NEW_VERSION>
```

## Verify Main Vault Still Auto-Unseals After Rotation

```bash
# Restart Main Vault pod — should auto-unseal with new key
kubectl delete pod vault-0 -n gamebox-security --grace-period=0
sleep 30
kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault status | grep Sealed
# Expected: Sealed false
```

## Token Rotation

If the `vault-transit-token` K8s secret token needs renewal:

```bash
# Renew token (if not expired)
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true VAULT_TOKEN=$(kubectl get secret vault-transit-token \
    -n gamebox-security -o jsonpath='{.data.token}' | base64 -d) \
  vault token renew

# Or create a new one and update the K8s secret
# (see bootstrap_unseal_vault.sh step 10, then kubectl patch the secret)
```
