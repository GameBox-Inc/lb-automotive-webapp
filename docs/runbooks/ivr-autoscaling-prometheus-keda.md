# IVR API autoscaling (Prometheus + KEDA)

This runbook covers **call-oriented autoscaling** for the `backend` Deployment: Prometheus scrapes `/metrics`, **KEDA** scales replicas from **sum of `ivr_webhook_in_flight`** (and CPU as a second trigger).

**Load balancing** is unchanged: Traefik → Kubernetes **Service** `backend` → pods. Autoscaling only changes **how many** pods run.

## Metrics (app)

| Metric | Type | Use |
|--------|------|-----|
| `ivr_webhook_in_flight` | Gauge | Concurrent Twilio webhook handlers **per process**; KEDA query typically `sum(...)` across pods. |
| `ivr_calls_total{step,language}` | Counter | Business counter; optional for dashboards. |
| `http_requests_total{endpoint,...}` | Counter | Alternative: RPS via `sum(rate(http_requests_total{endpoint="/api/twilio/webhook"}[1m]))` if you prefer not to use the gauge. |

Verify in Prometheus **Graph** after scrape is working:

```promql
sum(ivr_webhook_in_flight)
```

If your scrape adds different labels, inspect **Targets** → metric labels and adjust the ScaledObject query (e.g. filter by `namespace`).

## Prerequisites

1. **kube-prometheus-stack** (or any Prometheus) with the **Prometheus Operator** if you use `PodMonitor`.
2. **KEDA** installed, e.g. `helm install keda kedacore/keda --namespace keda --create-namespace`.

## 1. Scrape backend `/metrics`

**With Prometheus Operator** (repo manifest):

```bash
# From repo root on a machine with kubeconfig
kubectl apply -f deployment/k8s/monitoring/backend-podmonitor.yaml
```

- Backend pods expose port name **`http`** on container port `8000` (`deployment/k8s/backend.yaml`).
- Ensure the PodMonitor `metadata.labels` match your Prometheus `podMonitorSelector` (example in the file: `release: kube-prometheus-stack`).

**Without PodMonitor:** add a `scrape_configs` job that discovers pods in `lb-automotive` with label `app=backend` and path `/metrics` (see Prometheus `kubernetes_sd_configs` role `pod`).

Confirm in Prometheus: **Status → Targets** shows backend pods **UP**.

## 2. Enable KEDA scaling (replaces static CPU HPA)

`ScaledObject` creates its own HPA. **Do not** keep the manifest HPA and KEDA on the same Deployment.

1. Remove the CPU-only HPA (or stop shipping it from `deployment/k8s/backend.yaml` on future applies):

   ```bash
   kubectl delete hpa backend -n lb-automotive --ignore-not-found
   ```

2. Edit `deployment/k8s/monitoring/keda-backend-scaledobject.yaml`:
   - Set `spec.triggers[0].metadata.serverAddress` to your Prometheus **in-cluster** base URL (no `/query` path), e.g.  
     `http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090`
   - Tune `threshold` (Prometheus scalar vs desired scale-out behavior), `minReplicaCount`, and `maxReplicaCount` for your node size (2 vCPU / small nodes often cap at **2–3** backends).

3. Apply:

   ```bash
   kubectl apply -f deployment/k8s/monitoring/keda-backend-scaledobject.yaml
   ```

Check:

```bash
kubectl get scaledobject -n lb-automotive
kubectl get hpa -n lb-automotive
kubectl get pods -n lb-automotive -l app=backend
```

## 3. Load test and observe

**Only in dev/staging** with `TWILIO_SKIP_VALIDATION=true` (signatures are not validated):

```bash
npm run debug:webhook:stress -- --url "http://<backend-host>:8000/api/twilio/webhook?step=start" --count 50 --concurrency 15
```

During the test:

- Prometheus: `sum(ivr_webhook_in_flight)` should spike, then fall.
- `kubectl get hpa -n lb-automotive -w` (KEDA-managed HPA): target / replicas should react (may lag due to `cooldownPeriod` / `stabilizationWindowSeconds`).
- `kubectl top pods -n lb-automotive -l app=backend`

## 4. Rollback / CPU-only mode

To return to **CPU-only** autoscaling:

```bash
kubectl delete scaledobject backend-ivr -n lb-automotive --ignore-not-found
kubectl apply -f deployment/k8s/backend.yaml
```

(Ensure the `HorizontalPodAutoscaler` section in `backend.yaml` is present.)

## Files in repo

| File | Purpose |
|------|---------|
| `python-backend/observability/monitoring.py` | `ivr_webhook_in_flight`, `ivr_calls_total` |
| `python-backend/routes/twilio/webhook.py` | Tracks in-flight + increments `ivr_calls_total` |
| `deployment/k8s/backend.yaml` | Named port `http`, default CPU HPA |
| `deployment/k8s/monitoring/backend-podmonitor.yaml` | PodMonitor scrape |
| `deployment/k8s/monitoring/keda-backend-scaledobject.yaml` | KEDA Prometheus + CPU triggers |
| `deployment/k8s/monitoring/README.md` | Short ops notes |

## Risks

- Wrong PromQL or missing scrape → KEDA sees **0** → may scale down unexpectedly; verify queries in Prometheus first.
- **Two HPAs** on one Deployment → conflict; delete the static HPA before KEDA.
- **Over-sharding** on a single node: raising `maxReplicaCount` without enough CPU/RAM causes pending pods or thrashing.
