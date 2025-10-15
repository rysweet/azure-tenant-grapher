# IaC Validation Quick Reference

## One-Line Commands

```bash
# Validate IaC directory
uv run python scripts/validate_generated_iac.py <iac_directory>

# JSON output
uv run python scripts/validate_generated_iac.py --json <iac_directory>

# Validate and proceed if clean
uv run python scripts/validate_generated_iac.py <dir> && cd <dir> && terraform plan
```

## Exit Codes

| Code | Meaning | Next Action |
|------|---------|-------------|
| 0 | All passed | Proceed with deployment |
| 1 | Validation failed | Fix errors and re-run |
| 2 | Script error | Check arguments/files |

## 7 Validation Checks

| # | Check | What It Catches |
|---|-------|-----------------|
| 1 | No Placeholders | "xxx", "TODO", "FIXME", etc. |
| 2 | Valid Tenant IDs | Invalid/all-zero UUIDs |
| 3 | Valid Subscription IDs | Placeholder subscription IDs |
| 4 | Subnet CIDR Validation | Subnets outside VNet range |
| 5 | No Duplicate Resources | Duplicate resource names |
| 6 | Required Fields Populated | Empty/null critical fields |
| 7 | Valid Resource References | Invalid dependency references |

## Common Fixes

### Subnet CIDR Issues
```bash
# Regenerate with auto-fix
uv run atg generate-iac --tenant-id <ID> --auto-fix-subnets
```

### Placeholder Issues
- **Root Cause**: Missing metadata in Neo4j graph
- **Fix**: Regenerate IaC after ensuring complete Azure scan

### Tenant ID Issues
- **Root Cause**: Tenant ID not set during scan
- **Fix**: Re-scan with proper tenant ID in environment

## CI/CD Integration

### GitHub Actions
```yaml
- name: Validate IaC
  run: uv run python scripts/validate_generated_iac.py ${{ env.IAC_DIR }}
```

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
uv run python scripts/validate_generated_iac.py demos/latest_iac
```

### Makefile
```makefile
validate:
    uv run python scripts/validate_generated_iac.py $(IAC_DIR)

deploy: validate
    cd $(IAC_DIR) && terraform apply
```

## Output Formats

### Table (Default)
- Easy to read
- Color-coded
- Detailed issue breakdown

### JSON (--json flag)
- Machine-parsable
- CI/CD friendly
- Scriptable

## Tips

1. **Always validate before terraform plan**
2. **Use --json for automation**
3. **Fix critical errors first** (placeholders, invalid IDs)
4. **Warnings are informational** (won't fail validation)
5. **Save validation reports** for audit trail

## Related Files

- `scripts/validate_generated_iac.py` - Main script
- `scripts/README_VALIDATE_IAC.md` - Full documentation
- `scripts/VALIDATION_EXAMPLES.md` - Usage examples
- `tests/test_validate_generated_iac.py` - Test suite
