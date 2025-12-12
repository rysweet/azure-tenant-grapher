# Azure Tenant Inventory Report

**Tenant ID:** 3cd87a41-1f61-4aef-a212-cefdecd9a2d1
**Generated:** 2024-12-03 15:30:45 UTC
**Data Source:** Neo4j Graph Database
**Report Version:** 1.0

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Resources** | 2,248 |
| **Resource Types** | 93 |
| **Regions** | 16 |
| **Subscriptions** | 3 |
| **Resource Groups** | 45 |
| **Total Role Assignments** | 1,042 |

---

## Identity Overview

### Users

- **Total Users:** 214
- **Active Users:** 198
- **Guest Users:** 16
- **Licensed Users:** 187

**Top User Domains:**
- contoso.com: 165 users
- fabrikam.com: 31 users
- External guests: 18 users

### Service Principals

- **Total Service Principals:** 1,470
- **Application Service Principals:** 1,357
- **Enterprise Applications:** 113

**Top Service Principal Categories:**
- Azure DevOps Integrations: 234
- Third-party SaaS Apps: 189
- Custom Applications: 145
- Microsoft First-party: 902

### Managed Identities

- **Total Managed Identities:** 113
  - **System-Assigned:** 67
  - **User-Assigned:** 46

**Managed Identities by Service:**
- Virtual Machines: 34
- App Services: 23
- Logic Apps: 18
- Function Apps: 15
- Azure Container Instances: 12
- Other: 11

### Groups

- **Total Groups:** 84
- **Security Groups:** 72
- **Microsoft 365 Groups:** 12

**Group Membership Statistics:**
- Average members per group: 12.4
- Largest group: DevOps-All-Users (67 members)
- Groups with role assignments: 54

---

## Resource Inventory

### Top Resource Types

| Resource Type | Count | Primary Regions |
|--------------|-------|----------------|
| Microsoft.Network/networkInterfaces | 342 | East US (145), West US 2 (103), West Europe (94) |
| Microsoft.Compute/disks | 287 | East US (125), West US 2 (89), West Europe (73) |
| Microsoft.Storage/storageAccounts | 156 | East US (67), West Europe (45), West US 2 (44) |
| Microsoft.Compute/virtualMachines | 134 | East US (58), West US 2 (42), West Europe (34) |
| Microsoft.Network/virtualNetworks | 89 | East US (34), West US 2 (28), West Europe (27) |
| Microsoft.Web/sites | 78 | East US (32), West Europe (28), West US 2 (18) |
| Microsoft.KeyVault/vaults | 67 | East US (28), West Europe (23), West US 2 (16) |
| Microsoft.Network/publicIPAddresses | 64 | East US (26), West US 2 (22), West Europe (16) |
| Microsoft.Sql/servers | 45 | East US (18), West Europe (15), West US 2 (12) |
| Microsoft.Network/networkSecurityGroups | 43 | East US (17), West US 2 (15), West Europe (11) |

### Resources by Region

| Region | Resource Count | Percentage | Top Resource Types |
|--------|---------------|-----------|-------------------|
| **East US** | 678 | 30.2% | Network Interfaces (145), Disks (125), VMs (58) |
| **West US 2** | 542 | 24.1% | Network Interfaces (103), Disks (89), VMs (42) |
| **West Europe** | 387 | 17.2% | Network Interfaces (94), Disks (73), Storage (45) |
| **Central US** | 234 | 10.4% | Storage (34), Network Interfaces (28), Disks (23) |
| **North Europe** | 189 | 8.4% | Storage (28), Network Interfaces (22), Disks (18) |
| **East US 2** | 156 | 6.9% | Network Interfaces (18), Disks (16), VMs (12) |
| **Other (10 regions)** | 62 | 2.8% | Various |

### Resources by Subscription

| Subscription | Resource Count | Top Resource Groups | Primary Services |
|-------------|----------------|-------------------|-----------------|
| **Production-Subscription** | 1,234 | prod-web-rg (234), prod-data-rg (189) | Compute, Storage, Networking |
| **Development-Subscription** | 687 | dev-web-rg (145), dev-test-rg (112) | Compute, Web Apps, Storage |
| **Shared-Services-Subscription** | 327 | shared-monitoring-rg (89), shared-networking-rg (78) | Monitoring, Networking, Security |

### Top Resource Groups by Count

| Resource Group | Subscription | Resource Count | Primary Types |
|---------------|-------------|----------------|--------------|
| prod-web-rg | Production | 234 | VMs (45), NICs (67), Disks (56) |
| prod-data-rg | Production | 189 | Storage (34), SQL (23), VMs (18) |
| dev-web-rg | Development | 145 | App Services (34), Storage (28), VMs (12) |
| dev-test-rg | Development | 112 | VMs (23), NICs (34), Disks (28) |
| shared-monitoring-rg | Shared Services | 89 | Log Analytics (12), App Insights (15) |

---

## Role Assignments

**Total Role Assignments:** 1,042

### Top Roles Assigned

| Role | Assignment Count | Scope Distribution |
|------|-----------------|-------------------|
| **Reader** | 342 | Subscription (156), Resource Group (186) |
| **Contributor** | 287 | Subscription (89), Resource Group (198) |
| **Owner** | 156 | Subscription (45), Resource Group (111) |
| **Storage Blob Data Reader** | 134 | Resource (134) |
| **Virtual Machine Contributor** | 89 | Resource Group (67), Resource (22) |
| **Network Contributor** | 67 | Subscription (23), Resource Group (44) |
| **Key Vault Secrets User** | 54 | Resource (54) |
| **Monitoring Reader** | 45 | Subscription (34), Resource Group (11) |
| **SQL DB Contributor** | 38 | Resource Group (26), Resource (12) |
| **Storage Account Contributor** | 30 | Resource Group (22), Resource (8) |

### Role Assignments by Scope

| Scope Level | Assignment Count | Percentage |
|------------|-----------------|-----------|
| Subscription | 456 | 43.8% |
| Resource Group | 412 | 39.5% |
| Resource | 174 | 16.7% |

### Top Principals by Assignment Count

| Principal | Type | Assignment Count | Primary Roles |
|-----------|------|-----------------|--------------|
| **DevOps Service Principal** | Service Principal | 67 | Contributor (45), Owner (12), Reader (10) |
| **Admin-Group** | Security Group | 54 | Owner (34), Contributor (20) |
| **Monitoring-Identity** | Managed Identity (User-Assigned) | 42 | Monitoring Reader (42) |
| **admin@contoso.com** | User | 38 | Owner (23), Contributor (15) |
| **Backup-Service-Principal** | Service Principal | 34 | Contributor (34) |
| **Developers-Group** | Security Group | 31 | Contributor (18), Reader (13) |
| **Storage-Access-Identity** | Managed Identity (User-Assigned) | 28 | Storage Blob Data Reader (28) |
| **SQL-Admin-Identity** | Managed Identity (System-Assigned) | 23 | SQL DB Contributor (23) |

### High-Privilege Assignments

**Owner Role Assignments:** 156 total

| Scope | Count | Notable Principals |
|-------|-------|-------------------|
| Subscription | 45 | Admin-Group (15), admin@contoso.com (12), DevOps SP (8) |
| Resource Group | 111 | Admin-Group (34), devops@contoso.com (23), SRE-Group (18) |

**Contributor Role Assignments:** 287 total

| Scope | Count | Notable Principals |
|-------|-------|-------------------|
| Subscription | 89 | DevOps SP (45), Developers-Group (18), CI-CD SP (12) |
| Resource Group | 198 | DevOps SP (67), Developers-Group (34), App-Deployment SP (28) |

---

## Networking Overview

### Virtual Networks

- **Total VNets:** 89
- **Total Address Space:** 256 /16 networks (4,177,920 total IPs)
- **Average Subnets per VNet:** 4.2

**Largest VNets:**
- prod-hub-vnet: /16 (65,536 IPs) with 12 subnets
- dev-hub-vnet: /16 (65,536 IPs) with 8 subnets
- prod-spoke-1-vnet: /20 (4,096 IPs) with 6 subnets

### Network Security Groups

- **Total NSGs:** 43
- **Average Rules per NSG:** 8.4
- **Most Permissive NSG:** dev-test-nsg (allows 0.0.0.0/0 on port 3389)

**Security Concerns:**
- 12 NSGs allow RDP (3389) from internet (0.0.0.0/0)
- 8 NSGs allow SSH (22) from internet (0.0.0.0/0)
- 34 NSGs have custom rules blocking traffic

### Public IP Addresses

- **Total Public IPs:** 64
- **Static IPs:** 45
- **Dynamic IPs:** 19

**Public IP Distribution:**
- Virtual Machines: 28
- Application Gateways: 12
- Load Balancers: 15
- NAT Gateways: 6
- VPN Gateways: 3

---

## Storage Overview

### Storage Accounts

- **Total Storage Accounts:** 156
- **Account Types:**
  - General Purpose v2: 134
  - Blob Storage: 18
  - File Storage: 4

**Replication Types:**
- Locally Redundant (LRS): 89
- Geo-Redundant (GRS): 45
- Zone-Redundant (ZRS): 22

**Security Configuration:**
- Accounts with Private Endpoints: 67
- Accounts allowing public access: 89
- Accounts with Azure AD authentication: 134

---

## Compute Overview

### Virtual Machines

- **Total VMs:** 134
- **Running VMs:** 98
- **Stopped VMs:** 36

**VM Sizes:**
- Standard_D2s_v3: 45 VMs
- Standard_B2ms: 34 VMs
- Standard_D4s_v3: 23 VMs
- Standard_E4s_v3: 18 VMs
- Other sizes: 14 VMs

**Operating Systems:**
- Windows Server 2019: 67 VMs
- Ubuntu 20.04 LTS: 34 VMs
- Windows Server 2022: 23 VMs
- Red Hat Enterprise Linux 8: 10 VMs

### App Services

- **Total App Services:** 78
- **Running:** 65
- **Stopped:** 13

**App Service Plans:**
- Premium V2 P1v2: 34 apps
- Standard S1: 28 apps
- Basic B1: 16 apps

**Runtimes:**
- .NET 6.0: 34 apps
- Node.js 16: 23 apps
- Python 3.9: 12 apps
- Java 11: 9 apps

---

## Database Overview

### SQL Servers

- **Total SQL Servers:** 45
- **Total SQL Databases:** 89

**Service Tiers:**
- General Purpose: 56 databases
- Business Critical: 23 databases
- Hyperscale: 10 databases

**Security Features:**
- Servers with Azure AD authentication: 45 (100%)
- Servers with Private Endpoints: 34
- Servers with Transparent Data Encryption: 89 (100%)

---

## Security & Compliance

### Key Vaults

- **Total Key Vaults:** 67
- **Vaults with Private Endpoints:** 45
- **Vaults with RBAC enabled:** 67 (100%)

**Secrets Management:**
- Total Secrets: 342
- Total Keys: 156
- Total Certificates: 89

### Monitoring & Logging

- **Log Analytics Workspaces:** 12
- **Application Insights:** 15
- **Action Groups:** 23
- **Alert Rules:** 134

**Diagnostic Settings:**
- Resources with diagnostics enabled: 1,247 (55%)
- Resources without diagnostics: 1,001 (45%)

---

## Cost Analysis

**Note:** Cost data unavailable. To include cost information, run:
```bash
atg report --tenant-id <TENANT_ID> --include-costs
```

**Requirements:**
- Service principal must have `Cost Management Reader` role
- Cost data takes 24-48 hours to process in Azure
- Cost data represents the last 30 days of spending

---

## Report Metadata

**Generation Details:**
- Report generated using Azure Tenant Grapher v1.0
- Data source: Neo4j graph database (last scanned: 2024-12-03 12:00:00 UTC)
- Query execution time: 4.2 seconds
- Total data points analyzed: 3,962

**Data Freshness:**
- Resources: Scanned 3.5 hours ago
- Identities: Scanned 3.5 hours ago
- Role Assignments: Scanned 3.5 hours ago

**Report Generated By:**
- Tool: Azure Tenant Grapher CLI
- Command: `atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1`
- User: admin@contoso.com
- Machine: azureuser@tenant-scanner-vm

---

## Next Steps

### Documentation & Compliance
- Share this report with stakeholders
- Archive for compliance records
- Compare with previous reports to track changes

### Security Review
- Review 20 NSGs allowing RDP/SSH from internet
- Audit 89 storage accounts with public access
- Review 156 Owner role assignments

### Cost Optimization
- Run report with `--include-costs` to identify high-cost resources
- Review 36 stopped VMs (potential savings)
- Analyze storage account usage patterns

### Infrastructure as Code
Generate IaC templates for your resources:
```bash
atg generate-iac --format terraform --output ./iac-templates
```

### Visualization
Explore your tenant interactively:
```bash
atg visualize
```

### AI Analysis
Query your tenant with natural language:
```bash
atg agent-mode --question "Which resources have the most role assignments?"
```

---

**End of Report**
