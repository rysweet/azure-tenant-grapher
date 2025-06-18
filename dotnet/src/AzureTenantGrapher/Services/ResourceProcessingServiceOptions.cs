using System;

namespace AzureTenantGrapher.Services
{
    /// <summary>
    /// Options for configuring the ResourceProcessingService.
    /// </summary>
    public class ResourceProcessingServiceOptions
    {
        public int BatchSize { get; set; } = 5;
        public int MaxDegreeOfParallelism { get; set; } = 4;
        public int MaxRetries { get; set; } = 3;
        public int InitialRetryDelayMs { get; set; } = 500;
        public bool UseExponentialBackoff { get; set; } = true;

        public static ResourceProcessingServiceOptions CreateDefault()
        {
            return new ResourceProcessingServiceOptions();
        }
    }
}
