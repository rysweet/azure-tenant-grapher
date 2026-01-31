#!/bin/bash
# Corrected deployment command - all on one line

az account set --subscription 97a0811f-fec4-470d-8fb8-7f9be05fcc6d && \
uv run atg generate-iac --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 --target-tenant-id 8d788dbd-cd1c-4e00-b371-3933a12c0f7d --output outputs/iac --format terraform --skip-conflict-check --skip-name-validation --skip-validation --no-auto-import-existing && \
uv run atg deploy --iac-dir outputs/iac --target-tenant-id 8d788dbd-cd1c-4e00-b371-3933a12c0f7d --subscription-id 97a0811f-fec4-470d-8fb8-7f9be05fcc6d --resource-group ATG-Test-Deployment-RG --location eastus --format terraform --dry-run
