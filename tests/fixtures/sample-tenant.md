# Sample Tenant

This is a sample tenant markdown file for testing the create-tenant CLI command.

```json
{
  "tenant": {
    "id": "tenant-001",
    "name": "Contoso Ltd",
    "subscriptions": [
      {
        "id": "sub-123",
        "name": "Contoso-Prod",
        "resource_groups": [
          {
            "id": "rg-001",
            "name": "rg-app",
            "location": "eastus",
            "resources": [
              {
                "id": "vm-001",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "appvm01",
                "properties": {},
                "tags": {}
              }
            ]
          }
        ]
      }
    ]
  },
  "identities": {
    "users": [{"id": "u1", "name": "Alice", "department": "IT", "job_title": "Admin"}],
    "groups": [{"id": "g1", "name": "IT Admins", "members": ["u1"]}],
    "service_principals": [{"id": "sp1", "name": "AppSvc"}],
    "managed_identities": [{"id": "mi1", "name": "AppMI"}],
    "admin_units": [{"id": "au1", "name": "HQ"}]
  },
  "rbac_assignments": [
    {"principal_id": "u1", "role": "Owner", "scope": "sub-123"}
  ],
  "relationships": [
    {"source_id": "appvm01", "target_id": "kv01", "type": "CAN_READ_SECRET"}
  ]
}
