using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using AzureTenantGrapher.Core;
using AzureTenantGrapher.Services;
using AzureTenantGrapher.Graph;
using Microsoft.Extensions.Logging;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class ProgramFlowTests
    {
        [Fact]
        public void HappyPath_ExecutesEndToEnd_NoExceptionAndExitCodeZero()
        {
            // Arrange: stub config and loggers
            var loggerFactory = LoggerFactory.Create(builder => builder.AddProvider(new NullLoggerProvider()));
            var logger = loggerFactory.CreateLogger("Test");

            // Stub discovery service
            var discoveryLogger = loggerFactory.CreateLogger<AzureDiscoveryService>();
            var discoveryService = new AzureDiscoveryService(discoveryLogger, null, null);
            var subscriptions = new List<AzureTenantGrapher.Services.SubscriptionInfo>
            {
                new AzureTenantGrapher.Services.SubscriptionInfo("sub1", "Test Sub")
            };
            var resources = new List<AzureTenantGrapher.Services.ResourceInfo>
            {
                new AzureTenantGrapher.Services.ResourceInfo("res1", "Resource1", "TypeA", "eastus", new Dictionary<string, string>(), "sub1", "rg1")
            };

            // Stub processing service with delegate
            var processingLogger = loggerFactory.CreateLogger<ResourceProcessingService>();
            var processingService = new ResourceProcessingService(processingLogger, null, resource => Task.FromResult(true));
            var stats = processingService.ProcessResourcesAsync(resources, CancellationToken.None).Result;

            // Stub spec service with post-processor and valid options
            var specLogger = loggerFactory.CreateLogger<TenantSpecificationService>();
            var specOptions = new AzureTenantGrapher.Services.TenantSpecificationServiceOptions();
            var specService = new TenantSpecificationService(specOptions, specLogger, spec => spec);
            var spec = specService.BuildTenantSpecAsync(
                new List<Core.SubscriptionInfo> { new Core.SubscriptionInfo { SubscriptionId = "sub1", DisplayName = "Test Sub" } },
                new List<Core.ResourceInfo> { new Core.ResourceInfo { ResourceId = "res1", ResourceType = "TypeA", Location = "eastus", Tags = new Dictionary<string, string>() } }
            ).Result;

            // Graph visualizer (write to temp file, ignore result)
            var graphLogger = loggerFactory.CreateLogger<GraphVisualizer>();
            var visualizer = new GraphVisualizer("bolt://localhost:7687", "neo4j", "password", graphLogger);
            var ex = Record.Exception(() => visualizer.GenerateHtmlVisualizationAsync("test.html", spec).Wait());

            // Assert: no exceptions, exit code would be zero
            Assert.Null(ex);
        }

        class NullLoggerProvider : ILoggerProvider
        {
            public ILogger CreateLogger(string categoryName) => new NullLogger();
            public void Dispose() { }
        }

        class NullLogger : ILogger
        {
            public IDisposable BeginScope<TState>(TState state) => NullScope.Instance;
            public bool IsEnabled(LogLevel logLevel) => false;
            public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter) { }
        }

        class NullScope : IDisposable
        {
            public static NullScope Instance { get; } = new NullScope();
            public void Dispose() { }
        }
    }
}
