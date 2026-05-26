# Load Testing — DESC Cloud-Native Demo

This folder contains load tests designed to trigger HPA auto-scaling on EKS and validate the application under sustained traffic.

## Tools

| Tool | File | Use Case |
|------|------|----------|
| k6 | `k6/load-test.js` | Full ramp-up scenario (CI-friendly, threshold assertions) |
| k6 | `k6/stress-test.js` | Live demo spike — instant scale trigger |
| Locust | `locust/locustfile.py` | Alternative with web UI, good for evaluation board demos |

---

## Prerequisites

```bash
# Install k6 (Linux)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Install Locust
pip install locust
```

---

## Running the Full Ramp Test (k6)

```bash
export BASE_URL=http://$(kubectl get ingress -n desc-app -o jsonpath='{.items[0].status.loadBalancer.ingress[0].hostname}')
echo "Testing against: $BASE_URL"

k6 run --env BASE_URL=$BASE_URL k6/load-test.js
```

Expected output shows HPA scaling in the parallel watch window:
```
NAME             REFERENCE                       TARGETS   MINPODS   MAXPODS   REPLICAS
desc-backend     Deployment/desc-backend         67%/50%   2         15        6
desc-frontend    Deployment/desc-frontend        42%/60%   2         10        2
```

---

## Live Demo Spike (k6) — Evaluation Board

Open **two terminals side-by-side**:

**Terminal 1** (HPA watch — show to the board):
```bash
watch -n2 "kubectl get hpa,pods -n desc-app --no-headers | column -t"
```

**Terminal 2** (spike trigger):
```bash
k6 run --env BASE_URL=$BASE_URL k6/stress-test.js
```

Expected timeline:
- T+0s: Load starts, 300 VUs hammering `/api/stress`
- T+30s: HPA detects CPU > 50%, starts scaling backend 2 → 6 → 12 replicas
- T+60s: Cluster Autoscaler adds nodes if needed
- T+5m: Load drops, scale-down stabilisation window begins (5 minutes)
- T+10m: Pods scale back to minReplicas=2

---

## Locust Web UI (Interactive Demo)

```bash
locust -f locust/locustfile.py --host $BASE_URL
# Open http://localhost:8089
# Set: Number of users = 200, Spawn rate = 20, then click Start
```

The web UI shows real-time RPS, latency percentiles, and error rates — ideal for presenting to the evaluation committee.

---

## Correlating Load with Grafana

During load test, open the Grafana USE dashboard:
```bash
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
# Open http://localhost:3000
# Navigate to: Dashboards → DESC USE Metrics
```

Key panels to watch:
- **CPU Utilization %** — rises as load increases
- **HPA Replicas (current vs desired)** — shows scaling in action
- **P95 Latency** — should stay below 2000ms with scaling
- **HTTP Error Rate** — should stay near 0%
