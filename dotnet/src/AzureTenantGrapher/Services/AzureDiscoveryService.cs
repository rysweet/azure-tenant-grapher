using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Azure;
using Azure.Core;
using Azure.Identity;
using Azure.ResourceManager;
using Azure.ResourceManager.Resources;
using Microsoft.Extensions.Logging;
using Azure.Security.KeyVault.Secrets;
using AzureTenantGrapher.Core;

namespace AzureTenantGrapher.Services
{
    /// <summary>
    /// Information about an Azure subscription.
    /// </summary>
    // Removed: SubscriptionInfo and ResourceInfo records.
    // Use AzureTenantGrapher.Core.SubscriptionInfo and AzureTenantGrapher.Core.ResourceInfo instead.

    /// <summary>
    /// Service for discovering Azure subscriptions and resources.
    ///
    /// This service encapsulates all Azure API interactions for resource discovery,
    /// providing proper error handling, authentication fallback, and clear interfaces
    /// for testing and dependency injection.
    /// </summary>
    public class AzureDiscoveryService
    {
        private readonly ILogger<AzureDiscoveryService> _logger;
        private readonly AzureDiscoveryServiceOptions _options;
        private readonly ArmClient _armClient;
        private readonly TokenCredential _credential;
        private readonly List<SubscriptionInfo> _cachedSubscriptions = new();

        public AzureDiscoveryService(
            ILogger<AzureDiscoveryService> logger,
            AzureDiscoveryServiceOptions? options = null,
            TokenCredential? credential = null)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _options = options ?? AzureDiscoveryServiceOptions.CreateDefault();

            // Initialize credential with fallback to AzureCliCredential
            _credential = credential ?? CreateCredentialWithFallback();
            _armClient = new ArmClient(_credential);
        }

        /// <summary>
        /// Gets the cached list of discovered subscriptions.
        /// </summary>
        public virtual IReadOnlyList<SubscriptionInfo> CachedSubscriptions => _cachedSubscriptions.AsReadOnly();

        /// <summary>
        /// Discovers all subscriptions in the tenant.
        /// </summary>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>List of subscription information.</returns>
        /// <exception cref="AzureDiscoveryException">Thrown when subscription discovery fails.</exception>
        public virtual async Task<List<SubscriptionInfo>> DiscoverSubscriptionsAsync(CancellationToken cancellationToken = default)
        {
            _logger.LogInformation("🔍 Discovering subscriptions in tenant {TenantId}", _options.TenantId ?? "default");

            var subscriptions = await ExecuteWithRetryAsync(async () =>
            {
                var subscriptionInfos = new List<SubscriptionInfo>();

                await foreach (var subscription in _armClient.GetSubscriptions().GetAllAsync(cancellationToken: cancellationToken))
                {
                    var subscriptionData = subscription.Data;
                    var subscriptionInfo = new Core.SubscriptionInfo
                    {
                        SubscriptionId = subscriptionData.SubscriptionId ?? string.Empty,
                        DisplayName = subscriptionData.DisplayName ?? string.Empty
                    };

                    subscriptionInfos.Add(subscriptionInfo);
                    _logger.LogInformation($"📋 Found subscription: {subscriptionInfo.DisplayName} ({subscriptionInfo.SubscriptionId})");
                }

                return subscriptionInfos;
            }, "subscription discovery", cancellationToken);

            _cachedSubscriptions.Clear();
            _cachedSubscriptions.AddRange(subscriptions);

            _logger.LogInformation("✅ Discovered {Count} subscriptions total", subscriptions.Count);
            return subscriptions;
        }

        /// <summary>
        /// Discovers all resources in a specific subscription.
        /// </summary>
        /// <param name="subscriptionId">Azure subscription ID.</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>List of resource information.</returns>
        /// <exception cref="AzureDiscoveryException">Thrown when resource discovery fails.</exception>
        public virtual async Task<List<ResourceInfo>> DiscoverResourcesAsync(string subscriptionId, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(subscriptionId))
                throw new ArgumentException("Subscription ID cannot be null or whitespace.", nameof(subscriptionId));

            _logger.LogInformation("🔍 Discovering resources in subscription {SubscriptionId}", subscriptionId);

            var resources = await ExecuteWithRetryAsync(async () =>
            {
                var subscription = await _armClient.GetDefaultSubscriptionAsync(cancellationToken);
                if (subscription.Data.SubscriptionId != subscriptionId)
                {
                    subscription = _armClient.GetSubscriptionResource(SubscriptionResource.CreateResourceIdentifier(subscriptionId));
                }

                var resourceInfos = new List<ResourceInfo>();

                await foreach (var resource in subscription.GetGenericResourcesAsync(cancellationToken: cancellationToken))
                {
                    var resourceData = resource.Data;
                    var parsedInfo = ParseResourceId(resourceData.Id);

                    var resourceInfo = new Core.ResourceInfo
                    {
                        ResourceId = resourceData.Id?.ToString() ?? string.Empty,
                        ResourceType = resourceData.ResourceType.ToString(),
                        Location = resourceData.Location.ToString(),
                        Tags = resourceData.Tags?.ToDictionary(kvp => kvp.Key, kvp => kvp.Value) ?? new Dictionary<string, string>(),
                        ResourceGroup = parsedInfo.ResourceGroup,
                        KeyVaultSecrets = null // Will be populated later if KeyVault
                    };

                    resourceInfos.Add(resourceInfo);
                }

                // After collecting all resources, enumerate KeyVault secrets (async, rate-limited)
                var keyVaults = resourceInfos
                    .Where(r =>
                        (r.GetType().GetProperty("ResourceType")?.GetValue(r) as string ??
                         r.GetType().GetProperty("Type")?.GetValue(r) as string ??
                         string.Empty
                        ).Equals("Microsoft.KeyVault/vaults", StringComparison.OrdinalIgnoreCase)
                    )
                    .ToList();

                var semaphore = new SemaphoreSlim(5); // Limit concurrency to 5
                var secretTasks = new List<Task>();

                foreach (var kv in keyVaults)
                {
                    secretTasks.Add(Task.Run(async () =>
                    {
                        await semaphore.WaitAsync(cancellationToken);
                        try
                        {
                            var vaultUri = GetVaultUriFromResourceId(kv.ResourceId, kv.ResourceType, kv.ResourceGroup, kv.Location);
                            if (string.IsNullOrEmpty(vaultUri))
                                return;

                            var secretClient = new SecretClient(new Uri(vaultUri), _credential);

                            var secrets = new List<KeyVaultSecretInfo>();
                            await foreach (var secretProperties in secretClient.GetPropertiesOfSecretsAsync(cancellationToken))
                            {
                                secrets.Add(new KeyVaultSecretInfo
                                {
                                    Name = secretProperties.Name,
                                    ContentType = secretProperties.ContentType
                                });
                            }

                            kv.KeyVaultSecrets = secrets;
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning($"Failed to enumerate secrets for KeyVault {kv.ResourceId}: {ex.Message}");
                        }
                        finally
                        {
                            semaphore.Release();
                        }
                    }, cancellationToken));
                }

                await Task.WhenAll(secretTasks);

                return resourceInfos;
            }, $"resource discovery for subscription {subscriptionId}", cancellationToken);

            _logger.LogInformation("✅ Found {Count} resources in subscription {SubscriptionId}",
                resources.Count, subscriptionId);

            if (_logger.IsEnabled(LogLevel.Debug))
            {
                _logger.LogDebug("Resource IDs: {ResourceIds}",
                    string.Join(", ", resources.Select(r => r.ResourceId)));
            }

            return resources;
        }

        // Helper to construct the vault URI from resource info
        private static string? GetVaultUriFromResourceId(string resourceId, string resourceType, string? resourceGroup, string? location)
        {
            // Azure KeyVault resourceId: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vaultName}
            // Vault URI: https://{vaultName}.vault.azure.net/
            try
            {
                var segments = resourceId.Split('/', StringSplitOptions.RemoveEmptyEntries);
                var vaultNameIndex = Array.IndexOf(segments, "vaults") + 1;
                if (vaultNameIndex > 0 && vaultNameIndex < segments.Length)
                {
                    var vaultName = segments[vaultNameIndex];
                    return $"https://{vaultName}.vault.azure.net/";
                }
            }
            catch
            {
                // Ignore errors, return null
            }
            return null;
        }

        /// <summary>
        /// Checks if the service has valid Azure credentials.
        /// </summary>
        /// <returns>True if credentials appear to be valid.</returns>
        public async Task<bool> IsAuthenticatedAsync(CancellationToken cancellationToken = default)
        {
            try
            {
                var context = new TokenRequestContext(new[] { "https://management.azure.com/.default" });
                var token = await _credential.GetTokenAsync(context, cancellationToken);
                return !string.IsNullOrEmpty(token.Token);
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Clears cached subscription data.
        /// </summary>
        public virtual void ClearCache()
        {
            _cachedSubscriptions.Clear();
            _logger.LogDebug("🗑️ Cleared subscription cache");
        }

        private async Task<T> ExecuteWithRetryAsync<T>(
            Func<Task<T>> operation,
            string operationName,
            CancellationToken cancellationToken = default)
        {
            var delay = _options.InitialRetryDelayMs;

            for (int attempt = 1; attempt <= _options.MaxRetries; attempt++)
            {
                try
                {
                    return await operation();
                }
                catch (RequestFailedException ex) when (attempt < _options.MaxRetries)
                {
                    _logger.LogWarning("Attempt {Attempt} failed for {Operation}: {Error}",
                        attempt, operationName, ex.Message);

                    await Task.Delay(delay, cancellationToken);

                    if (_options.UseExponentialBackoff)
                        delay *= 2;
                }
                catch (RequestFailedException ex)
                {
                    _logger.LogError("Max attempts reached for {Operation}, raising AzureDiscoveryException. Exception: {Exception}", operationName, ex);
                    throw new AzureDiscoveryException($"Azure error during {operationName}: {ex.Message}", ex);
                }
                catch (Exception ex)
                {
                    _logger.LogError("Non-Azure error during {Operation}. Exception: {Exception}", operationName, ex);
                    throw new AzureDiscoveryException($"Non-Azure error during {operationName}: {ex.Message}", ex);
                }
            }

            // This should never be reached due to the logic above, but satisfies the compiler
            throw new AzureDiscoveryException($"Unexpected error during {operationName}");
        }

        private static TokenCredential CreateCredentialWithFallback()
        {
            try
            {
                return new DefaultAzureCredential();
            }
            catch
            {
                try
                {
                    return new AzureCliCredential();
                }
                catch
                {
                    throw new AzureDiscoveryException(
                        "Failed to create Azure credentials. Please ensure you are logged in with 'az login' or have proper Azure credentials configured.");
                }
            }
        }

        private static (string? SubscriptionId, string? ResourceGroup) ParseResourceId(ResourceIdentifier? resourceId)
        {
            if (resourceId?.ToString() is not string resourceIdString || string.IsNullOrWhiteSpace(resourceIdString))
                return (null, null);

            try
            {
                // Azure resource IDs follow the pattern:
                // /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/{provider}/{type}/{name}
                var segments = resourceIdString.Trim('/').Split('/');

                string? subscriptionId = null;
                string? resourceGroup = null;

                // Find subscription ID (should be after 'subscriptions')
                var subscriptionIndex = Array.IndexOf(segments, "subscriptions");
                if (subscriptionIndex >= 0 && subscriptionIndex + 1 < segments.Length)
                {
                    subscriptionId = segments[subscriptionIndex + 1];
                }

                // Find resource group (should be after 'resourceGroups')
                var resourceGroupIndex = Array.IndexOf(segments, "resourceGroups");
                if (resourceGroupIndex >= 0 && resourceGroupIndex + 1 < segments.Length)
                {
                    resourceGroup = segments[resourceGroupIndex + 1];
                }

                return (subscriptionId, resourceGroup);
            }
            catch
            {
                // If parsing fails, return nulls
                return (null, null);
            }
        }
    }

    /// <summary>
    /// Exception thrown when Azure discovery operations fail.
    /// </summary>
    public class AzureDiscoveryException : Exception
    {
        public AzureDiscoveryException(string message) : base(message) { }
        public AzureDiscoveryException(string message, Exception innerException) : base(message, innerException) { }
    }
}
