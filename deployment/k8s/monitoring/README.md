# Optional monitoring: IVR call-volume autoscaling

These manifests require extra cluster components. They are **not** applied by default in the Jenkins `kubectl apply` list (to avoid failures when CRDs are missing).

## Prerequisites

1. **Prometheus** scraping the `backend` pods (use `backend-podmonitor.yaml` if you run **kube-prometheus-stack** / Prometheus Operator).
2. **KEDA** installed (`helm install keda kedacore/keda --namespace keda --create-namespace`).

## Call-volume scaling (KEDA)

KEDA’s `ScaledObject` creates its own HPA. You **must remove** the static CPU HPA shipped in `deployment/k8s/backend.yaml` before applying the ScaledObject, or scaling will conflict:

```bash
sudo k3s kubectl delete hpa backend -n lb-automotive --ignore-not-found
sudo k3s kubectl apply -f deployment/k8s/monitoring/keda-backend-scaledobject.yaml
```

Edit `keda-backend-scaledobject.yaml` and set `serverAddress` to your Prometheus URL (cluster-internal).

## Prometheus scrape (PodMonitor)

If the Prometheus Operator CRDs exist:

```bash
sudo k3s kubectl apply -f deployment/k8s/monitoring/backend-podmonitor.yaml
```

Match `spec.selector` / labels to your Prometheus `podMonitorSelector` (often `release: kube-prometheus-stack` on the PodMonitor).

See also: [docs/runbooks/ivr-autoscaling-prometheus-keda.md](../../../docs/runbooks/ivr-autoscaling-prometheus-keda.md).
