# High-Level Cloud Architecture

**Project:** DESC Digital Innovation Center — Cloud-Native Citizen Portal
**Reference:** DESC-MRD-2026-CNC-088

## Overview

A cloud-native, microservices-based citizen portal running on AWS EKS. The monolith has been decomposed into four independent backend services behind an API Gateway, each with its own horizontal autoscaler, Prometheus metrics endpoint, and independent database schema.

```mermaid
flowchart TD
    subgraph Internet["Internet"]
        User([Citizens])
        Dev([Developers])
    end

    subgraph AWS["AWS Cloud — ap-south-1"]
        subgraph Edge["Edge Layer"]
            R53[Route 53]
            WAF[AWS WAF]
            ALB[Application Load Balancer\nHTTPS :443]
        end

        subgraph EKS["EKS Cluster — Private Subnets"]
            subgraph NS_APP["Namespace: desc-app"]
                FE[Frontend\nFlask :5000\nHPA: 2–10]
                GW[API Gateway\nFastAPI :8000\nHPA: 2–10]
                US[User Service\nFastAPI :8001\nHPA: 2–10]
                RS[Records Service\nFastAPI :8002\nHPA: 2–15\n★ HPA demo target]
                NS[Notification Service\nFastAPI :8003\nHPA: 2–10]
            end

            subgraph NS_MON["Namespace: monitoring"]
                PROM[Prometheus]
                GRAF[Grafana USE Dashboard]
                ALERT[Alertmanager]
            end

            subgraph NS_CD["Namespace: argocd"]
                ARGO[ArgoCD\nGitOps Sync]
            end
        end

        subgraph Data["Data Layer — Isolated Subnets"]
            RDS[(RDS PostgreSQL 15\nMulti-AZ · Encrypted\nusers · records · notifications tables)]
            REDIS[(ElastiCache Redis 7\nPrimary + Replica\ncache · pub/sub)]
        end

        ECR[Amazon ECR\n4 image repositories]
        S3[S3 + DynamoDB\nTerraform State]
    end

    subgraph CICD["CI/CD"]
        GH[GitHub]
        GHA[GitHub Actions]
    end

    User -->|HTTPS| R53 --> WAF --> ALB
    ALB -->|"/*"| FE
    ALB -->|"/api/*"| GW
    FE -->|REST| GW
    GW -->|"/api/users"| US
    GW -->|"/api/records\n/api/stress"| RS
    GW -->|"/api/notifications"| NS
    US -->|SQL users table| RDS
    RS -->|SQL records table| RDS
    RS -->|cache-aside| REDIS
    NS -->|SQL notifications table| RDS
    NS -->|pub/sub publish| REDIS

    US & RS & NS & GW & FE -->|scrape :port/metrics| PROM
    PROM --> GRAF
    PROM --> ALERT

    Dev --> GH --> GHA -->|push images| ECR
    GHA -->|update Helm values| GH
    ARGO -->|sync Helm chart| EKS
    GH -->|watched by| ARGO
    ECR -->|pull| EKS
```

## Microservices Decomposition

| Service | Port | Responsibility | Data Store |
|---------|------|---------------|------------|
| Frontend | 5000 | HTML UI, proxies to Gateway | — |
| API Gateway | 8000 | Single entry point, routing, fan-out health | — |
| User Service | 8001 | Citizen user profiles (CRUD) | PostgreSQL `users` |
| Records Service | 8002 | Citizen records/applications, Redis cache, `/stress` HPA trigger | PostgreSQL `records` + Redis |
| Notification Service | 8003 | System announcements, Redis pub/sub publish | PostgreSQL `notifications` + Redis |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| API Gateway pattern | Single ALB target; microservices are internal-only (ClusterIP) — no service exposed directly to internet |
| Service isolation | User Service has no Redis dependency — demonstrates that each service only takes on the dependencies it needs |
| Records Service as HPA target | Stress endpoint (`/stress`) is CPU-bound (prime calculation) — makes auto-scaling visually demonstrable |
| Redis pub/sub in Notification Service | Demonstrates event-driven pattern — downstream consumers (e.g., WebSocket service) can subscribe to `desc:notifications` channel |
| Separate PostgreSQL schemas | All services share one RDS instance (cost-efficient demo) but each owns a distinct table — simulates separate database-per-service without extra RDS cost |
