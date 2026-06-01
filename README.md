# DESC Cloud-Native Application Platform

**Tender Reference:** DESC-MRD-2026-CNC-088  
**Issuing Organisation:** DESC Digital Innovation Center, Mardan  
**Submission Deadline:** Sunday, 14th June 2026, 11:00 AM

---

## What This Is

This repository is the complete technical submission for the DESC RFP on Cloud-Native Application Orchestration & Deployment. It contains a **working, end-to-end deployable** three-tier web application running on AWS EKS, demonstrating:

- Containerised microservices with Docker multi-stage builds
- Kubernetes orchestration with Horizontal Pod Autoscaling (HPA)
- Infrastructure as Code with Terraform (VPC → EKS → RDS → ElastiCache → ArgoCD)
- GitOps continuous deployment via ArgoCD (no `kubectl apply` in pipelines)
- Load testing that visibly triggers auto-scaling in real-time
- Observability with Prometheus + Grafana using the USE methodology

The evaluation board can watch pods scale from 2 to 15 replicas live, with the Grafana dashboard showing CPU utilization climbing and HPA responding.

---

## Repository Structure

```
.
├── architecture/              # Mermaid architecture diagrams (5 views)
│   ├── 01-high-level-architecture.md
│   ├── 02-network-vpc-architecture.md
│   ├── 03-eks-cluster-architecture.md
│   ├── 04-cicd-gitops-pipeline.md
│   └── 05-monitoring-observability.md
│
├── terraform/                 # Infrastructure as Code — provisions all AWS resources
│   ├── main.tf                # Root module: wires VPC → SGs → EKS → RDS → Redis → ArgoCD
│   ├── providers.tf           # AWS, Helm, Kubernetes provider configs
│   ├── argocd.tf              # Deploys ArgoCD via Helm; registers GitOps Applications
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf             # S3 + DynamoDB remote state
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── vpc/               # 3-AZ VPC, subnets, NAT GWs, VPC Flow Logs
│       ├── security-groups/   # ALB / EKS nodes / RDS / Redis SGs
│       ├── eks/               # EKS cluster, managed node group, OIDC, add-ons
│       ├── rds/               # PostgreSQL 15 Multi-AZ, KMS encryption, Secrets Manager
│       └── elasticache/       # Redis 7 replication group, auth token, TLS
│
├── argocd/                    # GitOps declarations
│   ├── install/
│   │   └── argocd-values.yaml # ArgoCD Helm values (ALB ingress, notifications)
│   ├── projects/
│   │   └── desc-project.yaml  # AppProject: scopes repos, namespaces, RBAC
│   └── apps/
│       ├── desc-webapp.yaml           # Application: our 3-tier app
│       ├── kube-prometheus-stack.yaml # Application: monitoring stack
│       └── grafana-dashboards.yaml    # Application: USE dashboard ConfigMap
│
├── .github/
│   └── workflows/
│       ├── ci-gateway.yml             # PR check: lint + test + docker build
│       ├── ci-user-service.yml
│       ├── ci-records-service.yml
│       ├── ci-notification-service.yml
│       ├── ci-frontend.yml
│       └── release.yml                # Push to main: build all → DockerHub → update Helm tags
│
├── app/                       # Demo application source code
│   ├── gateway/               # FastAPI API Gateway (:8000)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── user-service/          # FastAPI User CRUD (:8001)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── records-service/       # FastAPI Records + Redis cache + /stress (:8002)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── notification-service/  # FastAPI Notifications + Redis pub/sub (:8003)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── frontend/              # Flask citizen portal + admin panel (:5000)
│   │   ├── app.py             # Session auth, role guards, proxy routes
│   │   ├── templates/
│   │   │   ├── base.html      # Shared navbar, flash messages
│   │   │   ├── landing.html   # Public home page (no tech content)
│   │   │   ├── login.html     # Email + password sign-in
│   │   │   ├── register.html  # New account (citizen / officer)
│   │   │   ├── portal.html    # Citizen dashboard (records, notifications, profile)
│   │   │   └── admin.html     # Admin panel (users, health, stress, system)
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── docker-compose.yml     # Local dev: all 9 services in one command
│   └── monitoring/
│       ├── prometheus.yml     # Scrape config for all 5 app services
│       └── grafana/
│           ├── provisioning/  # Auto-provisioned datasource + dashboard
│           └── dashboards/
│               └── desc-microservices.json  # Pre-built dashboard (20 panels)
│
├── helm/
│   └── desc-webapp/           # Helm chart for EKS deployment
│       ├── Chart.yaml
│       ├── values.yaml        # Demo defaults
│       ├── values-production.yaml
│       └── templates/
│           ├── backend-deployment.yaml
│           ├── backend-service.yaml
│           ├── frontend-deployment.yaml
│           ├── frontend-service.yaml
│           ├── hpa-backend.yaml    # HPA: scale at 50% CPU, max 15 replicas
│           ├── hpa-frontend.yaml   # HPA: scale at 60% CPU, max 10 replicas
│           ├── ingress.yaml        # AWS ALB Ingress
│           ├── servicemonitor.yaml           # Prometheus ServiceMonitor (all 5 svcs)
│           └── grafana-dashboard-configmap.yaml  # Auto-imported Grafana dashboard
│
├── load-testing/
│   ├── k6/
│   │   ├── load-test.js       # Full ramp: 0 → 200 VUs (triggers HPA)
│   │   └── stress-test.js     # Demo spike: 0 → 300 VUs in 30s
│   ├── locust/
│   │   └── locustfile.py      # Alternative with web UI
│   └── README.md
│
└── monitoring/
    ├── prometheus/
    │   ├── kube-prometheus-stack-values.yaml  # Full stack Helm values
    │   └── custom-rules/
    │       └── alert-rules.yaml               # PrometheusRule CRD (5 alerts)
    ├── grafana/
    │   └── dashboards/
    │       └── use-metrics-dashboard.json     # Import-ready USE dashboard
    └── exporters/
        └── app-exporter/                      # Standalone custom exporter
            ├── exporter.py
            └── Dockerfile
```

---

## Key Architecture Decisions

### 1. Monolith Decomposed into Domain-Aligned Microservices

The RFP explicitly requires containerising monolithic components into isolated microservices. The backend is split into **four independently deployable services** behind an API Gateway:

```
Browser
  └─► Frontend (Flask :5000)         ← Citizen portal + Admin panel (session auth)
        └─► API Gateway (FastAPI :8000)   ← single ALB target, /api/* routing
                ├─► User Service (:8001)      → PostgreSQL (users table)
                ├─► Records Service (:8002)   → PostgreSQL (records) + Redis cache + /stress HPA trigger
                └─► Notification Svc (:8003)  → PostgreSQL (notifications) + Redis pub/sub
```

The **Frontend** serves two distinct experiences based on the authenticated user's role:
- **Citizens** — landing page, login/register, citizen portal (submit records, read notifications, view profile)
- **Admins / Officers** — full admin panel (user management, service health, notification publishing, stress trigger, architecture info)

Each backend service has its own **Deployment, HPA, Service, and Prometheus ServiceMonitor**. They communicate only through internal Kubernetes DNS (ClusterIP) — none are exposed directly to the internet. The API Gateway is the sole external-facing backend entry point.

> **Why not more services?** Four domain services is the sweet spot for a demo — granular enough to show microservices patterns (independent scaling, separate data ownership, event-driven pub/sub) without the overhead of a service mesh or distributed tracing setup that would distract from the core demonstration.

### 2. Terraform Deploys ArgoCD, Then ArgoCD Deploys Everything Else

The bootstrap sequence is intentional:

```
terraform apply
   └── VPC / SGs / EKS / RDS / Redis     (AWS resources)
   └── helm_release.argocd               (ArgoCD on EKS, via Helm provider)
   └── kubernetes_manifest (AppProject)  (ArgoCD scope/RBAC)
   └── kubernetes_manifest (Applications) (tells ArgoCD what to sync)
         └── ArgoCD syncs desc-webapp Helm chart → running pods
         └── ArgoCD syncs kube-prometheus-stack → Prometheus + Grafana
```

**Why not deploy the app directly from Terraform?** Terraform is optimised for managing long-lived infrastructure state, not for managing the lifecycle of rapidly-changing application deployments. If we used `helm_release` for our app, every `terraform apply` would diff the entire Helm release — slow, stateful, and fragile. ArgoCD watches Git continuously and syncs within seconds of a push, with automatic drift correction if someone manually edits a pod.

### 3. HPA Configured with Separate Scale-Up and Scale-Down Policies

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 30   # start scaling within 30s of high CPU
    policies:
      - type: Pods
        value: 4
        periodSeconds: 30            # add up to 4 pods every 30s
  scaleDown:
    stabilizationWindowSeconds: 300  # wait 5 minutes before scaling down
```

The asymmetric windows are deliberate: scale up fast (protect the user experience), scale down slowly (avoid thrashing under bursty traffic). The 5-minute scale-down window also means the evaluation board can clearly see pods remain at the scaled count during the demo cool-down.

### 4. RDS and ElastiCache in Isolated Subnets, Not Private Subnets

Most tutorials put databases in private subnets alongside the application nodes. We place them in a separate **isolated** subnet tier with its own route table that has **no internet route at all**. The only traffic allowed is from the EKS node security group on the exact port. This satisfies defence-in-depth: even if a worker node is compromised, the attacker cannot reach the database directly from the internet.

### 5. USE Methodology for the Grafana Dashboard

Brendan Gregg's USE (Utilization, Saturation, Errors) methodology gives a structured way to identify performance bottlenecks without wading through hundreds of arbitrary metrics. Our dashboard has three rows — one per dimension — making it immediately obvious during the demo where the system is under pressure.

| Row | What you see |
|-----|-------------|
| Utilization | CPU %, Memory %, Network I/O — are resources being used? |
| Saturation | CPU throttle %, pending pods, HPA replicas, P95 latency — is there queued work? |
| Errors | HTTP 5xx rate, pod restarts, DB errors — is anything failing? |

### 6. Multi-Stage Docker Builds with Non-Root Users

Both Dockerfiles use a two-stage build: a `builder` stage installs Python dependencies into `~/.local`, and the final stage copies only the installed packages and source — no build tools, no pip cache, no temporary files. The container runs as a dedicated non-root `appuser`, satisfying the Kubernetes `restricted` Pod Security Standard enforced on the `desc-app` namespace.

### 7. Passwords Never Hardcoded — Terraform Generates and Vaults Them

The RDS password and Redis auth token are generated by `random_password` resources in Terraform and immediately stored in AWS Secrets Manager. The Kubernetes `Secret` objects in the Helm chart reference the Secrets Manager entries via ExternalSecrets Operator (or are seeded by a one-time `kubectl create secret` from the Terraform outputs). No credentials ever appear in Git or container images.

---

## Prerequisites

### Local Development

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24+ | Build and run containers |
| Docker Compose | v2.x | Orchestrate local stack |
| Python | 3.12 | (Optional) run without Docker |

### EKS Production

| Tool | Version | Purpose |
|------|---------|---------|
| Terraform | ≥ 1.6 | Provision AWS infrastructure |
| AWS CLI | v2 | Authenticate with AWS |
| kubectl | 1.29 | Interact with EKS |
| Helm | v3.14+ | Lint charts locally |
| k6 | latest | Run load tests |
| ArgoCD CLI | v2.10+ | (Optional) manage apps from terminal |

### AWS Permissions Required

The IAM user/role running `terraform apply` needs:

- `AmazonEKSClusterPolicy`, `AmazonEKSWorkerNodePolicy`
- `AmazonVPCFullAccess`
- `AmazonRDSFullAccess`
- `AmazonElastiCacheFullAccess`
- `SecretsManagerReadWrite`
- `IAMFullAccess` (for creating IRSA roles)
- `AmazonEC2FullAccess`
- S3 and DynamoDB access for the Terraform state bucket/table

---

## Option A — Local Development with Docker Compose

This runs the full stack locally — 5 microservices, PostgreSQL, Redis, Prometheus, and Grafana — with no AWS account needed. Ideal for developers iterating on the application code and demonstrating live metrics.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/desc-cloudnative-demo
cd desc-cloudnative-demo

# 2. Build and start all 9 services (first run takes ~3 min to build images)
cd app/
docker compose up --build

# 3. Open the citizen portal
# http://localhost:3500   ← landing page (no pod names, no architecture, no tech jargon)
#
# Login with ahmed.khan@desc.gov.pk / desc2026
#   → role=admin  → redirected to Admin Panel
#
# Login with tariq@desc.gov.pk / desc2026
#   → role=citizen → redirected to Citizen Portal
#
# Citizen visiting /admin → flash "Access restricted to administrators." → back to /portal

# 4. Observability
# http://localhost:9095           ← Prometheus (Status → Targets: 5 targets UP)
# http://localhost:3100           ← Grafana  (admin / desc2026)
#   → Dashboards → DESC → DESC — Microservices Platform

# 5. Test microservices directly via the gateway API
curl http://localhost:8000/api/users
curl http://localhost:8000/api/records
curl http://localhost:8000/api/notifications
curl http://localhost:8000/api/health      # aggregated health of all services

# 6. Trigger CPU stress (also available in Admin Panel → System)
curl "http://localhost:8000/api/stress?n=10000"

# 7. Tear down
docker compose down -v
```

**What runs where:**

| Container | Port | Role |
|-----------|------|------|
| `frontend` | 3500→5000 | Citizen portal + Admin panel (Flask, session auth) |
| `gateway` | 8000 | API Gateway — routes `/api/*` to domain services |
| `user-svc` | 8001 | User Service (PostgreSQL only) |
| `records-svc` | 8002 | Records Service (PostgreSQL + Redis cache) |
| `notification-svc` | 8003 | Notification Service (PostgreSQL + Redis pub/sub) |
| `postgres:15-alpine` | internal | Shared PostgreSQL (3 separate tables) |
| `redis:7-alpine` | internal | Redis (cache + pub/sub) |
| `prometheus:v2.51.2` | 9095→9090 | Scrapes all 5 app services every 15 s |
| `grafana:10.4.2` | 3100→3000 | Pre-provisioned DESC dashboard (20 panels) |

**Frontend pages:**

| URL | Access | Content |
|-----|--------|---------|
| `/` | Public | Hero landing page — no technical content |
| `/login` | Public | Email + password sign-in; demo hint shown |
| `/register` | Public | Name, email, password, role (citizen / officer) |
| `/portal` | Citizen+ | My Records (submit/view), Notifications (read-only), My Profile |
| `/admin` | Admin / Officer | Dashboard (health cards, stats), Users, Records, Notifications (publish), System (stress, k6, architecture) |

**Default demo accounts (all use password `desc2026`):**

| Email | Role | Redirects to | Notes |
|-------|------|-------------|-------|
| `ahmed.khan@desc.gov.pk` | admin | `/admin` → Admin Panel | Full access: users, health, stress trigger |
| `fatima.bibi@desc.gov.pk` | officer | `/admin` → Admin Panel | Same access as admin |
| `imran.gul@desc.gov.pk` | officer | `/admin` → Admin Panel | Same access as admin |
| `tariq@desc.gov.pk` | citizen | `/portal` → Citizen Portal | Records, notifications, profile only |
| `zainab@desc.gov.pk` | citizen | `/portal` → Citizen Portal | Records, notifications, profile only |

> Visiting `/admin` as a citizen redirects to `/portal` with a flash message: **"Access restricted to administrators."**
>
> To create a new account, use the **Register** page (`/register`). Officers get admin panel access; citizens get the citizen portal.

**Grafana dashboard panels:**
- **Overview row** — gateway req/s, 5xx error %, upstream p95 latency, cache hit ratio (4 stat cards)
- **Gateway** — request rate by status code, upstream p50/p95/p99 latency by service
- **Business Metrics** — creation rates (users/records/notifications), notifications by type
- **Database & Cache** — DB query p95 by service+operation, cache hits vs misses
- **Redis & Frontend** — Redis publish p50/p95 latency, frontend request rate by path

---

## Option B — Production Deployment on EKS

This is the full end-to-end deployment sequence. Follow these steps in order.

### Step 1 — Bootstrap Terraform Remote State

Before the first `terraform apply`, create the S3 bucket and DynamoDB table for state locking. Run this **once**:

```bash
aws s3 mb s3://desc-terraform-state-$(aws sts get-caller-identity --query Account --output text) \
  --region ap-south-1

aws dynamodb create-table \
  --table-name desc-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

Update `terraform/backend.tf` to replace `ACCOUNT_ID` with your actual AWS account ID.

### Step 2 — Configure Variables

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set git_repo_url to your fork
```

### Step 3 — Provision All Infrastructure

```bash
terraform init
terraform plan   # review: ~60 resources will be created
terraform apply  # takes 15–25 minutes (EKS is the slowest)
```

Terraform creates in dependency order:
1. VPC, subnets, NAT Gateways, security groups
2. EKS cluster, managed node group, OIDC provider, add-ons
3. RDS PostgreSQL (Multi-AZ) + passwords in Secrets Manager
4. ElastiCache Redis replication group
5. ArgoCD via Helm on EKS
6. ArgoCD AppProject (`desc`)
7. ArgoCD Applications (`desc-webapp`, `kube-prometheus-stack`)

### Step 4 — Configure kubectl

```bash
# Get the command from Terraform outputs
terraform output kubeconfig_command
# e.g.:
aws eks update-kubeconfig --name desc-cloudnative-demo-eks --region ap-south-1

# Verify nodes are Ready
kubectl get nodes
```

### Step 5 — Create the Application Secret

Terraform stores credentials in Secrets Manager. Seed the Kubernetes Secret the app needs:

```bash
# Get values from Terraform outputs
DB_URL=$(terraform output -raw rds_endpoint)
REDIS_URL=$(terraform output -raw elasticache_primary_endpoint)

kubectl create secret generic desc-webapp-secrets \
  --namespace desc-app \
  --from-literal=DATABASE_URL="postgresql://descadmin:$(aws secretsmanager get-secret-value \
    --secret-id /desc/rds/master-password \
    --query SecretString --output text | jq -r .password)@${DB_URL}/descapp" \
  --from-literal=REDIS_URL="redis://:$(aws secretsmanager get-secret-value \
    --secret-id /desc/redis/auth-token \
    --query SecretString --output text | jq -r .auth_token)@${REDIS_URL}:6379"
```

> In production, use the [ExternalSecrets Operator](https://external-secrets.io/) to automate this sync from Secrets Manager.

### Step 6 — Configure GitHub Actions Secrets and Push Images

The release workflow (`release.yml`) handles all image building automatically on every push to `main`. Add the following secrets to your GitHub repository (**Settings → Secrets and variables → Actions**):

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Your DockerHub account username |
| `DOCKERHUB_TOKEN` | DockerHub personal access token (read/write scope) |

`GITHUB_TOKEN` is provided automatically — no setup needed.

Once the secrets are set, pushing to `main` triggers the release workflow which:
1. Builds all 5 images in parallel using a matrix strategy
2. Pushes to DockerHub: `<username>/desc-<service>:sha-<7char>` and `:latest`
3. Updates `helm/desc-webapp/values.yaml` with the new image tags via `yq`
4. Commits the updated values with `[skip ci]` so CI does not loop
5. ArgoCD detects the Git change within 3 minutes and rolls out new pods

**First-time manual push** (before GitHub Actions is configured):

```bash
# Build and push all 5 services manually
DOCKERHUB_USERNAME=your-username
SHORT_SHA=$(git rev-parse --short HEAD)

for svc in gateway user-service records-service notification-service frontend; do
  docker build -t ${DOCKERHUB_USERNAME}/desc-${svc}:sha-${SHORT_SHA} \
               -t ${DOCKERHUB_USERNAME}/desc-${svc}:latest \
               app/${svc}/
  docker push ${DOCKERHUB_USERNAME}/desc-${svc}:sha-${SHORT_SHA}
  docker push ${DOCKERHUB_USERNAME}/desc-${svc}:latest
done

# Update values.yaml and commit
sed -i "s/imageRegistry: .*/imageRegistry: \"${DOCKERHUB_USERNAME}\"/" helm/desc-webapp/values.yaml
git add helm/desc-webapp/values.yaml
git commit -m "chore: set initial image registry [skip ci]"
git push
# ArgoCD detects the change within 3 minutes and auto-syncs
```

### Step 7 — Verify ArgoCD Sync

```bash
# Get ArgoCD admin password
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d

# Port-forward ArgoCD UI
kubectl port-forward svc/argocd-server 8080:443 -n argocd
# Open https://localhost:8080  (user: admin, pass: from above)

# Or use ArgoCD CLI
argocd login localhost:8080 --insecure --username admin
argocd app list
argocd app get desc-webapp
```

ArgoCD should show both applications as **Healthy / Synced**.

### Step 8 — Verify Application

```bash
# Get ALB DNS name
kubectl get ingress -n desc-app -o jsonpath='{.items[0].status.loadBalancer.ingress[0].hostname}'

# Open in browser: http://<alb-dns>
# You should see the DESC Cloud-Native Demo dashboard with items list
```

### Step 9 — Verify Monitoring

The Helm chart ships a `GrafanaDashboard` ConfigMap labeled `grafana_dashboard: "1"` in the `desc-app` namespace. The Grafana sidecar (deployed by `kube-prometheus-stack`) watches for this label and auto-imports the dashboard — no manual steps needed.

```bash
# Verify kube-prometheus-stack is healthy
kubectl get pods -n monitoring

# Verify ServiceMonitors were created (one per service)
kubectl get servicemonitor -n monitoring

# Verify Prometheus is scraping the desc-app targets
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
# Open http://localhost:9090/targets → look for 5 desc-app targets (all UP)

# Access Grafana
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
# Open http://localhost:3000  (admin / DescAdmin@2026!)
# Dashboard auto-appears under: Dashboards → DESC → DESC — Microservices Platform
```

**If the dashboard is missing** (sidecar not enabled in your kube-prometheus-stack install):
```bash
# Manual import — works regardless of sidecar config
kubectl get configmap -n desc-app | grep grafana-dashboard
kubectl get configmap desc-webapp-grafana-dashboard -n desc-app -o jsonpath='{.data.desc-microservices\.json}' > /tmp/desc-dashboard.json
# Grafana UI → Dashboards → Import → Upload /tmp/desc-dashboard.json
```

---

## Running the Live Demo (Evaluation Board)

This is the sequence to demonstrate the full system — citizen portal, auto-scaling, and live metrics — in front of the evaluation board.

### Window 1 — Citizen Portal (projector browser)
```
http://<ALB-DNS>/                          # landing page
http://<ALB-DNS>/login                     # sign in as ahmed.khan@desc.gov.pk / desc2026
                                           # → Admin Panel opens (service health, user table)
http://<ALB-DNS>/login                     # sign in as tariq@desc.gov.pk / desc2026
                                           # → Citizen Portal (submit a record, view notifications)
```

### Window 2 — HPA watch (terminal)
```bash
watch -n2 "kubectl get hpa,pods -n desc-app --no-headers | column -t"
```

### Window 3 — Trigger the spike load (terminal)
```bash
export BASE_URL=http://$(kubectl get ingress -n desc-app \
  -o jsonpath='{.items[0].status.loadBalancer.ingress[0].hostname}')

# Quick spike: 0 → 300 VUs in 30 s
k6 run --env BASE_URL=$BASE_URL load-testing/k6/stress-test.js

# Or trigger from the Admin Panel UI:
# Admin → System → "Trigger CPU Stress" / "Burst (×10)"
```

### Window 4 — Grafana (projector second tab)
```
http://localhost:3000  (admin / DescAdmin@2026!)
Dashboards → DESC → DESC — Microservices Platform
Set time range: Last 30 minutes, auto-refresh: 10 s
```

**Expected timeline:**

| Time | What happens |
|------|-------------|
| T+0s | k6 ramps to 300 virtual users hitting `/api/stress` via gateway |
| T+15s | Records Service CPU climbs past 50% threshold |
| T+30s | HPA fires — records-svc replicas: 2 → 6 |
| T+60s | HPA continues — records-svc replicas: 6 → 15 |
| T+90s | If nodes are insufficient, Cluster Autoscaler adds EC2 nodes |
| T+5m | k6 ramps down — CPU drops below threshold |
| T+10m | HPA scale-down stabilisation window expires — replicas: 15 → 2 |

**What to point out on the Grafana dashboard:**
- Gateway Request Rate climbing → 5xx % stays at 0 (resilient)
- Upstream p95 latency rising under load, then recovering
- Cache hit ratio (Records Service) — subsequent calls served from Redis
- DB query p95 by service — shows isolation (user-svc unaffected by records-svc load)

---

## CI/CD Pipeline

### Continuous Integration (per service, on PR and push)

Each service has its own CI workflow triggered only when that service's code changes — no unnecessary rebuilds. Each workflow runs two jobs:

```
lint-and-test
  ├── ruff check (linting)
  └── pytest tests/ (unit tests with mocked DB/Redis)

docker-build (needs: lint-and-test)
  └── docker/build-push-action (push: false) — validates the Dockerfile compiles
```

CI workflows: [ci-gateway.yml](.github/workflows/ci-gateway.yml) · [ci-user-service.yml](.github/workflows/ci-user-service.yml) · [ci-records-service.yml](.github/workflows/ci-records-service.yml) · [ci-notification-service.yml](.github/workflows/ci-notification-service.yml) · [ci-frontend.yml](.github/workflows/ci-frontend.yml)

### Continuous Delivery (on push to `main`)

```
Developer pushes to main
    │
    ▼
release.yml — matrix build (5 services in parallel)
    ├── docker/build-push-action → DockerHub
    │   ├── desc-gateway:sha-a1b2c3d
    │   ├── desc-user-service:sha-a1b2c3d
    │   ├── desc-records-service:sha-a1b2c3d
    │   ├── desc-notification-service:sha-a1b2c3d
    │   └── desc-frontend:sha-a1b2c3d
    └── update-helm-values job
        ├── yq: set .gateway.image.tag = "sha-a1b2c3d"
        ├── yq: set .userService.image.tag = "sha-a1b2c3d"
        ├── yq: ... (all 5 services)
        └── git commit "chore(release): bump image tags [skip ci]"
                │
                ▼
        ArgoCD detects Git change (polls every 3 min)
                │
                ▼
        helm upgrade — rolling update (maxUnavailable=0, maxSurge=1)
                │
                ▼
        Slack notification: ✅ desc-webapp synced (sha-a1b2c3d)
```

**Zero downtime:** `maxUnavailable: 0` ensures the old pod stays live until the new pod passes its readiness probe (`GET /ready` checks DB + Redis connectivity).

**Rollback:** Revert the `[skip ci]` commit and push. ArgoCD detects the old tag in `values.yaml` and rolls back within 3 minutes.

```bash
git revert HEAD
git push
# ArgoCD auto-syncs the previous sha tag → pods roll back
```

---

## Troubleshooting

### Pods stuck in Pending

```bash
kubectl describe pod <pod-name> -n desc-app
# Look for: "Insufficient cpu" or "Insufficient memory"
# Solution: Check Cluster Autoscaler logs
kubectl logs -n kube-system -l app.kubernetes.io/name=cluster-autoscaler
```

### ArgoCD Application out of sync

```bash
argocd app sync desc-webapp
# Or force a hard refresh:
argocd app get desc-webapp --hard-refresh
```

### Backend readiness probe failing

```bash
kubectl logs -n desc-app -l app.kubernetes.io/name=desc-webapp-backend
# Common cause: DATABASE_URL or REDIS_URL secret not created (Step 5)
kubectl get secret desc-webapp-secrets -n desc-app
```

### Grafana no data

```bash
# Verify ServiceMonitor is picked up
kubectl get servicemonitor -n monitoring
# Verify Prometheus targets
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
# Open http://localhost:9090/targets — look for desc-app targets
```

---

## Cost Estimate (Demo Environment)

| Resource | Spec | Est. Monthly Cost (USD) |
|----------|------|------------------------|
| EKS Control Plane | Managed | $73 |
| EC2 Worker Nodes | 3× t3.medium | $96 |
| RDS PostgreSQL | db.t3.medium Multi-AZ | $98 |
| ElastiCache Redis | cache.t3.micro × 2 | $25 |
| NAT Gateways | 3× (HA) | $99 |
| ALB | Per LCU | ~$20 |
| ECR Storage | <1 GB | <$1 |
| **Total** | | **~$412/month** |

> For a pre-demo environment, disable Multi-AZ on RDS (`rds_multi_az = false`) and reduce NAT GWs to 1 — reduces cost to ~$240/month. Never do this in production.

---

## Security Checklist

- [x] No hardcoded credentials — all secrets in AWS Secrets Manager
- [x] Private EKS API endpoint — not reachable from internet
- [x] Worker nodes in private subnets — only reachable via ALB
- [x] RDS/Redis in isolated subnets — no internet route
- [x] Security groups follow least-privilege (port-specific, SG-referenced)
- [x] KMS encryption at rest for EKS secrets, RDS, ElastiCache
- [x] TLS in transit for Redis (auth token + `transit_encryption_enabled`)
- [x] Container images run as non-root user (`runAsNonRoot: true`)
- [x] `readOnlyRootFilesystem: true` on backend container
- [x] Pod Security Standards: `baseline` enforced on `desc-app` namespace
- [x] ECR scan-on-push with CRITICAL CVE gate in CI
- [x] VPC Flow Logs enabled for audit

---

## Contacts & Submission

**Technical Proposal (Envelope A):** This repository  
**Financial Proposal (Envelope B):** Separate sealed document  
**Submission Deadline:** Sunday, 14th June 2026, 11:00 AM Sharp

Late submissions are automatically disqualified per Section 5 of the RFP.
