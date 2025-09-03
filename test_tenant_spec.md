# Simple Test Tenant

This tenant demonstrates the improved feedback in the create-tenant command.

```json
{
  "tenant": {
    "id": "test-tenant-001",
    "display_name": "Test Feedback Tenant",
    "subscriptions": [
      {
        "id": "sub-001",
        "name": "Production Subscription",
        "resource_groups": [
          {
            "id": "rg-001",
            "name": "prod-web-rg",
            "location": "eastus",
            "resources": [
              {
                "id": "vm-001",
                "name": "prod-web-vm",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
                "properties": {}
              },
              {
                "id": "storage-001",
                "name": "prodwebstorage",
                "type": "Microsoft.Storage/storageAccounts",
                "location": "eastus",
                "properties": {}
              }
            ]
          }
        ]
      }
    ],
    "users": [
      {"id": "user-001", "display_name": "John Admin"},
      {"id": "user-002", "display_name": "Jane Developer"}
    ],
    "groups": [
      {"id": "group-001", "display_name": "Administrators"}
    ],
    "service_principals": [
      {"id": "sp-001", "display_name": "Web App Service"}
    ],
    "rbac_assignments": [
      {
        "principal_id": "user-001",
        "role": "Owner",
        "scope": "sub-001"
      }
    ],
    "relationships": [
      {
        "source_id": "user-001",
        "target_id": "group-001",
        "type": "MEMBER_OF"
      }
    ]
  }
}
```