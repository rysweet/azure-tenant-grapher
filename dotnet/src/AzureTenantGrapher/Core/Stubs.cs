using System;
using System.Collections.Generic;
using AzureTenantGrapher.Services;

namespace AzureTenantGrapher.Config
{
    public class AzureTenantGrapherConfig
    {
        public string TenantId { get; set; } = string.Empty;
        public bool NoContainer { get; set; }
        public bool ContainerOnly { get; set; }
        public bool Visualize { get; set; }
        public bool AutoStopContainer { get; set; } = true;
        public ProcessingConfig Processing { get; set; } = new();
        public Neo4jConfig Neo4j { get; set; } = new();
        public LoggingConfig Logging { get; set; } = new();
        public string VisualizationPath { get; set; } = string.Empty;
    }

    public class ProcessingConfig
    {
        public int ResourceLimit { get; set; }
        public int BatchSize { get; set; } = 5;
        public int MaxRetries { get; set; } = 3;
    }

    public class Neo4jConfig
    {
        public string Uri { get; set; } = "bolt://localhost:7687";
        public string Username { get; set; } = "neo4j";
        public string Password { get; set; } = string.Empty;
    }

    public class LoggingConfig
    {
        public string LogLevel { get; set; } = "Information";
    }

    public static class ConfigManager
    {
        public static AzureTenantGrapherConfig CreateConfigFromArgs(string[] args)
        {
            var config = new AzureTenantGrapherConfig();
            var dict = new Dictionary<string, string>();

            for (int i = 0; i < args.Length; i++)
            {
                var key = args[i].TrimStart('-');
                string value = (i + 1) < args.Length && !args[i + 1].StartsWith("--") ? args[i + 1] : "true";
                if (!dict.ContainsKey(key))
                {
                    dict[key] = value;
                }
            }

            if (dict.TryGetValue("tenantId", out var tenantId))
                config.TenantId = tenantId;

            if (dict.TryGetValue("noContainer", out var noContainer))
                config.NoContainer = bool.Parse(noContainer);

            if (dict.TryGetValue("containerOnly", out var containerOnly))
                config.ContainerOnly = bool.Parse(containerOnly);

            if (dict.TryGetValue("visualize", out var visualize))
                config.Visualize = bool.Parse(visualize);

            if (dict.TryGetValue("skipAutoStop", out var skipAutoStop))
                config.AutoStopContainer = !bool.Parse(skipAutoStop);

            if (dict.TryGetValue("resourceLimit", out var resLimit))
                config.Processing.ResourceLimit = int.Parse(resLimit);

            if (dict.TryGetValue("batchSize", out var batchSize))
                config.Processing.BatchSize = int.Parse(batchSize);

            if (dict.TryGetValue("maxRetries", out var maxRetries))
                config.Processing.MaxRetries = int.Parse(maxRetries);

            if (dict.TryGetValue("logLevel", out var logLevel))
                config.Logging.LogLevel = logLevel;

            if (dict.TryGetValue("visualizationPath", out var visPath))
                config.VisualizationPath = visPath;

            if (dict.TryGetValue("NEO4J_URI", out var uri))
                config.Neo4j.Uri = uri;

            if (dict.TryGetValue("NEO4J_USER", out var user))
                config.Neo4j.Username = user;

            if (dict.TryGetValue("NEO4J_PASSWORD", out var pwd))
                config.Neo4j.Password = pwd;

            return config;
        }

        /// <summary>
        /// Creates default Azure Discovery Service options from configuration.
        /// </summary>
        /// <param name="config">The main configuration object.</param>
        /// <returns>AzureDiscoveryServiceOptions with values from config.</returns>
        public static AzureDiscoveryServiceOptions CreateAzureDiscoveryOptions(AzureTenantGrapherConfig config)
        {
            return new AzureDiscoveryServiceOptions
            {
                TenantId = config.TenantId,
                MaxRetries = config.Processing.MaxRetries,
                InitialRetryDelayMs = 1000,
                UseExponentialBackoff = true
            };
        }
        /// <summary>
        /// Creates default Resource Processing Service options from configuration.
        /// </summary>
        /// <param name="config">The main configuration object.</param>
        /// <returns>ResourceProcessingServiceOptions with values from config and environment.</returns>
        public static AzureTenantGrapher.Services.ResourceProcessingServiceOptions CreateResourceProcessingOptions(AzureTenantGrapherConfig config)
        {
            var options = new AzureTenantGrapher.Services.ResourceProcessingServiceOptions
            {
                BatchSize = config.Processing.BatchSize,
                MaxRetries = config.Processing.MaxRetries,
                // Allow override via env var, else default to 4
                MaxDegreeOfParallelism = int.TryParse(Environment.GetEnvironmentVariable("RESOURCE_PROCESSING_MAX_DOP"), out var dop) ? dop : 4,
                InitialRetryDelayMs = 500,
                UseExponentialBackoff = true
            };
            return options;
        }
    /// <summary>
    /// Creates default Tenant Specification Service options from configuration.
    /// </summary>
    /// <param name="config">The main configuration object.</param>
    /// <returns>TenantSpecificationServiceOptions with values from config.</returns>
    public static AzureTenantGrapher.Services.TenantSpecificationServiceOptions CreateTenantSpecOptions(AzureTenantGrapherConfig config)
    {
        // In future, map config fields to options as needed
        return new AzureTenantGrapher.Services.TenantSpecificationServiceOptions
        {
            IncludeTags = true,
            IncludeLocations = true
        };
    }
}
}

namespace AzureTenantGrapher.Container
{
    public class Neo4jContainerManager
    {
        public void SetupNeo4j(int retries)
        {
            throw new InvalidOperationException("Docker not installed.");
        }

        public void StartContainer() { }

        public void StopContainer() { }
    }
}

namespace AzureTenantGrapher.Graph
{
    public class GraphVisualizer
    {
        public GraphVisualizer(string uri, string username, string password)
        {
        }

        public void GenerateHtmlVisualization(string path) { }
    }
}

namespace AzureTenantGrapher.Llm
{
    public record AzureOpenAIConfig(string Endpoint, string ApiKey, string Version, string ChatModel, string ReasonModel);

    public class AzureLLMDescriptionGenerator { }

    public static class LlmFactory
    {
        public static AzureLLMDescriptionGenerator? Create(AzureOpenAIConfig? config) =>
            config is null ? null : new AzureLLMDescriptionGenerator();
    }
}

namespace AzureTenantGrapher.Processing
{
    public class ProcessingStats
    {
        public int TotalResources { get; set; }
        public int Processed { get; set; }
        public int Successful { get; set; }
        public int Failed { get; set; }
        public int LlmGenerated { get; set; }
    }
}