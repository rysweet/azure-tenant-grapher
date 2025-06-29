using System;
using System.Collections.Generic;
using AzureTenantGrapher.Processing;

namespace AzureTenantGrapher.Core
{
    public class TenantSpecification
    {
        public string TenantId { get; set; } = string.Empty;
        public List<SubscriptionInfo> Subscriptions { get; set; } = new();
        public List<ResourceInfo> Resources { get; set; } = new();
        public ProcessingStats Stats { get; set; } = new();
        public DateTime GeneratedOnUtc { get; set; }
    }

    public class SubscriptionInfo
    {
        public string SubscriptionId { get; set; } = string.Empty;
        public string DisplayName { get; set; } = string.Empty;
    }

    public class ResourceInfo
    {
        public string ResourceId { get; set; } = string.Empty;
        public string ResourceType { get; set; } = string.Empty;
        public string? Location { get; set; }
        public Dictionary<string, string>? Tags { get; set; }

        public string? ResourceGroup { get; set; }
        // For KeyVaults: list of discovered secrets (name, contentType only)
        public List<KeyVaultSecretInfo>? KeyVaultSecrets { get; set; }
    }

    public class KeyVaultSecretInfo
    {
        public string Name { get; set; } = string.Empty;
        public string? ContentType { get; set; }
    }
}
