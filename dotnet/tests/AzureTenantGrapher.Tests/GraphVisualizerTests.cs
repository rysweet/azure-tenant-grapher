using System;
using System.IO;
using System.Threading.Tasks;
using AzureTenantGrapher.Core;
using AzureTenantGrapher.Graph;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class GraphVisualizerTests
    {
        [Fact]
        public async Task GenerateHtmlVisualizationAsync_CreatesFile()
        {
            // Arrange
            var loggerMock = new Mock<ILogger<GraphVisualizer>>();
            var visualizer = new GraphVisualizer(
                "bolt://localhost:7687", "neo4j", "pass", loggerMock.Object);

            var spec = new TenantSpecification
            {
                TenantId = "test-tenant",
                GeneratedOnUtc = DateTime.UtcNow,
                Subscriptions = { new SubscriptionInfo { SubscriptionId = "sub1", DisplayName = "Sub One" } },
                Resources = { new ResourceInfo { ResourceId = "res1", ResourceType = "typeA", Location = "westus" } }
            };

            var tempPath = Path.GetTempFileName() + ".html";
            try
            {
                // Act
                await visualizer.GenerateHtmlVisualizationAsync(tempPath, spec);

                // Assert
                Assert.True(File.Exists(tempPath));
                var content = await File.ReadAllTextAsync(tempPath);
                Assert.Contains("Subscriptions (1)", content);
                Assert.Contains("Sub One", content);
                Assert.Contains("res1", content);
            }
            finally
            {
                if (File.Exists(tempPath))
                    File.Delete(tempPath);
            }
        }
    }
}