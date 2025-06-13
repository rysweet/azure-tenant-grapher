# Tenant Architecture Specification
_Date: 2024-06-XX_

---

## 1. Executive Summary
This Azure tenant hosts ≈936 resources across ten regions, supporting a mix of IaaS virtual machines, PaaS data services, AI/ML workloads, and automation.
Key characteristics:

* Strong network segmentation using VNets, NSGs, and Private Link
* Heavy use of IaaS (70 VMs, 126 NICs, 72 managed disks) combined with modern PaaS (Databricks, Cognitive Services, Container Apps)
* Well-established security primitives (47 Key Vaults, 49 Private Endpoints, 19 Bastion Hosts, 16 User-Assigned Managed Identities)
* Centralized observability through Log Analytics, Application Insights, and alerting rules
Overall, the environment follows common Azure “hub-and-spoke with private-link” design patterns and is ready for further scale, but would benefit from governance consolidation and cost-optimization.

---

## 2. Infrastructure Overview

| Capability Area | Representative Resource Types | Count | % of Total |
|-----------------|------------------------------|------:|-----------:|
| Compute (IaaS/Labs) | Virtual Machines (70) + DevTest VMs (16) + VM Extensions (44) | 130 | 14% |
| Networking | NICs (126), VNets (40), NSGs (50), Private Endpoints (49), Bastion (19), Public IPs (40), App Gateway (1) | 325 | 35% |
| Storage & Backup | Disks (72), Snapshots (16), Storage Accounts (53) | 141 | 15% |
| Security & Identity | Key Vaults (47), Managed Identities (16), Security Copilot Capacity (1) | 64 | 7% |
| Data & Analytics | Log Analytics (14), Kusto Clusters (2), Databricks (2), Synapse (1), Cosmos DB (4), SQL DB (4) | 27 | 3% |
| Application & Integration | App Service Plans (11), Web Apps (10), Container Apps (1), Event Hub NS (6) | 28 | 3% |
| AI / ML | Cognitive Services (11), ML Workspaces (10 + 4 endpoints), Purview (1), Search (1) | 27 | 3% |
| Management & Automation | Automation Accounts (8), Runbooks (27), DCRs (9), Alerts (14 + 9 smart detector), Action Groups (3) | 70 | 7% |
| Other (Images, Template Specs, etc.) | – | 124 | 13% |

Key take-aways
• Networking is the largest footprint (1 in 3 resources).
• Compute workloads remain VM-centric; limited use of autoscale sets or Kubernetes.
• Security controls are broadly deployed, but Key Vault sprawl may create management overhead.

---

## 3. Geographic Distribution

| Region | Observed Role / Workload Type |
|--------|-------------------------------|
| eastus / eastus2 | Primary production landing zones, majority of compute and data services |
| westus, westus2, westus3 | Secondary production / DR, latency-sensitive West-coast users |
| southcentralus / northcentralus | Test & Dev, regional redundancy |
| swedencentral / switzerlandnorth | EU compliance & data residency |
| global | DNS zone and monitoring meta-resources |

Patterns
* Dual-region pairs (East US ↔ West US) suggest active/standby or active/active architectures.
* European regions appear scoped to specific compliance domains; private link and key vaults are present there as well.

---

## 4. Architecture Patterns

1. Hub-and-Spoke Networking
   • Central hub VNets likely contain Bastion Hosts, Network Watchers, and shared services.
   • Spokes host workload VNets linked via VNet peering and private DNS zones (35 zones, 30 VNet links).

2. Private-Link & Service Endpoints
   • 49 Private Endpoints map PaaS resources (Storage, SQL, Cosmos, etc.) into VNets, reducing public exposure.

3. Landing Zone Modularization
   • Repeated sets of VNets, Key Vaults, Log Analytics, and Automation Accounts in each region indicate a standardized landing-zone template.

4. Observability Pipeline
   • Data Collection Rules → Log Analytics → Metric Alerts/Smart Detector Rules → Action Groups provide end-to-end monitoring.

5. Dev/Test Isolation
   • DevTest Labs VMs (16) and schedules imply cost-efficient testing environments separated from production.

---

## 5. Security Posture

Strengths
• Network security: 50 NSGs, Bastion for jump-box-less RDP/SSH, single Application Gateway.
• Identity: 16 user-assigned Managed Identities reduce embedded credentials; Key Vault pervasive.
• Data exfiltration controls: Private Endpoints + Private DNS restrict PaaS to internal networks.
• Governance: Alerting, Log Analytics, and DCRs indicate proactive monitoring.

Gaps / Risks
• 47 Key Vaults may fragment secrets management—risk of inconsistent RBAC, policies, and purge protection.
• Limited use of Azure Policy or Blueprints observed (no policy resources in inventory).
• VM disks/snapshots exist, but no explicit Backup Vaults—confirm backup/restore compliance.
• Only one Application Gateway; web workloads might lack WAF coverage.

---

## 6. Scalability Considerations

Compute
• Static VM inventory suggests fixed-size scaling. Transitioning stateless tiers to VM Scale Sets, AKS, or Container Apps would enable elastic growth.

Data
• Cosmos DB and SQL PaaS instances support autoscale; confirm throughput settings match demand patterns.

Network
• 40 VNets and 126 NICs scale linearly; consider Azure Virtual WAN or Route Server for simpler routing at larger scale.

Observability
• 14 Log Analytics workspaces may cause data siloes; a centralized workspace per region/landing zone streamlines query and retention management.

---

## 7. Recommendations

Governance & Organization
• Consolidate Key Vaults where possible; enforce soft-delete & purge protection via Azure Policy.
• Implement a tenant-wide tagging standard (owner, cost center, environment, data classification).
• Enable Azure Policy/Defender for Cloud to enforce baseline configurations and collect secure-score metrics.

Cost & Performance
• Evaluate VM sizing; right-size or deallocate under-utilized VMs.
• Migrate eligible VMs to Reserved Instances or Savings Plans.
• Leverage Azure Storage lifecycle management to tier infrequently accessed data.

Security Enhancements
• Deploy Web Application Firewall on the existing Application Gateway or create regional AGIC-enabled AKS ingress.
• Expand use of user-assigned Managed Identity to all automation/runbooks.
• Activate Microsoft Sentinel on existing Log Analytics to consolidate SIEM functions.

Scalability & Modernization
• Containerize stateless web and API workloads onto Azure Container Apps or AKS for rapid scaling.
• Adopt Virtual Machine Scale Sets with autoscaling rules for stateful services that remain VM-based.
• Explore Azure Virtual WAN for hub centralization as VNet count grows.

Operational Excellence
• Rationalize Log Analytics workspaces—target one per landing zone with cross-workspace queries.
• Standardize runbook code repositories and CI/CD pipelines; consider GitHub Actions or Azure DevOps for infrastructure as code.
• Create a disaster recovery runbook leveraging paired regions (East US ↔ West US, Sweden Central ↔ Switzerland North).

By addressing these areas, the tenant can improve security, reduce operational overhead, and position itself for future growth and cloud-native transformation.
