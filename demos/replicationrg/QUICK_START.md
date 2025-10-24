# ReplicationRG Demo - Quick Start Guide

## What This Demo Shows

Complete Azure infrastructure replication demonstration using a Windows Active Directory lab environment.

**Source**: ReplicationRG (westus2) - 89 resources  
**Target**: Any subscription with Contributor permissions

---

## Quick Start

### 1. Review the Environment

```bash
# See what's in ReplicationRG
cat demos/replicationrg/replicationrg_resources.json
```

**Contains**: 16 VMs (1 DC, 15 Workstations), VNet, Bastion, Storage, Key Vaults

### 2. Review the ARM Template

```bash
# Check the exported template
cat demos/replicationrg/replicationrg_template.json
```

**Size**: 151 KB, 115 template resources, 73 parameters

### 3. Deploy (Requires Permissions)

```bash
# Create target resource group
az group create --name ReplicationRG-Demo-Target --location westus2

# Deploy the template
az deployment group create \
  --resource-group ReplicationRG-Demo-Target \
  --template-file demos/replicationrg/replicationrg_template.json \
  --mode Incremental
```

### 4. Verify Fidelity

```bash
# Compare resource counts
source_count=$(az resource list --resource-group ReplicationRG --query "length(@)" -o tsv)
target_count=$(az resource list --resource-group ReplicationRG-Demo-Target --query "length(@)" -o tsv)
echo "Source: $source_count | Target: $target_count"
```

---

## Files in This Demo

- **README.md**: Complete demonstration documentation
- **QUICK_START.md**: This file
- **BUGS_AND_FIXES.md**: Issues discovered and fixes
- **MISSION_SUMMARY.md**: Full mission completion report
- **replicationrg_template.json**: ARM template for deployment
- **replicationrg_resources.json**: Resource inventory

---

## Prerequisites

- Azure CLI authenticated
- Contributor role on target subscription
- Target subscription has available quota for 16 VMs

---

## Expected Results

After deployment completes (30-45 minutes):
- 89 Azure resources created
- 1 Domain Controller operational
- 15 Workstations domain-joined
- Azure Bastion for secure access
- 4 Storage accounts configured
- 2 Key Vaults with secrets

---

## Troubleshooting

See `BUGS_AND_FIXES.md` for common issues and solutions.

🏴‍☠️ Prepared by Claude Code with amplihack framework
