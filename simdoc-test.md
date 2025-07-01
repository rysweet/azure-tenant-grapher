# Contoso Wind & Solar – Simulated Azure Customer Profile
*Version 1.0 – December 2023*

---

## 1. Company Overview

| Attribute | Detail |
|-----------|--------|
| Legal Name | Contoso Wind & Solar Holdings (CWSH) |
| Industry | Renewable Energy Generation & Trading |
| Headquarters | Portland, Oregon (USA) |
| Employees | ≈ 6,400 worldwide |
| Annual Revenue | ≈ USD 2.3 Billion |
| Geographic Footprint | 14 wind farms and 6 solar parks across North America & Western Europe |
| Regulatory Drivers | NERC-CIP, ISO 27001, SOX, GDPR (for EU operations) |

CWSH builds, owns, and operates renewable-energy assets and sells power on wholesale markets. The firm is expanding into real-time energy arbitrage and carbon-credit trading. Data-driven operations (weather prediction, turbine telemetry, and energy forecasting) are mission-critical, as are secure Operational Technology (OT) and strict compliance with NERC-CIP.

---

## 2. Strategic Technology Goals

1. Consolidate 11 legacy data centers into Azure landing zones within 24 months.
2. Enable ML-based energy forecasting with sub-hourly granularity.
3. Unify IT + OT security monitoring in a single SOC running Azure Sentinel.
4. Reach 99.95 % availability SLA for all customer-facing APIs.
5. Attain “NERC-CIP Audit-Ready in Cloud” certification by Q3 FY25.

---

## 3. Key Personas & Organizational Structure

| Persona | Title/Role | Responsibility | Azure Privileges |
|---------|------------|----------------|------------------|
| Maria Adams | Chief Digital Officer | Owns overall Azure adoption roadmap | Owner at Mgmt-Group root |
| Devin Yu | Director, Cloud Platform | Landing zone architecture, FinOps | User Access Admin |
| Priya Kapoor | Lead OT Engineer | SCADA and IoT Hub integrations | Contributor in OT sub |
| Hector García | Security Operations Manager | Threat protection, SOC tooling | Security Reader + PIM eligible Security Admin |
| Dr. Lena Šimunović | Principal Data Scientist | Forecasting & trading models | Contributor Synapse workspace |
| April Smith | DevOps Lead | CI/CD, AKS clusters | Contributor in Dev/Test and Prod |
| Oliver Laurent | Compliance Officer (EU) | GDPR & ISO 27001 mapping | Reader + Policy insights |

Roughly 120 IT staff have direct Azure access:
• 4 enterprise architects, 8 cloud engineers, 12 DevOps pipelines engineers, 40 developers, 16 data engineers, 10 security analysts, 30 OT/SCADA specialists.

---

## 4. Azure Subscription & Management-Group Layout

```
mgmt-groups:
  contoso (root)
  ├─ platform
  │  ├─ identity-sub
  │  └─ management-sub
  ├─ connectivity
  │  └─ hubnetwork-sub
  ├─ corp-it
  │  ├─ dev-sub
  │  ├─ test-sub
  │  └─ prod-sub
  └─ ot-secure
     ├─ ot-dev
     └─ ot-prod
```

• Azure Policy and Defender plans are assigned at **platform** and **ot-secure** levels.
• Cost-management tags (`CostCenter`, `Env`, `Owner`) enforced via policy.
• Landing zones built from the Cloud Adoption Framework (CAF) Terraform modules (latest release).

---

## 5. Core Workloads & Architectures

### 5.1 “GreenSpark” Energy Forecasting Platform

Purpose: Hour-ahead and day-ahead generation forecasting; feeds trading desks.
Architecture Highlights:

- Ingest ~4 GB/hr of turbine & panel telemetry via **Azure IoT Hub**.
- Event streaming through **Azure Event Hubs → Stream Analytics**.
- Persist raw data in **Data Lake Gen2** (raw, curated, gold zones).
- Feature engineering pipelines run in **Azure Databricks Premium** on autoscaling GPU clusters.
- Models registered/retrained in **Azure Machine Learning**; batch scoring outputs to **Azure SQL MI**.
- Analytics dashboards in **Power BI Embedded** surfaced to traders.
- Deployed across two regions (West US 2 / Central US) with **GEO-DR** for Synapse & SQL MI.

Security: Private endpoints on all PaaS services, double encryption (at rest + in transit), customer-managed keys in **Azure Key Vault HSM**.

### 5.2 SCADA & OT Digital Twin

Purpose: Real-time visualization and predictive maintenance for turbines/solar arrays.
Architecture Highlights:

- Each farm uses **Azure Stack Edge** for local mode buffering.
- Data travels over MPLS to Azure via dual **ExpressRoute** circuits (ER Global Reach).
- **Azure Digital Twins** models assets; twin graph drives **Azure Time Series Insights**.
- Field engineers view alarms via **Azure App Service** (Blazor WASM) on ruggedized tablets.
- Critical commands (e.g., turbine stop) routed through **Azure Arc-enabled Kubernetes** cluster dedicated to OT (k8s-ot-prod).
- All OT resources isolated in **ot-prod** subscription behind **Azure Firewall Premium** with IDPS enabled.

### 5.3 B2B Trading API (“VoltX Exchange”)

Purpose: External partners retrieve generation schedules, buy renewable energy blocks.
Architecture Highlights:

- Containerized microservices on **Azure Kubernetes Service** (aks-trading-prod) with **Istio-based** service mesh.
- API traffic fronted by **Azure Application Gateway** (WAF v2) + **Azure Front Door Standard** for global entry.
- Identity via **Azure AD B2C** with custom policies (MFA for high-value trades).
- Persistent data in **Cosmos DB (SQL API)**, point-in-time restore enabled.
- Payment settlement queues handled by **Azure Service Bus Premium**.
- CI/CD through **GitHub Actions**, gated by **Azure DevOps** release approvals.

---

## 6. Security & Governance Controls

1. Azure AD single tenant; P2 licensing; **Conditional Access** with device compliance & location.
2. Privileged roles use **Azure AD PIM**; approval workflow via ServiceNow.
3. **Azure Sentinel** aggregates logs from Defender for Cloud, Office 365, Palo Alto NGFW (on-prem), and SAP.
4. Custom Sentinel analytics:
   • Excessive turbine stop commands (threshold per farm)
   • Impossible travel logins for Data Scientists
5. Secrets sealed in three **Key Vault** instances (per-env) with RBAC-disabled (access policies only).
6. Quarterly **Azure Blueprints** compliance attestation for NERC-CIP & ISO 27001.
7. **MDE + Defender for IoT** sensors deployed on SCADA VLANs; speaks to Sentinel via IoT connector.

---

## 7. Networking Topology

- Hub-Spoke with **two dedicated hub VNETs** (IT & OT) connected by **Azure Virtual WAN** secure hub.
- **ExpressRoute** primary (10 Gbps) + backup (5 Gbps).
- **Azure DNS Private Resolver** centralizes name resolution.
- Forced tunneling: All egress from spokes cross **Azure Firewall**; logging to **Log Analytics**.
- **Just-In-Time VM Access** on 38 Windows VMs still in IaaS.
- DDoS Network Protection enabled at VNET level for public endpoints.

---

## 8. Data Protection & Residency

| Data Set | Residency Requirement | Service / Feature |
|----------|-----------------------|-------------------|
| EU customer data | Must stay in EU | Primary region: West Europe, Secondary: North Europe |
| SCADA telemetry | 1-year hot → 7-year cold | Lifecycle mgmt tiers in Data Lake Gen2 + Archive |
| Trading transactions | 10-year retention / SOX | Azure SQL MI with Long-Term Backup Retention (LTR) to GRS blob |

Encryption keys stored in **Key Vault Managed HSM** tier; rotation every 180 days.

---

## 9. DevOps & SDLC

- Source: **GitHub Enterprise Cloud** (org: cwsh).
- Pipelines: **GitHub Actions** runners hosted on Azure VMSS; hardened via **OS Image Builder**.
- Environments: dev, test, staging, prod – separated by subscriptions and AKS namespaces.
- Policy-as-Code: **Terraform Cloud** with Sentinel policies; drift detection nightly via GitOps workflow.
- SAST/DAST: CodeQL + OWASP ZAP container scan.
- Container images pushed to **Azure Container Registry Premium** (geo-replicated).

---

## 10. High-Value Assets for Security Testing

1. `iot-hub-prod` – Receives signed OP commands to turbines.
2. `sqlmi-trading-prod` – Settlement & billing; SOX scope.
3. `kv-hsm-prod` – Root encryption keys (double-wrapped).
4. `aks-trading-prod` namespace `trade-engine` – Handles market orders <30 ms latency.
5. `sentinel-workspace-prod` – SOC analytics & playbooks.

---

## 11. Known Pain Points / Open Items

• Legacy on-prem Active Directory forests with one-way trusts complicate Azure AD DS roadmap.
• OT team resists agent-based monitoring; Defender for IoT passive sensors only partly deployed.
• Current tagging compliance ~84 %; finance wants ≥95 % to improve chargeback accuracy.
• EU operations need Azure Confidential VMs for certain ML workloads (in backlog).

---

## 12. Modeling Guidance for Researchers

When standing up the simulation:

1. Emulate multi-subscription layout (minimum 6 subs).
2. Populate IoT Hub with synthetic turbine telemetry (JSON ~3 KB per msg, 10 msgs/sec).
3. Deploy AKS cluster with Istio sidecars; approximate 20 microservices.
4. Implement Azure Policy assignments (NIST, CIS) and capture policy-violation scenarios.
5. Integrate Sentinel with at least 4 data connectors (AzureActivity, SecurityAlert, Syslog, IoTHub).
6. Seed Key Vault with 50 randomly generated secrets and 5 RSA keys; enable soft-delete & purge protection.
7. Insert deliberate misconfigurations (e.g., open NSG rule on dev subnet, outdated SQL VM) to create hunt exercises.

---

### End of Profile
