using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Neo4j.Driver;
using Azure.ResourceManager.Resources;
using Azure.ResourceManager.Resources.Models;
using AzureTenantGrapher.Llm;

namespace AzureTenantGrapher.Processing
{
    public class DatabaseOperations
    {
        private readonly IAsyncSession _session;

        public DatabaseOperations(IDriver driver)
        {
            _session = driver.AsyncSession();
        }

        public async Task UpsertResourceAsync(string id, string name, string type)
        {
            var cypher = @"MERGE (r:Resource {id: $id})
                            SET r.name = $name, r.type = $type";
            await _session.RunAsync(cypher, new { id, name, type });
        }
    }

    public class ResourceProcessor
    {
        private readonly DatabaseOperations _dbOps;
        private readonly GenericResourceCollection _resources;
        private readonly AzureLLMDescriptionGenerator? _llm;

        public ResourceProcessor(IDriver driver, SubscriptionResource subscription, AzureTenantGrapher.Config.AzureOpenAIConfig? openAIConfig)
        {
            _dbOps = new DatabaseOperations(driver);
            _resources = subscription.GetGenericResources();
            _llm = openAIConfig != null ? new AzureLLMDescriptionGenerator(openAIConfig) : null;
        }

        public async Task<ProcessingStats> ProcessResourcesBatchAsync(IEnumerable<GenericResource> resources, int batchSize)
        {
            var stats = new ProcessingStats();
            var all = resources.ToList();
            stats.TotalResources = all.Count;

            var batches = all.Chunk(batchSize);
            foreach (var batch in batches)
            {
                var tasks = batch.Select(res => ProcessSingleResourceAsync(res, stats));
                await Task.WhenAll(tasks);
            }
            return stats;
        }

        private async Task ProcessSingleResourceAsync(GenericResource resource, ProcessingStats stats)
        {
            stats.Processed++;
            try
            {
                var id = resource.Id.ToString();
                var name = resource.Data.Name;
                var type = resource.Data.ResourceType.Type;

                await _dbOps.UpsertResourceAsync(id, name, type);
                stats.Successful++;

                if (_llm != null)
                {
                    var desc = await _llm.GenerateResourceDescriptionAsync(resource.Data.ToDictionary());
                    // TODO: update node description in Neo4j
                    stats.LlmGenerated++;
                }
            }
            catch
            {
                stats.Failed++;
            }
        }
    }

    public class ProcessingStats
    {
        public int TotalResources { get; set; }
        public int Processed { get; set; }
        public int Successful { get; set; }
        public int Failed { get; set; }
        public int LlmGenerated { get; set; }
    }

    public static class ResourceProcessorFactory
    {
        public static ResourceProcessor Create(IDriver driver, SubscriptionResource subscription, AzureTenantGrapher.Config.AzureOpenAIConfig? openAIConfig)
        {
            return new ResourceProcessor(driver, subscription, openAIConfig);
        }
    }
}
