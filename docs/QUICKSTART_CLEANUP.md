# Quick Start: Iteration Cleanup

## TL;DR

```bash
# 1. Preview (always do this first!)
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run

# 2. Clean up
./scripts/cleanup_iteration_resources.sh ITERATION15_

# 3. Verify
az group list --query "[?starts_with(name, 'ITERATION15_')]"

# 4. Deploy new iteration
uv run atg create-tenant --spec demos/simuland_iteration2/iteration16/iteration16_spec.md
```

## Why Use This?

Prevents "already exists" errors when deploying new iterations by cleaning up:
- Resource groups
- Soft-deleted Key Vaults
- Orphaned storage accounts
- Individual resources

## Common Commands

### See Examples
```bash
./scripts/cleanup_examples.sh
```

### Get Help
```bash
./scripts/cleanup_iteration_resources.sh --help
```

### Automated Cleanup (CI/CD)
```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation
```

### Verbose Mode
```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --verbose
```

## Files Created

| File | Purpose |
|------|---------|
| `scripts/cleanup_iteration_resources.sh` | Main cleanup script |
| `scripts/cleanup_examples.sh` | Quick examples |
| `scripts/README_CLEANUP.md` | Quick reference |
| `docs/cleanup_iteration_resources.md` | Full documentation |
| `tests/test_cleanup_script.sh` | Test suite |

## Safety Features

- ✅ Dry-run mode to preview
- ✅ Confirmation prompts
- ✅ Parallel deletion for speed
- ✅ Comprehensive logging
- ✅ Error handling

## More Info

- **Quick Reference:** [scripts/README_CLEANUP.md](/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/scripts/README_CLEANUP.md)
- **Full Docs:** [docs/cleanup_iteration_resources.md](/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/docs/cleanup_iteration_resources.md)
- **Summary:** [demos/simuland_iteration2/iteration16/CLEANUP_SCRIPT_SUMMARY.md](/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/demos/simuland_iteration2/iteration16/CLEANUP_SCRIPT_SUMMARY.md)
