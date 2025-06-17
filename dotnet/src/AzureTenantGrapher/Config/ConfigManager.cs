using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.Extensions.Configuration;

namespace AzureTenantGrapher.Config
{
    public record Neo4jConfig(string Uri, string Username, string Password);
    public record AzureOpenAIConfig(string Endpoint, string ApiKey, string ApiVersion, string ModelChat, string ModelReasoning);
    public record ProcessingConfig(int ResourceLimit, int BatchSize);
    public record LoggingConfig(string LogLevel, string? LogFile);
    public record AzureTenantGrapherConfig(
        string TenantId,
        Neo4jConfig Neo4j,
        AzureOpenAIConfig? OpenAI,
        ProcessingConfig Processing,
        LoggingConfig Logging,
        bool NoContainer,
        bool ContainerOnly,
        bool Visualize,
        bool AutoStopContainer,
        string? VisualizationPath
    );

    public static class ConfigManager
    {
        public static AzureTenantGrapherConfig CreateConfigFromArgs(string[] args)
        {
            var configBuilder = new ConfigurationBuilder()
                .AddEnvironmentVariables()
                .AddCommandLine(args);
            var config = configBuilder.Build();

            string tenantId = config["tenantId"] ?? throw new ArgumentException("tenantId is required");
            var neo4j = new Neo4jConfig(
                config["NEO4J_URI"] ?? "bolt://localhost:7687",
                config["NEO4J_USER"] ?? "neo4j",
                config["NEO4J_PASSWORD"] ?? string.Empty);

            AzureOpenAIConfig? openAI = null;
            var endpoint = config["AZURE_OPENAI_ENDPOINT"];
            var key = config["AZURE_OPENAI_KEY"];
            if (!string.IsNullOrEmpty(endpoint) && !string.IsNullOrEmpty(key))
            {
                openAI = new AzureOpenAIConfig(
                    endpoint,
                    key,
                    config["AZURE_OPENAI_API_VERSION"] ?? string.Empty,
                    config["AZURE_OPENAI_MODEL_CHAT"] ?? string.Empty,
                    config["AZURE_OPENAI_MODEL_REASONING"] ?? string.Empty);
            }

            int resourceLimit = int.TryParse(config["resourceLimit"], out var rl) ? rl : 0;
            int batchSize = int.TryParse(config["batchSize"], out var bs) ? bs : 5;
            var processing = new ProcessingConfig(resourceLimit, batchSize);

            var logging = new LoggingConfig(
                config["logLevel"] ?? "Information",
                config["logFile"] ?? GenerateDefaultLogFile());

            bool noContainer = bool.TryParse(config["noContainer"], out var nc) && nc;
            bool containerOnly = bool.TryParse(config["containerOnly"], out var co) && co;
            bool visualize = bool.TryParse(config["visualize"], out var vz) && vz;
            bool autoStop = true;
            var visPath = config["visualizationPath"];

            return new AzureTenantGrapherConfig(
                tenantId,
                neo4j,
                openAI,
                processing,
                logging,
                noContainer,
                containerOnly,
                visualize,
                autoStop,
                visPath
            );
        }

        private static string GenerateDefaultLogFile()
        {
            var tempDir = Path.GetTempPath();
            var uniqueId = Guid.NewGuid().ToString()[..8]; // Use first 8 chars of GUID
            var logFileName = $"azure-tenant-grapher-{uniqueId}.log";
            return Path.Combine(tempDir, logFileName);
        }
    }
}
