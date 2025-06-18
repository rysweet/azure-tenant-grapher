using System;

namespace AzureTenantGrapher.Services
{
    /// <summary>
    /// Configuration options for the Azure Discovery Service.
    /// </summary>
    public class AzureDiscoveryServiceOptions
    {
        /// <summary>
        /// Gets or sets the Azure tenant ID.
        /// </summary>
        public string? TenantId { get; set; }

        /// <summary>
        /// Gets or sets the maximum number of retry attempts for Azure API calls.
        /// Default is 3.
        /// </summary>
        public int MaxRetries { get; set; } = 3;

        /// <summary>
        /// Gets or sets the initial delay in milliseconds for retry backoff.
        /// Default is 1000ms (1 second).
        /// </summary>
        public int InitialRetryDelayMs { get; set; } = 1000;

        /// <summary>
        /// Gets or sets whether to use exponential backoff for retries.
        /// Default is true.
        /// </summary>
        public bool UseExponentialBackoff { get; set; } = true;

        /// <summary>
        /// Creates default options from environment variables.
        /// </summary>
        /// <returns>AzureDiscoveryServiceOptions with default values.</returns>
        public static AzureDiscoveryServiceOptions CreateDefault()
        {
            return new AzureDiscoveryServiceOptions
            {
                TenantId = Environment.GetEnvironmentVariable("AZURE_TENANT_ID"),
                MaxRetries = int.TryParse(Environment.GetEnvironmentVariable("AZURE_MAX_RETRIES"), out var retries) ? retries : 3,
                InitialRetryDelayMs = int.TryParse(Environment.GetEnvironmentVariable("AZURE_RETRY_DELAY_MS"), out var delay) ? delay : 1000,
                UseExponentialBackoff = !bool.TryParse(Environment.GetEnvironmentVariable("AZURE_DISABLE_EXPONENTIAL_BACKOFF"), out var disable) || !disable
            };
        }
    }
}