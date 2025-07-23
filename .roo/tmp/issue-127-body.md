## Background

Currently, the `generate-iac` workflow and associated Bicep/ARM templates do not natively support the creation or replication of Azure Active Directory (AAD) users, groups, or RBAC assignments. This limitation prevents full automation of tenant setup, especially for scenarios requiring pre-populated accounts, group memberships, and role assignments. Manual post-deployment steps are error-prone and hinder reproducibility.

## Goals

- Automate the creation and replication of AAD users, groups, and RBAC assignments as part of the tenant provisioning process.
- Integrate Microsoft Graph Python SDK to perform these operations where Bicep/ARM lacks native support.
- Ensure the process is idempotent, robust, and easily invoked via CLI and automation scripts.

## Acceptance Criteria

### CLI/Flag Behavior

- Add a CLI flag/option (e.g., `--create-aad-objects` or similar) to `generate-iac` and/or related commands to trigger AAD user/group/RBAC creation.
- The flag must be documented in CLI help output and README.

### deploy.sh Integration

- `deploy.sh` (or equivalent automation) must invoke the AAD creation logic when the flag is set.
- The process must be idempotent: repeated runs do not create duplicates or fail on existing objects.
- Comprehensive error handling: failures in AAD operations must be logged and surfaced, but not cause silent data loss or inconsistent state.
- Logging: all actions (created, skipped, failed) must be logged with sufficient detail for troubleshooting.

### Authentication

- The process must authenticate to Microsoft Graph using a service principal or managed identity with sufficient permissions (e.g., `User.ReadWrite.All`, `Group.ReadWrite.All`, `Directory.ReadWrite.All`, `RoleManagement.ReadWrite.Directory`).
- Document required permissions and setup steps in the README.

### Test Coverage

- Unit tests for all new logic (user/group/RBAC creation, idempotency checks, error handling).
- Integration tests that exercise the end-to-end flow against a test tenant (using environment variables for secrets, never hardcoding credentials).
- E2E tests validating that a full deployment results in the expected AAD state.
- Tests must be self-contained and idempotent, using fixtures for setup/teardown.

### Documentation

- Update CLI and deployment documentation to describe the new flag/option, authentication requirements, and expected behavior.
- Provide example usage and troubleshooting tips.

## Out of Scope

- Creation or management of non-AAD resources (e.g., Azure subscriptions, resource groups, non-directory RBAC).
- Support for non-Microsoft identity providers.
- Manual intervention steps outside the automated workflow.

## References

- [Microsoft Graph Python SDK Documentation](https://learn.microsoft.com/en-us/graph/sdks/sdks-overview)
- [MS Graph API Permissions Reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Sample: Create users and groups with MS Graph Python SDK](https://github.com/microsoftgraph/msgraph-sdk-python)
- [Azure AD RBAC Concepts](https://learn.microsoft.com/en-us/azure/active-directory/roles/concept-understand-roles)