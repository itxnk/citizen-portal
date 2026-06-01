# FINANCIAL PROPOSAL — ENVELOPE B

---

**Tender Reference:** DESC-MRD-2026-CNC-088  
**Issuing Organisation:** DESC Digital Innovation Center, Mardan  
**Submission:** Cloud-Native Application Orchestration & Deployment  
**Submitted by:** [Your Company Name]  
**Date:** 25th May 2026  
**Document Classification:** Financial — Confidential  
**Currency:** USD (AWS ap-south-1 pricing) · PKR equivalent at 280 PKR/USD

---

## Table of Contents

1. [Cost Summary](#1-cost-summary)
2. [One-Time Setup & Implementation Fees](#2-one-time-setup--implementation-fees)
3. [AWS Cloud Infrastructure Costs](#3-aws-cloud-infrastructure-costs)
4. [1-Year Managed Service Retainer](#4-1-year-managed-service-retainer)
5. [Total Cost of Ownership — Year 1](#5-total-cost-of-ownership--year-1)
6. [Cost Optimization Options](#6-cost-optimization-options)
7. [Payment Schedule](#7-payment-schedule)
8. [Assumptions & Exclusions](#8-assumptions--exclusions)

---

## 1. Cost Summary

| Category | USD | PKR (est.) |
|----------|-----|-----------|
| One-time setup & implementation | $19,000 | PKR 5,320,000 |
| AWS cloud infrastructure (Year 1) | $5,712 | PKR 1,599,360 |
| 1-year managed service retainer | $7,200 | PKR 2,016,000 |
| **Total Year 1 Investment** | **$31,912** | **PKR 8,935,360** |
| Year 2+ annual (infrastructure + managed service only) | **$12,912** | **PKR 3,615,360** |

> PKR equivalent is indicative at 280 PKR/USD exchange rate and will be adjusted to the SBP rate on invoice date.

---

## 2. One-Time Setup & Implementation Fees

These are professional services fees for designing, building, and deploying the complete cloud-native platform. Charged once, invoiced across the delivery milestones.

### 2.1 Architecture & Infrastructure

| Deliverable | Description | Fee (USD) |
|-------------|-------------|-----------|
| Cloud Architecture Design | VPC network design (3-tier, 3-AZ), security group rules, subnet isolation strategy, architecture documentation (5 Mermaid diagrams) | $2,500 |
| Terraform IaC Development | All 5 modules: VPC, Security Groups, EKS, RDS, ElastiCache; remote state backend; variable/output structure | $3,500 |
| EKS Cluster Setup | Cluster config, managed node group, OIDC provider, 4 managed add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI) | $1,500 |
| RDS & ElastiCache Provisioning | Multi-AZ PostgreSQL, Redis replication group, Secrets Manager integration, KMS encryption | $1,000 |

**Infrastructure Subtotal: $8,500**

### 2.2 Application Containerization & Microservices

| Deliverable | Description | Fee (USD) |
|-------------|-------------|-----------|
| Microservices Decomposition | Decompose monolith into 4 domain services (Gateway, User, Records, Notification) + Frontend — each with FastAPI/Flask, asyncpg, Redis client, Prometheus metrics | $3,000 |
| Citizen Portal & Admin Panel | Flask frontend with session-based auth: public landing, login, register; citizen portal (records, notifications, profile); role-gated admin panel (user management, health dashboard, notification publishing, stress trigger, architecture view) | $1,000 |
| Docker Multi-Stage Builds | 5 Dockerfiles (multi-stage, non-root, read-only filesystem), Docker Compose for local dev (9-service stack incl. Prometheus + Grafana) | $500 |
| Helm Chart Development | Helm chart with 21 templates: 5 Deployments, 5 Services, 5 HPAs, ConfigMap, Ingress, ServiceMonitor (range loop), ServiceAccount | $1,500 |
| ArgoCD GitOps Setup | AppProject, ArgoCD Applications (desc-webapp, kube-prometheus-stack), self-heal + prune config, ignoreDifferences for HPA drift; Helm `grafanaDashboard.enabled: true` auto-provisions dashboard via sidecar ConfigMap | $1,000 |

**Application Subtotal: $7,000**

### 2.3 CI/CD Pipeline & Testing

| Deliverable | Description | Fee (USD) |
|-------------|-------------|-----------|
| GitHub Actions CI Workflows | 5 per-service CI workflows (ruff lint + pytest + docker build); path-filtered triggers | $500 |
| GitHub Actions Release Workflow | Matrix build → DockerHub push (sha tag + latest) → yq values.yaml update → git commit → ArgoCD auto-sync | $500 |
| Unit Test Suites | Pytest tests for all 5 services; asyncpg/Redis mocked; runs in CI with no live infra | $500 |

**CI/CD Subtotal: $1,500**

### 2.4 Observability & Security

| Deliverable | Description | Fee (USD) |
|-------------|-------------|-----------|
| Monitoring Stack | kube-prometheus-stack Helm values, 7 PrometheusRule alerts, Alertmanager Slack integration; Docker Compose Prometheus scrape config for local dev | $500 |
| Grafana Dashboard | 20-panel dashboard JSON (Overview stats · Gateway · Business Metrics · DB & Cache · Redis & Frontend · HPA Scaling rows); auto-provisioned in Docker Compose; auto-imported via ConfigMap sidecar in EKS | $500 |
| Load Testing Suite | k6 load test (200 VU ramp), k6 spike test (300 VU instant), Locust file; all target HPA trigger endpoint | $500 |

**Observability & Security Subtotal: $1,500**

### 2.5 Documentation & Knowledge Transfer

| Deliverable | Description | Fee (USD) |
|-------------|-------------|-----------|
| Technical Documentation | README.md (end-to-end deploy guide), 5 architecture diagrams, Troubleshooting guide | Included |
| Technical Proposal (Envelope A) | Full technical proposal document as submitted | Included |
| Knowledge Transfer Session | 2× half-day sessions: Terraform walkthrough, ArgoCD operations, Grafana dashboard tour, load test live demo | $500 |

**Documentation Subtotal: $500**

---

### Setup Fee Summary

| Category | USD |
|----------|-----|
| Architecture & Infrastructure | $8,500 |
| Application Containerization & Microservices | $7,000 |
| CI/CD Pipeline & Testing | $1,500 |
| Observability & Security | $1,500 |
| Documentation & Knowledge Transfer | $500 |
| **Total One-Time Setup Fee** | **$19,000** |

---

## 3. AWS Cloud Infrastructure Costs

All costs are based on AWS ap-south-1 (Mumbai) pricing as of May 2026. Prices are estimates; actual billing will reflect actual usage and current AWS pricing.

### 3.1 Compute (EKS)

| Resource | Spec | Unit Price | Quantity | Monthly | Annual |
|----------|------|-----------|---------|---------|--------|
| EKS Control Plane | Managed | $0.10/hour | 1 cluster | $73 | $876 |
| EC2 Worker Nodes | t3.medium (2 vCPU / 4 GB) | $0.0416/hour | 3 nodes (baseline) | $91 | $1,092 |
| EC2 Auto-Scaling Headroom | Up to 10 nodes at peak | avg 1 extra node | — | $30 | $360 |

**Compute Monthly: $194 | Annual: $2,328**

### 3.2 Managed Database (RDS)

| Resource | Spec | Unit Price | Monthly | Annual |
|----------|------|-----------|---------|--------|
| RDS PostgreSQL | db.t3.medium, Multi-AZ | $0.136/hour | $99 | $1,188 |
| RDS Storage | 50 GB gp2 (Multi-AZ doubles) | $0.115/GB-month | $12 | $144 |
| RDS Backup Storage | 50 GB (7-day retention) | $0.095/GB-month | $5 | $60 |

**Database Monthly: $116 | Annual: $1,392**

### 3.3 Managed Cache (ElastiCache Redis)

| Resource | Spec | Unit Price | Monthly | Annual |
|----------|------|-----------|---------|--------|
| ElastiCache Redis | cache.t3.micro × 2 (primary + replica) | $0.017/hour each | $25 | $300 |

**Cache Monthly: $25 | Annual: $300**

### 3.4 Networking

| Resource | Spec | Unit Price | Monthly | Annual |
|----------|------|-----------|---------|--------|
| NAT Gateways | 3× (one per AZ for HA) | $0.045/hour each | $99 | $1,188 |
| NAT Data Processed | est. 100 GB/month | $0.045/GB | $5 | $60 |
| Application Load Balancer | 1× | $0.018/hour + LCU | $18 | $216 |
| Data Transfer Out | est. 50 GB/month | $0.085/GB | $4 | $48 |

**Networking Monthly: $126 | Annual: $1,512**

> **Cost Reduction Option:** Reduce to 1 NAT Gateway (non-HA) → saves $66/month ($792/year). Acceptable for dev/staging; not recommended for production.

### 3.5 Supporting Services

| Resource | Spec | Monthly | Annual |
|----------|------|---------|--------|
| S3 (Terraform state + ALB logs) | < 5 GB | $1 | $12 |
| DynamoDB (Terraform state lock) | On-demand, minimal | $1 | $12 |
| CloudWatch Logs (VPC Flow Logs, EKS) | est. 10 GB/month | $5 | $60 |
| CloudWatch Metrics | Standard metrics | $3 | $36 |
| Secrets Manager | 4 secrets + API calls | $2 | $24 |
| KMS | 2 keys + 10K operations | $2 | $24 |
| Route 53 | 1 hosted zone + queries | $1 | $12 |

**Supporting Monthly: $15 | Annual: $180**

---

### AWS Infrastructure Cost Summary

| Category | Monthly (USD) | Annual (USD) |
|----------|--------------|-------------|
| Compute (EKS + EC2) | $194 | $2,328 |
| Database (RDS) | $116 | $1,392 |
| Cache (ElastiCache) | $25 | $300 |
| Networking (NAT + ALB) | $126 | $1,512 |
| Supporting Services | $15 | $180 |
| **AWS Total** | **$476/month** | **$5,712/year** |

> Note: Free Tier savings not assumed (DESC is an organisation, not a new AWS account). Costs rounded up to nearest dollar for conservatism. Actual bill may be 5–10% lower.

> The README cost estimate of ~$412/month used a slightly smaller traffic assumption. This proposal uses $476/month which includes a one additional auto-scaling node and 100 GB NAT data for a more conservative figure.

---

## 4. 1-Year Managed Service Retainer

The managed service covers ongoing operations for the 12-month contract duration. Billed monthly.

### 4.1 Scope of Managed Service

| Service | Details | Included |
|---------|---------|---------|
| 24/7 Infrastructure Monitoring | Grafana dashboards + Alertmanager; on-call pager for Critical alerts | ✓ |
| Incident Response (Critical) | 4-hour response SLA for Critical alerts; 8-hour for Warning | ✓ |
| Monthly Kubernetes Patching | EKS version upgrades, node group AMI rotation, add-on updates | ✓ |
| Monthly Security Patching | Base image updates, dependency vulnerability remediation | ✓ |
| CI/CD Pipeline Maintenance | Workflow updates, Docker build optimisation, registry maintenance | ✓ |
| ArgoCD & Helm Chart Updates | Chart version bumps, values tuning as requirements change | ✓ |
| Monthly Architecture Review | 1-hour call: capacity planning, cost review, scaling recommendations | ✓ |
| Monthly Reporting | Uptime report, cost breakdown, incident log, performance summary | ✓ |
| Minor Application Changes | Up to 8 hours/month of minor feature or configuration changes | ✓ |

### 4.2 What Is Not Included in Retainer

- Major new feature development (scoped and quoted separately)
- Additional microservices beyond the 4 delivered at setup
- AWS cost increases due to traffic growth beyond baseline assumptions
- Third-party software licensing

### 4.3 Managed Service Pricing

| Tier | Monthly Fee | Annual |
|------|------------|--------|
| Standard Managed Service | $600/month | $7,200 |

---

## 5. Total Cost of Ownership — Year 1

| Item | Amount (USD) | Amount (PKR) |
|------|-------------|-------------|
| One-time setup & implementation | $19,000 | PKR 5,320,000 |
| AWS cloud infrastructure (12 months × $476) | $5,712 | PKR 1,599,360 |
| Managed service retainer (12 months × $600) | $7,200 | PKR 2,016,000 |
| **Year 1 Total** | **$31,912** | **PKR 8,935,360** |

### Year 2+ Recurring Costs

After the one-time setup is paid, ongoing annual cost:

| Item | Annual (USD) | Annual (PKR) |
|------|-------------|-------------|
| AWS cloud infrastructure | $5,712 | PKR 1,599,360 |
| Managed service retainer | $7,200 | PKR 2,016,000 |
| **Year 2+ Annual Total** | **$12,912** | **PKR 3,615,360** |

---

## 6. Cost Optimization Options

### Option A — Non-HA (Dev/Staging) Configuration

Reduces cost by removing redundancy. Suitable for evaluation or non-critical workloads only.

| Change | Monthly Saving | Annual Saving |
|--------|---------------|--------------|
| Reduce NAT Gateways: 3 → 1 | -$66 | -$792 |
| RDS: Multi-AZ off, db.t3.micro | -$55 | -$660 |
| Reduce EKS nodes: 3 → 2 | -$30 | -$360 |
| ElastiCache: cache.t3.micro × 1 (no replica) | -$12 | -$144 |
| **Total Saving** | **-$163/month** | **-$1,956/year** |
| **Non-HA Monthly AWS Cost** | **$313/month** | **$3,756/year** |

> **Not recommended for production.** RDS failover loss alone would break the 99.99% SLA commitment.

### Option B — Reserved Instance Pricing (12-month commitment)

AWS Reserved Instances reduce EC2 and RDS costs for steady-state resources:

| Resource | On-Demand/month | 1-Year Reserved/month | Monthly Saving |
|----------|---------------|----------------------|---------------|
| EC2 t3.medium × 3 | $91 | $58 | $33 |
| RDS db.t3.medium Multi-AZ | $99 | $67 | $32 |
| ElastiCache cache.t3.micro × 2 | $25 | $17 | $8 |
| **Total RI Saving** | — | — | **-$73/month (-$876/year)** |

Reserved Instances require upfront commitment. DESC can purchase directly through the AWS Management Console after baseline usage is established (recommended at Month 2).

### Option C — Savings Plans (flexible, no instance-type lock-in)

AWS Compute Savings Plans give up to 66% discount on EC2 with commitment flexibility. At $60/month Compute commitment:
- Estimated annual saving: ~$500–700 (actual varies by usage profile)

---

## 7. Payment Schedule

| Milestone | % | Amount (USD) | Due |
|-----------|---|-------------|-----|
| Contract signing + project kickoff | 25% | $4,750 | Week 0 |
| Infrastructure provisioned (EKS running) | 25% | $4,750 | Week 2 |
| Application deployed on EKS (all services healthy) | 25% | $4,750 | Week 5 |
| Live demonstration accepted by evaluation board | 25% | $4,750 | Week 8 |
| **Setup Total** | **100%** | **$19,000** | |
| Managed Service Retainer | — | $600/month | Monthly from Month 1 |

AWS costs are billed directly by AWS to DESC's AWS account — passed through at cost with no markup.

---

## 8. Assumptions & Exclusions

### Assumptions

- DESC provides an AWS account with an IAM user/role having the permissions listed in the Technical Proposal (Envelope A)
- A GitHub repository is available for the project (public or private)
- DockerHub account (free tier) is available for image registry
- A registered domain name is available for Route 53 (or ALB DNS name is acceptable for demo)
- Network egress traffic remains below 100 GB/month; higher traffic will increase NAT and data transfer costs proportionally
- AWS pricing as of May 2026 (ap-south-1); AWS price changes passed through at cost
- Exchange rate of 280 PKR/USD is indicative; actual PKR invoices converted at SBP rate on invoice date

### Exclusions

- AWS account creation or AWS Organization setup (if required, quoted separately)
- Domain registration fees (Route 53 domain: ~$12/year if needed)
- SSL/TLS certificate (AWS ACM is free for ALB-terminated certs — included)
- Major new feature development beyond the scope defined in Section 2 of the Technical Proposal
- On-site visits (all work delivered remotely; travel costs quoted separately if required)
- VAT/GST/WHT — proposal is exclusive of applicable taxes; tax treatment per Pakistani FBR regulations

---

*Tender Reference: DESC-MRD-2026-CNC-088 | Submission Deadline: Sunday, 14th June 2026, 11:00 AM*  
*This document is confidential and intended solely for the evaluation of DESC Digital Innovation Center, Mardan.*
