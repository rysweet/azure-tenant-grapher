# Azure Tenant Infrastructure Specification

_Generated at: 2025-08-27 19:55:08 UTC_

## Web

### app-azure-ae017bd4 (Microsoft.Web/sites)

> Azure App Service Web App named **simMgr160224hpcp4rein6** is deployed in the **northcentralus** region within the **ARTBAS-160224hpcp4rein6** resource group. This resource acts as a Campaign Manager web application, integrating with Application Insights (**simAI160224hpcp4rein6**) for monitoring and diagnostics via a dedicated connection string and instrumentation key. It is associated with an App Service Plan (**ASP-160224hpcp4rein6**), as indicated by hidden-related resource tags, ensuring the web app’s compute resources are managed and scaled per the plan’s configuration. Critical deployment metadata such as **Creator**, **DeployedBy**, **CampaignManager identifier**, and **source commit ID ([ANONYMIZED]de9f)** are tracked for compliance and auditability. No SKU, authentication, or advanced networking/security configuration is defined in this template, so default App Service settings will apply unless further specified; it is recommended to review SKU, access controls, and networking for production environments before deployment.

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
    - TAGGED_WITH ➔ res-generic-a510ec19 ()
    - TAGGED_WITH ➔ res-generic-8b8c2dd1 ()
    - TAGGED_WITH ➔ res-generic-5af99c88 ()
    - TAGGED_WITH ➔ res-generic-910ab80e ()
    - TAGGED_WITH ➔ res-generic-ce0b8c4c ()
    - TAGGED_WITH ➔ res-generic-2722887b ()
    - TAGGED_WITH ➔ res-generic-83e7f710 ()
    - TAGGED_WITH ➔ res-generic-4e39c451 ()
    - TAGGED_WITH ➔ res-generic-85862a49 ()
    - TAGGED_WITH ➔ res-generic-159528f2 ()

## Other

### res-this-d7aa1e71 (Microsoft.Network/networkInterfaces)

> This resource is an Azure network interface (NIC) named **cm160224hpcp4rein6-blob-private-endpoint.nic.[ANONYMIZED]** in the **northcentralus** region, designed to support a private endpoint connection to an Azure Blob Storage account. The NIC is integral for securely routing traffic from virtual networks to the storage account over a private IP, ensuring data remains within Microsoft's backbone and is not exposed to the public internet. While no SKU or additional networking/security properties are specified in this configuration, the NIC is automatically managed and associated with the private endpoint resource for blob storage, inheriting VNet and subnet assignments, and by default is subject to any network security group (NSG) rules within its subnet. Deployment must occur in the same resource group as the related private endpoint, and its lifecycle is tightly coupled to the private endpoint’s existence; thus, network policies or security controls should be managed at the subnet or NSG level. For full compliance and secure access, ensure that the subnet where this NIC is deployed has private endpoint network policies enabled or configured according to organizational standards.

- **Location:** northcentralus
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**

### res-this-e72a7aaa (ResourceGroup)

> This Resource Group appears to support a modest-scale web application or microservice deployment, indicated by the presence of an Azure Web App (Microsoft.Web/sites), a network interface, and a private DNS zone. The architecture suggests a single web-facing component, potentially connected to other Azure services or on-premises resources via private DNS and specific network configurations, with resources located in the 'northcentralus' region and DNS global scope. The combination of networking and web resources points to either a basic production or staging environment, emphasizing secure, internal resolution for service endpoints but lacking broader infrastructure elements typically seen in more complex or distributed workloads.

- **Location:** [ANONYMIZED]
- **Resource Group:** anon-rg
- **Subscription:** anon-sub
- **Properties:**
- **Relationships:**
    - CONTAINS ➔ res-privatelinkf-5738c167 (Microsoft.Network/privateDnsZones)
    - CONTAINS ➔ app-azure-ae017bd4 (Microsoft.Web/sites)
    - CONTAINS ➔ res-this-d7aa1e71 (Microsoft.Network/networkInterfaces)
