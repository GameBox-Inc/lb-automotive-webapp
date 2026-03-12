# Optional: Automated Unseal Vault Unseal

This CronJob runs every 5 minutes and unseals Unseal Vault if it is sealed (e.g. after a pod restart). It reduces dependence on running Jenkins after every restart.

**Prerequisites:**

1. Namespace `vault-unseal` exists (created when you deploy Unseal Vault).
2. Create a Secret with the three unseal keys (do **not** commit keys to Git):

```bash
kubectl create secret generic vault-unseal-keys -n vault-unseal \
  --from-literal=key1="<unseal-key-1>" \
  --from-literal=key2="<unseal-key-2>" \
  --from-literal=key3="<unseal-key-3>"
```

3. Apply the CronJob:

```bash
kubectl apply -f deployment/k8s/vault-unseal-automation/unseal-cronjob.yaml
```

**Security note:** Storing unseal keys in a cluster Secret is a tradeoff (automation vs. key exposure). For higher security, keep using Jenkins to unseal and do not deploy this CronJob.
