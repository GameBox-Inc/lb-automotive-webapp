# Break-Glass: Manual Unseal When Unseal Vault Is Down

## When This Applies

Main Vault is sealed and Unseal Vault is unreachable or crashed. This is a last-resort procedure.

> [!CAUTION]
> You MUST have the Main Vault recovery keys from `main_vault_init.json`. These are generated during `bootstrap_main_vault.sh`. Store them offline.

## Manual Recovery Steps

### 1. Try to restore Unseal Vault first (fastest path)

```bash
# Check pod status
kubectl get pod vault-0 -n vault-unseal

# If CrashLoopBackOff — check logs
kubectl logs vault-0 -n vault-unseal --tail=30

# If pod is just restarting, wait — it re-initializes itself
# If Unseal Vault itself is sealed, it needs its own unseal keys
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <UNSEAL_VAULT_KEY1>
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <UNSEAL_VAULT_KEY2>
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator unseal <UNSEAL_VAULT_KEY3>
```

### 2. If Unseal Vault data is lost — use recovery keys on Main Vault

With transit auto-unseal, Main Vault has **recovery keys** (not unseal keys). These allow manual recovery:

```bash
# Trigger recovery mode
kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator generate-root -init

# Use recovery keys (threshold of 3/5 required)
# Each person provides their key shard
kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator generate-root -nonce=<NONCE> \
  <RECOVERY_KEY_1>
# ... repeat for each recovery key shard
```

### 3. Worst case — rebuild Unseal Vault, restore transit key from Raft snapshot

```bash
# Restore Unseal Vault from Raft snapshot
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault login <UNSEAL_VAULT_ROOT_TOKEN>
kubectl exec -n vault-unseal vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator raft snapshot restore \
  /path/to/snapshot.snap
```

## Prevention

- Take weekly Raft snapshots of Unseal Vault (see README.md backup section)
- Store Unseal Vault init keys in a physical safe or password manager
- Monitor Unseal Vault Pod readiness with alerts
