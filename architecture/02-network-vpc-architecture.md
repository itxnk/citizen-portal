# Network & VPC Architecture

## CIDR Plan

| Resource | CIDR | Notes |
|----------|------|-------|
| VPC | `10.0.0.0/16` | 65,536 IPs total |
| Public Subnet AZ-a | `10.0.1.0/24` | ALB, NAT GW |
| Public Subnet AZ-b | `10.0.2.0/24` | ALB, NAT GW |
| Public Subnet AZ-c | `10.0.3.0/24` | ALB, NAT GW |
| Private Subnet AZ-a | `10.0.11.0/24` | EKS worker nodes |
| Private Subnet AZ-b | `10.0.12.0/24` | EKS worker nodes |
| Private Subnet AZ-c | `10.0.13.0/24` | EKS worker nodes |
| Isolated Subnet AZ-a | `10.0.21.0/24` | RDS, ElastiCache |
| Isolated Subnet AZ-b | `10.0.22.0/24` | RDS, ElastiCache |
| Isolated Subnet AZ-c | `10.0.23.0/24` | RDS, ElastiCache |

## Network Topology

```mermaid
flowchart TD
    subgraph VPC["AWS VPC — 10.0.0.0/16"]
        subgraph AZ_A["Availability Zone A"]
            PUB_A["Public Subnet\n10.0.1.0/24\nALB + NAT GW"]
            PRIV_A["Private Subnet\n10.0.11.0/24\nEKS Nodes"]
            ISO_A["Isolated Subnet\n10.0.21.0/24\nRDS + Redis"]
        end

        subgraph AZ_B["Availability Zone B"]
            PUB_B["Public Subnet\n10.0.2.0/24\nALB + NAT GW"]
            PRIV_B["Private Subnet\n10.0.12.0/24\nEKS Nodes"]
            ISO_B["Isolated Subnet\n10.0.22.0/24\nRDS + Redis"]
        end

        subgraph AZ_C["Availability Zone C"]
            PUB_C["Public Subnet\n10.0.3.0/24\nALB + NAT GW"]
            PRIV_C["Private Subnet\n10.0.13.0/24\nEKS Nodes"]
            ISO_C["Isolated Subnet\n10.0.23.0/24\nRDS + Redis"]
        end

        IGW[Internet Gateway]
        RT_PUB[Public Route Table\n0.0.0.0/0 → IGW]
        RT_PRIV_A[Private Route Table A\n0.0.0.0/0 → NAT GW A]
        RT_PRIV_B[Private Route Table B\n0.0.0.0/0 → NAT GW B]
        RT_PRIV_C[Private Route Table C\n0.0.0.0/0 → NAT GW C]
        RT_ISO[Isolated Route Table\nno internet route]

        NATGW_A[NAT GW A\nElastic IP]
        NATGW_B[NAT GW B\nElastic IP]
        NATGW_C[NAT GW C\nElastic IP]

        subgraph SGs["Security Groups"]
            SG_ALB["sg_alb\n:80/:443 from 0.0.0.0/0"]
            SG_EKS["sg_eks_nodes\nall from sg_alb\nnode-to-node all"]
            SG_RDS["sg_rds\n:5432 from sg_eks_nodes only"]
            SG_REDIS["sg_elasticache\n:6379 from sg_eks_nodes only"]
        end
    end

    Internet([Internet]) --> IGW
    IGW <--> RT_PUB
    RT_PUB <--> PUB_A & PUB_B & PUB_C
    PUB_A --- NATGW_A
    PUB_B --- NATGW_B
    PUB_C --- NATGW_C
    NATGW_A --> RT_PRIV_A --> PRIV_A
    NATGW_B --> RT_PRIV_B --> PRIV_B
    NATGW_C --> RT_PRIV_C --> PRIV_C
    RT_ISO <--> ISO_A & ISO_B & ISO_C
```

## Traffic Flow Rules

```mermaid
sequenceDiagram
    participant I as Internet
    participant ALB as ALB (Public Subnet)
    participant EKS as EKS Nodes (Private Subnet)
    participant RDS as RDS (Isolated Subnet)
    participant Redis as Redis (Isolated Subnet)

    I->>ALB: HTTPS :443 (sg_alb allows)
    ALB->>EKS: HTTP to NodePort/Pod IP (sg_eks_nodes allows from sg_alb)
    EKS->>RDS: PostgreSQL :5432 (sg_rds allows from sg_eks_nodes)
    EKS->>Redis: Redis :6379 (sg_elasticache allows from sg_eks_nodes)
    EKS->>I: Outbound via NAT GW (ECR pull, AWS APIs)
    Note over RDS,Redis: No inbound from internet\nNo outbound route (isolated)
```

## VPC Endpoints

To avoid NAT GW costs for AWS service calls:

| Endpoint | Type | Service |
|----------|------|---------|
| `com.amazonaws.*.s3` | Gateway | ECR layer pulls, S3 state |
| `com.amazonaws.*.ecr.api` | Interface | ECR API |
| `com.amazonaws.*.ecr.dkr` | Interface | ECR image pulls |
| `com.amazonaws.*.ec2` | Interface | EC2 API (Cluster Autoscaler) |
| `com.amazonaws.*.sts` | Interface | IRSA token exchange |

## Security Notes

- **No SSH** — SSM Session Manager used for node access (no bastion host)
- **VPC Flow Logs** — all traffic logged to S3 for audit
- **NACLs** — stateless layer; deny rules for known malicious CIDRs
- **Private EKS endpoint** — API server not reachable from internet; kubectl via VPN or SSM tunnel
