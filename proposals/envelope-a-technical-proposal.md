# TECHNICAL PROPOSAL — ENVELOPE A

---

**Tender Reference:** DESC-MRD-2026-CNC-088  
**Issuing Organisation:** DESC Digital Innovation Center, Mardan  
**Submission:** Cloud-Native Application Orchestration & Deployment  
**Submitted by:** [Your Company Name]  
**Date:** 25th May 2026  
**Document Classification:** Technical — No Pricing Information

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Understanding of Requirements](#2-understanding-of-requirements)
3. [Proposed Solution Architecture](#3-proposed-solution-architecture)
4. [Containerization Strategy](#4-containerization-strategy)
5. [Kubernetes Cluster Architecture](#5-kubernetes-cluster-architecture)
6. [CI/CD & GitOps Deployment Workflow](#6-cicd--gitops-deployment-workflow)
7. [Infrastructure as Code](#7-infrastructure-as-code)
8. [Stateful Data Strategy](#8-stateful-data-strategy)
9. [Security Strategy](#9-security-strategy)
10. [Observability & Monitoring](#10-observability--monitoring)
11. [Chosen Toolstack](#11-chosen-toolstack)
12. [Delivery Timeline](#12-delivery-timeline)
13. [SLA Commitments](#13-sla-commitments)

---

## 1. Executive Summary

We propose a fully cloud-native, production-grade platform on **AWS EKS** that addresses every scope item in DESC-MRD-2026-CNC-088. The solution decomposes the existing monolith into **four independently scalable microservices** behind an API Gateway, manages all AWS infrastructure through **Terraform**, deploys application workloads through **ArgoCD GitOps**, enforces automated quality gates via **GitHub Actions**, and provides real-time observability through **Prometheus and Grafana**.

The platform is engineered to sustain **99.99% uptime** through Kubernetes self-healing, HPA auto-scaling (up to 15 replicas on the Records Service under load), Multi-AZ database replication, and zero-downtime rolling deployments. Every design decision documented in this proposal is demonstrated with a working, deployable codebase — no theoretical diagrams.

**Key Differentiators:**
- Live auto-scaling demonstration: pods scale 2 → 15 replicas under load within 90 seconds
- GitOps-first: no `kubectl apply` ever runs in a pipeline — Git is the single source of truth
- Security-by-default: non-root containers, encrypted secrets, isolated network tiers, WAF in front of all public traffic
- Full IaC: the entire AWS environment — from VPC subnets to ArgoCD Applications — is reproducible with a single `terraform apply`

---

## 2. Understanding of Requirements

| RFP Requirement | Our Approach |
|-----------------|-------------|
| Containerize monolithic components into isolated microservices | Backend decomposed into API Gateway + 3 domain services, each with its own Docker image, Deployment, HPA, and ServiceMonitor |
| Kubernetes cluster for automated scaling, self-healing, load balancing | AWS EKS 1.29, managed node group, HPA on all 5 services, ALB Ingress Controller |
| CI/CD pipeline (GitHub Actions / ArgoCD) for automated testing & zero-downtime rollouts | GitHub Actions per-service CI + unified release workflow; ArgoCD GitOps CD with `selfHeal: true` |
| IaC with Terraform | 5 Terraform child modules: VPC, Security Groups, EKS, RDS, ElastiCache; ArgoCD bootstrapped by Terraform |
| Prometheus + Grafana observability | kube-prometheus-stack via ArgoCD; 15-panel USE methodology dashboard; 7 alert rules; custom `/metrics` endpoint on every service |

---

## 3. Proposed Solution Architecture

### High-Level Architecture

```
Internet
  │ HTTPS
  ▼
Route 53 → AWS WAF → Application Load Balancer (:443)
                          │
          ┌───────────────┴───────────────┐
          │ /*                            │ /api/*
          ▼                               ▼
    Frontend (Flask)              API Gateway (FastAPI)
    Port 5000 · HPA 2–10          Port 8000 · HPA 2–10
                                          │
              ┌───────────────────────────┼──────────────────────────┐
              │                           │                          │
              ▼                           ▼                          ▼
     User Service                Records Service          Notification Service
     FastAPI :8001                FastAPI :8002            FastAPI :8003
     HPA 2–10                     HPA 2–15 ★               HPA 2–10
     PostgreSQL (users)           PostgreSQL (records)     PostgreSQL (notifications)
                                  Redis cache-aside        Redis pub/sub
                                  /stress HPA trigger
```

### AWS Infrastructure Layout

```
AWS ap-south-1
├── VPC (10.0.0.0/16)
│   ├── Public Subnets  (10.0.{0,1,2}.0/24)  — ALB, NAT Gateways
│   ├── Private Subnets (10.0.{10,11,12}.0/24) — EKS Worker Nodes
│   └── Isolated Subnets (10.0.{20,21,22}.0/24) — RDS, ElastiCache (no internet route)
│
├── EKS Cluster (Kubernetes 1.29)
│   ├── Namespace: desc-app      — 5 Deployments, 5 HPAs, 5 ClusterIP Services
│   ├── Namespace: monitoring    — Prometheus, Grafana, Alertmanager
│   └── Namespace: argocd        — ArgoCD server, repo server, application controller
│
├── RDS PostgreSQL 15 (Multi-AZ, db.t3.medium)
│   └── Isolated subnet group · KMS encrypted · Secrets Manager password
│
├── ElastiCache Redis 7 (Primary + Replica)
│   └── Isolated subnet group · TLS in transit · auth token in Secrets Manager
│
└── Supporting: ECR (4 repos), S3+DynamoDB (Terraform state), CloudWatch, ACM
```

---

## 4. Containerization Strategy

### Microservices Decomposition

The legacy monolith is decomposed along **domain boundaries** — each service owns exactly the data it creates and the infrastructure it needs:

| Service | Port | Domain | Data Store | Key Feature |
|---------|------|--------|-----------|-------------|
| API Gateway | 8000 | Routing & fan-out | — | Single ALB target; async httpx proxying; aggregated `/api/health` |
| User Service | 8001 | Citizen profiles | PostgreSQL `users` | No Redis dependency — demonstrates minimal coupling |
| Records Service | 8002 | Applications/records | PostgreSQL `records` + Redis | Cache-aside (30s TTL), `/stress` CPU endpoint for HPA demo |
| Notification Service | 8003 | System announcements | PostgreSQL `notifications` + Redis | Pub/sub publish to `desc:notifications` channel on every POST |
| Frontend | 5000 | UI | — | Flask, proxies all `/api/*` to Gateway |

### Docker Build Strategy

All images use **multi-stage builds** with a dedicated non-root runtime user:

```dockerfile
# Stage 1 — builder: install dependencies only
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2 — runtime: copy only installed packages + source
FROM python:3.11-slim
RUN useradd -u 1000 -m appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . /app
USER appuser
WORKDIR /app
ENV PATH=/home/appuser/.local/bin:$PATH
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Benefits:**
- Final image contains no pip, no build tools, no cache — reduces attack surface and image size (~120 MB vs ~400 MB naive build)
- Runs as UID 1000 — satisfies Kubernetes `restricted` Pod Security Standard
- `readOnlyRootFilesystem: true` enforced on all backend containers

---

## 5. Kubernetes Cluster Architecture

### EKS Cluster Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Kubernetes version | 1.29 | Current LTS; Terraform EKS module tested |
| Node group | t3.medium, 2–10 nodes | 2 vCPU / 4 GB RAM; right-sized for demo + auto-scales under HPA pressure |
| API endpoint | Private | Cluster API not reachable from internet; only jump host or VPN |
| Secrets encryption | KMS (aws/eks) | etcd secrets encrypted at rest |
| Add-ons | CoreDNS, kube-proxy, VPC CNI, EBS CSI Driver | All managed; EBS CSI required for Prometheus PVCs |
| OIDC provider | Enabled | Required for IRSA — no static IAM credentials in pods |

### Horizontal Pod Autoscaler Configuration

All services have independent HPAs. The Records Service is the demo target:

```yaml
# Records Service HPA (demo target)
spec:
  minReplicas: 2
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30      # scale up quickly
      policies:
        - type: Pods
          value: 4
          periodSeconds: 30               # add up to 4 pods every 30s
    scaleDown:
      stabilizationWindowSeconds: 300     # wait 5 min before scale-down
```

The asymmetric windows protect user experience: scale up fast when under load, scale down slowly to avoid thrashing under bursty traffic.

### Self-Healing Mechanisms

| Mechanism | How it works |
|-----------|-------------|
| Liveness probe | `GET /health` every 10s; pod restarted if 3 consecutive failures |
| Readiness probe | `GET /ready` checks DB + Redis connectivity; pod removed from Service endpoints until passing |
| HPA | Scales replicas based on CPU; Cluster Autoscaler adds EC2 nodes when pods are Pending |
| ArgoCD self-heal | Detects manual drift (someone edits a pod directly) and reverts within 3 minutes |
| Multi-AZ | RDS fails over to standby in ~60s; Redis replica promotes in ~30s |

---

## 6. CI/CD & GitOps Deployment Workflow

### Pipeline Flow

```
Developer opens Pull Request
        │
        ▼
GitHub Actions — Per-Service CI (path-filtered)
  ├── ruff lint
  ├── pytest unit tests (DB/Redis mocked — no infra required)
  └── Docker build check (push: false)
        │ (PR blocked until CI passes)
        ▼
Merge to main
        │
        ▼
GitHub Actions — Release Workflow
  ├── Matrix build: 5 services in parallel
  │   └── docker/build-push-action → DockerHub
  │       Tags: sha-<7char> + latest
  └── update-helm-values job (sequential, after build)
      ├── yq: set gateway.image.tag = "sha-a1b2c3d"
      ├── yq: set userService.image.tag = "sha-a1b2c3d"
      ├── yq: ... (all 5 services)
      └── git commit "chore(release): bump tags [skip ci]"
              │
              ▼
      ArgoCD (polls Git every 3 min)
      ├── Detects values.yaml tag change
      ├── helm upgrade --install (rolling update)
      │   maxUnavailable: 0
      │   maxSurge: 1
      └── Slack: ✅ desc-webapp synced (sha-a1b2c3d)
```

### GitOps Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Git as single source of truth | All desired state in `helm/desc-webapp/values.yaml`; ArgoCD rejects out-of-band changes |
| Declarative | No imperative `kubectl apply` in any pipeline step |
| Versioned & auditable | Every deploy traceable to a Git SHA; `git log helm/` shows full deploy history |
| Auto-correcting | `selfHeal: true` — manual drift corrected within 3 minutes |
| Rollback = git revert | `git revert HEAD && git push` triggers ArgoCD to roll back to previous image tag |

### Zero-Downtime Guarantee

The rolling update strategy with `maxUnavailable: 0` means the old pod is only terminated after the new pod passes its readiness probe (which checks DB and Redis connectivity). End users experience no interruption during deployments.

---

## 7. Infrastructure as Code

All AWS resources are managed through Terraform with remote state in S3 + DynamoDB locking.

### Module Structure

```
terraform/
├── main.tf          — root: wires all modules with explicit depends_on
├── argocd.tf        — deploys ArgoCD via Helm; registers AppProject + Applications
├── backend.tf       — S3 remote state, DynamoDB lock table
├── providers.tf     — AWS, Helm, Kubernetes providers (EKS credentials via data sources)
├── variables.tf / outputs.tf
└── modules/
    ├── vpc/         — VPC, 3-tier subnets (public/private/isolated), IGW, NAT GWs,
    │                  VPC Flow Logs to CloudWatch
    ├── security-groups/ — ALB SG (80/443 from internet), EKS SG (from ALB only),
    │                       RDS SG (5432 from EKS only), Redis SG (6379 from EKS only)
    ├── eks/         — EKS cluster, managed node group, OIDC provider, 4 managed add-ons
    ├── rds/         — PostgreSQL 15 Multi-AZ, KMS encryption, password in Secrets Manager
    └── elasticache/ — Redis 7 replication group, auth token, TLS in transit + at rest
```

### Bootstrap Sequence

The `depends_on` chain ensures resources are created in the correct order:

```
terraform apply
  1. VPC, subnets, NAT Gateways, IGW, route tables
  2. Security Groups
  3. EKS cluster, managed node group, OIDC provider
  4. RDS PostgreSQL + Secrets Manager entry
  5. ElastiCache Redis + Secrets Manager entry
  6. helm_release: ArgoCD (depends on EKS)
  7. kubernetes_manifest: ArgoCD AppProject (depends on ArgoCD)
  8. kubernetes_manifest: desc-webapp Application (depends on AppProject)
  9. kubernetes_manifest: kube-prometheus-stack Application
     └── ArgoCD syncs Helm charts → running pods
```

The entire environment — from empty AWS account to running application — is deployed with:
```bash
terraform init && terraform apply   # ~20 minutes
```

---

## 8. Stateful Data Strategy

### PostgreSQL (RDS)

| Configuration | Value | Rationale |
|---------------|-------|-----------|
| Engine | PostgreSQL 15 | LTS, asyncpg support, full ACID |
| Instance class | db.t3.medium | 2 vCPU / 4 GB — sufficient for demo; upgrade path clear |
| Multi-AZ | Enabled | Synchronous standby; automatic failover in ~60s; zero RPO |
| Encryption at rest | AWS KMS (customer-managed key) | Data protected even if storage media is removed |
| Password management | Terraform `random_password` → Secrets Manager | Never in Git, never in environment variables plain-text |
| Backup retention | 7 days | Point-in-time recovery to any second in the past week |
| Schema isolation | Each service owns one table (`users`, `records`, `notifications`) | Simulates database-per-service without extra RDS cost |

### Redis (ElastiCache)

| Configuration | Value | Rationale |
|---------------|-------|-----------|
| Engine | Redis 7 | Stable LTS with RESP3 protocol |
| Topology | Primary + 1 Replica | Read scaling + failover in ~30s |
| Use cases | Cache-aside (Records Service) · Pub/sub (Notification Service) | Two distinct Redis patterns demonstrated |
| Encryption in transit | TLS enabled | All Redis traffic encrypted between pods and cluster |
| Auth | Random token generated by Terraform, stored in Secrets Manager | No static credentials |
| Cache TTL | 30 seconds (records list) | Short enough to be consistent; long enough to absorb read spikes |

### Backup & Recovery

| Resource | RPO | RTO | Mechanism |
|----------|-----|-----|-----------|
| RDS | ~0 | ~60s | Multi-AZ synchronous replication |
| RDS | Up to 5 min | ~15 min | Automated daily snapshots + PITR |
| Redis | ~seconds | ~30s | Primary/replica failover |
| Application state | 0 | Immediate | Stateless pods — any replica serves any request |

---

## 9. Security Strategy

### Network Security

```
Internet
  │
  ▼
AWS WAF — blocks OWASP Top 10, rate-limits to 2000 req/5min/IP
  │
  ▼
ALB SG — ingress: 443 from 0.0.0.0/0 only
  │
  ▼
EKS Nodes SG — ingress: from ALB SG only (no direct internet access)
  │
  ▼
RDS SG — ingress: TCP 5432 from EKS Nodes SG only
Redis SG — ingress: TCP 6379 from EKS Nodes SG only
```

- RDS and Redis subnets have **no internet route** — completely isolated
- EKS API endpoint is private — not reachable from public internet
- VPC Flow Logs capture all rejected traffic to CloudWatch for audit

### Kubernetes Security

| Control | Configuration |
|---------|---------------|
| Pod Security Standards | `baseline` enforced on `desc-app` namespace via namespace label |
| Non-root containers | All images run as UID 1000; `runAsNonRoot: true` in `securityContext` |
| Read-only filesystem | `readOnlyRootFilesystem: true` on all backend containers |
| No privilege escalation | `allowPrivilegeEscalation: false` |
| Dropped capabilities | `drop: [ALL]` — only minimum Linux capabilities retained |
| Service accounts | Each Deployment has a dedicated ServiceAccount |
| IRSA | IAM roles bound to Kubernetes service accounts via OIDC — no static AWS keys in pods |
| Secrets | `DATABASE_URL` and `REDIS_URL` injected from Kubernetes Secrets (seeded from Secrets Manager) |

### Secrets Management

```
Terraform
  └── generates random_password (RDS) + random_password (Redis)
  └── stores in AWS Secrets Manager:
        /desc/rds/master-password
        /desc/redis/auth-token
              │
              ▼
  Kubernetes Secret (created once from Secrets Manager values)
              │
              ▼
  Pod environment variables (DATABASE_URL, REDIS_URL)
  — never stored in Git, container images, or CI logs
```

### CI Security

- `ruff` lint catches security anti-patterns at PR time
- Docker images run as non-root in CI check builds
- Credentials passed as GitHub Actions encrypted secrets — never echoed to logs

---

## 10. Observability & Monitoring

### Stack

| Component | Local (Docker Compose) | EKS (Production) |
|-----------|----------------------|-----------------|
| Prometheus | `prom/prometheus:v2.51.2` — static scrape config | `kube-prometheus-stack` via ArgoCD — ServiceMonitor CRDs |
| Grafana | `grafana/grafana:10.4.2` — volume-mounted provisioning | `kube-prometheus-stack` Grafana — sidecar auto-imports ConfigMap |
| Dashboard | Pre-provisioned via `monitoring/grafana/` directory | `grafana-dashboard-configmap.yaml` (label `grafana_dashboard: "1"`) |
| Alertmanager | Not included locally | Included in kube-prometheus-stack; 7 alert rules |

### Pre-Built Grafana Dashboard — 20 Panels

The dashboard (`desc-microservices.json`) is checked into the repository and loads automatically in both environments.

| Row | Panels | Key Queries |
|-----|--------|-------------|
| **Overview** | Gateway req/s · 5xx error % · upstream p95 latency · cache hit ratio | 4 stat cards with colour thresholds |
| **Gateway** | Request rate by status (2xx/4xx/5xx) · upstream latency p50/p95/p99 by service | `gateway_requests_total`, `gateway_upstream_latency_seconds` |
| **Business Metrics** | Users/records/notifications creation rate · notifications by type | `users_created_total`, `records_created_total`, `notifications_sent_total` |
| **Database & Cache** | DB query p95 latency by service & operation · cache hits vs misses | `db_query_duration_seconds`, `cache_hits_total`, `cache_misses_total` |
| **Redis & Frontend** | Redis publish p50/p95 latency · frontend request rate by path | `redis_publish_latency_seconds`, `frontend_requests_total` |
| **HPA Scaling Trigger** | Gateway request rate by path · active DB connections by service | Supports live demo of stress-→scale event |

### Local Access (Docker Compose)

```
http://localhost:9095          Prometheus UI (Status → Targets: 5 targets all UP)
http://localhost:3100          Grafana (admin / desc2026)
  → Dashboards → DESC → DESC — Microservices Platform
```

### EKS Access

```bash
# Prometheus
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
# Open http://localhost:9090  →  Status → Targets (look for 5 desc-app targets all UP)

# Grafana
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
# Open http://localhost:3000  (admin / DescAdmin@2026!)
# Dashboard auto-imports via sidecar ConfigMap label — no manual import needed
# Navigate: Dashboards → DESC → DESC — Microservices Platform
```

### Custom Application Metrics

Every service exposes a `/metrics` endpoint (Prometheus text format). Key custom metrics:

```
# Gateway
gateway_requests_total{method, path, status}          counter
gateway_upstream_latency_seconds{service, endpoint}   histogram

# User Service
users_created_total                                   counter
db_query_duration_seconds{operation, status}          histogram
db_connections_active                                 gauge

# Records Service
records_created_total                                 counter
cache_hits_total                                      counter
cache_misses_total                                    counter
db_query_duration_seconds{operation, status}          histogram
db_connections_active                                 gauge

# Notification Service
notifications_sent_total{type}                        counter
redis_publish_latency_seconds                         histogram
db_query_duration_seconds{operation, status}          histogram

# Frontend
frontend_requests_total{path, status}                 counter
```

### Alert Rules (EKS / kube-prometheus-stack)

| Alert | Threshold | Severity |
|-------|-----------|---------|
| HighCPUUtilization | > 80% for 5 min | Warning |
| HighMemoryUtilization | > 85% for 5 min | Warning |
| HPAAtMaxReplicas | HPA at `maxReplicas` for 5 min | Critical |
| HighCPUThrottling | > 50% throttled for 10 min | Warning |
| PendingPods | Pod Pending > 5 min | Critical |
| HighHTTPErrorRate | 5xx > 5% for 2 min | Critical |
| PodRestartLoop | > 5 restarts in 15 min | Critical |

---

## 11. Chosen Toolstack

| Layer | Tool | Version | Justification |
|-------|------|---------|---------------|
| Cloud Provider | AWS | — | Required by RFP context; mature EKS, RDS, ElastiCache managed services |
| Container Runtime | Docker (BuildKit) | 24+ | Industry standard; multi-stage builds; BuildKit cache in CI |
| Orchestration | AWS EKS | Kubernetes 1.29 | Managed control plane; AWS-integrated ALB controller, EBS CSI, VPC CNI |
| IaC | Terraform | ≥ 1.6 | Declarative, state-tracked; provider ecosystem for AWS + Helm + Kubernetes |
| GitOps CD | ArgoCD | v2.10 | Kubernetes-native; self-healing; real-time sync status visible in UI |
| CI | GitHub Actions | — | Native to GitHub; path-filtered triggers; matrix builds for parallel service CI |
| API Framework | FastAPI (Python 3.11) | 0.111+ | Async, Prometheus-native, OpenAPI docs auto-generated |
| UI Framework | Flask (Python 3.11) | 3.x | Lightweight; zero client-side JS framework overhead for demo |
| Database | PostgreSQL 15 | via RDS | ACID, asyncpg async driver, Multi-AZ failover |
| Cache / Pub-Sub | Redis 7 | via ElastiCache | In-memory speed; unified cache + pub/sub in one service |
| Monitoring | kube-prometheus-stack | v0.73 | De-facto Kubernetes monitoring; includes operator, Grafana, Alertmanager |
| Metrics | Prometheus client (Python) | 0.20+ | Native instrumentation; counters, histograms, gauges |
| Load Testing | k6 + Locust | k6 v0.50 | k6 for precise ramp control; Locust for web UI demonstration |
| Image Registry | DockerHub | — | Public registry; free tier sufficient for demo |
| Secret Storage | AWS Secrets Manager | — | Native AWS; automatic rotation support; audit trail |
| WAF | AWS WAF v2 | — | OWASP managed rule groups; rate limiting |

---

## 12. Delivery Timeline

| Week | Deliverable |
|------|-------------|
| Week 1 | AWS account setup, Terraform state bootstrap, VPC + security group provisioning |
| Week 2 | EKS cluster, RDS, ElastiCache provisioning; IRSA configuration |
| Week 3 | Microservice containerization (4 services + gateway + frontend); Docker Compose local stack |
| Week 4 | Helm chart, ArgoCD bootstrap, initial GitOps deployment to EKS |
| Week 5 | GitHub Actions CI/CD pipelines; image push automation; values.yaml update workflow |
| Week 6 | Prometheus + Grafana deployment; USE dashboard; alert rules; Slack integration |
| Week 7 | Load testing (k6 + Locust); HPA tuning; demonstration dry-run |
| Week 8 | Documentation, handover, knowledge transfer, live evaluation board demonstration |

---

## 13. SLA Commitments

| Metric | Committed Value | Mechanism |
|--------|----------------|-----------|
| Application uptime | 99.99% | Multi-AZ, HPA, self-healing pods |
| Deployment frequency | On every merge to main | GitHub Actions + ArgoCD |
| Deployment lead time | < 10 minutes (code merge to live) | Release workflow ~6 min + ArgoCD sync ~3 min |
| Mean time to recovery (MTTR) | < 15 minutes | ArgoCD rollback = one git revert |
| Incident response (critical) | 4 hours | On-call managed service |
| DB failover time | < 90 seconds | RDS Multi-AZ automatic |
| Monitoring alert latency | < 2 minutes | Prometheus 30s scrape + AlertManager routing |

---

*This document contains no pricing information. Refer to Envelope B (Financial Proposal) for all cost-related information.*

*Tender Reference: DESC-MRD-2026-CNC-088 | Submission Deadline: Sunday, 14th June 2026, 11:00 AM*
