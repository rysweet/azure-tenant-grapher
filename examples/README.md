# Azure Tenant Grapher - Examples Directory

This directory contains practical examples and usage guides for Azure Tenant Grapher, with a focus on cross-tenant deployment scenarios.

## Overview

The examples in this directory demonstrate:
- Complete cross-tenant deployment workflows
- Identity mapping between tenants
- Translation system testing and validation
- Real-world usage patterns

## Files in This Directory

### 1. `cross_tenant_deployment.sh` ⭐
**End-to-end deployment script**

A complete bash script demonstrating the full cross-tenant deployment workflow:
1. Scan source tenant
2. Generate IaC with translation for target tenant
3. Validate Terraform
4. Plan deployment

**Usage:**
```bash
# Set required environment variables
export SOURCE_TENANT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export TARGET_TENANT_ID="yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
export TARGET_SUBSCRIPTION="zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"

# Run the script
./examples/cross_tenant_deployment.sh
```

**Features:**
- ✅ Prerequisite checking (uv, terraform, az CLI)
- ✅ Configuration validation
- ✅ Azure authentication handling
- ✅ Colored output for easy reading
- ✅ Error handling and recovery
- ✅ Safe deployment workflow

**Perfect for:** Production deployments, CI/CD pipelines, automation

---

### 2. `generate_identity_mapping.md` 📖
**Comprehensive identity mapping guide**

Step-by-step guide for creating identity mapping files to translate Entra ID (Azure AD) objects between tenants.

**Topics covered:**
- What is identity mapping and when you need it
- Identity mapping file structure
- Finding source and target identities with Azure CLI
- Creating mappings for users, groups, service principals, and managed identities
- Validation and troubleshooting
- Best practices and common pitfalls

**Perfect for:** Understanding identity translation, first-time users, reference documentation

**Quick start:**
```bash
# Read the guide
cat examples/generate_identity_mapping.md

# Or open in your browser (if converted to HTML)
```

---

### 3. `test_translation.py` 🧪
**Offline translation testing script**

Python script that demonstrates and tests the translation system WITHOUT requiring Azure connectivity.

**What it does:**
- Example 1: Private endpoint resource ID translation
- Example 2: Custom translator implementation (storage account)
- Example 3: Batch translation of multiple resources
- Example 4: Identity mapping (conceptual demonstration)

**Usage:**
```bash
# Run all examples
uv run python examples/test_translation.py

# Or with plain python (if dependencies installed)
python examples/test_translation.py
```

**Output includes:**
- Visual demonstration of translation
- Before/after comparisons
- Translation statistics
- Warning and error messages

**Perfect for:** Learning how translation works, debugging, custom translator development

---

### 4. `identity_mapping_example.json` 📋
**Reference identity mapping file**

A complete, well-documented example of an identity mapping file with:
- Sample mappings for users, groups, service principals, and managed identities
- Inline documentation (in JSON comments)
- Azure CLI helper commands
- Example scenarios
- Best practices and troubleshooting tips

**Structure:**
```json
{
  "users": {
    "SOURCE_OBJECT_ID": "TARGET_OBJECT_ID",
    "source@domain.com": "target@domain.com"
  },
  "groups": {
    "SOURCE_GROUP_ID": "TARGET_GROUP_ID"
  },
  "service_principals": {
    "SOURCE_SP_ID": "TARGET_SP_ID"
  },
  "managed_identities": {
    "SOURCE_MI_ID": "TARGET_MI_ID"
  }
}
```

**Perfect for:** Template for your own mappings, understanding the format, reference

---

### 5. `azure_mcp_example.py`
**Model Context Protocol (MCP) integration example**

Demonstrates using Azure Tenant Grapher with AI agents via MCP protocol.

**Perfect for:** AI/LLM integration, automated workflows, agent-based systems

---

## Quick Start Guide

### Scenario 1: Simple Cross-Tenant Deployment (No Identities)

If your infrastructure only contains network and compute resources without IAM/RBAC:

```bash
# 1. Scan source tenant
uv run atg scan --tenant-id SOURCE_TENANT_ID

# 2. Generate IaC for target tenant
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-subscription TARGET_SUBSCRIPTION_ID \
  --format terraform

# 3. Deploy
cd outputs/iac-out-*/
terraform init
terraform plan
terraform apply
```

### Scenario 2: Cross-Tenant with Identity Translation

If your infrastructure includes Key Vaults, Storage Accounts with RBAC, or other identity-dependent resources:

```bash
# 1. Scan source tenant
uv run atg scan --tenant-id SOURCE_TENANT_ID

# 2. Create identity mapping (see generate_identity_mapping.md)
# Create examples/my_identity_mapping.json with your mappings

# 3. Generate IaC with translation
# (Identity mapping is currently handled internally)
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-subscription TARGET_SUBSCRIPTION_ID \
  --format terraform

# 4. Review and deploy
cd outputs/iac-out-*/
terraform init
terraform plan
terraform apply
```

### Scenario 3: Testing Translation Offline

Before deploying to Azure, test the translation logic:

```bash
# Run the test script to see how translation works
uv run python examples/test_translation.py

# This will show you:
# - How resource IDs are translated
# - How identity mapping works
# - What warnings/errors to expect
```

---

## Common Use Cases

### Use Case 1: Disaster Recovery Setup

**Goal:** Replicate production infrastructure to DR tenant

**Steps:**
1. Use `cross_tenant_deployment.sh` with DR tenant credentials
2. Create identity mapping with break-glass admin accounts
3. Review generated Terraform for DR-specific adjustments
4. Deploy to DR tenant

### Use Case 2: Dev/Test Environment

**Goal:** Copy production infrastructure to dev/test tenant

**Steps:**
1. Scan production tenant
2. Generate IaC for dev/test tenant
3. Use identity mapping to point to test users/service principals
4. Deploy with smaller instance sizes (adjust Terraform variables)

### Use Case 3: Tenant Consolidation

**Goal:** Merge multiple tenants into one

**Steps:**
1. Scan each source tenant separately
2. Generate IaC for consolidated target tenant
3. Use unique resource group prefixes to avoid conflicts
4. Create identity mappings for each source tenant
5. Deploy all workloads to target tenant

### Use Case 4: Compliance Migration

**Goal:** Move workloads to compliance-approved tenant

**Steps:**
1. Scan current tenant
2. Generate IaC for compliance tenant
3. Add compliance tags/policies to generated Terraform
4. Map identities to compliance-approved accounts
5. Deploy and validate compliance

---

## Troubleshooting

### Issue: "Module not found" when running test_translation.py

**Solution:**
```bash
# Use uv to run with proper dependencies
uv run python examples/test_translation.py

# Or install dependencies manually
uv sync
python examples/test_translation.py
```

### Issue: Authentication failures in cross_tenant_deployment.sh

**Solution:**
```bash
# Authenticate to both tenants manually first
az login --tenant SOURCE_TENANT_ID
az login --tenant TARGET_TENANT_ID --allow-no-subscriptions

# Then run the script
./examples/cross_tenant_deployment.sh
```

### Issue: "Identity not found" warnings during translation

**Solution:**
1. Review `generate_identity_mapping.md`
2. Create complete identity mapping file
3. Verify all identities exist in target tenant
4. Run test_translation.py to validate mappings

### Issue: Resource conflicts in target tenant

**Solution:**
```bash
# Use resource group prefix to avoid conflicts
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-subscription TARGET_SUBSCRIPTION_ID \
  --resource-group-prefix "MIGRATION_" \
  --format terraform
```

---

## Advanced Topics

### Custom Translators

You can create custom translators for specific resource types. See `test_translation.py` Example 2 for a complete implementation of a custom Storage Account translator.

**Pattern:**
```python
from src.iac.translators.base_translator import BaseTranslator, TranslationContext, TranslationResult

class MyCustomTranslator(BaseTranslator):
    @property
    def supported_resource_types(self):
        return ["Microsoft.CustomProvider/customResources"]

    def translate(self, resource, context):
        # Your custom translation logic here
        pass
```

### Automation and CI/CD

The `cross_tenant_deployment.sh` script can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Deploy to target tenant
  env:
    SOURCE_TENANT_ID: ${{ secrets.SOURCE_TENANT_ID }}
    TARGET_TENANT_ID: ${{ secrets.TARGET_TENANT_ID }}
    TARGET_SUBSCRIPTION: ${{ secrets.TARGET_SUBSCRIPTION }}
  run: |
    ./examples/cross_tenant_deployment.sh
```

### Identity Mapping Automation

For large organizations with hundreds of identities:

```bash
# Generate mapping from Azure CLI queries
az ad user list --query "[].{src:id, tgt:id}" > users.json
az ad group list --query "[].{src:id, tgt:id}" > groups.json

# Merge into identity_mapping.json
python merge_identity_mappings.py users.json groups.json > identity_mapping.json
```

---

## Additional Resources

- **Main Documentation:** [../README.md](../README.md)
- **Architecture Guide:** [../UNIFIED_TRANSLATION_ARCHITECTURE.md](../UNIFIED_TRANSLATION_ARCHITECTURE.md)
- **Terraform Importer:** [../TERRAFORM_IMPORTER_QUICK_START.md](../TERRAFORM_IMPORTER_QUICK_START.md)
- **Project Instructions:** [../CLAUDE.md](../CLAUDE.md)

---

## Contributing

Have a useful example or improvement? Contributions are welcome!

1. Create your example script/document
2. Add documentation to this README
3. Submit a pull request

---

## License

These examples are part of Azure Tenant Grapher and follow the same license as the main project.

---

## Support

For issues, questions, or feature requests:
- File an issue on GitHub
- Check existing documentation
- Run `uv run atg --help` for CLI help
- Review example scripts in this directory

---

**Happy deploying! 🚀**
