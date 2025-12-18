# Deployment Troubleshooting Guide

## Auth Token Expiration

**Symptom**: Deployment fails with `AADSTS50173: The provided grant has expired`

**Cause**: Azure CLI auth tokens expire after ~1 hour. Long-running deployments (40+ minutes) will hit this.

**Solution**:
```bash
# Re-authenticate
az logout
az login --tenant c7674d41-af6c-46f5-89a5-d41495d2151e

# Set subscription
az account set --subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285

# Resume deployment
cd /tmp/iac_iteration_8
terraform apply -auto-approve -parallelism=40
```

**Prevention**: For large deployments, use service principal authentication:
```bash
az login --service-principal -u <APP_ID> -p <PASSWORD> --tenant <TENANT_ID>
```

## PrincipalNotFound Errors

**Symptom**: Role assignments fail with `Principal {hash} does not exist in the directory`

**Cause**: Cross-tenant deployment without identity mapping. Principal IDs are abstracted hashes that don't exist as real principals in target tenant.

**Expected Behavior**: This is NORMAL for cross-tenant deployment without identity mapping.

**Impact**:
- ✅ Infrastructure resources (RGs, VNets, Storage, VMs) deploy successfully
- ❌ Role assignments fail (need identity mapping)

**Solution**: Implement identity mapping (future work) or accept role assignment failures.

## Subscription Not Found

**Symptom**: `subscription ID not known by Azure CLI`

**Cause (Before Bug #59 Fix)**: Subscription IDs in properties weren't abstracted

**Solution**:
- Bug #59 now fixed in main branch
- Future scans will have subscription IDs properly abstracted
- For old data: Re-scan tenant to get properly abstracted data

## Deployment State Management

**Resuming Failed Deployments:**
```bash
cd /tmp/iac_iteration_8

# Check current state
terraform state list | wc -l  # Count deployed resources

# Resume deployment (skips existing)
terraform apply -auto-approve

# If state is corrupted, refresh:
terraform refresh
```

**Starting Fresh:**
```bash
# Remove state
rm -f terraform.tfstate terraform.tfstate.backup

# Deploy from scratch
terraform apply -auto-approve
```

## Performance Optimization

**Slow Deployments:**
- Increase parallelism: `terraform apply -parallelism=50`
- Deploy in batches (community-based splitting - future work)
- Use faster Azure regions (eastus, westus2)

**Auth Token Timeout:**
- Use service principal (no expiration)
- Deploy in smaller batches
- Implement automatic token refresh (future work)
