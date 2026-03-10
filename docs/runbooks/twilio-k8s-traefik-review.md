# K3s & Traefik Config Review: Twilio Callbacks & Audio

**Last Updated:** March 2026  
**Scope:** Routes serving Twilio webhooks and hosted audio files  
**Focus:** Misconfigurations that could cause intermittent 503 or 404 errors

---

## Summary

| Severity | Issue | Location | Impact |
|----------|-------|----------|--------|
| **Critical** | Cloudflared → Traefik port mismatch | cloudflared.yaml:34 | 503/connection refused |
| **Critical** | No route for `/audio/*` | lb-automotive-routes.yaml | 404 for audio files |
| **High** | Backend has no readiness probe | backend.yaml | 503 during pod startup |
| **High** | Single backend replica | backend.yaml | 503 during restarts |
| **Medium** | ReferenceGrant API version | reference-grant.yaml | Possible cross-naming issues |
| **Low** | HTTPRoute method restriction | lb-automotive-routes.yaml | GET to webhook → 404 |

---

## 1. Critical: Cloudflared → Traefik Port Mismatch

**File:** `deployment/k8s/gamebox-security/cloudflared.yaml` (line 34)

```yaml
service: http://traefik.gamebox-security.svc.cluster.local:80
```

**File:** `deployment/k8s/gamebox-security/traefik/traefik-helm-values.yaml` (lines 36–37)

```yaml
ports:
  web:
    port: 8000
    nodePort: 30881
```

**Issue:** Traefik is configured to listen on port **8000** for the web entrypoint. The Traefik Helm chart exposes the Service port based on this value, so the Service port is **8000**, not 80. Cloudflared connecting to `:80` will hit a closed port or the wrong service.

**Impact:** 503 or connection refused for all Twilio traffic.

**Fix:** Update cloudflared config:

```yaml
service: http://traefik.gamebox-security.svc.cluster.local:8000
```

**Verify:** `kubectl get svc -n gamebox-security traefik` and confirm the port used for the web entrypoint. If the Service exposes 80, the runbook is correct and the Helm values may need adjustment instead.

---

## 2. Critical: No Route for Hosted Audio Files

**File:** `python-backend/database.py` (line 413)

```python
('ivr_thinking_sound_url', 'https://twilio.kozytherocket.space/audio/thinking.mp3', ...)
```

**File:** `deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml`

**Issue:** The HTTPRoute only matches `/api/twilio` and `/lb-automotive/api/twilio`. There is **no route** for `/audio/*`. When Twilio fetches `https://twilio.kozytherocket.space/audio/thinking.mp3`, Traefik has no matching route and returns 404.

**Impact:** 404 for audio playback; IVR may fail or play no audio.

**Fix:** Add an HTTPRoute rule for audio:

```yaml
- matches:
    - path:
        type: PathPrefix
        value: /audio
      method: GET
  backendRefs:
    - name: backend
      namespace: lb-automotive
      port: 8000
```

**Prerequisite:** The backend must serve `/audio/*` (e.g. via `StaticFiles` or a dedicated route). If not implemented, add that first.

---

## 3. High: Backend Has No Readiness Probe

**File:** `deployment/k8s/backend.yaml`

**Issue:** The backend pod has no `readinessProbe` or `livenessProbe`. Traffic is sent to the pod as soon as it is scheduled, even before:

- Vault Agent init completes
- Secrets are written to `/vault/secrets/*`
- Uvicorn finishes startup

**Impact:** Intermittent 503 during pod startup, restarts, or rollouts.

**Fix:** Add a readiness probe:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
```

---

## 4. High: Single Backend Replica

**File:** `deployment/k8s/backend.yaml` (line 9)

```yaml
replicas: 1
```

**Issue:** With one replica, any backend restart (Vault init, OOM, rollout) causes a brief period with no endpoints. Traefik will return 503 during that window.

**Impact:** Intermittent 503 during deployments, restarts, or evictions.

**Mitigation:** Add a second replica if resources allow, or ensure readiness probes delay traffic until the app is ready.

---

## 5. Medium: ReferenceGrant API Version

**File:** `deployment/k8s/lb-automotive/reference-grant.yaml`

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
```

**Issue:** HTTPRoute uses `gateway.networking.k8s.io/v1`. ReferenceGrant uses `v1beta1`. In most clusters this is fine, but API deprecation or migration can cause cross-naming issues.

**Impact:** Low risk; mainly future compatibility.

**Fix:** Use `apiVersion: gateway.networking.k8s.io/v1` when available.

---

## 6. Low: HTTPRoute Method Restriction

**File:** `deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml`

**Issue:** Both rules use `method: POST`. Twilio webhooks are POST, but if a GET is sent (e.g. health check or misconfiguration), it will not match and return 404.

**Impact:** 404 for non-POST requests; usually acceptable for webhooks.

---

## Request Flow (Current)

```
Twilio
  → twilio.kozytherocket.space (Cloudflare DNS)
  → Cloudflare Tunnel (cloudflared)
  → traefik.gamebox-security.svc.cluster.local:80  ← port mismatch if Service uses 8000
  → Traefik (Gateway API)
  → HTTPRoute (hostname + path match)
  → backend.lb-automotive.svc.cluster.local:8000
  → backend pod
```

---

## Checklist for 503/404 Debugging

1. **Cloudflared → Traefik port:** `kubectl get svc -n gamebox-security traefik` — confirm port matches cloudflared config.
2. **Backend endpoints:** `kubectl get endpoints -n lb-automotive backend` — must have at least one Ready pod.
3. **HTTPRoute status:** `kubectl describe httproute lb-automotive-twilio -n gamebox-security` — check for errors.
4. **ReferenceGrant:** `kubectl get referencegrant -n lb-automotive` — ensure it exists.
5. **Audio route:** `curl -I https://twilio.kozytherocket.space/audio/thinking.mp3` — should return 200 if route exists and backend serves it.

---

## Related

- [ingress-service-endpoints.md](ingress-service-endpoints.md)
- [twilio-503.md](twilio-503.md)
- [audio-playback.md](audio-playback.md)
