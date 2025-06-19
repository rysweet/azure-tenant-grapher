using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using AzureTenantGrapher.Config;
using AzureTenantGrapher.Logging;
using AzureTenantGrapher.Services;
using AzureTenantGrapher.Core;
using AzureTenantGrapher.Graph;
using AzureTenantGrapher.Container;
using Microsoft.Extensions.Logging;

namespace AzureTenantGrapher
{
    class Program
    {
        static int Main(string[] args)
        {
            var cts = new CancellationTokenSource();
            Console.CancelKeyPress += (sender, eventArgs) =>
            {
                Console.WriteLine("Cancellation requested. Exiting...");
                cts.Cancel();
                eventArgs.Cancel = true;
            };

            try
            {
                // Parse config from args
                var config = ConfigManager.CreateConfigFromArgs(args);

                // Determine log level
                LogLevel logLevel = LogLevel.Information; // Default, or parse from config if available

                // Build logger factory
                using var loggerFactory = Logging.Logging.CreateLoggerFactory(logLevel);
                var logger = loggerFactory.CreateLogger<Program>();

                logger.LogInformation("AzureTenantGrapher CLI started.");

                // Handle --containerOnly
                if (config.GetType().GetProperty("ContainerOnly")?.GetValue(config) as bool? == true)
                {
                    var containerLogger = loggerFactory.CreateLogger<Neo4jContainerManager>();
                    var containerManager = new Neo4jContainerManager(containerLogger);
                    containerManager.StartContainer();
                    logger.LogInformation("Container-only mode complete.");
                    Environment.ExitCode = 0;
                    return 0;
                }
                if (!string.IsNullOrWhiteSpace(config.GetType().GetProperty("BackupNeo4jPath")?.GetValue(config) as string))
                {
                    // Backup Neo4j database
                    var backupLogger = loggerFactory.CreateLogger<Container.Neo4jContainerManager>();
                    var containerManager = new Container.Neo4jContainerManager(backupLogger);
                    var backupPath = config.GetType().GetProperty("BackupNeo4jPath")?.GetValue(config) as string;
                    containerManager.BackupDatabase(backupPath!);
                    logger.LogInformation("Backup completed at {Path}", backupPath);
                    Environment.ExitCode = 0;
                    return 0;
                }

                // Discovery
                var discoveryLogger = loggerFactory.CreateLogger<AzureDiscoveryService>();
                var discoveryOptions = ConfigManager.CreateAzureDiscoveryOptions(config);
                var discoveryService = new AzureDiscoveryService(discoveryLogger, discoveryOptions);

                var subscriptions = Task.Run(() => discoveryService.DiscoverSubscriptionsAsync(cts.Token)).Result;
                logger.LogInformation("Discovered {Count} subscriptions.", subscriptions.Count);

                var allResources = subscriptions
                    .SelectMany(sub =>
                        Task.Run(() => discoveryService.DiscoverResourcesAsync(sub.Id, cts.Token)).Result
                    ).ToList();
                logger.LogInformation("Discovered {Count} resources.", allResources.Count);

                // Processing
                var processingLogger = loggerFactory.CreateLogger<ResourceProcessingService>();
                var processingOptions = ConfigManager.CreateResourceProcessingOptions(config);
                var processingService = new ResourceProcessingService(processingLogger, processingOptions);

                var processingStats = Task.Run(() => processingService.ProcessResourcesAsync(allResources, cts.Token)).Result;

                // Spec
                var specLogger = loggerFactory.CreateLogger<TenantSpecificationService>();
                var specOptions = ConfigManager.CreateTenantSpecOptions(config);
                var specService = new TenantSpecificationService(specOptions, specLogger);

                var spec = Task.Run(() => specService.BuildTenantSpecAsync(
                    subscriptions.Select(s => new Core.SubscriptionInfo { SubscriptionId = s.Id, DisplayName = s.DisplayName }),
                    allResources.Select(r => new Core.ResourceInfo
                    {
                        ResourceId = r.Id,
                        ResourceType = r.Type,
                        Location = r.Location,
                        Tags = r.Tags != null ? r.Tags.ToDictionary(kvp => kvp.Key, kvp => kvp.Value) : null
                    })
                )).Result;

                spec.Stats = processingStats;
                spec.GeneratedOnUtc = DateTime.UtcNow;

                // Visualization
                var visualizeProp = config.GetType().GetProperty("Visualize")?.GetValue(config) as bool?;
                if (visualizeProp == true)
                {
                    var graphLogger = loggerFactory.CreateLogger<GraphVisualizer>();
                    var graphOptions = ConfigManager.CreateGraphVisualizerOptions(config);
                    var visualizer = new GraphVisualizer(
                        graphOptions.Uri ?? "bolt://localhost:7687",
                        graphOptions.Username ?? "neo4j",
                        graphOptions.Password ?? "password",
                        graphLogger
                    );
                    // Get visualization path from config, fallback to default
                    var visPathProp = config.GetType().GetProperty("VisualizationPath") ?? config.GetType().GetProperty("visualizationPath");
                    var outputPath = visPathProp?.GetValue(config) as string;
                    if (string.IsNullOrWhiteSpace(outputPath))
                        outputPath = Path.Combine(Directory.GetCurrentDirectory(), "visualization.html");
                    Task.Run(() => visualizer.GenerateHtmlVisualizationAsync(outputPath, spec)).Wait();
                    logger.LogInformation("Visualization generated at {Path}", outputPath);
                }

                // Print summary
                PrintSummary(spec);

                logger.LogInformation("Workflow completed successfully.");
                Environment.ExitCode = 0;
                return 0;
            }
            catch (OperationCanceledException)
            {
                Console.WriteLine("Operation cancelled.");
                Environment.ExitCode = 2;
                return 2;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Fatal error: {ex.Message}");
                Environment.ExitCode = 1;
                return 1;
            }
        }

        static LogLevel ParseLogLevel(string? logLevel)
        {
            if (string.IsNullOrWhiteSpace(logLevel))
                return LogLevel.Information;
            return logLevel.ToLower() switch
            {
                "trace" => LogLevel.Trace,
                "debug" => LogLevel.Debug,
                "information" => LogLevel.Information,
                "info" => LogLevel.Information,
                "warning" => LogLevel.Warning,
                "error" => LogLevel.Error,
                "critical" => LogLevel.Critical,
                _ => LogLevel.Information
            };
        }

        static void PrintSummary(TenantSpecification spec)
        {
            Console.WriteLine("==== Azure Tenant Grapher Summary ====");
            Console.WriteLine($"Tenant ID: {spec.TenantId}");
            Console.WriteLine($"Subscriptions: {spec.Subscriptions.Count}");
            Console.WriteLine($"Resources: {spec.Resources.Count}");
            Console.WriteLine($"Processed: {spec.Stats.Processed}");
            Console.WriteLine($"Successful: {spec.Stats.Successful}");
            Console.WriteLine($"Failed: {spec.Stats.Failed}");
            Console.WriteLine($"LLM-Generated: {spec.Stats.LlmGenerated}");
            Console.WriteLine($"Generated On (UTC): {spec.GeneratedOnUtc:u}");
            Console.WriteLine("======================================");
        }
    }
}
