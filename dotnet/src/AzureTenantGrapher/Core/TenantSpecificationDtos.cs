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
    }
}