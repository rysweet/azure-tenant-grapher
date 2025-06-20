# Azure resource types considered "high-value" or "sensitive" for attackers,
# based on Microsoft security documentation and best practices.
# This can be expanded or made dynamic in the future.

HIGH_VALUE_AZURE_RESOURCE_TYPES = [
    "KeyVault",  # Secrets, keys, certificates
    "SqlServer",  # Databases
    "SqlDatabase",
    "ManagedIdentity",  # Privileged identities
    "UserAssignedIdentity",
    "AppService",  # Web apps, API apps
    "FunctionApp",
    "StorageAccount",  # Data exfiltration
    "VirtualMachine",  # Compute, lateral movement
    "NetworkSecurityGroup",  # Controls access
    "Firewall",  # Controls access
    "LoadBalancer",  # Controls access
    "ApplicationGateway",
    "AKS",  # Kubernetes clusters
    "CosmosDB",  # NoSQL DB
    "RedisCache",  # Caching, session hijack
    "AutomationAccount",  # Runbooks, automation
    "LogicApp",  # Workflow automation
    "ServiceBus",  # Messaging
    "EventHub",  # Messaging
    "ApiManagement",  # API gateway
    "BastionHost",  # Secure access
    "VpnGateway",  # Network access
    "ExpressRoute",  # Network access
    "Disk",  # Data at rest
    "Snapshot",  # Data at rest
    "ContainerRegistry",  # Images, secrets
    "AppConfiguration",  # App settings
    "DataFactory",  # Data movement
    "DataLake",  # Data at scale
    "Synapse",  # Analytics
    "HDInsight",  # Analytics
    "CognitiveServices",  # AI/ML
    "MachineLearningWorkspace",
    "ManagedCluster",  # AKS
    "RoleAssignment",  # Privilege escalation
    "RoleDefinition",  # Privilege escalation
    "PolicyAssignment",  # Security controls
    "PolicyDefinition",  # Security controls
    "Subscription",  # Tenant-wide access
    "ResourceGroup",  # Resource scoping
]
