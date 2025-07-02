# Sample Tenant

## Resource Groups

- name: demo-rg
  location: eastus

## Resources

- type: Microsoft.Storage/storageAccounts
  name: demostorage
  resourceGroup: demo-rg
  location: eastus
