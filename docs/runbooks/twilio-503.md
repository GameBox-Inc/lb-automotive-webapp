# Twilio 503 Checklist

**Last Updated:** March 2026  
**Related:** [Twilio Debugging](twilio-debugging.md) | [K8s Debugging](k8s-debugging.md)

---

## Checklist

1. **Confirm Twilio request hit the ingress**
   - Twilio Console → Monitor → Logs: check request status
   - Cloudflare Tunnel / cloudflared logs: `kubectl logs -n gamebox-security -l app=cloudflared`

2. **Check Traefik route + backend service**
   - `kubectl get httproute -n gamebox-security`
   - `kubectl get svc -n lb-automotive backend`
   - Traefik logs: `kubectl logs -n gamebox-security -l app.kubernetes.io/name=traefik --tail=50`

3. **Verify service has endpoints**
   - `kubectl get endpoints -n lb-automotive backend`

4. **Verify pods are Ready**
   - `kubectl get pods -n lb-automotive -o wide`
   - Backend must be `1/1` or `2/2` (with init container)

5. **Check init containers / sidecars**
   - `kubectl describe pod -n lb-automotive -l app=backend`
   - Vault Agent init must complete before main container starts

6. **Check app route returned valid TwiML or expected payload**
   - Backend logs: `kubectl logs -n lb-automotive -l app=backend -c backend --tail=100`
   - Ensure no 500 or unhandled exception before response

7. **Check timeout duration vs Twilio expectations**
   - Twilio webhook timeout (default 15s)
   - Backend gather timeout (e.g. 8s in DECISION_TREE)
   - LLM latency if using Smart Jump

8. **Confirm DNS / public URL / TLS path**
   - `twilio.kozytherocket.space` resolves correctly
   - TLS valid for Twilio
   - Cloudflare Tunnel → Traefik → backend path intact

9. **Correlate by request ID / call SID**
   - Use `CallSid` to trace logs end-to-end
   - `grep <CallSid> backend.logs`

---

## Quick Commands

```bash
# Full status
npm run debug:k8s

# Tail backend logs
npm run logs:app

# Tail Traefik logs
npm run logs:ingress
```
