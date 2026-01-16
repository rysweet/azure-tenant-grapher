// Azure Lighthouse Delegation for Microsoft Sentinel Multi-Tenant Access
// This template enables cross-tenant management for Sentinel workspaces
// Deploy this template in the CUSTOMER tenant for each subscription or resource group

@description('The managing tenant ID (your service provider tenant)')
param managingTenantId string

@description('The authorization definitions for delegated access')
param authorizations array = [
  {
    // Service Principal for Automated Queries
    principalId: '<your-service-principal-object-id>'  // Replace with your SP Object ID
    roleDefinitionId: 'ab8e14d6-4a74-4a29-9ba8-549422addade'  // Microsoft Sentinel Contributor
    principalIdDisplayName: 'Sentinel Management SP'
  }
  {
    // Security Team Group for Manual Access
    principalId: '<your-security-team-group-id>'  // Replace with your Azure AD Group Object ID
    roleDefinitionId: 'acdd72a7-3385-48ef-bd42-f606fba81ae7'  // Security Reader
    principalIdDisplayName: 'Security Operations Team'
  }
]

@description('Registration definition name')
param registrationDefinitionName string = 'Sentinel MSSP Management'

@description('Registration definition description')
param registrationDefinitionDescription string = 'Delegated access for Sentinel MSSP operations - cross-tenant monitoring and incident response'

// Create unique GUID based on inputs for idempotency
var registrationId = guid(managingTenantId, subscription().subscriptionId, registrationDefinitionName)

// Registration Definition - Defines WHAT access is delegated
resource registrationDefinition 'Microsoft.ManagedServices/registrationDefinitions@2022-10-01' = {
  name: registrationId
  properties: {
    registrationDefinitionName: registrationDefinitionName
    description: registrationDefinitionDescription
    managedByTenantId: managingTenantId
    authorizations: authorizations
    eligibleAuthorizations: []  // Optional: PIM-enabled authorizations
  }
}

// Registration Assignment - Applies delegation to this scope (subscription or resource group)
resource registrationAssignment 'Microsoft.ManagedServices/registrationAssignments@2022-10-01' = {
  name: registrationId
  properties: {
    registrationDefinitionId: registrationDefinition.id
  }
}

// Outputs
output registrationDefinitionId string = registrationDefinition.id
output registrationAssignmentId string = registrationAssignment.id
output managingTenantId string = managingTenantId
output customerTenantId string = subscription().tenantId
output customerSubscriptionId string = subscription().subscriptionId
output delegationScope string = subscription().id
output deploymentTimestamp string = utcNow()
