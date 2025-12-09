// ATG Remote Service - Azure Container Instance Deployment
// Supports dev and integration environments with 64GB+ RAM

param environment string = 'dev'
param location string = resourceGroup().location
param containerImage string
param neo4jUri string
@secure()
param neo4jPassword string
@secure()
param apiKey string
param targetTenantId string

// Container configuration
var containerName = 'atg-${environment}'
var cpuCores = 4
var memoryInGb = 64

resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: containerName
  location: location
  properties: {
    containers: [
      {
        name: 'atg-service'
        properties: {
          image: containerImage
          ports: [
            {
              port: 8000
              protocol: 'TCP'
            }
          ]
          resources: {
            requests: {
              cpu: cpuCores
              memoryInGB: memoryInGb
            }
          }
          environmentVariables: [
            {
              name: 'NEO4J_URI'
              value: neo4jUri
            }
            {
              name: 'NEO4J_PASSWORD'
              secureValue: neo4jPassword
            }
            {
              name: 'API_KEY'
              secureValue: apiKey
            }
            {
              name: 'TARGET_TENANT_ID'
              value: targetTenantId
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
          ]
        }
      }
    ]
    osType: 'Linux'
    restartPolicy: 'Always'
    ipAddress: {
      type: 'Public'
      ports: [
        {
          port: 8000
          protocol: 'TCP'
        }
      ]
      dnsNameLabel: '${containerName}-${uniqueString(resourceGroup().id)}'
    }
  }
}

output containerUrl string = 'http://${containerGroup.properties.ipAddress.fqdn}:8000'
output containerFqdn string = containerGroup.properties.ipAddress.fqdn
output containerName string = containerGroup.name
