# Azure Tenant Infrastructure Specification

_Generated at: 2025-10-20 20:18:57 UTC_

## Storage

### storage-this-f2f06dda (Microsoft.Storage/storageAccounts)

> This Azure Storage Account (cm160224hpcp4rein6) is deployed in the northcentralus region within the ARTBAS-160224hpcp4rein6 resource group, serving as a secure, high-performance data store for the ARTBas Campaign Manager solution. The account utilizes the Hot access tier to optimize storage costs and performance for frequently accessed data, enforces minimum TLS1_2 for transport security, and requires HTTPS for all traffic, with encryption enabled for both blob and file services using Microsoft-managed keys. Public access to blobs is disabled to prevent unauthorized data exposure, while private endpoint connections are established for both Blob and File services, ensuring all traffic remains within the Azure private network for enhanced security and compliance. Network ACLs allow access for trusted Azure services and default to Allow, but can be further restricted; cross-tenant replication is disabled to maintain data residency. Key deployment details include comprehensive resource tagging for traceability, two private endpoint dependencies, and enforced platform encryption and security settings according to current enterprise standards.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - keyCreationTime: {'key1': '2024-02-17T00:56:27.5896940Z', 'key2': '2024-02-17T00:56:27.5896940Z'}
    - allowCrossTenantReplication: False
    - privateEndpointConnections: [{'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Storage/storageAccounts/cm160224hpcp4rein6/privateEndpointConnections/cm160224hpcp4rein6.467f1e41-5d70-463e-8f42-fbba89913ac0', 'name': 'cm160224hpcp4rein6.467f1e41-5d70-463e-8f42-fbba89913ac0', 'type': 'Microsoft.Storage/storageAccounts/privateEndpointConnections', 'properties': {'provisioningState': 'Succeeded', 'privateEndpoint': {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/cm160224hpcp4rein6-blob-private-endpoint'}, 'privateLinkServiceConnectionState': {'status': 'Approved', 'description': 'Auto-Approved', 'actionRequired': 'None'}}}, {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Storage/storageAccounts/cm160224hpcp4rein6/privateEndpointConnections/cm160224hpcp4rein6.3079f303-d7d6-4111-bce0-14c0d0a6d058', 'name': 'cm160224hpcp4rein6.3079f303-d7d6-4111-bce0-14c0d0a6d058', 'type': 'Microsoft.Storage/storageAccounts/privateEndpointConnections', 'properties': {'provisioningState': 'Succeeded', 'privateEndpoint': {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/cm160224hpcp4rein6-file-private-endpoint'}, 'privateLinkServiceConnectionState': {'status': 'Approved', 'description': 'Auto-Approved', 'actionRequired': 'None'}}}]
    - minimumTlsVersion: TLS1_2
    - allowBlobPublicAccess: False
    - networkAcls: {'ipv6Rules': [], 'bypass': 'AzureServices', 'virtualNetworkRules': [], 'ipRules': [], 'defaultAction': 'Allow'}
    - supportsHttpsTrafficOnly: True
    - encryption: {'services': {'file': {'keyType': 'Account', 'enabled': True, 'lastEnabledTime': '2024-02-17T00:56:27.9490219Z'}, 'blob': {'keyType': 'Account', 'enabled': True, 'lastEnabledTime': '2024-02-17T00:56:27.9490219Z'}}, 'keySource': 'Microsoft.Storage'}
    - accessTier: Hot
    - provisioningState: Succeeded
    - creationTime: 2024-02-17T00:56:27.5118651Z
    - primaryEndpoints: {'dfs': 'https://cm160224hpcp4rein6.dfs.core.windows.net/', 'web': 'https://cm160224hpcp4rein6.z14.web.core.windows.net/', 'blob': 'https://cm160224hpcp4rein6.blob.core.windows.net/', 'queue': 'https://cm160224hpcp4rein6.queue.core.windows.net/', 'table': 'https://cm160224hpcp4rein6.table.core.windows.net/', 'file': 'https://cm160224hpcp4rein6.file.core.windows.net/'}
    - primaryLocation: northcentralus
    - statusOfPrimary: available
- **Tags:**
    - Creator: ARTBAS
    - DeployedBy: mmelndezlujn@microsoft.com
    - ARTBasCampaignManager: 160224hpcp4rein6
    - LastDeployed: 2024-02-17 00:56:22Z
    - ARTBasType: CampaignManager
    - Commit: [ANONYMIZED]de9f
- **Relationships:**
    - TAGGED_WITH ➔ res-generic-85862a49 ()
    - TAGGED_WITH ➔ res-generic-4e39c451 ()
    - TAGGED_WITH ➔ res-generic-83e7f710 ()
    - TAGGED_WITH ➔ res-generic-2722887b ()
    - TAGGED_WITH ➔ res-generic-ce0b8c4c ()
    - TAGGED_WITH ➔ res-generic-910ab80e ()

## Web

### app-azure-ae017bd4 (Microsoft.Web/sites)

> Azure Function App "simMgr160224hpcp4rein6" is deployed in the "northcentralus" region within the "ARTBAS-160224hpcp4rein6" resource group to support campaign management and event-driven workloads as part of the ARTBAS architecture. It runs on an Elastic Premium (EP) plan ("ASP-160224hpcp4rein6"), with a dedicated container size of 1536 MB, one worker, and minimum elastic instance count set to 1 for scalable performance. Network security and connectivity are enforced via integration with a private subnet (“/subnets/snet-func” in vnet-ljio3xx7w6o6y), requires client certificates (“clientCertMode”: “Required”), disables anonymous inbound traffic by enforcing HTTPS-only access, and enables system-assigned managed identity for secure Key Vault integration (“[ANONYMIZED]y”: “SystemAssigned”). The app is tagged for deployment tracking, is instrumented with Application Insights for monitoring (instrumentation key: [ANONYMIZED]), and exposes public endpoints ("simmgr160224hpcp4rein6.azurewebsites.net") while outbound VNet routing is explicitly configured. To recreate this resource, ensure proper linkage to the Elastic Premium plan, VNet subnet, Application Insights resource, and match all critical security, scaling, and observability configurations.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
- **Tags:**
    - hidden-related:/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Web/serverfarms/ASP-160224hpcp4rein6: empty
    - Creator: ARTBAS
    - DeployedBy: mmelndezlujn@microsoft.com
    - ARTBasCampaignManager: 160224hpcp4rein6
    - LastDeployed: 2024-02-17 00:56:22Z
    - ARTBasType: CampaignManager
    - Commit: [ANONYMIZED]de9f
    - hidden-link: /app-insights-resource-id: [ANONYMIZED][ANONYMIZED]/providers/microsoft.insights/components/simAI160224hpcp4rein6
    - hidden-link: /app-insights-instrumentation-key: [ANONYMIZED]
    - hidden-link: /app-insights-conn-string: InstrumentationKey=[ANONYMIZED];IngestionEndpoint=https://northcentralus-0.in.applicationinsights.azure.com/;LiveEndpoint=https://northcentralus.livediagnostics.monitor.azure.com/;ApplicationId=[ANONYMIZED]
- **Relationships:**
    - TAGGED_WITH ➔ res-generic-159528f2 ()
    - TAGGED_WITH ➔ res-generic-85862a49 ()
    - TAGGED_WITH ➔ res-generic-4e39c451 ()
    - TAGGED_WITH ➔ res-generic-83e7f710 ()
    - TAGGED_WITH ➔ res-generic-2722887b ()
    - TAGGED_WITH ➔ res-generic-ce0b8c4c ()
    - TAGGED_WITH ➔ res-generic-910ab80e ()
    - TAGGED_WITH ➔ res-generic-5af99c88 ()
    - TAGGED_WITH ➔ res-generic-8b8c2dd1 ()
    - TAGGED_WITH ➔ res-generic-a510ec19 ()

## Other

### res-abhirame-79ff40a0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-abhirameswar-87456e0d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-acartamersoy-4c85d572 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adnanalam-b88c4597 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-aishwaryaset-3953b6bb (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-abujaye-87867ea0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-abujaye-279b8834 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-alecsolway-2b4e8216 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-alexklein-0256ab3e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-alfredpennyw-cbb44dea (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-amirabramovi-0648cd7d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-amparopirain-b7bc6eb2 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-amysantiago-2e56edb7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresjaurri-9d86a36e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresrios-2987a4b9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresrios-a237fa65 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresrios-09093292 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresrios-c9e6f808 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andresrios-6e018ce6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andycoles-2def52b3 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andrewwicker-df7f7120 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andycoles-2d02448e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andyye-e309e267 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-anjelpatel-3b55947b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ankitsrivast-8806ce6f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ankitsrivast-5f6ee5a6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nareshannam-8038698d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ajeetprakash-4c334806 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-arijitbanerj-578cfce7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-arjunchakrab-64df71f6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-artorias-eb5834ef (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-d238eb04 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-anushsankara-6b245f61 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-de383426 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-355f2587 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-bbc2d419 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-cdab9ab7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-a49b3222 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-dc3b7d52 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-0d0031ba (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hemanthsread-bf135463 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-himanshusrea-f7b531d9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-himanisreadm-a4b7d126 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-tonytwumbari-0a07098a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-avychalla-10ab46c0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shonalibalak-7e367fd1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-umabatchu-99e6ea0f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-bennycorak-29e86d13 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-blaineherro-9561ad20 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-brianhooperd-a1a00fc2 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-benjaminrode-f5bac3ac (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-brownie-7e8b3717 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-brucewayne-a8ac08b7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-bruno-f063a364 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-ad439e1a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-cameronandre-2c0301bb (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-cameronthoma-062a7ad7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-carmelruball-f31ca007 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-chiderabirin-d91091ec (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-chadwicknabo-eb7360d1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-cindypetroch-c1d5c29a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-cliffcazaree-b88e2689 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-continentalu-13c6318b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adamcook-f8a97f00 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-coryclowes-ef779594 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-chloeramirez-bf522bbb (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-cristalruiz-98933cde (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-christiansei-0dce7575 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-christiansei-cae8dad2 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-charlottesis-5097e029 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-curtdennis-09e7f939 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-danieldawson-6df9f69e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-danabaril-d99c1274 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-davidmarshal-aeaa8bfe (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dianadamenov-09727a9f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dianadamenov-339c7943 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-79e12c99 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-90be5233 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-106eaf28 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dianaiftimie-e690032e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dianaiftimie-6de06e2c (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dayquanjulie-0242851e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-doronbarzila-a8636e54 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dustinstewar-9aec0629 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dustinduran-e497577f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-edirgarciala-6e256f19 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ethankwan-5773ae8e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-elliotharper-91e7bbd9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-emmettbrown-7c0e0ca0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-0483f14b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ericajeppsen-f338d88e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-fernandovbmg-f0dae576 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-floralday-97380c93 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-aartighangho-c8eba89d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ginowaite-aff60600 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-gagandeepkoh-c640af23 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-garylopez-301a8b80 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-garylopez-5401fc56 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-gregcrow-d4792d13 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-gregoriobaue-7dade179 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-haijunzhai-a27f18ab (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hassanbadir-f549c8cd (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hemaldesai-fa13e9a1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hemaldesai-3738d9ed (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hamidrezasag-a7c05774 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ianhellen-7471682d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-idanlahav-ec71c730 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jakeperalta-b33c0397 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jameshetfiel-c6a91fc4 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jamiehuang-fa90b753 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jasontodd-7f00d555 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jeanlucpicar-7bdea5e7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-johnlambert-9099a15f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-josema-9910dd31 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jaystokes-ec892e02 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-juliakiselev-a196a4fc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-jugalparikh-50ec4b01 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-justinabaran-ea38a91a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-katyruss-bc11ce6b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-kimi-8821ea06 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-3bffc610 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-kiranbagepal-64ae7f06 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-kiranbagepal-2b67c316 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-kirkhammett-9ae0ee07 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-kiranlakkara-3cd626a4 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-luisarzola-800fbd3f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-leiaorgana-2c7ff1af (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lidiabanvelo-01c1a1ba (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lilianliebl-85451612 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-liminyang-e048349e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lironcohen-3f410c78 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lizarezina-1784dcc6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lenamcallist-2af798fe (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-logan-2af2441c (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-d725c05e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-1178eea0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-luigi-56d25717 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-luisazanza-a4bab2bc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-lukeskywalke-95c22760 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-mohsenalimom-192640ca (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-manny-b54d4f88 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-marcmarino-033f5b34 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-martymcfly-1ccfa213 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-maximiliantu-3cae7c98 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-mbvulnuser-cc86bd58 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-fatihbulut-631958bc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-megaman-7b336561 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-melissaailem-6a7f9cd4 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-martinfontai-0dda94a5 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-michaelhowar-bdd2f14e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-michaelmelon-ced9f0ed (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-minwei-58bbd8f1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-marcmarino-659c860e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-manuelmelend-c136562b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-mosesfadden-dfdc3d8e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-martinpoulio-7599a9da (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-maimoonsiddi-14842f7d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-marcusvarela-d2c65f72 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-mauriciovela-21636678 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-marikowakaba-bc7465b3 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-naveedahmad-a8a66ed3 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nelsoncheng-4f80ee5e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nitinkumargo-29813866 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nildaflitt-9ed4c940 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nigelkumanku-913dc53a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nigelkumanku-212f85d5 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-noabratman-84165f79 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-noahbaertsch-464098f9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-nonachristia-9a5e3aa1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-010ba13c (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-noyhaluba-cf9ccd3b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-natalierusso-611e1828 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ornstein-ba13603b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-pamelabhatta-a0734c54 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-peterparker-5838328e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-prateekjain-bda43bbf (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-protoman-2216dd96 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-74016ff2 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-23014a97 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-redteamescal-1977b39b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-richardgrays-3ed4b8b9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-roberttrevin-f725a3dc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ryankivett-03d15fcd (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ryancobb-8bb09423 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-ryansweet-3abdf8a6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-samiaitouahm-8a4a9f06 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sarahwilliam-613bf429 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sivagangadha-4d696394 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shaebailey-782ddd44 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shaunfaulds-9c8ef046 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shaunfaulds-0fdc0c59 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shirleysalas-d2291a7f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shiv-40f602b1 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shriramlaksh-cc5be8e7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sif-780d7604 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-simredteamag-9a11718d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-solaireofast-1592cc8d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-spongebob-780aee62 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-f0f4bfaa (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shanmugaraja-48ae4a73 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-shanmugaraja-d05b2b7a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-stefansellme-15a5e65b (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-subiepatel-d6e98e58 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-subiepatel-a313c3ce (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-surajjacob-67990c2f (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sumamovva-64253a50 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-surinahn-5469c275 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sulaimanvesa-848ec8b0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sulaimanvesa-55a538ad (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-anandmudgeri-513f0814 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-andrewzhao-385f587e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-quangnguyen-b15fdf08 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sumamovva-3aecef68 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-yiranwu-0c026ad6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-trevordelgad-4eba74a0 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-teamcondemou-f1ed2ff9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-teamcondemou-7c92eb47 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-teeratornkad-3f28265a (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-340b415d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-c1fcb1b4 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-20775974 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-09542b68 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-4bd1836c (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-894d47cf (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-084b2479 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-c7c76efd (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-b55d7da9 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testmanny-f18c25fc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-c1976e66 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-496e63a8 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-5d5650c5 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-c72f46cc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-c8bcbd7d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testscenario-2f73f0d6 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testscenario-ffe3f0ab (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testscenario-e7bb248e (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-theodorebord-71309ff5 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-thomasroccia-79330d05 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-tianweichen-097373d4 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-tianweichen-8f779f0d (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-teeratornkad-c9c987a7 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-tomgreen-fd81e409 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-tongwang-93f09d43 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-victorkrepp-948ca9fc (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-vineetkhare-7dfad095 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-siyuewang-caed9c40 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-whitneyflora-c85fce2c (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-williamblum-9e06cb86 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-williamriker-19c3d5c3 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-xpiaryancobb-b62bdcae (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-yingqiliu-a667e014 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-yotamsegev-b1c87ca8 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-zixiaochen-ab659001 (Microsoft.Graph/users)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-hybridworkmo-992b640e (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-azureatpdefe-60070135 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-regulatoryco-cf15dff3 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-internalaudi-a3ddd8ca (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-2589a3d8 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-eligibleglob-ca42ec7f (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-intermediary-bfb88259 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-platformappo-63b9a556 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-test-d940322a (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-securityuser-95bfe079 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncbrowse-ca8fbee4 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsupdatepro-ffab85c6 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-campusrecrui-840778a3 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncbrowse-1329d081 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-logistics-85653661 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncoperat-071ceca9 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-eleveatedpla-f40fd53d (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testgroupmv-5f279073 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-platformuser-e7d77b78 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-assetmanagem-108241ab (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-sreadmins-809dfd83 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncadmins-a5412285 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-researchpart-aa9ad5f8 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-fleetmanagem-0a19efea (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncoperat-2887a746 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-securityinci-4139cea3 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-atevetsubscr-1d745aca (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsadmins-8006b920 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-rctobservers-083eccc1 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-continentalh-5e9b9861 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncadmins-cc3cb000 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-wargamingrea-74f04522 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncbrowse-6df3635a (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-205c6a88 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-crowdstriket-80e71e28 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-azureatpdefe-c8a3d2c3 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncadmins-379261ca (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncpasswo-2b9611cf (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncpasswo-f0bd9c46 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsupdatepro-8ce36367 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-securitycopi-85183887 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-intuneboardi-89cac2fe (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-costmanageme-3e44a506 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-53b1b090 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-datagovernan-cd943104 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-08d451f7 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-msecadapt-95c653c3 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-allcompany-7843dc9c (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-expanedplatf-81378f4f (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-atevetsubscr-82e66129 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsupdatepro-886d42fd (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-masterdatama-e7058d16 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsadmins-8dc89bc5 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncoperat-8aa82e79 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-simulandapi-5a7725fb (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-rctusers-2e7e85a0 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-demosite-8e54985c (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-securityrese-581a2783 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-yubikeytest-4a70996e (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-datastrategy-d9b4fb38 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-continentalh-6cd9ab37 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-intunepolicy-f7dacd6f (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-allcompany-43aa786a (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-adsyncpasswo-2000ab93 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-atevetappadm-b882fae9 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-performancem-cd3716a2 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-4bff7415 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-messagingand-9b43e89e (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-staticanalys-0fa848ea (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-qualitycontr-04707366 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-7c0b96a6 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-azureuseracc-39bc0223 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-controllersh-a42c4b8e (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-dnsadmins-8ca5d7de (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-disablemfa-80cc3458 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-testteam-34c33b81 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-attackbothar-243f476d (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-generic-83b3a583 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-rctcontrolsu-4c4136d6 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-rcttreatment-e8f1946d (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-azureatpdefe-451b07e5 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-aisocadmins-b9b252c2 (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-rctadmins-c28b988d (Microsoft.Graph/groups)

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-this-d7aa1e71 (Microsoft.Network/networkInterfaces)

> This Azure network interface (NIC) resource, named "cm160224hpcp4rein6-blob-private-endpoint.nic.[ANONYMIZED]," is provisioned in the "northcentralus" region and is designed to provide secure, private connectivity between a Private Endpoint and an Azure Blob Storage account ("cm160224hpcp4rein6.blob.core.windows.net"). The NIC is configured with a single IPv4 dynamic private IP address (10.100.1.5) allocated within the "snet-pe" subnet of the "vnet-ljio3xx7w6o6y" virtual network, ensuring traffic between the Storage Account and clients on the VNet remains on the Microsoft backbone rather than traversing the public Internet. The resource is associated with a Private Endpoint ("cm160224hpcp4rein6-blob-private-endpoint") and linked to the "blob" Private Link Service, specifying "blob" as both the group ID and required member name for scoping and access control. Security and compliance settings include IP forwarding and TCP state tracking both disabled, outbound port 25 traffic allowed, and encryption not enabled on the VNet connection. This NIC must be deployed within the resource group "ARTBAS-160224hpcp4rein6," and is essential for enforcing private, isolated access to sensitive data in blob storage, meeting architecture requirements for network segmentation and restricted data exfiltration paths.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - resourceGuid: [ANONYMIZED]
    - ipConfigurations: [{'name': 'privateEndpointIpConfig.50a2efda-fd32-464c-9275-5019f9015841', 'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/networkInterfaces/cm160224hpcp4rein6-blob-private-endpoint.nic.fb5d0aaa-3647-4862-9ca4-70a4038aa2fd/ipConfigurations/privateEndpointIpConfig.50a2efda-fd32-464c-9275-5019f9015841', 'etag': 'W/"9f043294-dfd6-4989-ad66-bde54f9eea5b"', 'type': 'Microsoft.Network/networkInterfaces/ipConfigurations', 'properties': {'provisioningState': 'Succeeded', 'privateIPAddress': '10.100.1.5', 'privateIPAllocationMethod': 'Dynamic', 'subnet': {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe'}, 'primary': True, 'privateIPAddressVersion': 'IPv4', 'privateLinkConnectionProperties': {'groupId': 'blob', 'requiredMemberName': 'blob', 'fqdns': ['cm160224hpcp4rein6.blob.core.windows.net']}}}]
    - dnsSettings: {'dnsServers': [], 'appliedDnsServers': [], 'internalDomainNameSuffix': 'ugusu541iapezejjxuicgvwqsc.ex.internal.cloudapp.net'}
    - macAddress: 
    - vnetEncryptionSupported: False
    - enableIPForwarding: False
    - disableTcpStateTracking: False
    - hostedWorkloads: []
    - tapConfigurations: []
    - privateEndpoint: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/cm160224hpcp4rein6-blob-private-endpoint'}
    - nicType: Standard
    - allowPort25Out: True
    - defaultOutboundConnectivityEnabled: False
    - auxiliaryMode: None
    - auxiliarySku: None

### res-generic-e72a7aaa (ResourceGroup)

- **Location:** [ANONYMIZED]
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
- **Relationships:**
    - CONTAINS ➔ res-this-d7aa1e71 (Microsoft.Network/networkInterfaces)
    - CONTAINS ➔ app-azure-ae017bd4 (Microsoft.Web/sites)
    - CONTAINS ➔ res-this-5738c167 (Microsoft.Network/privateDnsZones)
    - CONTAINS ➔ res-this-9d55d2df (Microsoft.Network/privateEndpoints)
    - CONTAINS ➔ res-this-7dbfa89e (microsoft.insights/components)
    - CONTAINS ➔ storage-this-f2f06dda (Microsoft.Storage/storageAccounts)
    - CONTAINS ➔ res-private-c8e33dfe (Microsoft.Network/privateDnsZones)
    - CONTAINS ➔ res-this-22fb73c8 (Microsoft.Network/privateEndpoints)
    - CONTAINS ➔ res-this-e98dd9fa (Microsoft.Network/privateDnsZones/virtualNetworkLinks)
    - CONTAINS ➔ res-this-7470e981 (Microsoft.Network/privateEndpoints)

### res-this-5738c167 (Microsoft.Network/privateDnsZones)

> This resource defines a private DNS zone named **privatelink.function.simMgr160224hpcp4rein6** of type `Microsoft.Network/privateDnsZones` in the **global** location, designed for secure, private name resolution of Azure resources integrating with Private Link, notably Azure Functions. With a maximum capacity of **25,000 record sets** and support for up to **1,000 virtual network links**—including **100 links with auto-registration**—the DNS zone efficiently scales to accommodate extensive private endpoint connectivity across multiple Azure virtual networks. No SKU tier is specified, and the resource currently contains **one record set** with no virtual network links, indicating it's provisioned but not yet attached to any VNETs. Security and isolation are inherent, as private DNS zones facilitate name resolution strictly within trusted Azure networks, preventing public DNS exposure and supporting compliance requirements for internal service access. Deployment should occur within a designated resource group, and engineers must ensure virtual networks are properly linked and, if required, registration enabled for seamless private DNS integration; note that this resource does not rely on any pre-existing DNS infrastructure but will serve any connected private endpoints once network links are established.

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - internalId: [ANONYMIZED][ANONYMIZED][ANONYMIZED]MWY3ODsw
    - maxNumberOfRecordSets: 25000
    - maxNumberOfVirtualNetworkLinks: 1000
    - maxNumberOfVirtualNetworkLinksWithRegistration: 100
    - numberOfRecordSets: 1
    - numberOfVirtualNetworkLinks: 0
    - numberOfVirtualNetworkLinksWithRegistration: 0
    - provisioningState: Succeeded

### res-this-9d55d2df (Microsoft.Network/privateEndpoints)

> This Azure Private Endpoint resource, named **simKV160224hpcp4rein6-keyvault-private-endpoint**, provides secure, private connectivity from a designated virtual network subnet (`vnet-ljio3xx7w6o6y/snet-pe` in the **ARTBAS-160224hpcp4rein6** resource group) to the Azure Key Vault `simKV160224hpcp4rein6`, located in the **northcentralus** region. The endpoint establishes a private link service connection (`[ANONYMIZED]ction`) approved for access to the Key Vault service (`groupIds: vault`), thereby ensuring that all Key Vault traffic remains on the Microsoft backbone and is isolated from the public internet for enhanced security and compliance. The resource leverages an automatically managed network interface (`simKV160224hpcp4rein6-keyvault-private-endp.nic.[ANONYMIZED]`) and is provisioned for IPv4 addressing per `ipVersionType`. Deployment of this endpoint is critically dependent on the existence of the target Key Vault and the specified virtual network and subnet; it should be considered part of a tightly controlled perimeter architecture where private resource traffic is mandated, and public access is explicitly restricted or disabled. No SKU is required; no custom DNS or manual connections are configured—default settings are used for network and DNS integration.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - resourceGuid: [ANONYMIZED]
    - privateLinkServiceConnections: [{'name': 'KeyVaultPrivateLinkConnection', 'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/simKV160224hpcp4rein6-keyvault-private-endpoint/privateLinkServiceConnections/KeyVaultPrivateLinkConnection', 'etag': 'W/"09b3e90b-d378-4b90-8b25-5bed145fd904"', 'properties': {'provisioningState': 'Succeeded', 'privateLinkServiceId': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.KeyVault/vaults/simKV160224hpcp4rein6', 'groupIds': ['vault'], 'privateLinkServiceConnectionState': {'status': 'Approved', 'description': '', 'actionsRequired': 'None'}}, 'type': 'Microsoft.Network/privateEndpoints/privateLinkServiceConnections'}]
    - manualPrivateLinkServiceConnections: []
    - customNetworkInterfaceName: 
    - subnet: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe'}
    - ipConfigurations: []
    - networkInterfaces: [{'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/networkInterfaces/simKV160224hpcp4rein6-keyvault-private-endp.nic.db1e33b0-d99f-43ed-b2e6-f71b2a5188c1'}]
    - customDnsConfigs: []
    - ipVersionType: IPv4

### res-this-7dbfa89e (microsoft.insights/components)

> This resource is an Azure Application Insights component ("simAI160224hpcp4rein6") deployed in the North Central US region to provide full-stack monitoring and telemetry for a web application, supporting real-time diagnostics and analytics. It is configured with Application_Type set to "web", uses the Bluefield flow, and is provisioned to ingest telemetry via the Log Analytics workspace "[ANONYMIZED][ANONYMIZED]/providers/microsoft.operationalinsights/workspaces/la-160224hpcp4rein6", with data retention set to 90 days for compliance and historical analysis. Public network access for both ingestion and query operations is enabled, ensuring connectivity for external monitoring agents and integration with REST APIs; its connection string and instrumentation key are pre-configured to securely route telemetry traffic. Key identifiers such as ApplicationId and AppId, as well as tagging for ownership, deployment tracking, and campaign management, facilitate resource governance and traceability. Deployment is tied to the "ARTBAS-160224hpcp4rein6" resource group, and special consideration should be given to integration with the specified Log Analytics workspace and network accessibility for secure telemetry ingestion and query.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - ApplicationId: simAI160224hpcp4rein6
    - AppId: [ANONYMIZED]
    - Application_Type: web
    - Flow_Type: Bluefield
    - Request_Source: rest
    - InstrumentationKey: [ANONYMIZED]
    - ConnectionString: InstrumentationKey=[ANONYMIZED];IngestionEndpoint=https://northcentralus-0.in.applicationinsights.azure.com/;LiveEndpoint=https://northcentralus.livediagnostics.monitor.azure.com/;ApplicationId=[ANONYMIZED]
    - Name: simAI160224hpcp4rein6
    - CreationDate: 2024-02-17T00:56:57.318407+00:00
    - TenantId: [ANONYMIZED]
    - provisioningState: Succeeded
    - SamplingPercentage: None
    - RetentionInDays: 90
    - WorkspaceResourceId: [ANONYMIZED][ANONYMIZED]/providers/microsoft.operationalinsights/workspaces/la-160224hpcp4rein6
    - IngestionMode: LogAnalytics
    - publicNetworkAccessForIngestion: Enabled
    - publicNetworkAccessForQuery: Enabled
    - Ver: v2
- **Tags:**
    - Creator: ARTBAS
    - DeployedBy: mmelndezlujn@microsoft.com
    - ARTBasCampaignManager: 160224hpcp4rein6
    - LastDeployed: 2024-02-17 00:56:22Z
    - ARTBasType: CampaignManager
    - Commit: [ANONYMIZED]de9f
- **Relationships:**
    - TAGGED_WITH ➔ res-generic-85862a49 ()
    - TAGGED_WITH ➔ res-generic-4e39c451 ()
    - TAGGED_WITH ➔ res-generic-83e7f710 ()
    - TAGGED_WITH ➔ res-generic-2722887b ()
    - TAGGED_WITH ➔ res-generic-ce0b8c4c ()
    - TAGGED_WITH ➔ res-generic-910ab80e ()

### res-private-c8e33dfe (Microsoft.Network/privateDnsZones)

> Private DNS Zone named **privatelink.file.core.windows.net** (type: Microsoft.Network/privateDnsZones) is deployed in the global Azure region to enable private DNS resolution for Azure Files accessed via Private Endpoints. This DNS zone allows secure, internal name resolution for storage accounts using Azure Files over a private link, eliminating public exposure and ensuring compliant, isolated connectivity within your virtual network architecture. Key configuration includes a maximum capacity of **25,000 record sets** and support for up to **1,000 virtual network links** (with **100 allowed for automatic registration**), optimizing scalability and multi-network support. The resource currently has **3 DNS record sets** and is linked to **1 virtual network**, operating in a successfully provisioned state. There are no SKU-specific settings, and no custom tags are applied; special deployment considerations include assigning this zone to the appropriate resource group and ensuring all related Private Endpoints and virtual networks are correctly configured for private DNS integration and name resolution.

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - internalId: [ANONYMIZED][ANONYMIZED][ANONYMIZED]Y2E0OTsw
    - maxNumberOfRecordSets: 25000
    - maxNumberOfVirtualNetworkLinks: 1000
    - maxNumberOfVirtualNetworkLinksWithRegistration: 100
    - numberOfRecordSets: 3
    - numberOfVirtualNetworkLinks: 1
    - numberOfVirtualNetworkLinksWithRegistration: 0
    - provisioningState: Succeeded

### res-this-22fb73c8 (Microsoft.Network/privateEndpoints)

> This resource is an Azure Private Endpoint named "cm160224hpcp4rein6-file-private-endpoint" deployed in the "northcentralus" region, which provides secure, private connectivity between resources in a virtual network and the Azure Storage Account "cm160224hpcp4rein6" (specifically for Azure Files service) by mapping traffic through a dedicated network interface. It is connected to the "snet-pe" subnet within the virtual network "vnet-ljio3xx7w6o6y" and is associated with the resource group "ARTBAS-160224hpcp4rein6." The private link service connection is configured for the "file" groupId, ensuring only the Azure Files endpoint is exposed privately, with the connection status set to "Approved" (Auto-Approved) for streamlined access management. The Private Endpoint is IPv4-only, does not specify a custom network interface name or custom DNS configuration, and does not use manual approval, relying instead on auto-approval to minimize administrative overhead. Deployment requires the referenced virtual network, subnet, and storage account to exist, and creating this endpoint is essential for enforcing secure, compliant access to Azure Files by eliminating public exposure and routing access exclusively through Azure backbone infrastructure.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - resourceGuid: [ANONYMIZED]
    - privateLinkServiceConnections: [{'name': 'StorageFilePrivateLinkConnection', 'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/cm160224hpcp4rein6-file-private-endpoint/privateLinkServiceConnections/StorageFilePrivateLinkConnection', 'etag': 'W/"b21f9c97-a28e-42e1-9aa7-71c3adf9aad5"', 'properties': {'provisioningState': 'Succeeded', 'privateLinkServiceId': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Storage/storageAccounts/cm160224hpcp4rein6', 'groupIds': ['file'], 'privateLinkServiceConnectionState': {'status': 'Approved', 'description': 'Auto-Approved', 'actionsRequired': 'None'}}, 'type': 'Microsoft.Network/privateEndpoints/privateLinkServiceConnections'}]
    - manualPrivateLinkServiceConnections: []
    - customNetworkInterfaceName: 
    - subnet: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe'}
    - ipConfigurations: []
    - networkInterfaces: [{'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/networkInterfaces/cm160224hpcp4rein6-file-private-endpoint.nic.01d50b0e-7da6-4343-a4e3-243f95505ba8'}]
    - customDnsConfigs: []
    - ipVersionType: IPv4

### res-this-e98dd9fa (Microsoft.Network/privateDnsZones/virtualNetworkLinks)

> This resource defines a Private DNS Zone Virtual Network Link, connecting the Azure private DNS zone **privatelink.vaultcore.azure.net** with the virtual network **vnet-ljio3xx7w6o6y** in the resource group **ARTBAS-160224hpcp4rein6**. The link enables secure, internal name resolution for Azure Key Vault private endpoints within the specified VNet, ensuring that all traffic to vaultcore resources can be resolved privately without relying on public DNS. The **registrationEnabled** property is set to **false**, preventing automatic DNS record registration for virtual machines in the linked VNet, which maintains more controlled DNS management and security. The resource is deployed in the **global** Azure location, and is essential for supporting private connectivity patterns often required for compliance and secure architectures. Critical dependencies include the existence of both the appropriate Private DNS Zone and the target virtual network; careful configuration is advised to ensure correct linkage and that registration settings match organizational requirements.

- **Location:** global
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - registrationEnabled: False
    - virtualNetwork: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y'}
    - virtualNetworkLinkState: Completed

### res-this-7470e981 (Microsoft.Network/privateEndpoints)

> This Azure Private Endpoint resource (exec160224hpcp4rein6-blob-private-endpoint) provides secure, private connectivity from a subnet within the vnet-ljio3xx7w6o6y virtual network (subnet: snet-pe) in the northcentralus region to the blob service of the exec160224hpcp4rein6 Storage Account. The private endpoint is integrated with the Storage Account using an auto-approved Private Link Service Connection (group ID: blob), ensuring data traffic between resources stays entirely within the Azure backbone network and is not exposed to the public internet. This endpoint depends on an existing virtual network, subnet, and storage account, and it is associated with a dedicated network interface for private communications. The configuration enforces IPv4 addressing and does not assign custom DNS or manual private link connections, streamlining connectivity for compliance and security best practices. Deployed in the ARTBAS-160224hpcp4rein6 resource group, this setup is ideal for workloads requiring enhanced data privacy and regulatory compliance.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - resourceGuid: [ANONYMIZED]
    - privateLinkServiceConnections: [{'name': 'StorageBlobPrivateLinkConnection', 'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/exec160224hpcp4rein6-blob-private-endpoint/privateLinkServiceConnections/StorageBlobPrivateLinkConnection', 'etag': 'W/"99e7dc07-77c5-489c-b0d2-a67f20f5f84b"', 'properties': {'provisioningState': 'Succeeded', 'privateLinkServiceId': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Storage/storageAccounts/exec160224hpcp4rein6', 'groupIds': ['blob'], 'privateLinkServiceConnectionState': {'status': 'Approved', 'description': 'Auto-Approved', 'actionsRequired': 'None'}}, 'type': 'Microsoft.Network/privateEndpoints/privateLinkServiceConnections'}]
    - manualPrivateLinkServiceConnections: []
    - customNetworkInterfaceName: 
    - subnet: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe'}
    - ipConfigurations: []
    - networkInterfaces: [{'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/networkInterfaces/exec160224hpcp4rein6-blob-private-endpoint.nic.f482636a-11a9-41e7-a32b-0f4fd2548d34'}]
    - customDnsConfigs: []
    - ipVersionType: IPv4

### res-generic-96e6a0d6 (Microsoft.Network/networkInterfaces)

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
    - provisioningState: Succeeded
    - resourceGuid: [ANONYMIZED]
    - ipConfigurations: [{'name': 'privateEndpointIpConfig.1e12a750-4a40-457c-ab96-6f558b65e55a', 'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/networkInterfaces/exec160224hpcp4rein6-file-private-endpoint.nic.efd5da1b-8201-494e-a3c8-44503c7b0a9a/ipConfigurations/privateEndpointIpConfig.1e12a750-4a40-457c-ab96-6f558b65e55a', 'etag': 'W/"94eee6a7-99b1-4059-9ffc-5fe65fb5f88d"', 'type': 'Microsoft.Network/networkInterfaces/ipConfigurations', 'properties': {'provisioningState': 'Succeeded', 'privateIPAddress': '10.100.1.6', 'privateIPAllocationMethod': 'Dynamic', 'subnet': {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe'}, 'primary': True, 'privateIPAddressVersion': 'IPv4', 'privateLinkConnectionProperties': {'groupId': 'file', 'requiredMemberName': 'file', 'fqdns': ['exec160224hpcp4rein6.file.core.windows.net']}}}]
    - dnsSettings: {'dnsServers': [], 'appliedDnsServers': [], 'internalDomainNameSuffix': 'ugusu541iapezejjxuicgvwqsc.ex.internal.cloudapp.net'}
    - macAddress: 
    - vnetEncryptionSupported: False
    - enableIPForwarding: False
    - disableTcpStateTracking: False
    - hostedWorkloads: []
    - tapConfigurations: []
    - privateEndpoint: {'id': '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/exec160224hpcp4rein6-file-private-endpoint'}
    - nicType: Standard
    - allowPort25Out: True
    - defaultOutboundConnectivityEnabled: False
    - auxiliaryMode: None
    - auxiliarySku: None
