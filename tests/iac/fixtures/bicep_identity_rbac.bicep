// User-assigned managed identity
resource myuami_identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'myuami'
  location: 'westus2'
  properties: {}
}

// VM with system-assigned identity
resource vmwithsysid_res 'Microsoft.Compute/virtualMachines@2023-03-01' = {
  name: 'vmwithsysid'
  location: 'eastus'
  identity: {
    type: 'SystemAssigned'
    principalId: '11111111-2222-3333-4444-555555555555'
  }
  properties: {}
}

// WebApp with user-assigned identity
resource webappwithuami_res 'Microsoft.Web/sites@2023-01-01' = {
  name: 'webappwithuami'
  location: 'eastus2'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.ManagedIdentity/userAssignedIdentities/myuami': {}
    }
  }
  properties: {}
}

// Role assignment
resource myra_ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: 'myra'
  properties: {
    roleDefinitionId: '/subscriptions/xxx/providers/Microsoft.Authorization/roleDefinitions/abc'
    principalId: '11111111-2222-3333-4444-555555555555'
    principalType: 'ServicePrincipal'
    scope: '/subscriptions/xxx/resourceGroups/yyy'
  }
}
