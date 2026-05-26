# EKS Cluster Architecture

## Cluster Overview

| Property | Value |
|----------|-------|
| EKS Version | 1.29 |
| Node Type | `t3.medium` (2 vCPU, 4 GiB RAM) |
| Min Nodes | 2 |
| Max Nodes | 10 |
| Desired Nodes | 3 |
| Endpoint | Private only |
| CNI | AWS VPC CNI |
| Container Runtime | containerd |

## Cluster Architecture

```mermaid
flowchart TD
    subgraph CP["EKS Control Plane (AWS Managed)"]
        KAPI[Kubernetes API Server]
        ETCD[etcd]
        SCHED[Scheduler]
        CM[Controller Manager]
    end

    subgraph NG["Managed Node Group — 3 AZs"]
        subgraph N1["Node 1 (AZ-a) t3.medium"]
            FE1[frontend-pod-1]
            BE1[backend-pod-1]
            PROM1[prometheus-agent]
        end
        subgraph N2["Node 2 (AZ-b) t3.medium"]
            FE2[frontend-pod-2]
            BE2[backend-pod-2]
            GRAF1[grafana-pod]
        end
        subgraph N3["Node 3 (AZ-c) t3.medium"]
            BE3[backend-pod-3\n auto-scaled]
            ARGO1[argocd-server]
        end
    end

    subgraph ADDONS["Cluster Add-ons"]
        COREDNS[CoreDNS\nService Discovery]
        KUBEPROXY[kube-proxy\nIPTables rules]
        VPCCNI[aws-vpc-cni\nPod networking]
        EBSCSI[aws-ebs-csi-driver\nPersistentVolumes]
    end

    subgraph CONTROLLERS["Controllers — kube-system"]
        CA[Cluster Autoscaler\nASG management]
        ALBCTRL[AWS LB Controller\nALB provisioning]
        METRICSSVR[Metrics Server\nHPA data source]
    end

    subgraph HPA["Horizontal Pod Autoscalers"]
        HPA_FE[HPA: frontend\nmin:2 max:10\nCPU target: 60%]
        HPA_BE[HPA: backend\nmin:2 max:15\nCPU target: 50%]
    end

    KAPI <--> NG
    HPA_FE -->|scale| FE1 & FE2
    HPA_BE -->|scale| BE1 & BE2 & BE3
    METRICSSVR -->|cpu/mem metrics| HPA_FE & HPA_BE
    CA -->|add/remove nodes| NG
    ALBCTRL -->|manage| ALB[Application Load Balancer]
    ALB -->|route /api/*| BE1 & BE2 & BE3
    ALB -->|route /*| FE1 & FE2
```

## Namespace Layout

```
kube-system         → CoreDNS, kube-proxy, aws-vpc-cni, Cluster Autoscaler, ALB Controller, Metrics Server
desc-app            → frontend pods, backend pods, configmaps, secrets, HPAs, ServiceAccount
monitoring          → Prometheus, Grafana, Alertmanager, node-exporter, kube-state-metrics
argocd              → ArgoCD server, repo-server, application-controller, redis, dex
```

## Pod Autoscaling Flow

```mermaid
sequenceDiagram
    participant LT as Load Test (k6)
    participant ALB as ALB
    participant BE as Backend Pods (x2)
    participant MS as Metrics Server
    participant HPA as HPA Controller
    participant CA as Cluster Autoscaler
    participant ASG as EC2 Auto Scaling Group

    LT->>ALB: 200 VUs → /api/stress
    ALB->>BE: distribute requests
    BE->>BE: CPU spikes above 50%
    MS->>HPA: report CPU utilization
    HPA->>BE: scale replicas 2 → 6 → 15
    Note over CA: Pending pods due to insufficient nodes
    CA->>ASG: increase desired capacity 3 → 7
    ASG->>BE: new nodes join, pods scheduled
    Note over HPA,BE: Load drops → scale down after cool-down (5 min)
```

## Resource Quotas (Namespace: desc-app)

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: desc-app-quota
  namespace: desc-app
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "50"
```

## Security Hardening

- **Pod Security Standards**: `restricted` profile on `desc-app` namespace
- **Network Policies**: backend pods only accept traffic from frontend pods; DB pods have no ingress from internet
- **IRSA**: backend pod SA bound to IAM role with `s3:GetObject` (config), `secretsmanager:GetSecretValue` (DB password)
- **Image scanning**: ECR scan-on-push enabled; critical CVEs block deployment via GitHub Actions gate
- **Secrets**: DB credentials stored in AWS Secrets Manager; ExternalSecrets Operator syncs to K8s Secrets
