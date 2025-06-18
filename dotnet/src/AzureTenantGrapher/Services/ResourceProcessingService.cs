using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using AzureTenantGrapher.Processing;
using Microsoft.Extensions.Logging;

namespace AzureTenantGrapher.Services
{
    /// <summary>
    /// Service for processing and enriching discovered Azure resources.
    /// </summary>
    public class ResourceProcessingService
    {
        private readonly ILogger<ResourceProcessingService> _logger;
        private readonly ResourceProcessingServiceOptions _options;
        private readonly Func<ResourceInfo, Task<bool>> _processor;

        /// <summary>
        /// Constructs a new ResourceProcessingService.
        /// </summary>
        /// <param name="logger">Logger instance.</param>
        /// <param name="options">Processing options.</param>
        /// <param name="processor">
        /// Optional processor delegate for a single resource. 
        /// If not provided, a default placeholder processor is used.
        /// </param>
        public ResourceProcessingService(
            ILogger<ResourceProcessingService> logger,
            ResourceProcessingServiceOptions? options = null,
            Func<ResourceInfo, Task<bool>>? processor = null)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _options = options ?? ResourceProcessingServiceOptions.CreateDefault();
            _processor = processor ?? DefaultProcessorAsync;
        }

        /// <summary>
        /// Processes a collection of resources asynchronously in batches and in parallel.
        /// </summary>
        /// <param name="resources">The resources to process.</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>Aggregate processing statistics.</returns>
        public async Task<ProcessingStats> ProcessResourcesAsync(
            IEnumerable<ResourceInfo> resources,
            CancellationToken cancellationToken = default)
        {
            if (resources == null) throw new ArgumentNullException(nameof(resources));
            var resourceList = resources.ToList();
            var stats = new ProcessingStats
            {
                TotalResources = resourceList.Count
            };

            _logger.LogInformation("🔄 Starting resource processing for {Count} resources (BatchSize={BatchSize}, MaxDegreeOfParallelism={MaxDop})",
                stats.TotalResources, _options.BatchSize, _options.MaxDegreeOfParallelism);

            int processed = 0, successful = 0, failed = 0, llmGenerated = 0;

            var batches = Batch(resourceList, _options.BatchSize);

            foreach (var batch in batches)
            {
                var tasks = batch.Select(resource =>
                    ProcessWithRetryAsync(resource, cancellationToken)
                ).ToList();

                // Limit parallelism
                foreach (var chunk in Batch(tasks, _options.MaxDegreeOfParallelism))
                {
                    var results = await Task.WhenAll(chunk);
                    foreach (var result in results)
                    {
                        processed++;
                        if (result.Success)
                        {
                            successful++;
                            if (result.LlmGenerated)
                                llmGenerated++;
                        }
                        else
                        {
                            failed++;
                        }
                    }
                }
            }

            stats.Processed = processed;
            stats.Successful = successful;
            stats.Failed = failed;
            stats.LlmGenerated = llmGenerated;

            _logger.LogInformation("✅ Resource processing complete: {Processed} processed, {Successful} successful, {Failed} failed, {LlmGenerated} LLM-generated",
                stats.Processed, stats.Successful, stats.Failed, stats.LlmGenerated);

            return stats;
        }

        private async Task<(bool Success, bool LlmGenerated)> ProcessWithRetryAsync(ResourceInfo resource, CancellationToken cancellationToken)
        {
            int attempt = 0;
            int delay = _options.InitialRetryDelayMs;
            Exception? lastException = null;

            while (attempt < _options.MaxRetries)
            {
                attempt++;
                try
                {
                    _logger.LogDebug("Processing resource {Id} (Attempt {Attempt}/{MaxRetries})", resource.Id, attempt, _options.MaxRetries);
                    bool result = await _processor(resource);
                    // Simulate LLM-generated flag for demo: randomly true 1/5 of the time
                    bool llmGenerated = (new Random().Next(5) == 0);
                    _logger.LogDebug("Resource {Id} processed: Success={Success}, LlmGenerated={LlmGenerated}", resource.Id, result, llmGenerated);
                    return (result, llmGenerated);
                }
                catch (Exception ex)
                {
                    lastException = ex;
                    _logger.LogWarning("Processing resource {Id} failed on attempt {Attempt}: {Error}", resource.Id, attempt, ex.Message);
                    if (attempt < _options.MaxRetries)
                    {
                        await Task.Delay(delay, cancellationToken);
                        if (_options.UseExponentialBackoff)
                            delay *= 2;
                    }
                }
            }
            _logger.LogError("Resource {Id} failed after {MaxRetries} attempts. Last error: {Error}", resource.Id, _options.MaxRetries, lastException?.Message);
            return (false, false);
        }

        private static async Task<bool> DefaultProcessorAsync(ResourceInfo resource)
        {
            // Simulate enrichment work (e.g., LLM call, API call, etc.)
            await Task.Delay(50);
            return true;
        }

        private static IEnumerable<List<T>> Batch<T>(IEnumerable<T> source, int batchSize)
        {
            var batch = new List<T>(batchSize);
            foreach (var item in source)
            {
                batch.Add(item);
                if (batch.Count == batchSize)
                {
                    yield return new List<T>(batch);
                    batch.Clear();
                }
            }
            if (batch.Count > 0)
                yield return batch;
        }
    }
}