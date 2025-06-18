using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using AzureTenantGrapher.Core;
using AzureTenantGrapher.Processing;
using Microsoft.Extensions.Logging;

namespace AzureTenantGrapher.Services
{
    public class TenantSpecificationService
    {
        private readonly TenantSpecificationServiceOptions _options;
        private readonly ILogger<TenantSpecificationService> _logger;
        private readonly Func<TenantSpecification, TenantSpecification>? _postProcessor;

        public TenantSpecificationService(
            TenantSpecificationServiceOptions options,
            ILogger<TenantSpecificationService> logger,
            Func<TenantSpecification, TenantSpecification>? postProcessor = null)
        {
            _options = options;
            _logger = logger;
            _postProcessor = postProcessor;
        }

        public async Task<TenantSpecification> BuildTenantSpecAsync(
            IEnumerable<AzureTenantGrapher.Core.SubscriptionInfo> subs,
            IEnumerable<AzureTenantGrapher.Core.ResourceInfo> resources)
        {
            if (subs == null) throw new ArgumentNullException(nameof(subs));
            if (resources == null) throw new ArgumentNullException(nameof(resources));

            var subList = subs.ToList();
            var resList = resources.ToList();

            _logger.LogInformation("Starting tenant specification assembly. Subscriptions: {SubCount}, Resources: {ResCount}", subList.Count, resList.Count);

            var spec = new TenantSpecification
            {
                TenantId = subList.FirstOrDefault()?.SubscriptionId ?? string.Empty,
                Subscriptions = subList,
                Resources = resList,
                Stats = new ProcessingStats
                {
                    TotalResources = resList.Count,
                    Processed = resList.Count,
                    Successful = resList.Count,
                    Failed = 0,
                    LlmGenerated = 0
                },
                GeneratedOnUtc = DateTime.UtcNow
            };

            if (!_options.IncludeTags)
            {
                foreach (var r in spec.Resources)
                    r.Tags = null;
            }
            if (!_options.IncludeLocations)
            {
                foreach (var r in spec.Resources)
                    r.Location = null;
            }

            _logger.LogDebug("Spec contains {SubCount} subscriptions and {ResCount} resources.", spec.Subscriptions.Count, spec.Resources.Count);

            if (_postProcessor != null)
            {
                spec = _postProcessor(spec);
                _logger.LogDebug("Post-processor applied to tenant spec.");
            }

            _logger.LogInformation("Tenant specification assembly complete.");
            return await Task.FromResult(spec);
        }
    }
}
