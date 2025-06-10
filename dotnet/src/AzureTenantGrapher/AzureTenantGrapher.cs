using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Azure.Identity;
using Azure.ResourceManager;
using Azure.ResourceManager.Resources;
using Neo4j.Driver;
using AzureTenantGrapher.Config;
using AzureTenantGrapher.Processing;
using AzureTenantGrapher.Llm;

namespace AzureTenantGrapher
{
    public class AzureTenantGrapher
    {
        private readonly AzureTenantGrapherConfig _config;
        private readonly IDriver _neo4jDriver;
        private readonly ArmClient _armClient;

        public AzureTenantGrapher(AzureTenantGrapherConfig config)
        {
            _config = config;
            _armClient = new ArmClient(new DefaultAzureCredential());
            _neo4jDriver = GraphDatabase.Driver(
                _config.Neo4j.Uri,
                AuthTokens.Basic(_config.Neo4j.Username, _config.Neo4j.Password)
            );
        }

        public async Task RunAsync()
        {
            // Discover subscriptions
            await foreach (var subscription in DiscoverSubscriptionsAsync())
            {
                // Process resources in subscription
                var processor = new ResourceProcessor(_neo4jDriver, subscription, _config.OpenAI);
                await processor.ProcessSubscriptionAsync();
            }
        }

        private async IAsyncEnumerable<SubscriptionResource> DiscoverSubscriptionsAsync()
        {
            var subscriptionsClient = _armClient.GetSubscriptions();
            await foreach (var sub in subscriptionsClient.GetAllAsync())
            {
                yield return sub;
            }
        }
    }
}
